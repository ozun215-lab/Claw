# Windows 11 QEMU/KVM VM 구축 요약

## 목표
- QEMU/KVM 기반 Windows 11 VM 구축
- **복구 파티션을 EFI와 C: 사이에 배치**하는 커스텀 파티션 레이아웃 적용
- 자동 설치, virtio 드라이버 설치, 성능 최적화까지 포함

## 핵심 파티션 레이아웃
```text
[EFI 260MB] -> [MSR 16MB] -> [Recovery 1GB] -> [Windows(C:)]
```

### 파티션 포인트
- Recovery 파티션 GUID: `de94bba4-06d1-4d40-a16a-bfd50179d6ac`
- GPT 보호 속성: `0x8000000000000001`
- Windows 설치 대상: 4번 파티션(C:)

## 주요 파일
- `autounattend.xml` : Windows 자동 설치 + 파티션 자동 구성
- `setup.sh` : 최초 설치용 QEMU 실행 스크립트
- `run-vm.sh` : 설치 후 최적화된 VM 실행 스크립트
- `windows11.xml` : libvirt XML 정의
- `install-virtio.ps1` : virtio 드라이버 자동 설치
- `post-install.ps1` : 설치 후 검증
- `post-install.bat` : 수동 드라이버 실행용

## 설치 흐름
1. Windows 11 ISO와 `virtio-win.iso` 준비
2. `setup.sh` 실행
3. 설치 중 자동 파티션/자동 설치 진행
4. 설치 완료 후 `run-vm.sh`로 재실행
5. Windows 내부에서 `post-install.ps1`로 검증

## QEMU 성능 최적화 요약
- CPU: `host` + Hyper-V 플래그 사용
- 디스크: `virtio-scsi` + `cache=none` + `aio=native`
- 메모리: `mem-prealloc` 또는 hugepages 고려
- 그래픽: `virtio-vga-gl`
- TPM 2.0: `swtpm` 사용

## qcow2 권장 설정
### 사무용 VM 기준
- 추천 클러스터 크기: **`256K`** 또는 **`512K`**
- 이유: 작은 파일/랜덤 I/O가 많은 사무용 워크로드에 유리

### 예시
```bash
qemu-img create -f qcow2 \
  -o preallocation=falloc,cluster_size=256K \
  windows11-office.qcow2 64G
```

### falloc 사용 시 실행 옵션
```bash
-drive file=windows11-office.qcow2,if=none,id=disk0,\
  cache=none,aio=native,discard=ignore,detect_zeroes=off
```

## virtio 드라이버 자동 설치 항목
- `viostor` : 스토리지
- `vioscsi` : SCSI passthrough
- `NetKVM` : 네트워크
- `Balloon` : 메모리 벌룬
- `vioserial` : virtio-serial
- `vioinput` : 입력 장치
- `viogpudo` : 디스플레이
- `qxldod` : SPICE/QXL 관련
- `QEMU Guest Agent` : 호스트-게스트 통신

## Notion용 한 줄 결론
- Windows 11 VM은 **autounattend.xml + virtio + TPM + UEFI** 조합으로 자동화하고,
- 사무용 qcow2는 **`cluster_size=256K`**가 가장 무난하며,
- 필요에 따라 **`512K`**로 부팅/앱 로딩 속도를 더 챙길 수 있다.
