#!/bin/bash
###############################################################################
# swtpm-post-install.sh
# 사후 swtpm 자동 설치 + 복구 (12단계)
#
# 사용법:
#   sudo ./swtpm-post-install.sh <VM_NAME> [ORIGINAL_SWTPM_PATH]
#
# 예시:
#   # 케이스 ①/② (원본 swtpm 상태 보유):
#   sudo ./swtpm-post-install.sh win11-25h2 /tmp/orig-swtpm/
#
#   # 케이스 ③/④ (새 EK 생성):
#   sudo ./swtpm-post-install.sh win11-25h2
#
# 종료 코드:
#   0  — 성공
#   1  — 잘못된 사용
#   2  — VM 미존재
#   3+ — 단계별 실패
#
# 참조: INFRA-VM-TPM-GUIDE-011
###############################################################################

set -euo pipefail

VM_NAME="${1:?Usage: $0 <VM_NAME> [ORIGINAL_SWTPM_PATH]}"
ORIG_SWTPM="${2:-}"

# ── 색상 ────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
    BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m'; NC='\033[0m'
else
    RED=''; GRN=''; YEL=''; BLU=''; CYN=''; BLD=''; NC=''
fi

# ── root 확인 ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[ERROR]${NC} root 권한 필요"
    exit 1
fi

# ── VM 존재 ─────────────────────────────────────────────────────────────────
if ! virsh dominfo "$VM_NAME" &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} VM '$VM_NAME' 없음"
    exit 2
fi

UUID=$(virsh domuuid "$VM_NAME")
STATE=$(virsh domstate "$VM_NAME")

# ── OS 감지 (apt vs dnf) ────────────────────────────────────────────────────
if command -v apt &>/dev/null; then
    PKG_MGR="apt"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
else
    echo -e "${RED}[ERROR]${NC} 지원 패키지 매니저 없음 (apt/dnf)"
    exit 3
fi

# ── 헤더 ────────────────────────────────────────────────────────────────────
echo
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLD}  swtpm Post-Install — $VM_NAME${NC}"
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "  UUID            : ${CYN}$UUID${NC}"
echo -e "  Package Manager : $PKG_MGR"
echo -e "  Original swtpm  : ${ORIG_SWTPM:-${YEL}(없음 — 새 EK 생성)${NC}}"
echo -e "  VM State        : $STATE"
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo

# ── VM 종료 (실행 중이면) ───────────────────────────────────────────────────
if [[ "$STATE" != "shut off" ]]; then
    echo -e "${YEL}[Pre]${NC} VM 종료..."
    virsh shutdown "$VM_NAME" 2>/dev/null || true
    for i in {1..30}; do
        [[ "$(virsh domstate $VM_NAME)" == "shut off" ]] && break
        sleep 2
    done
    if [[ "$(virsh domstate $VM_NAME)" != "shut off" ]]; then
        virsh destroy "$VM_NAME"
    fi
fi

# ── 1) swtpm 패키지 설치 ────────────────────────────────────────────────────
echo -e "${YEL}[1/12]${NC} swtpm 패키지 설치..."
if [[ "$PKG_MGR" == "apt" ]]; then
    apt update -qq
    DEBIAN_FRONTEND=noninteractive apt install -y -qq \
        swtpm swtpm-tools libtpms0 ovmf \
        python3-virt-firmware python3-importlib-resources \
        >/dev/null
else
    dnf install -y -q \
        swtpm swtpm-tools libtpms edk2-ovmf \
        python3-virt-firmware \
        >/dev/null
fi
echo -e "       ${GRN}✓ 설치 완료${NC} ($(swtpm --version 2>&1 | head -1))"

# ── 2) tss 사용자/그룹 ──────────────────────────────────────────────────────
echo -e "${YEL}[2/12]${NC} tss 사용자/그룹 확인..."
if ! id tss &>/dev/null; then
    useradd -r -s /sbin/nologin -d /var/lib/swtpm-localca tss
    echo -e "       ${GRN}✓ tss 사용자 생성${NC}"
else
    echo -e "       ${GRN}✓ 이미 존재${NC}"
fi

# ── 3) qemu.conf swtpm_user 설정 ───────────────────────────────────────────
echo -e "${YEL}[3/12]${NC} qemu.conf swtpm_user 설정..."
if ! grep -q '^swtpm_user' /etc/libvirt/qemu.conf 2>/dev/null; then
    {
        echo ''
        echo '# Added by swtpm-post-install.sh'
        echo 'swtpm_user = "tss"'
        echo 'swtpm_group = "tss"'
    } >> /etc/libvirt/qemu.conf
    echo -e "       ${GRN}✓ swtpm_user/group 추가${NC}"
    RESTART_LIBVIRTD=1
