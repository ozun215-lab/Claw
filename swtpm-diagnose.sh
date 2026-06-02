#!/bin/bash
###############################################################################
# swtpm-diagnose.sh
# 사후 swtpm 설치 전 상태 자동 진단 + 케이스 식별
#
# 사용법:
#   sudo ./swtpm-diagnose.sh <VM_NAME> [ORIGINAL_SWTPM_PATH]
#
# 예시:
#   sudo ./swtpm-diagnose.sh win11-25h2
#   sudo ./swtpm-diagnose.sh win11-25h2 /tmp/orig-swtpm/
#
# 종료 코드:
#   0 — 정상 / 권장 조치 안내
#   1 — 잘못된 사용
#   2 — VM 미존재
#
# 참조: INFRA-VM-TPM-GUIDE-011
###############################################################################

set -uo pipefail

VM_NAME="${1:-}"
ORIG_SWTPM="${2:-}"

# ── 색상 ────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
    BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m'; NC='\033[0m'
else
    RED=''; GRN=''; YEL=''; BLU=''; CYN=''; BLD=''; NC=''
fi

# ── 인자 확인 ───────────────────────────────────────────────────────────────
if [[ -z "$VM_NAME" ]]; then
    echo "사용법: $0 <VM_NAME> [ORIGINAL_SWTPM_PATH]"
    exit 1
fi

# ── root 확인 ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} root 권한 필요"
    exit 1
fi

# ── VM 존재 확인 ────────────────────────────────────────────────────────────
if ! virsh dominfo "$VM_NAME" &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} VM '$VM_NAME' 없음"
    exit 2
fi

UUID=$(virsh domuuid "$VM_NAME")

# ── 헤더 ────────────────────────────────────────────────────────────────────
echo
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLD}  swtpm Post-Install Diagnosis — $VM_NAME${NC}"
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo

# 카운터
ENV_PASS=0; ENV_FAIL=0
HAS_SWTPM_STATE=0
HAS_ORIG_BACKUP=0
BOOTED_WITHOUT_TPM=0

# ── [환경 검사] ─────────────────────────────────────────────────────────────
echo -e "${BLD}[환경 검사]${NC}"

# swtpm 패키지
if command -v swtpm &>/dev/null; then
    SWTPM_VER=$(swtpm --version 2>/dev/null | head -1)
    echo -e "  swtpm 패키지       : ${GRN}✓ 설치됨${NC} ($SWTPM_VER)"
    ENV_PASS=$((ENV_PASS+1))
else
    echo -e "  swtpm 패키지       : ${RED}✘ 미설치${NC}"
    ENV_FAIL=$((ENV_FAIL+1))
fi

# swtpm_user 설정
if grep -q '^swtpm_user' /etc/libvirt/qemu.conf 2>/dev/null; then
    SWTPM_USER=$(grep '^swtpm_user' /etc/libvirt/qemu.conf | awk -F'"' '{print $2}')
    echo -e "  swtpm_user 설정    : ${GRN}✓ ${SWTPM_USER}${NC}"
    ENV_PASS=$((ENV_PASS+1))
else
    echo -e "  swtpm_user 설정    : ${RED}✘ 미설정${NC}"
    ENV_FAIL=$((ENV_FAIL+1))
fi

# swtpm-localca 권한
if [[ -d /var/lib/swtpm-localca ]]; then
    OWNER=$(stat -c '%U:%G' /var/lib/swtpm-localca)
    if [[ "$OWNER" == "tss:tss" ]]; then
        echo -e "  swtpm-localca 권한 : ${GRN}✓ tss:tss${NC}"
        ENV_PASS=$((ENV_PASS+1))
    else
        echo -e "  swtpm-localca 권한 : ${YEL}⚠ ${OWNER}${NC} (tss:tss 권장)"
        ENV_FAIL=$((ENV_FAIL+1))
    fi
else
    echo -e "  swtpm-localca 권한 : ${RED}✘ 디렉토리 없음${NC}"
    ENV_FAIL=$((ENV_FAIL+1))
fi

# OVMF TCG2 지원
OVMF_PATH=$(virsh dumpxml "$VM_NAME" | grep -oP "(?<=<loader[^>]*>)[^<]+" | head -1)
if [[ -f "$OVMF_PATH" ]]; then
    if command -v virt-fw-dump &>/dev/null; then
        TCG2_COUNT=$(virt-fw-dump --input "$OVMF_PATH" 2>&1 \
                     | grep -cE "name=Tcg2(Pei|Dxe|ConfigPei|ConfigDxe)" 2>/dev/null || echo 0)
        if [[ $TCG2_COUNT -ge 3 ]]; then
            echo -e "  OVMF TCG2 지원     : ${GRN}✓ ${TCG2_COUNT} modules${NC}"
            ENV_PASS=$((ENV_PASS+1))
        else
            echo -e "  OVMF TCG2 지원     : ${RED}✘ ${TCG2_COUNT} modules${NC}"
            ENV_FAIL=$((ENV_FAIL+1))
        fi
    else
        echo -e "  OVMF TCG2 지원     : ${YEL}⚠ virt-fw-dump 미설치${NC}"
    fi
