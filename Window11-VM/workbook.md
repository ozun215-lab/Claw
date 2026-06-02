# Windows 11 QEMU/KVM VM 작업 노트

_마지막 수정: 2026-05-15_

---

## 작업 상태

- [x] 파티션 레이아웃 설계 (EFI → Recovery → C:)
- [x] autounattend.xml 작성
- [x] QEMU 실행 스크립트 작성 (setup.sh / run-vm.sh)
- [x] libvirt XML 정의 작성 (windows11.xml)
- [x] 성능 최적화 설정 정리
- [x] virtio 드라이버 자동 설치 스크립트 작성
- [ ] 실제 VM 생성 및 설치 테스트
- [ ] WinRE 활성화 확인
- [ ] 스냅샷 생성 (초기 설치 완료 상태)
- [ ] RDP 접속 테스트

---

## 파일 목록

| 파일 | 용도 | 상태 |
|------|------|------|
| `Windows11-QEMU-Guide.md` | 전체 통합 가이드 | ✅ 완료 |
| `autounattend.xml` | Windows 자동 설치 | ✅ 완료 |
| `setup.sh` | 초기 VM 생성 & 설치 부팅 | ✅ 완료 |
| `run-vm.sh` | 설치 완료 후 실행 | ✅ 완료 |
| `windows11.xml` | libvirt 정의 | ✅ 완료 |
| `install-virtio.ps1` | virtio 드라이버 설치 | ✅ 완료 |
| `post-install.bat` | 수동 드라이버 트리거 | ✅ 완료 |
| `post-install.ps1` | 설치 후 검증 | ✅ 완료 |
| `Win11.iso` | Windows 11 ISO | 다운로드 필요 |
| `virtio-win.iso` | virtio 드라이버 ISO | 다운로드 필요 |

---

## 핵심 메모

### 파티션 레이아웃
```
디스크 0 (GPT):
  [1] EFI       260MB   FAT32
  [2] MSR        16MB   (없음)
  [3] Recovery 1024MB   NTFS   GUID: de94bba4-06d1-4d40-a16a-bfd50179d6ac
  [4] Windows   나머지   NTFS   C:
```
- Recovery GUID: `de94bba4-06d1-4d40-a16a-bfd50179d6ac`
- GPT 보호 속성: `0x8000000000000001`
- autounattend.xml의 `<InstallTo><PartitionID>4</PartitionID>`

### 디스크 생성
```bash
# falloc + qcow2 (권장)
qemu-img create -f qcow2 -o preallocation=falloc,cluster_size=2M windows11.qcow2 64G

# falloc 사용 시 discard/detect_zeroes 설정
# discard=ignore    ← qcow2에서 TRIM 실효 없음
# detect_zeroes=off ← 오버헤드만 추가됨
-drive file=windows11.qcow2,if=none,id=disk0,cache=none,aio=native,discard=ignore,detect_zeroes=off
```

### CPU 벤더별 Hyper-V 설정
```bash
# AMD
-cpu host,hv_relaxed,...,hv_vendor_id=AuthenticAMD

# Intel
-cpu host,hv_relaxed,...,hv_vendor_id=GenuineIntel
```

### TPM 시작 순서
```bash
# VM 실행 전 반드시 먼저 실행
mkdir -p /tmp/tpm-state
swtpm socket --tpmstate dir=/tmp/tpm-state \
  --ctrl type=unixio,path=/tmp/swtpm.sock \
  --tpm2 --daemon
```

### virtio-win ISO 다운로드
```bash
wget https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win.iso
```

### OVMF 경로 (배포판별)
```
Ubuntu/Debian : /usr/share/OVMF/OVMF_CODE.fd
Fedora/RHEL   : /usr/share/edk2/ovmf/OVMF_CODE.fd
Arch          : /usr/share/ovmf/x64/OVMF_CODE.fd
```

---

## 주의사항 / 트러블슈팅

### virtio 디스크 인식 안 될 때
- autounattend.xml의 `<DriverPaths>`에 `viostor` 경로 포함됐는지 확인
- virtio-win.iso가 설치 중 마운트되어 있어야 함 (E: 드라이브)
- `E:\viostor\w11\amd64\viostor.inf` 경로 존재 여부 확인

### Windows 11 TPM 오류
- swtpm 데몬이 QEMU 실행 전에 먼저 떠있어야 함
- 소켓 경로 일치 여부 확인 (`/tmp/swtpm.sock`)
- `swtpm` 패키지 설치 여부: `which swtpm`

### KVM 가속 안 될 때
```bash
# KVM 지원 확인
egrep -c '(vmx|svm)' /proc/cpuinfo   # 0이면 CPU 미지원
ls /dev/kvm                           # 없으면 모듈 로드 필요
sudo modprobe kvm_intel               # Intel
sudo modprobe kvm_amd                 # AMD
```

### libvirt 권한 오류
```bash
sudo usermod -aG libvirt,kvm $USER
newgrp libvirt
```

### QEMU GL 가속 오류 (virtio-vga-gl)
```bash
# 호스트에 OpenGL 지원 필요
sudo apt install libgl1-mesa-dri
# 안 되면 -device virtio-vga (GL 없이) 로 변경
```

---

## 자주 쓰는 명령어

```bash
# VM 상태 확인
virsh list --all

# VM 시작 / 종료
virsh start windows11
virsh shutdown windows11

# 스냅샷
virsh snapshot-create-as windows11 "snap-이름" --description "설명"
virsh snapshot-list windows11
virsh snapshot-revert windows11 "snap-이름"

# ISO 제거 (설치 완료 후)
virsh change-media windows11 sdb --eject --live
virsh change-media windows11 sdc --eject --live
virsh change-media windows11 sdd --eject --live

# RDP 접속
xfreerdp /v:localhost:3389 /u:User /p:YourPassword123!

# 디스크 정보
qemu-img info windows11.qcow2

# 디스크 압축 (사용 후)
qemu-img convert -O qcow2 -c windows11.qcow2 windows11-compact.qcow2
```

---

## 참고 링크

- virtio-win ISO: https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/
- Windows 11 ISO: https://www.microsoft.com/software-download/windows11
- QEMU 문서: https://www.qemu.org/docs/master/
- libvirt 문서: https://libvirt.org/docs.html
- OVMF/EDK2: https://github.com/tianocore/tianocore.github.io/wiki/OVMF

---

## 개인 메모

_작업하면서 추가로 기록할 내용:_

```
날짜:
내용:

날짜:
내용:
```
