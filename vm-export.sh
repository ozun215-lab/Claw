#!/bin/bash
###############################################################################
# vm-export.sh — Windows 11 vTPM VM 패키징 자동화
#
# 시나리오 A (완전 복제) 방식으로 VM을 패키징합니다.
# 디스크 + NVRAM + swtpm 상태 + libvirt XML을 하나의 tar.gz로 묶습니다.
#
# 사용법:
#   sudo ./vm-export.sh <VM_NAME> [OUTPUT_DIR]
#
# 예시:
#   sudo ./vm-export.sh win11-25h2
#   sudo ./vm-export.sh win11-25h2 /mnt/backup
#
# 참조: INFRA-VM-DEPLOY-006 v2
###############################################################################

set -euo pipefail

# ── 인자 확인 ────────────────────────────────────────────────────────────────
VM_NAME="${1:?Usage: $0 <VM_NAME> [OUTPUT_DIR]}"
OUT_DIR="${2:-/var/backup/vm-export}"
DATE=$(date +%Y%m%d-%H%M%S)
PKG_DIR="${OUT_DIR}/${VM_NAME}-${DATE}"

# ── 색상 ─────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
    BLU='\033[0;34m'; BLD='\033[1m'; NC='\033[0m'
else
    RED=''; GRN=''; YEL=''; BLU=''; BLD=''; NC=''
fi

# ── root 권한 확인 ───────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} root 권한 필요. sudo로 실행하세요."
    exit 1
fi

# ── 의존성 확인 ──────────────────────────────────────────────────────────────
for cmd in virsh qemu-img tar sha256sum rsync; do
    if ! command -v "$cmd" &>/dev/null; then
        echo -e "${RED}[ERROR]${NC} 명령 없음: $cmd"
        exit 2
    fi
done

# ── VM 존재 확인 ─────────────────────────────────────────────────────────────
if ! virsh dominfo "$VM_NAME" &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} VM '$VM_NAME' 없음"
    exit 3
fi

UUID=$(virsh domuuid "$VM_NAME")
STATE=$(virsh domstate "$VM_NAME")

# ── 헤더 ─────────────────────────────────────────────────────────────────────
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "${BLD}  VM Export${NC} — Windows 11 vTPM 완전 복제 패키징"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  VM Name : ${BLU}$VM_NAME${NC}"
echo -e "  UUID    : $UUID"
echo -e "  State   : $STATE"
echo -e "  Output  : ${BLU}$PKG_DIR${NC}"
echo -e "${BLD}────────────────────────────────────────────────────${NC}"

# ── 1) VM 종료 ───────────────────────────────────────────────────────────────
if [[ "$STATE" != "shut off" ]]; then
    echo -e "${YEL}[1/7]${NC} VM 종료 중..."
    virsh shutdown "$VM_NAME" 2>/dev/null || true

    # 최대 60초 대기
    for i in {1..30}; do
        if [[ "$(virsh domstate $VM_NAME)" == "shut off" ]]; then
            break
        fi
        sleep 2
    done

    # 그래도 안 꺼지면 강제 종료
    if [[ "$(virsh domstate $VM_NAME)" != "shut off" ]]; then
        echo -e "${YEL}  경고: shutdown 시간 초과, destroy 실행${NC}"
        virsh destroy "$VM_NAME"
    fi
else
    echo -e "${GRN}[1/7]${NC} VM 이미 종료 상태"
fi

mkdir -p "$PKG_DIR/swtpm-state"

# ── 2) XML 추출 ──────────────────────────────────────────────────────────────
echo -e "${YEL}[2/7]${NC} libvirt XML 추출..."
virsh dumpxml "$VM_NAME" > "$PKG_DIR/${VM_NAME}.xml"

# ── 3) 디스크 복사 (압축) ────────────────────────────────────────────────────
echo -e "${YEL}[3/7]${NC} 디스크 압축 복사..."
DISK=$(virsh domblklist "$VM_NAME" --details \
       | awk '$2=="disk" {print $4}' | head -1)
if [[ -z "$DISK" || ! -f "$DISK" ]]; then
    echo -e "${RED}[ERROR]${NC} 디스크 경로 확인 실패"
    exit 4
fi
DISK_BASE=$(basename "$DISK")
qemu-img convert -O qcow2 -c -p "$DISK" "$PKG_DIR/$DISK_BASE"

# ── 4) NVRAM 복사 ────────────────────────────────────────────────────────────
echo -e "${YEL}[4/7]${NC} NVRAM 복사..."
NVRAM=$(virsh dumpxml "$VM_NAME" \
        | grep -oP "(?<=<nvram[^>]*>)[^<]+" | head -1)
