#!/bin/bash
# =============================================================================
# install.sh  —  hugepages-setup 설치 스크립트
# 사용법: sudo bash install.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== HugePage Setup Installer ==="

# root 확인
[[ $EUID -eq 0 ]] || { echo "root 로 실행하세요: sudo bash install.sh"; exit 1; }

# 파일 복사
install -m 755 "$SCRIPT_DIR/hugepages-setup.sh"      /usr/local/sbin/hugepages-setup.sh
install -m 644 "$SCRIPT_DIR/hugepages.conf"           /etc/hugepages.conf
install -m 644 "$SCRIPT_DIR/hugepages-setup.service"  /etc/systemd/system/hugepages-setup.service

echo "✓ 파일 설치 완료"

# libvirt XML 패치 안내
echo ""
echo "── libvirt VM XML 설정 안내 ─────────────────────────────────────────"
echo "  각 VM의 XML 에 아래 항목을 추가해야 hugepage 를 사용합니다:"
echo ""
echo "  1) <memoryBacking> 블록 추가 (virsh edit <vm이름>):"
echo "     <memoryBacking>"
echo "       <hugepages/>"
echo "     </memoryBacking>"
echo ""
echo "  2) NUMA 환경에서 특정 노드 지정 시:"
echo "     <memoryBacking>"
echo "       <hugepages>"
echo "         <page size='2048' unit='KiB' nodeset='0'/>"
echo "       </hugepages>"
echo "     </memoryBacking>"
echo "─────────────────────────────────────────────────────────────────────"
echo ""

# systemd 등록 및 즉시 실행
systemctl daemon-reload
systemctl enable --now hugepages-setup.service

echo ""
echo "✓ 서비스 등록 및 실행 완료"
echo ""

# 현재 상태 출력
echo "=== 현재 HugePage 상태 ==="
echo "[ /proc/meminfo ]"
grep -i huge /proc/meminfo

echo ""
echo "[ sysfs ]"
for dir in /sys/kernel/mm/hugepages/*/; do
    size=$(basename "$dir")
    total=$(cat "$dir/nr_hugepages" 2>/dev/null || echo 0)
    free=$(cat "$dir/nr_free_hugepages" 2>/dev/null || echo 0)
    printf "  %-30s total=%-6s free=%-6s\n" "$size" "$total" "$free"
done

echo ""
echo "=== 설치 완료 ==="
echo "설정 변경: /etc/hugepages.conf"
echo "로그 확인: journalctl -u hugepages-setup.service"