else
    echo -e "  OVMF 경로          : ${RED}✘ 파일 없음 ($OVMF_PATH)${NC}"
    ENV_FAIL=$((ENV_FAIL+1))
fi

echo

# ── [VM 상태] ───────────────────────────────────────────────────────────────
echo -e "${BLD}[VM 상태]${NC}"
echo -e "  VM UUID            : ${CYN}${UUID}${NC}"

# XML TPM 디바이스
TPM_MODEL=$(virsh dumpxml "$VM_NAME" | grep -oP "(?<=<tpm model=')[^']+" | head -1)
TPM_TYPE=$(virsh dumpxml "$VM_NAME" | grep -oP "(?<=<backend type=')[^']+" | head -1)
if [[ -n "$TPM_MODEL" && -n "$TPM_TYPE" ]]; then
    echo -e "  XML tpm 디바이스   : ${GRN}✓ ${TPM_MODEL} / ${TPM_TYPE}${NC}"
    if [[ "$TPM_MODEL" != "tpm-crb" ]]; then
        echo -e "                       ${YEL}⚠ Windows 11은 tpm-crb 권장${NC}"
    fi
else
    echo -e "  XML tpm 디바이스   : ${RED}✘ 없음${NC} (XML 수정 필요)"
fi

# swtpm 상태 파일
SWTPM_STATE_FILE="/var/lib/libvirt/swtpm/${UUID}/tpm2/tpm2-00.permall"
if [[ -f "$SWTPM_STATE_FILE" ]]; then
    STATE_SIZE=$(stat -c%s "$SWTPM_STATE_FILE")
    STATE_HUMAN=$(numfmt --to=iec --suffix=B $STATE_SIZE 2>/dev/null || echo "${STATE_SIZE}B")
    if [[ $STATE_SIZE -ge 4000 ]]; then
        echo -e "  swtpm 상태 파일    : ${GRN}✓ 존재${NC} ($STATE_HUMAN)"
        HAS_SWTPM_STATE=1
    else
        echo -e "  swtpm 상태 파일    : ${YEL}⚠ 빈 상태${NC} ($STATE_HUMAN — EK 없음)"
    fi
else
    echo -e "  swtpm 상태 파일    : ${RED}✘ 없음${NC}"
fi

# 원본 swtpm 백업
if [[ -n "$ORIG_SWTPM" ]]; then
    if [[ -d "$ORIG_SWTPM" ]]; then
        # 백업 디렉토리 내부에 tpm2-00.permall 찾기
        ORIG_PERMALL=$(find "$ORIG_SWTPM" -name "tpm2-00.permall" 2>/dev/null | head -1)
        if [[ -n "$ORIG_PERMALL" ]]; then
            ORIG_SIZE=$(stat -c%s "$ORIG_PERMALL")
            if [[ $ORIG_SIZE -ge 4000 ]]; then
                echo -e "  원본 백업 swtpm    : ${GRN}✓ 유효${NC} ($(basename $(dirname $(dirname $ORIG_PERMALL))) ${ORIG_SIZE}B)"
                HAS_ORIG_BACKUP=1
            else
                echo -e "  원본 백업 swtpm    : ${YEL}⚠ 빈 상태${NC} (${ORIG_SIZE}B)"
            fi
        else
            echo -e "  원본 백업 swtpm    : ${RED}✘ tpm2-00.permall 찾을 수 없음${NC}"
        fi
    else
        echo -e "  원본 백업 swtpm    : ${RED}✘ 경로 없음${NC} ($ORIG_SWTPM)"
    fi
else
    echo -e "  원본 백업 swtpm    : ${YEL}✘ 미지정${NC} (인자로 경로 전달 시 검증)"
fi

# 부팅 이력 추정
DISK=$(virsh domblklist "$VM_NAME" --details \
       | awk '$2=="disk" {print $4}' | head -1)
