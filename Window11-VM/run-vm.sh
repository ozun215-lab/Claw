#!/bin/bash
# =============================================================================
#  run-vm.sh — Windows 11 VM 실행 (설치 완료 후 사용)
#  성능 최적화 옵션 전체 포함
# =============================================================================
set -e

# ── 설정 변수 ─────────────────────────────────────────────────────────────────
VM_NAME="windows11"
DISK="${VM_NAME}.qcow2"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE.fd"
OVMF_VARS="${VM_NAME}_VARS.fd"
TPM_STATE="/tmp/tpm-${VM_NAME}"
TPM_SOCK="/tmp/swtpm-${VM_NAME}.sock"
RAM="8192"
CORES="4"
THREADS="2"
RDP_PORT="3389"
# Fedora/RHEL 사용 시:
# OVMF_CODE="/usr/share/edk2/ovmf/OVMF_CODE.fd"
# ─────────────────────────────────────────────────────────────────────────────

echo "============================================="
echo "  Windows 11 VM 시작"
echo "============================================="

# 디스크 존재 확인
if [ ! -f "$DISK" ]; then
  echo "[오류] 디스크를 찾을 수 없습니다: $DISK"
  echo "       먼저 setup.sh를 실행하세요."
  exit 1
fi

# OVMF VARS 없으면 생성
if [ ! -f "$OVMF_VARS" ]; then
  echo "[경고] OVMF_VARS 없음, 새로 생성..."
  cp /usr/share/OVMF/OVMF_VARS.fd "$OVMF_VARS"
fi

# ── TPM 2.0 시작 ─────────────────────────────────────────────────────────────
echo ""
echo "==> TPM 2.0 시작..."
mkdir -p "$TPM_STATE"
# 기존 프로세스 정리
pkill -f "swtpm.*${VM_NAME}" 2>/dev/null || true
sleep 0.5
swtpm socket \
  --tpmstate dir="$TPM_STATE" \
  --ctrl type=unixio,path="$TPM_SOCK" \
  --tpm2 \
  --daemon
sleep 1

if [ ! -S "$TPM_SOCK" ]; then
  echo "[오류] TPM 소켓 생성 실패: $TPM_SOCK"
  echo "       swtpm 설치 확인: sudo apt install swtpm swtpm-tools"
  exit 1
fi
echo "    TPM 소켓: $TPM_SOCK"

# ── CPU 벤더 감지 ─────────────────────────────────────────────────────────────
CPU_VENDOR=$(grep -m1 vendor_id /proc/cpuinfo | awk '{print $3}')
if [[ "$CPU_VENDOR" == "AuthenticAMD" ]]; then
  HV_VENDOR="hv_vendor_id=AuthenticAMD"
else
  HV_VENDOR="hv_vendor_id=GenuineIntel"
fi
echo "==> CPU 벤더: $CPU_VENDOR"

# ── VM 실행 ───────────────────────────────────────────────────────────────────
echo ""
echo "==> VM 시작 (RAM: ${RAM}MB, CPU: ${CORES}c/${THREADS}t, RDP: ${RDP_PORT})..."
echo "    종료하려면 창을 닫거나 Ctrl+Alt+G 후 창 닫기"
echo ""

qemu-system-x86_64 \
  \
  -enable-kvm \
  -machine q35,accel=kvm \
  -cpu host,hv_relaxed,hv_spinlocks=0x1fff,hv_vapic,hv_time,${HV_VENDOR},hv_synic,hv_stimer,hv_tlbflush,hv_ipi \
  -smp cores=${CORES},threads=${THREADS},sockets=1 \
  \
  -m ${RAM} \
  -mem-prealloc \
  \
  -drive if=pflash,format=raw,readonly=on,file="${OVMF_CODE}" \
  -drive if=pflash,format=raw,file="${OVMF_VARS}" \
  \
  -device virtio-scsi-pci,id=scsi0 \
  -drive file="${DISK}",if=none,id=disk0,cache=none,aio=native,discard=ignore,detect_zeroes=off \
  -device scsi-hd,drive=disk0,bus=scsi0.0 \
  \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp::${RDP_PORT}-:3389 \
  \
  -device virtio-vga-gl \
  -display gtk,gl=on \
  \
  -device qemu-xhci \
  -device usb-tablet \
  -device usb-kbd \
  \
  -audiodev pa,id=snd0 \
  -device ich9-intel-hda \
  -device hda-output,audiodev=snd0 \
  \
  -chardev socket,id=chrtpm,path="${TPM_SOCK}" \
  -tpmdev emulator,id=tpm0,chardev=chrtpm \
  -device tpm-tis,tpmdev=tpm0 \
  \
  -rtc base=localtime,clock=host \
  -name "${VM_NAME}" \
  -boot order=c

# ── 종료 후 TPM 정리 ─────────────────────────────────────────────────────────
echo ""
echo "==> VM 종료됨. TPM 정리..."
pkill -f "swtpm.*${VM_NAME}" 2>/dev/null || true
echo "==> 완료."
