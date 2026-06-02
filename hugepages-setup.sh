#!/bin/bash
# =============================================================================
# hugepages-setup.sh
# 부팅 시 KVM/libvirt 용 HugePage 런타임 할당 스크립트
# - 커널 파라미터(GRUB) 수정 없이 sysfs/proc 를 통해 할당
# - /etc/hugepages.conf 에서 설정값 읽음
# =============================================================================

set -euo pipefail

CONFIG_FILE="/etc/hugepages.conf"
LOG_TAG="hugepages-setup"

log()  { logger -t "$LOG_TAG" "$*"; echo "[$(date '+%F %T')] $*"; }
err()  { logger -t "$LOG_TAG" -p user.err "ERROR: $*"; echo "[$(date '+%F %T')] ERROR: $*" >&2; }
die()  { err "$*"; exit 1; }

# ── 기본값 ────────────────────────────────────────────────────────────────────
HP_SIZE_KB=2048        # 2 MiB (표준 huge page)
HP_COUNT=0             # 0 = 자동 계산 (여유 메모리의 AUTO_RATIO %)
AUTO_RATIO=40          # 여유 메모리의 몇 % 를 hugepage 로 잡을지 (0~100)
NUMA_NODE=""           # "" = 모든 노드, "0" / "0,1" = 특정 노드만
MOUNT_POINT="/dev/hugepages"
HUGETLBFS_MODE=1770    # libvirt 가 접근할 수 있도록
LIBVIRT_GROUP="libvirt-qemu"   # 배포판에 따라 kvm / libvirt-qemu
RETRY_COUNT=3          # 할당 재시도 횟수
RETRY_DELAY=2          # 재시도 간격 (초)

# ── 설정 파일 읽기 ─────────────────────────────────────────────────────────────
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
    log "Config loaded from $CONFIG_FILE"
fi

# ── hugepage 크기별 sysfs 경로 반환 ───────────────────────────────────────────
hugepage_sys_path() {
    local size_kb="$1"
    echo "/sys/kernel/mm/hugepages/hugepages-${size_kb}kB"
}

# ── 사용 가능한 hugepage 크기 목록 ────────────────────────────────────────────
list_supported_sizes() {
    ls /sys/kernel/mm/hugepages/ 2>/dev/null | sed 's/hugepages-//' | sed 's/kB//'
}

# ── 현재 할당된 hugepage 수 ───────────────────────────────────────────────────
current_hugepages() {
    local path
    path="$(hugepage_sys_path "$HP_SIZE_KB")/nr_hugepages"
    [[ -f "$path" ]] && cat "$path" || echo 0
}

# ── 자동 계산: 여유 메모리 기반 ──────────────────────────────────────────────
auto_calculate_count() {
    local free_kb ratio page_size_kb count
    free_kb=$(awk '/^MemFree:/{print $2}' /proc/meminfo)
    ratio="$AUTO_RATIO"
    page_size_kb="$HP_SIZE_KB"
    count=$(( free_kb * ratio / 100 / page_size_kb ))
    echo "$count"
}

