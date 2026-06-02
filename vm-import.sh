#!/bin/bash
###############################################################################
# vm-import.sh — Windows 11 vTPM VM 복원 자동화
#
# vm-export.sh로 생성된 패키지를 대상 호스트에 복원합니다.
# 디스크 + NVRAM + swtpm 상태 + libvirt XML을 자동 배치하고 등록합니다.
#
# 사용법:
#   sudo ./vm-import.sh <PACKAGE.tar.gz>
#
# 예시:
#   sudo ./vm-import.sh /mnt/secure/win11-25h2-20260519-172500.tar.gz
#
# 참조: INFRA-VM-DEPLOY-006 v2
###############################################################################

set -euo pipefail

# ── 인자 확인 ────────────────────────────────────────────────────────────────
PKG="${1:?Usage: $0 <PACKAGE.tar.gz>}"

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

# ── 의존성 ───────────────────────────────────────────────────────────────────
for cmd in virsh tar sha256sum; do
    if ! command -v "$cmd" &>/dev/null; then
        echo -e "${RED}[ERROR]${NC} 명령 없음: $cmd"
        exit 2
    fi
done

# ── 패키지 파일 확인 ─────────────────────────────────────────────────────────
if [[ ! -f "$PKG" ]]; then
    echo -e "${RED}[ERROR]${NC} 패키지 파일 없음: $PKG"
    exit 3
fi

PKG=$(realpath "$PKG")
PKG_DIR=$(dirname "$PKG")
PKG_BASE=$(basename "$PKG")

# ── 헤더 ─────────────────────────────────────────────────────────────────────
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "${BLD}  VM Import${NC} — Windows 11 vTPM 복원"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  패키지: ${BLU}$PKG_BASE${NC}"
echo -e "${BLD}────────────────────────────────────────────────────${NC}"

# ── 1) 패키지 체크섬 검증 ────────────────────────────────────────────────────
if [[ -f "${PKG}.sha256" ]]; then
    echo -e "${YEL}[1/9]${NC} 패키지 체크섬 검증..."
    if (cd "$PKG_DIR" && sha256sum -c "${PKG_BASE}.sha256" >/dev/null 2>&1); then
        echo -e "      ${GRN}✓ OK${NC}"
    else
        echo -e "${RED}[ERROR]${NC} 체크섬 불일치 — 패키지 손상 또는 변조"
        exit 4
    fi
else
    echo -e "${YEL}[1/9]${NC} ${YEL}⚠ 체크섬 파일 없음 (검증 생략)${NC}"
fi

# ── 2) GPG 서명 검증 (선택) ──────────────────────────────────────────────────
if [[ -f "${PKG}.asc" ]]; then
    echo -e "${YEL}[2/9]${NC} GPG 서명 검증..."
    if gpg --verify "${PKG}.asc" "$PKG" 2>/dev/null; then
        echo -e "      ${GRN}✓ 서명 유효${NC}"
    else
        echo -e "${YEL}      ⚠ 서명 검증 실패 — 계속 진행할까요? [y/N]${NC}"
        read -r ans
        [[ "$ans" =~ ^[Yy]$ ]] || exit 5
    fi
else
    echo -e "${YEL}[2/9]${NC} GPG 서명 없음 (생략)"
fi

# ── 3) 임시 디렉토리 해제 ────────────────────────────────────────────────────
echo -e "${YEL}[3/9]${NC} 패키지 해제..."
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT
tar xzf "$PKG" -C "$TMP"
EXPORT_DIR=$(find "$TMP" -maxdepth 1 -mindepth 1 -type d | head -1)
if [[ -z "$EXPORT_DIR" ]]; then
    echo -e "${RED}[ERROR]${NC} 패키지 내부 구조 비정상"
    exit 6
fi