if [[ -f "$DISK" ]]; then
    LAST_MOD=$(stat -c '%y' "$DISK" | cut -d'.' -f1)
    # 디스크가 마지막 수정된 시각이 swtpm 상태 파일보다 새로우면 우회 부팅 의심
    if [[ -f "$SWTPM_STATE_FILE" ]]; then
        DISK_MOD=$(stat -c%Y "$DISK")
        STATE_MOD=$(stat -c%Y "$SWTPM_STATE_FILE")
        if [[ $DISK_MOD -gt $STATE_MOD ]]; then
            echo -e "  부팅 이력 추정     : ${YEL}⚠ 우회 부팅 의심됨${NC}"
            echo -e "                       (디스크 수정: $LAST_MOD)"
            BOOTED_WITHOUT_TPM=1
        else
            echo -e "  부팅 이력 추정     : ${GRN}✓ 미부팅 또는 vTPM과 함께 부팅${NC}"
        fi
    else
        # swtpm 상태 없이 디스크가 수정된 시각이 최근이면 우회 부팅
        DISK_MOD=$(stat -c%Y "$DISK")
        NOW=$(date +%s)
        DAY=$((24*60*60))
        if [[ $((NOW - DISK_MOD)) -lt $((7 * DAY)) ]]; then
            echo -e "  부팅 이력 추정     : ${YEL}⚠ 최근 부팅 흔적${NC} (디스크: $LAST_MOD)"
            BOOTED_WITHOUT_TPM=1
        else
            echo -e "  부팅 이력 추정     : ${GRN}✓ 최근 부팅 없음${NC}"
        fi
    fi
fi

echo

# ── [케이스 판정] ───────────────────────────────────────────────────────────
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLD}[케이스 판정]${NC}"

if [[ $HAS_ORIG_BACKUP -eq 1 ]] || [[ $HAS_SWTPM_STATE -eq 1 ]]; then
    if [[ $BOOTED_WITHOUT_TPM -eq 0 ]]; then
        echo -e "  → ${GRN}${BLD}케이스 ① (BEST)${NC}"
        echo -e "    swtpm 상태 보유 + 우회 부팅 없음"
        echo -e "    단순 복구로 BitLocker/Hello 유지"
        CASE=1
    else
        echo -e "  → ${YEL}${BLD}케이스 ② (GOOD)${NC}"
        echo -e "    swtpm 상태 보유 + 우회 부팅 의심"
        echo -e "    복구 후 Windows TPM 드라이버 재로드 필요"
        CASE=2
    fi
else
    if [[ $BOOTED_WITHOUT_TPM -eq 0 ]]; then
        echo -e "  → ${BLU}${BLD}케이스 ③ (FAIR)${NC}"
        echo -e "    swtpm 상태 없음 + 우회 부팅 미경험"
        echo -e "    새 EK 생성. BitLocker 활성 시 복구 키 필요"
        CASE=3
    else
        echo -e "  → ${RED}${BLD}케이스 ④ (WORST)${NC}"
        echo -e "    swtpm 상태 없음 + 우회 부팅 + BL 활성 가능"
        echo -e "    ${RED}BitLocker 복구 키 확보가 필수${NC}"
        CASE=4
    fi
fi

echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo

# ── [권장 조치] ─────────────────────────────────────────────────────────────
echo -e "${BLD}[권장 조치]${NC}"

case $CASE in
    1)
        echo -e "  ${GRN}1.${NC} swtpm-post-install.sh 실행"
        echo -e "     ${CYN}sudo ./swtpm-post-install.sh $VM_NAME $ORIG_SWTPM${NC}"
        echo -e "  ${GRN}2.${NC} VM 기동 후 Get-Tpm으로 검증"
        ;;
    2)
        echo -e "  ${YEL}1.${NC} swtpm-post-install.sh 실행"
        echo -e "     ${CYN}sudo ./swtpm-post-install.sh $VM_NAME $ORIG_SWTPM${NC}"
        echo -e "  ${YEL}2.${NC} 게스트에서 TPM 드라이버 재로드:"
        echo -e "     ${CYN}pnputil /restart-device 'ACPI\\MSFT0101\\*'${NC}"
        echo -e "  ${YEL}3.${NC} 재부팅 후 Get-Tpm 검증"
        ;;
    3)
        echo -e "  ${BLU}1.${NC} (게스트) BitLocker 상태 확인:"
        echo -e "     ${CYN}manage-bde -status C:${NC}"
        echo -e "  ${BLU}2.${NC} 활성 상태면 복구 키 준비 후 진행"
        echo -e "  ${BLU}3.${NC} swtpm-post-install.sh 실행 (백업 경로 없이):"
        echo -e "     ${CYN}sudo ./swtpm-post-install.sh $VM_NAME${NC}"
        ;;
    4)
        echo -e "  ${RED}1.${NC} ${BLD}BitLocker 복구 키 확보 (필수)${NC}"
        echo -e "     - Microsoft 계정: https://account.microsoft.com/devices/recoverykey"
        echo -e "     - Azure AD / Intune"
        echo -e "     - 사용자가 직접 저장한 키"
        echo -e "  ${RED}2.${NC} 복구 키 확보 후 swtpm-post-install.sh 실행"
        echo -e "  ${RED}3.${NC} 첫 부팅 시 복구 키 입력 → 즉시 manage-bde -off"
        echo -e "  ${RED}4.${NC} 키 미확보 시 — 데이터 복구 불가. 재설치 검토."
        ;;
esac

echo
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo

exit 0