else
    echo -e "       ${GRN}✓ 이미 설정됨${NC}"
    RESTART_LIBVIRTD=0
fi

# ── 4) libvirtd 재시작 ──────────────────────────────────────────────────────
if [[ $RESTART_LIBVIRTD -eq 1 ]]; then
    echo -e "${YEL}[4/12]${NC} libvirtd 재시작..."
    systemctl restart libvirtd
    sleep 2
    echo -e "       ${GRN}✓ 재시작 완료${NC}"
else
    echo -e "${YEL}[4/12]${NC} libvirtd 재시작 생략 (설정 변경 없음)"
fi

# ── 5) swtpm-localca 디렉토리 + 권한 ────────────────────────────────────────
echo -e "${YEL}[5/12]${NC} swtpm-localca 디렉토리 권한..."
mkdir -p /var/lib/swtpm-localca
chown -R tss:tss /var/lib/swtpm-localca/
chmod 750 /var/lib/swtpm-localca
echo -e "       ${GRN}✓ /var/lib/swtpm-localca (tss:tss 750)${NC}"

# ── 6) OVMF TCG2 지원 검증 ──────────────────────────────────────────────────
echo -e "${YEL}[6/12]${NC} OVMF TCG2 지원 검증..."
OVMF_PATH=$(virsh dumpxml "$VM_NAME" | grep -oP "(?<=<loader[^>]*>)[^<]+" | head -1)
if [[ ! -f "$OVMF_PATH" ]]; then
    echo -e "       ${RED}✘ OVMF 경로 없음: $OVMF_PATH${NC}"
    echo -e "       VM XML에서 loader 경로 수정 필요"
    exit 6
fi

if command -v virt-fw-dump &>/dev/null; then
    TCG2_COUNT=$(virt-fw-dump --input "$OVMF_PATH" 2>&1 \
                 | grep -cE "name=Tcg2(Pei|Dxe|ConfigPei|ConfigDxe)" 2>/dev/null || echo 0)
    if [[ $TCG2_COUNT -ge 3 ]]; then
        echo -e "       ${GRN}✓ Tcg2 모듈 $TCG2_COUNT 개 (정상)${NC}"
    else
        echo -e "       ${RED}✘ Tcg2 모듈 $TCG2_COUNT 개 (부족)${NC}"
        echo -e "       OVMF_CODE_4M.ms.fd 또는 secboot.strictnx.fd 사용 권장"
        exit 6
    fi
else
    echo -e "       ${YEL}⚠ virt-fw-dump 미설치 — 검증 생략${NC}"
fi

# ── 7) VM XML tpm 디바이스 확인 ─────────────────────────────────────────────
echo -e "${YEL}[7/12]${NC} VM XML tpm 디바이스 확인..."
TPM_MODEL=$(virsh dumpxml "$VM_NAME" | grep -oP "(?<=<tpm model=')[^']+" | head -1)
if [[ -z "$TPM_MODEL" ]]; then
    echo -e "       ${RED}✘ TPM 디바이스 없음${NC}"
    echo -e "       virsh edit $VM_NAME 으로 다음 추가 필요:"
    echo -e "       ${CYN}<tpm model='tpm-crb'>${NC}"
    echo -e "       ${CYN}  <backend type='emulator' version='2.0'/>${NC}"
    echo -e "       ${CYN}</tpm>${NC}"
    exit 7
elif [[ "$TPM_MODEL" != "tpm-crb" ]]; then
    echo -e "       ${YEL}⚠ TPM 모델: $TPM_MODEL (Win11은 tpm-crb 권장)${NC}"
else
    echo -e "       ${GRN}✓ tpm-crb / emulator${NC}"
fi

# ── 8) swtpm 상태 디렉토리 준비 ─────────────────────────────────────────────
echo -e "${YEL}[8/12]${NC} swtpm 상태 디렉토리 준비..."
SWTPM_DIR="/var/lib/libvirt/swtpm/${UUID}/tpm2"
mkdir -p "$SWTPM_DIR"

# ── 9) 원본 swtpm 상태 배치 또는 새로 초기화 ────────────────────────────────
echo -e "${YEL}[9/12]${NC} swtpm 상태 파일 처리..."
USE_ORIGINAL=0