# ── hugepage 실제 할당 (NUMA 지원) ────────────────────────────────────────────
allocate_hugepages() {
    local count="$1"
    local sys_path
    sys_path="$(hugepage_sys_path "$HP_SIZE_KB")"

    [[ -d "$sys_path" ]] || die "HugePage size ${HP_SIZE_KB}kB not supported by this kernel. Supported: $(list_supported_sizes)"

    if [[ -z "$NUMA_NODE" ]]; then
        # 전체 시스템 할당
        local target_path="$sys_path/nr_hugepages"
        log "Allocating $count hugepages (${HP_SIZE_KB}kB) system-wide"
        echo "$count" > "$target_path"
    else
        # 특정 NUMA 노드에 할당
        IFS=',' read -ra nodes <<< "$NUMA_NODE"
        local per_node=$(( count / ${#nodes[@]} ))
        local remainder=$(( count % ${#nodes[@]} ))
        for i in "${!nodes[@]}"; do
            local node="${nodes[$i]}"
            local node_path="/sys/devices/system/node/node${node}/hugepages/hugepages-${HP_SIZE_KB}kB/nr_hugepages"
            [[ -f "$node_path" ]] || { err "NUMA node $node not found: $node_path"; continue; }
            local node_count=$(( per_node + (i == 0 ? remainder : 0) ))
            log "Allocating $node_count hugepages on NUMA node $node"
            echo "$node_count" > "$node_path"
        done
    fi
}

# ── 할당 검증 ──────────────────────────────────────────────────────────────────
verify_allocation() {
    local requested="$1"
    local actual
    actual="$(current_hugepages)"
    if [[ "$actual" -ge "$requested" ]]; then
        log "OK: allocated=$actual / requested=$requested (${HP_SIZE_KB}kB each)"
        return 0
    else
        err "Partial allocation: allocated=$actual / requested=$requested"
        return 1
    fi
}

# ── hugetlbfs 마운트 ───────────────────────────────────────────────────────────
mount_hugetlbfs() {
    # 이미 마운트되어 있으면 스킵
    if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
        log "hugetlbfs already mounted at $MOUNT_POINT"
        return 0
    fi

    mkdir -p "$MOUNT_POINT"

    # libvirt-qemu 그룹 존재 여부 확인
    local gid
    if getent group "$LIBVIRT_GROUP" &>/dev/null; then
        gid=$(getent group "$LIBVIRT_GROUP" | cut -d: -f3)
        mount -t hugetlbfs -o "pagesize=${HP_SIZE_KB}k,mode=${HUGETLBFS_MODE},gid=${gid}" \
            hugetlbfs "$MOUNT_POINT"
        log "hugetlbfs mounted at $MOUNT_POINT (gid=$gid, mode=$HUGETLBFS_MODE)"
    else
        # 그룹 없으면 기본 마운트
        mount -t hugetlbfs -o "pagesize=${HP_SIZE_KB}k" hugetlbfs "$MOUNT_POINT"
        log "hugetlbfs mounted at $MOUNT_POINT (no group)"
    fi
}

# ── /etc/fstab 항목 자동 추가 (재부팅 후에도 유지) ────────────────────────────
ensure_fstab() {
    local fstab_entry="hugetlbfs  ${MOUNT_POINT}  hugetlbfs  pagesize=${HP_SIZE_KB}k  0  0"
    if ! grep -qs "hugetlbfs.*${MOUNT_POINT}" /etc/fstab; then
        echo "$fstab_entry" >> /etc/fstab
        log "Added hugetlbfs entry to /etc/fstab"
    fi
}

# ── 상태 출력 ──────────────────────────────────────────────────────────────────
show_status() {
    local sys_path
    sys_path="$(hugepage_sys_path "$HP_SIZE_KB")"
    log "──────────────────────────────────────"
    log "HugePage size   : ${HP_SIZE_KB} kB"
    log "nr_hugepages    : $(cat "${sys_path}/nr_hugepages" 2>/dev/null || echo N/A)"
    log "nr_free         : $(cat "${sys_path}/nr_free_hugepages" 2>/dev/null || echo N/A)"
    log "nr_overcommit   : $(cat "${sys_path}/nr_overcommit_hugepages" 2>/dev/null || echo N/A)"
    log "Mount point     : $MOUNT_POINT"
    log "──────────────────────────────────────"
}

# ── 메인 ───────────────────────────────────────────────────────────────────────
main() {
    log "=== HugePage setup start ==="

    # 할당 수 결정
    local target_count="$HP_COUNT"
    if [[ "$target_count" -le 0 ]]; then
        target_count="$(auto_calculate_count)"
        log "Auto-calculated hugepage count: $target_count (${AUTO_RATIO}% of free memory)"
    fi

    [[ "$target_count" -gt 0 ]] || die "Calculated 0 hugepages. Check HP_COUNT or AUTO_RATIO in $CONFIG_FILE"

    # 재시도 루프
    local success=0
    for attempt in $(seq 1 "$RETRY_COUNT"); do
        log "Attempt $attempt/$RETRY_COUNT: requesting $target_count hugepages"

        # 메모리 컴팩션으로 연속 물리 메모리 확보
        if [[ -f /proc/sys/vm/compact_memory ]]; then
            echo 1 > /proc/sys/vm/compact_memory
            log "Memory compaction triggered"
            sleep 1
        fi

        allocate_hugepages "$target_count"

        if verify_allocation "$target_count"; then
            success=1
            break
        fi

        [[ "$attempt" -lt "$RETRY_COUNT" ]] && sleep "$RETRY_DELAY"
    done

    if [[ "$success" -eq 0 ]]; then
        err "Could not allocate requested hugepages after $RETRY_COUNT attempts"
        # 실패해도 실제 할당된 만큼으로 계속 진행 (부분 할당 허용)
    fi

    # hugetlbfs 마운트 및 fstab 등록
    mount_hugetlbfs
    ensure_fstab

    show_status
    log "=== HugePage setup done ==="
}

main "$@"
