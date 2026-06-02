#!/bin/bash
###############################################################################
# deploy-instance.sh
# 시나리오 B — Sysprep 골든이미지 기반 Windows 11 vTPM 인스턴스 자동 배포
#
# 사용법:
#   sudo ./deploy-instance.sh <VM_NAME> [MEMORY_GB] [VCPU]
#
# 예시:
#   sudo ./deploy-instance.sh win11-vdi-01
#   sudo ./deploy-instance.sh win11-dev-01 16 8
#
# 사전 요구사항:
#   1. 골든 디스크 준비됨
#      /var/lib/libvirt/images/golden-win11-25h2.qcow2 (chmod 444)
#   2. XML 템플릿 준비됨
#      /etc/libvirt/templates/win11-tpm.xml.tpl
#   3. qemu.conf swtpm_user = "tss" 설정됨
#   4. OVMF 일반 Tcg2 모듈 포함 (verify-ovmf-tcg2.sh 통과)
#
# 참조: INFRA-VM-DEPLOY-007 (Scenario B)
###############################################################################

set -euo pipefail

# ── 인자 ─────────────────────────────────────────────────────────────────────
VM_NAME="${1:?Usage: $0 <VM_NAME> [MEMORY_GB] [VCPU]}"
MEMORY_GB="${2:-8}"
VCPU="${3:-4}"

# ── 경로 설정 (필요 시 수정) ─────────────────────────────────────────────────
GOLDEN_DISK="/var/lib/libvirt/images/golden-win11-25h2.qcow2"
TEMPLATE="/etc/libvirt/templates/win11-tpm.xml.tpl"
NVRAM_TEMPLATE="/usr/share/OVMF/OVMF_VARS_4M.ms.fd"
INVENTORY_LOG="/var/log/vm-deploy-inventory.log"

IMG_DIR="/var/lib/libvirt/images"
NVRAM_DIR="/var/lib/libvirt/qemu/nvram"
SWTPM_DIR="/var/lib/libvirt/swtpm"

# ── 색상 ─────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
    BLU='\033[0;34m'; PRP='\033[0;35m'; BLD='\033[1m'; NC='\033[0m'
else
    RED=''; GRN=''; YEL=''; BLU=''; PRP=''; BLD=''; NC=''
fi

# ── root 확인 ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} root 권한 필요"
    exit 1
fi