if [[ -n "$ORIG_SWTPM" && -d "$ORIG_SWTPM" ]]; then
    # 백업 디렉토리에서 tpm2-00.permall 찾기
    ORIG_PERMALL=$(find "$ORIG_SWTPM" -name "tpm2-00.permall" 2>/dev/null | head -1)

    if [[ -n "$ORIG_PERMALL" && -f "$ORIG_PERMALL" ]]; then
        ORIG_SIZE=$(stat -c%s "$ORIG_PERMALL")
        if [[ $ORIG_SIZE -ge 4000 ]]; then
            echo -e "       원본 발견: $ORIG_PERMALL (${ORIG_SIZE}B)"

            # 원본 디렉토리 전체 복사 (tpm2 하위 구조 포함)
            ORIG_TPM2_DIR=$(dirname "$ORIG_PERMALL")
            cp -a "$ORIG_TPM2_DIR"/. "$SWTPM_DIR/"

            # 추가 파일 (.lock 등) 제거
            rm -f "$SWTPM_DIR/.lock"

            USE_ORIGINAL=1
            echo -e "       ${GRN}✓ 원본 swtpm 상태 배치 완료${NC}"
        else
            echo -e "       ${YEL}⚠ 원본 파일 크기 부족 (${ORIG_SIZE}B) — 새로 초기화${NC}"
        fi
    else
        echo -e "       ${YEL}⚠ tpm2-00.permall 못 찾음 — 새로 초기화${NC}"
    fi
fi

if [[ $USE_ORIGINAL -eq 0 ]]; then
    # 디렉토리 비우기 (있다면)
    rm -f "$SWTPM_DIR"/* 2>/dev/null || true
    echo -e "       ${BLU}→ libvirt 첫 기동 시 swtpm_setup 자동 실행 예정${NC}"
fi

# ── 10) 권한 설정 ───────────────────────────────────────────────────────────
echo -e "${YEL}[10/12]${NC} swtpm 디렉토리 권한 설정..."
chown -R tss:tss "/var/lib/libvirt/swtpm/${UUID}/"
find "/var/lib/libvirt/swtpm/${UUID}/" -type d -exec chmod 700 {} \;
find "/var/lib/libvirt/swtpm/${UUID}/" -type f -exec chmod 600 {} \;
echo -e "       ${GRN}✓ tss:tss (700/600)${NC}"

# ── 11) VM 기동 ─────────────────────────────────────────────────────────────
echo -e "${YEL}[11/12]${NC} VM 기동..."
virsh start "$VM_NAME" >/dev/null
sleep 3
echo -e "       ${GRN}✓ VM 기동 완료${NC}"

# ── 12) QEMU TPM 등록 확인 ──────────────────────────────────────────────────
echo -e "${YEL}[12/12]${NC} QEMU TPM 등록 확인..."
TPM_INFO=$(virsh qemu-monitor-command "$VM_NAME" --hmp "info tpm" 2>/dev/null || echo "")
if echo "$TPM_INFO" | grep -q "tpm-crb"; then
    echo -e "       ${GRN}✓ tpm-crb 등록 확인${NC}"
else
    echo -e "       ${YEL}⚠ TPM 등록 확인 실패${NC}"
    echo "$TPM_INFO"
fi

# swtpm 프로세스
SWTPM_PID=$(pgrep -f "${VM_NAME}.*swtpm" 2>/dev/null | head -1)
if [[ -n "$SWTPM_PID" ]]; then
    SWTPM_USER=$(ps -p $SWTPM_PID -o user= 2>/dev/null | tr -d ' ')
    echo -e "       swtpm PID $SWTPM_PID (user=${SWTPM_USER})"
fi

# ── 결과 출력 ───────────────────────────────────────────────────────────────
echo
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}${BLD}✅ swtpm 사후 설치 완료${NC}"
echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"
echo

if [[ $USE_ORIGINAL -eq 1 ]]; then
    echo -e "${GRN}원본 swtpm 상태 복원됨${NC} — BitLocker / Hello / EFS 유지"
else
    echo -e "${BLU}새 EK 생성됨${NC} — BitLocker 봉인 키 해제 불가 (복구 키 필요 가능)"
fi

echo
echo -e "${YEL}다음 단계 (게스트 PowerShell 관리자):${NC}"
echo -e "  ${CYN}Get-Tpm${NC}"
echo -e "  ${CYN}#  → TpmPresent: True / ManufacturerIdTxt: IBM 확인${NC}"
echo
echo -e "  ${CYN}Get-BitLockerVolume${NC}"
echo -e "  ${CYN}#  → ProtectionStatus 확인${NC}"
echo

if [[ $USE_ORIGINAL -eq 0 ]]; then
    echo -e "${YEL}참고:${NC} 우회 부팅 경험이 있고 BitLocker 활성이었다면"
    echo -e "      복구 키 입력 후 즉시 ${CYN}manage-bde -off C:${NC} 실행 권장"
    echo
fi

echo -e "${BLD}═══════════════════════════════════════════════════════${NC}"

exit 0