# ── 4) 내부 무결성 검증 ──────────────────────────────────────────────────────
echo -e "${YEL}[4/9]${NC} 파일 무결성 검증..."
if (cd "$EXPORT_DIR" && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
    echo -e "      ${GRN}✓ OK${NC}"
else
    echo -e "${RED}[ERROR]${NC} 패키지 내부 체크섬 불일치"
    exit 7
fi

# ── 5) MANIFEST 확인 ─────────────────────────────────────────────────────────
echo -e "${YEL}[5/9]${NC} MANIFEST 확인..."
echo -e "${BLD}─── MANIFEST ───${NC}"
cat "$EXPORT_DIR/MANIFEST.txt"
echo -e "${BLD}────────────────${NC}"

VM_NAME=$(grep "^VM_NAME:" "$EXPORT_DIR/MANIFEST.txt" | awk '{print $2}')
UUID=$(grep "^UUID:" "$EXPORT_DIR/MANIFEST.txt" | awk '{print $2}')
DISK_FILE=$(grep "^DISK_FILE:" "$EXPORT_DIR/MANIFEST.txt" | awk '{print $2}')
NVRAM_FILE=$(grep "^NVRAM_FILE:" "$EXPORT_DIR/MANIFEST.txt" | awk '{print $2}')
OVMF_LOADER=$(grep "^OVMF_LOADER:" "$EXPORT_DIR/MANIFEST.txt" | awk '{print $2}')

# ── 6) 환경 호환성 검증 ──────────────────────────────────────────────────────
echo -e "${YEL}[6/9]${NC} 환경 호환성 검증..."

# OVMF 경로 확인
if [[ -n "$OVMF_LOADER" && ! -f "$OVMF_LOADER" ]]; then
    echo -e "${RED}[ERROR]${NC} OVMF 경로 없음: $OVMF_LOADER"
    echo -e "      verify-ovmf-tcg2.sh 실행으로 사용 가능한 OVMF 확인 후 XML 수정 필요"
    exit 8
fi

# swtpm_user 확인
if ! grep -q '^swtpm_user' /etc/libvirt/qemu.conf 2>/dev/null; then
    echo -e "${YEL}      ⚠ /etc/libvirt/qemu.conf에 swtpm_user 미설정${NC}"
    echo -e "${YEL}        TPM 동작 실패 가능. 다음 명령으로 설정 권장:${NC}"
    echo -e "          echo 'swtpm_user = \"tss\"' >> /etc/libvirt/qemu.conf"
    echo -e "          echo 'swtpm_group = \"tss\"' >> /etc/libvirt/qemu.conf"
    echo -e "          systemctl restart libvirtd"
fi

# 중복 VM 확인
if virsh dominfo "$VM_NAME" &>/dev/null; then
    echo -e "${RED}[ERROR]${NC} 동일 이름 VM이 이미 존재: $VM_NAME"
    echo -e "      조치: virsh undefine $VM_NAME --keep-nvram 후 재실행"
    exit 9
fi

echo -e "      ${GRN}✓ 호환성 OK${NC}"

# ── 7) 파일 배치 ─────────────────────────────────────────────────────────────
echo -e "${YEL}[7/9]${NC} 파일 배치..."

# 디스크
echo "      → 디스크: /var/lib/libvirt/images/$DISK_FILE"
cp "$EXPORT_DIR/$DISK_FILE" /var/lib/libvirt/images/
chown libvirt-qemu:libvirt-qemu /var/lib/libvirt/images/$DISK_FILE
chmod 660 /var/lib/libvirt/images/$DISK_FILE

# NVRAM
echo "      → NVRAM:  /var/lib/libvirt/qemu/nvram/$NVRAM_FILE"
cp "$EXPORT_DIR/$NVRAM_FILE" /var/lib/libvirt/qemu/nvram/
chown libvirt-qemu:libvirt-qemu /var/lib/libvirt/qemu/nvram/$NVRAM_FILE
chmod 660 /var/lib/libvirt/qemu/nvram/$NVRAM_FILE

# swtpm 상태
if [[ -d "$EXPORT_DIR/swtpm-state/${UUID}" ]]; then
    echo "      → swtpm:  /var/lib/libvirt/swtpm/${UUID}/"
    mkdir -p /var/lib/libvirt/swtpm/
    cp -a "$EXPORT_DIR/swtpm-state/${UUID}/" /var/lib/libvirt/swtpm/
    chown -R tss:tss /var/lib/libvirt/swtpm/${UUID}/
    find /var/lib/libvirt/swtpm/${UUID}/ -type d -exec chmod 700 {} \;
    find /var/lib/libvirt/swtpm/${UUID}/ -type f -exec chmod 600 {} \;
    rm -f /var/lib/libvirt/swtpm/${UUID}/tpm2/.lock
fi

# ── 8) libvirt XML 등록 ──────────────────────────────────────────────────────
echo -e "${YEL}[8/9]${NC} libvirt XML 등록..."
virsh define "$EXPORT_DIR/${VM_NAME}.xml" >/dev/null
echo -e "      ${GRN}✓ 도메인 정의 완료${NC}"

# ── 9) 경로 무결성 최종 검증 ─────────────────────────────────────────────────
echo -e "${YEL}[9/9]${NC} 경로 무결성 검증..."
MISSING=0
while IFS= read -r path; do
    if [[ -e "$path" ]]; then
        echo -e "      ${GRN}✓${NC} $path"
    else
        echo -e "      ${RED}✗ MISSING:${NC} $path"
        MISSING=$((MISSING+1))
    fi
done < <(virsh dumpxml $VM_NAME \
    | grep -oE "(/var/lib/libvirt|/usr/share/OVMF)[^'\"<]+" \
    | sort -u)

if [[ $MISSING -gt 0 ]]; then
    echo -e "${RED}[ERROR]${NC} ${MISSING}개 경로 누락. VM 기동 실패 가능."
fi

# ── 결과 출력 ────────────────────────────────────────────────────────────────
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}${BLD}✅ Import 완료${NC}"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
echo -e "  VM Name : ${BLU}$VM_NAME${NC}"
echo -e "  UUID    : $UUID"
echo
echo -e "${YEL}다음 단계:${NC}"
echo -e "  ${BLU}# 1. VM 기동${NC}"
echo -e "  virsh start $VM_NAME"
echo
echo -e "  ${BLU}# 2. QEMU 측 TPM 등록 확인${NC}"
echo -e "  virsh qemu-monitor-command $VM_NAME --hmp 'info tpm'"
echo
echo -e "  ${BLU}# 3. Windows 부팅 후 게스트 확인 (관리자 PowerShell)${NC}"
echo -e "  Get-Tpm"
echo -e "  ${BLU}#    → TpmPresent: True, ManufacturerIdTxt: IBM 이어야 정상${NC}"
echo
echo -e "${YEL}주의사항:${NC}"
echo -e "  • 원본 VM과 동일 UUID/MAC/SID 보유 — 원본 정지 후 기동할 것"
echo -e "  • 동일 네트워크 세그먼트에 동시 실행 시 충돌 발생"
echo -e "${BLD}════════════════════════════════════════════════════${NC}"