# ── VM 이름 유효성 ───────────────────────────────────────────────────────────
if ! [[ "$VM_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo -e "${RED}[ERROR]${NC} VM 이름은 영문/숫자/하이픈/언더스코어만 허용"
    exit 2
fi

# ── 사전 검증 ────────────────────────────────────────────────────────────────
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "${BLD}  Deploy Instance${NC} — Scenario B (Sysprep Golden)"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"

# 골든 디스크 존재
if [[ ! -f "$GOLDEN_DISK" ]]; then
    echo -e "${RED}[ERROR]${NC} 골든 디스크 없음: $GOLDEN_DISK"
    exit 3
fi

# XML 템플릿 존재
if [[ ! -f "$TEMPLATE" ]]; then
    echo -e "${RED}[ERROR]${NC} XML 템플릿 없음: $TEMPLATE"
    exit 4
fi

# NVRAM 템플릿 존재
if [[ ! -f "$NVRAM_TEMPLATE" ]]; then
    echo -e "${RED}[ERROR]${NC} NVRAM 템플릿 없음: $NVRAM_TEMPLATE"
    exit 5
fi

# VM 이름 중복 확인
if virsh dominfo "$VM_NAME" &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} VM '$VM_NAME' 이미 존재"
    exit 6
fi

# 디스크 파일 중복 확인
if [[ -f "$IMG_DIR/${VM_NAME}.qcow2" ]]; then
    echo -e "${RED}[ERROR]${NC} 디스크 파일 이미 존재: $IMG_DIR/${VM_NAME}.qcow2"
    exit 7
fi

# qemu.conf swtpm_user 확인
if ! grep -q '^swtpm_user' /etc/libvirt/qemu.conf 2>/dev/null; then
    echo -e "${YEL}[WARN]${NC} /etc/libvirt/qemu.conf에 swtpm_user 미설정"
    echo -e "       TPM 동작 실패 가능. 다음 명령으로 설정 권장:"
    echo -e "       ${BLU}echo 'swtpm_user = \"tss\"' >> /etc/libvirt/qemu.conf${NC}"
    echo -e "       ${BLU}echo 'swtpm_group = \"tss\"' >> /etc/libvirt/qemu.conf${NC}"
    echo -e "       ${BLU}systemctl restart libvirtd${NC}"
fi

# ── 인스턴스 고유 값 생성 ────────────────────────────────────────────────────
NEW_UUID=$(uuidgen)
NEW_MAC=$(printf '52:54:00:%02x:%02x:%02x' \
    $((RANDOM%256)) $((RANDOM%256)) $((RANDOM%256)))
MEMORY_KB=$((MEMORY_GB * 1024 * 1024))

echo -e "  VM Name : ${PRP}${BLD}$VM_NAME${NC}"
echo -e "  UUID    : $NEW_UUID"
echo -e "  MAC     : $NEW_MAC"
echo -e "  Memory  : ${MEMORY_GB} GB"
echo -e "  vCPU    : $VCPU"
echo -e "  Golden  : $(basename $GOLDEN_DISK)"
echo -e "${BLD}────────────────────────────────────────────────────${NC}"

# ── 1) Overlay 디스크 생성 ───────────────────────────────────────────────────
echo -e "${YEL}[1/6]${NC} Overlay 디스크 생성..."
qemu-img create -f qcow2 \
    -b "$GOLDEN_DISK" -F qcow2 \
    "$IMG_DIR/${VM_NAME}.qcow2" >/dev/null
chown libvirt-qemu:libvirt-qemu "$IMG_DIR/${VM_NAME}.qcow2"
chmod 660 "$IMG_DIR/${VM_NAME}.qcow2"
echo -e "       ${GRN}✓${NC} $IMG_DIR/${VM_NAME}.qcow2"

# ── 2) NVRAM 신규 생성 ───────────────────────────────────────────────────────
echo -e "${YEL}[2/6]${NC} NVRAM 신규 생성..."
cp "$NVRAM_TEMPLATE" "$NVRAM_DIR/${VM_NAME}_VARS.fd"
chown libvirt-qemu:libvirt-qemu "$NVRAM_DIR/${VM_NAME}_VARS.fd"
chmod 660 "$NVRAM_DIR/${VM_NAME}_VARS.fd"
echo -e "       ${GRN}✓${NC} $NVRAM_DIR/${VM_NAME}_VARS.fd"

# ── 3) swtpm 상태 디렉토리 생성 ──────────────────────────────────────────────
echo -e "${YEL}[3/6]${NC} swtpm 상태 디렉토리 생성..."
mkdir -p "$SWTPM_DIR/${NEW_UUID}/tpm2"
chown -R tss:tss "$SWTPM_DIR/${NEW_UUID}/"
chmod 700 "$SWTPM_DIR/${NEW_UUID}/tpm2"
echo -e "       ${GRN}✓${NC} $SWTPM_DIR/${NEW_UUID}/tpm2/"

# ── 4) XML 템플릿 치환 ───────────────────────────────────────────────────────
echo -e "${YEL}[4/6]${NC} XML 템플릿 치환..."
XML_FILE="/tmp/${VM_NAME}-$$.xml"
sed -e "s|__VM_NAME__|${VM_NAME}|g" \
    -e "s|__UUID__|${NEW_UUID}|g" \
    -e "s|__MAC__|${NEW_MAC}|g" \
    -e "s|__MEMORY_KB__|${MEMORY_KB}|g" \
    -e "s|__VCPU__|${VCPU}|g" \
    "$TEMPLATE" > "$XML_FILE"

# 치환 검증 (남은 placeholder 확인)
if grep -q "__[A-Z_]*__" "$XML_FILE"; then
    echo -e "${RED}[ERROR]${NC} XML 템플릿 치환 누락:"
    grep "__[A-Z_]*__" "$XML_FILE"
    rm -f "$XML_FILE"
    exit 8
fi
echo -e "       ${GRN}✓${NC} $XML_FILE"

# ── 5) libvirt 도메인 등록 ───────────────────────────────────────────────────
echo -e "${YEL}[5/6]${NC} libvirt 도메인 등록..."
virsh define "$XML_FILE" >/dev/null
echo -e "       ${GRN}✓${NC} 도메인 정의 완료"

# ── 6) VM 기동 ───────────────────────────────────────────────────────────────
echo -e "${YEL}[6/6]${NC} VM 기동..."
virsh start "$VM_NAME" >/dev/null
echo -e "       ${GRN}✓${NC} VM 기동 완료"

# 임시 파일 정리
rm -f "$XML_FILE"

# ── 인벤토리 기록 ────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$INVENTORY_LOG")"
printf "%s\t%s\t%s\t%s\t%dGB\t%dvCPU\t%s\n" \
    "$(date -Iseconds)" \
    "$VM_NAME" \
    "$NEW_UUID" \
    "$NEW_MAC" \
    "$MEMORY_GB" \
    "$VCPU" \
    "$(basename $GOLDEN_DISK)" \
    >> "$INVENTORY_LOG"

# ── TPM 정상 등록 확인 ───────────────────────────────────────────────────────
sleep 3
TPM_STATUS=$(virsh qemu-monitor-command "$VM_NAME" --hmp "info tpm" 2>/dev/null \
             | grep -oP "model=\K\S+" | head -1)

# ── 결과 출력 ────────────────────────────────────────────────────────────────
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}${BLD}✅ 배포 완료${NC}"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  VM      : ${PRP}${BLD}$VM_NAME${NC}"
echo -e "  UUID    : $NEW_UUID"
echo -e "  MAC     : $NEW_MAC"
if [[ -n "$TPM_STATUS" ]]; then
    echo -e "  TPM     : ${GRN}$TPM_STATUS${NC} (QEMU 등록 확인)"
else
    echo -e "  TPM     : ${YEL}확인 불가${NC}"
fi
echo
echo -e "${YEL}다음 단계:${NC}"
echo -e "  ${BLU}# 콘솔 접속${NC}"
echo -e "  virt-viewer $VM_NAME"
echo
echo -e "  ${BLU}# OOBE 자동 진행 중 (약 5분 소요)${NC}"
echo -e "  unattend.xml에 의해 자동 처리"
echo
echo -e "  ${BLU}# 게스트에서 TPM 확인 (PowerShell 관리자)${NC}"
echo -e "  Get-Tpm"
echo
echo -e "  ${BLU}# 인벤토리 확인${NC}"
echo -e "  tail -1 $INVENTORY_LOG"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