if [[ -z "$NVRAM" || ! -f "$NVRAM" ]]; then
    echo -e "${RED}[ERROR]${NC} NVRAM 경로 확인 실패"
    exit 5
fi
NVRAM_BASE=$(basename "$NVRAM")
cp "$NVRAM" "$PKG_DIR/$NVRAM_BASE"

# ── 5) swtpm 상태 복사 ───────────────────────────────────────────────────────
echo -e "${YEL}[5/7]${NC} swtpm 상태 복사..."
if [[ -d "/var/lib/libvirt/swtpm/${UUID}/" ]]; then
    rsync -a --exclude=".lock" \
        "/var/lib/libvirt/swtpm/${UUID}/" \
        "$PKG_DIR/swtpm-state/${UUID}/"

    # swtpm 상태 크기 확인 (정상 5KB 이상)
    SWTPM_SIZE=$(stat -c%s "$PKG_DIR/swtpm-state/${UUID}/tpm2/tpm2-00.permall" 2>/dev/null || echo 0)
    if [[ $SWTPM_SIZE -lt 3000 ]]; then
        echo -e "${YEL}  ⚠ 경고: swtpm 상태 파일이 비정상적으로 작음 (${SWTPM_SIZE}B)${NC}"
        echo -e "${YEL}    복원 후 swtpm_setup 재실행이 필요할 수 있습니다.${NC}"
    fi
else
    echo -e "${YEL}  ⚠ 경고: swtpm 상태 디렉토리 없음. TPM 미사용 VM?${NC}"
fi

# ── 6) MANIFEST 작성 ─────────────────────────────────────────────────────────
echo -e "${YEL}[6/7]${NC} MANIFEST 작성..."
cat > "$PKG_DIR/MANIFEST.txt" <<EOF
=== VM EXPORT MANIFEST ===
VM_NAME: $VM_NAME
UUID: $UUID
EXPORT_DATE: $(date -Iseconds)
SOURCE_HOST: $(hostname)
SOURCE_OS: $(. /etc/os-release; echo "$PRETTY_NAME")
QEMU_VERSION: $(qemu-system-x86_64 --version | head -1)
LIBVIRT_VERSION: $(libvirtd --version 2>&1 | head -1)
SWTPM_VERSION: $(swtpm --version 2>&1 | head -1)
OVMF_LOADER: $(grep -oP "(?<=<loader[^>]*>)[^<]+" "$PKG_DIR/${VM_NAME}.xml" | head -1)
MACHINE_TYPE: $(grep -oP "machine='[^']+'" "$PKG_DIR/${VM_NAME}.xml" | head -1)
DISK_FILE: $DISK_BASE
DISK_SIZE: $(qemu-img info "$PKG_DIR/$DISK_BASE" | grep "virtual size:" | head -1)
NVRAM_FILE: $NVRAM_BASE
SWTPM_PERMALL_SIZE: ${SWTPM_SIZE:-N/A} bytes
EXPORTED_BY: $(whoami)@$(hostname)
EOF

# ── 7) SHA256SUMS 생성 ───────────────────────────────────────────────────────
echo -e "${YEL}[7/7]${NC} 무결성 체크섬 생성..."
cd "$PKG_DIR"
find . -type f ! -name "SHA256SUMS" -print0 \
    | xargs -0 sha256sum > SHA256SUMS

# ── tar.gz 압축 ──────────────────────────────────────────────────────────────
echo -e "${BLU}tar.gz 압축 중...${NC}"
cd "$OUT_DIR"
TAR_FILE="${VM_NAME}-${DATE}.tar.gz"
tar czf "$TAR_FILE" "$(basename $PKG_DIR)"
sha256sum "$TAR_FILE" > "${TAR_FILE}.sha256"

# 임시 디렉토리 정리
rm -rf "$PKG_DIR"

# ── 결과 출력 ────────────────────────────────────────────────────────────────
TAR_SIZE=$(du -h "$TAR_FILE" | cut -f1)
TAR_HASH=$(awk '{print $1}' "${TAR_FILE}.sha256")

echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}${BLD}✅ Export 완료${NC}"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  패키지   : ${BLU}$OUT_DIR/$TAR_FILE${NC}"
echo -e "  크기     : $TAR_SIZE"
echo -e "  체크섬   : $OUT_DIR/${TAR_FILE}.sha256"
echo -e "  SHA256   : ${TAR_HASH:0:32}..."
echo
echo -e "${YEL}다음 단계:${NC}"
echo -e "  1. (선택) GPG 서명:"
echo -e "     gpg --armor --detach-sign $OUT_DIR/$TAR_FILE"
echo -e "  2. 보안 매체로 복사 → 매체 검사 → 반입 승인"
echo -e "  3. 대상 호스트에서 vm-import.sh 실행"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
