#!/bin/bash
# =============================================================================
#  setup.sh — Windows 11 VM 초기 생성 & 설치 부팅
#  용도: 처음 한 번만 실행. 설치 완료 후에는 run-vm.sh 사용.
# =============================================================================
set -e

# ── 설정 변수 ─────────────────────────────────────────────────────────────────
VM_NAME="windows11"
DISK_SIZE="64G"
RAM="4096"
CORES="4"
WIN_ISO="./Win11.iso"
VIRTIO_ISO="./virtio-win.iso"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE.fd"
OVMF_VARS_TEMPLATE="/usr/share/OVMF/OVMF_VARS.fd"
# Fedora/RHEL 사용 시 아래 경로로 변경:
# OVMF_CODE="/usr/share/edk2/ovmf/OVMF_CODE.fd"
# OVMF_VARS_TEMPLATE="/usr/share/edk2/ovmf/OVMF_VARS.fd"
# ─────────────────────────────────────────────────────────────────────────────

DISK="${VM_NAME}.qcow2"
OVMF_VARS="${VM_NAME}_VARS.fd"
UNATTEND_ISO="${VM_NAME}_unattend.iso"

echo "============================================="
echo "  Windows 11 VM 설치 시작"
echo "============================================="

# 필수 파일 확인
if [ ! -f "$WIN_ISO" ]; then
  echo "[오류] Windows 11 ISO를 찾을 수 없습니다: $WIN_ISO"
  echo "       https://www.microsoft.com/software-download/windows11"
  exit 1
fi

if [ ! -f "$VIRTIO_ISO" ]; then
  echo "[경고] virtio-win.iso 없음. 드라이버 없이 진행합니다."
  echo "       wget https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win.iso"
  VIRTIO_ISO=""
fi

# [1/4] OVMF VARS 복사
echo ""
echo "==> [1/4] OVMF VARS 복사..."
if [ ! -f "$OVMF_VARS_TEMPLATE" ]; then
  echo "[오류] OVMF 펌웨어를 찾을 수 없습니다: $OVMF_VARS_TEMPLATE"
  echo "       sudo apt install ovmf"
  exit 1
fi
cp "$OVMF_VARS_TEMPLATE" "$OVMF_VARS"
echo "    완료: $OVMF_VARS"

# [2/4] 가상 디스크 생성 (falloc 방식)
echo ""
echo "==> [2/4] 가상 디스크 생성 ($DISK_SIZE)..."
if [ ! -f "$DISK" ]; then
  qemu-img create -f qcow2 \
    -o preallocation=falloc,cluster_size=2M \
    "$DISK" "$DISK_SIZE"
  echo "    생성됨: $DISK"
else
  echo "    이미 존재함, 건너뜀: $DISK"
fi

# [3/4] autounattend.xml → ISO 패키징
echo ""
echo "==> [3/4] autounattend.xml ISO 패키징..."
if [ ! -f "autounattend.xml" ]; then
  echo "[오류] autounattend.xml을 찾을 수 없습니다."
  exit 1
fi
mkdir -p unattend_tmp
cp autounattend.xml unattend_tmp/
# install-virtio.ps1이 있으면 함께 포함
if [ -f "install-virtio.ps1" ]; then
  cp install-virtio.ps1 unattend_tmp/
fi
genisoimage -o "$UNATTEND_ISO" -J -r unattend_tmp/ 2>/dev/null \
  || mkisofs -o "$UNATTEND_ISO" -J -r unattend_tmp/
echo "    생성됨: $UNATTEND_ISO"

# [4/4] QEMU 부팅 (설치 시작)
echo ""
echo "==> [4/4] QEMU 부팅 (Windows 11 설치 시작)..."
echo "    설치 완료 후 종료하면 run-vm.sh로 재시작하세요."
echo ""

VIRTIO_DRIVE=""
if [ -n "$VIRTIO_ISO" ] && [ -f "$VIRTIO_ISO" ]; then
  VIRTIO_DRIVE="-drive file=${VIRTIO_ISO},media=cdrom,index=3"
fi

qemu-system-x86_64 \
  -enable-kvm \
  -machine q35 \
  -cpu host \
  -smp cores="${CORES}",threads=1,sockets=1 \
  -m "${RAM}" \
  \
  -drive if=pflash,format=raw,readonly=on,file="${OVMF_CODE}" \
  -drive if=pflash,format=raw,file="${OVMF_VARS}" \
  \
  -drive file="${DISK}",if=virtio,cache=none,aio=native,discard=ignore,detect_zeroes=off \
  -cdrom "${WIN_ISO}" \
  -drive file="${UNATTEND_ISO}",media=cdrom,index=2 \
  ${VIRTIO_DRIVE} \
  \
  -boot order=d,once=d \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0 \
  -vga virtio \
  -display gtk \
  -usb \
  -device usb-tablet \
  -rtc base=localtime \
  -name "${VM_NAME}"

echo ""
echo "============================================="
echo "  설치 완료. run-vm.sh로 VM을 시작하세요."
echo "============================================="
