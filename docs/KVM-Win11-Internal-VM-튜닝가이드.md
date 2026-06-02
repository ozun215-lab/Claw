# KVM/QEMU Windows 11 VM 튜닝 및 점검 가이드

**대상 VM**: `Internal` (Windows 11, Q35, OVMF, 16GB / 12 vCPU)
**호스트**: 노트북 + 가상머신 2대 운영 환경 (Debian 11/12 기반, QEMU 9.0.2, libvirt 8.0.0)
**작성일**: 2026-05-20
**목적**: 저지연(low-latency) Windows 11 게스트 운영 + 안정성 확보

---

## 1. 현재 환경 요약

| 항목 | 값 | 비고 |
|---|---|---|
| 호스트 OS | Debian 11/12 기반 (NST/Gooroom 계열) | 망 분리 환경 |
| QEMU | 9.0.2 (bpo12 백포트) | QXL device 미포함 빌드 |
| libvirt | 8.0.0 (bpo11) | |
| 가상화 모드 | KVM (full HW acceleration) | |
| 머신 타입 | pc-q35-7.2 | 모던 PCIe 칩셋 |
| 펌웨어 | OVMF (UEFI, Secure Boot 가능) | Win11 요구사항 충족 |
| TPM | swtpm 2.0 (tpm-crb) | Win11 요구사항 충족 |
| 게스트 | Windows 11 25H2 (no-app) | |
| vCPU | 12 (1소켓 × 12코어 × 1스레드) | |
| RAM | 16 GiB | |
| 디스크 | qcow2 + backing chain (nst-win11-base) | virtio-blk, iothread, multi-queue |
| 비디오 | QXL × 3 (멀티 모니터) | **호스트 QEMU에서 미지원** |
| 네트워크 | virtio-net + InternalNet bridge | |
| 운영 방식 | 노트북 + VM 2대 동시 운영 | **CPU 핀닝은 비적용** |

---

## 2. 발견된 주요 이슈

### 2.1 [P0/Blocker] 비디오 모델 QXL이 호스트에서 미지원

**증상**
```
오류: 지원되지 않는 설정: 도메인 구성이 비디오 모델 'qxl'을(를) 지원하지 않습니다
```

**원인**
- 호스트 QEMU `1:9.0.2+ds-1~bpo12+1+dev8~1.gbpf2c620` 빌드에 QXL device가 포함되어 있지 않음.
- `qemu-system-x86_64 -device help | grep -i qxl` → 결과 없음.
- `qemu-system-gui` 패키지(QXL 포함)는 NST 저장소에 7.2 버전만 있어 9.0.2와 의존성 충돌.

**조치 방향**
| 옵션 | 장단점 | 추천 |
|---|---|---|
| A. QEMU를 7.2로 다운그레이드 | QXL 사용 가능하나 보안 패치 후퇴, libvirt 호환 불확실 | ✕ |
| B. QEMU 9.0.2 + QXL 활성 재빌드 | 운영 부담 큼, 업데이트 시 깨짐 | ✕ |
| **C. virtio-gpu로 전환 (권장)** | 모던 표준, QXL 이상 성능, 멀티모니터 지원 | ✅ |

**적용 방법** — XML의 `<video>` 블록을 다음으로 교체:
```xml
<video>
  <model type='virtio' heads='3' primary='yes'>
    <acceleration accel3d='no'/>
  </model>
</video>
```
- Windows 11 게스트에 `virtio-win` 드라이버 ISO 마운트 후 `viogpu` 드라이버 설치 필요.
- SPICE 디스플레이는 그대로 유지.

### 2.2 [P1] 메모리 부족으로 VM 시작 실패 사례

**증상**
```
qemu-system-x86_64: unable to map backing store for guest RAM: Cannot allocate memory
```

**점검 포인트**
1. `free -h` — 호스트 가용 메모리가 16GB 이상 확보돼 있는가?
2. 다른 VM이 메모리를 점유 중인가? (`virsh list --all`)
3. hugepages 설정 여부 (`virsh dumpxml ... | grep -i huge`, `cat /proc/meminfo | grep -i huge`)
4. `<memoryBacking><locked/>` 사용 시 ulimit -l 확인
5. `/proc/sys/vm/overcommit_memory` 값 확인 (2면 엄격, 0 권장)

**권장 메모리 배분 (노트북 + VM 2대)**
- 호스트 16GB: 호스트 6GB / VM1 4GB / VM2 4GB / 여유 2GB
- 호스트 24GB: 호스트 8GB / VM1 6GB / VM2 6GB / 여유 4GB
- 호스트 32GB+: 현재의 VM당 16GB 구성 가능
- **메모리 오버커밋(합 > 실제) 금지** — 스왑 진입 시 응답성 급락

---

## 3. XML 개선 권장사항 (우선순위별)

### 우선순위 1 — 차단 이슈 해소

- **`<video>` 전체를 virtio로 교체** (위 2.1 참조)
  - 현재 QXL × 3 → virtio × 1 (heads=3)

### 우선순위 2 — 저지연 효과 큼, 부작용 없음

**`<features>` 블록**
```xml
<features>
  <acpi/>
  <apic/>
  <ioapic driver='kvm'/>           <!-- 추가: 인터럽트 in-kernel 처리 -->
  <hyperv mode='custom'>
    <relaxed state='on'/>
    <vapic state='on'/>
    <spinlocks state='on' retries='8191'/>
    <vpindex state='on'/>
    <synic state='on'/>
    <stimer state='on'/>
    <tlbflush state='on'/>
    <ipi state='on'/>              <!-- 추가: IPI 가속 -->
    <frequencies state='on'/>      <!-- 추가: TSC/APIC 주파수 -->
    <reset state='on'/>            <!-- 추가: 깔끔한 리셋 -->
  </hyperv>
  <kvm>                            <!-- 블록 추가 -->
    <hidden state='on'/>
    <poll-control state='on'/>
  </kvm>
  <vmport state='off'/>
  <smm state='on'/>
</features>
```

**`<cpu>` 블록**
```xml
<cpu mode='host-passthrough' check='none' migratable='off'>
  <topology sockets='1' dies='1' cores='12' threads='1'/>
  <cache mode='passthrough'/>
  <feature policy='require' name='invtsc'/>   <!-- 추가: 안정 TSC -->
</cpu>
```

**`<clock>` 블록**
```xml
<clock offset='localtime'>
  <timer name='rtc' tickpolicy='catchup'/>
  <timer name='pit' tickpolicy='delay'/>
  <timer name='hpet' present='no'/>
  <timer name='hypervclock' present='yes'/>
  <timer name='tsc' present='yes' mode='native'/>   <!-- 추가 -->
</clock>
```

### 우선순위 3 — 메모리/I-O 안정성

**메모리**
```xml
<memoryBacking>
  <hugepages>
    <page size='2048' unit='KiB'/>   <!-- 2MB hugepage (노트북에 적합) -->
  </hugepages>
  <nosharepages/>                     <!-- KSM 스캔 회피 (jitter ↓) -->
</memoryBacking>
```
> `<locked/>`는 노트북에선 비권장 (스왑 압박 시 호스트 영향).

**메모리 벌룬 비활성** (저지연 우선이면)
```xml
<memballoon model='none'/>
```

**디스크 TRIM 활성**
```xml
<driver name='qemu' type='qcow2' cache='none' io='native'
        discard='unmap'                 <!-- 'ignore' → 'unmap' -->
        iothread='1' detect_zeroes='off' queues='8'/>
```

### 우선순위 4 — 정리 (선택)

- **입력 디바이스 중복 제거**
  - 유지: USB tablet, PS/2 keyboard
  - 제거: PS/2 mouse, virtio mouse, virtio keyboard
- **사용 안 하는 PCI 브리지 4개 제거** (pci.12 ~ pci.16)
- **네트워크 vhost-net 가속** (네트워크 부하 많을 때)
  ```xml
  <interface ...>
    ...
    <driver name='vhost' queues='4'/>
  </interface>
  ```

---

## 4. 호스트 측 점검/설정

### 4.1 이미 확인된 양호 항목
- `Transparent Hugepage = madvise` ✅
  ```
  cat /sys/kernel/mm/transparent_hugepage/enabled
  → always [madvise] never
  ```
  QEMU에 최적. 영구화하려면 GRUB에 `transparent_hugepage=madvise` 추가 권장.

### 4.2 점검 권장 항목
```bash
# THP defrag (madvise 권장)
cat /sys/kernel/mm/transparent_hugepage/defrag
echo madvise > /sys/kernel/mm/transparent_hugepage/defrag

# KSM 비활성 (저지연이면 권장)
systemctl is-active ksm ksmtuned
systemctl disable --now ksm ksmtuned

# CPU governor (전원 연결 시)
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
cpupower frequency-set -g performance

# 호스트 코어 수와 vCPU 분배 검토
nproc
virsh list --all
```

### 4.3 노트북에서 권장하지 않는 설정
- `isolcpus`, `nohz_full`, `idle=poll` — 호스트 일상 작업 영향 큼
- 1:1 CPU 핀닝 (`<cputune><vcpupin/></cputune>`) — 토폴로지 변동/열 throttling 대응 어려움
- 1GB hugepages — 노트북 메모리 단편화 환경에서 할당 실패 위험
- `<memoryBacking><locked/>` — 스왑 시나리오에서 호스트 위협

---

## 5. 게스트(Windows 11) 측 권장

| 항목 | 권장 설정 |
|---|---|
| virtio 드라이버 | virtio-win 최신 ISO에서 일괄 설치 (NetKVM, viostor, vioserial, viogpu, Balloon 등) |
| 전원 옵션 | 고성능 또는 Ultimate Performance |
| USB selective suspend | Off |
| Hardware-accelerated GPU scheduling | Off (passthrough 환경) |
| MSI 인터럽트 | NVMe/GPU에 활성화 (디바이스 매니저 Properties → Resources) |
| Defender 실시간 검사 | 가능 시 제외 디렉터리 설정 / 비활성 |
| Windows Update | 운영 시간에 예약 |
| TSC 사용 시 | `bcdedit /set useplatformtick yes` / `disabledynamictick yes` |

---

## 6. 적용 절차 권장 순서

1. **백업**
   ```bash
   virsh dumpxml Internal > ~/Internal.xml.bak.$(date +%F)
   cp /var/lib/libvirt/images/Internal.qcow2{,.bak}   # 가능하다면
   ```
2. **비디오 모델 변경 (P0)** — VM 시작 가능하게 만들기
   `virsh edit Internal` → `<video>` 블록 virtio로 교체 → `virsh start Internal`
3. **virtio-gpu 드라이버 게스트에 설치** (Windows 부팅 후)
4. **P2 항목 일괄 반영** (features, cpu, clock)
5. **P3 항목 반영** (hugepages, memballoon, discard)
6. **베이스라인 측정**
   - 게스트: LatencyMon (Windows) / 일반 작업 응답성 체감
   - 호스트: `top`, `vmstat 1`, `cat /proc/interrupts`
7. **P4 정리 (선택)** — 중복 디바이스 정리

각 단계마다 VM 시작 가능 여부 확인 후 다음 단계로 진행.

---

## 7. 미해결/추가 검토 필요

- [ ] 호스트 노트북의 정확한 코어 수와 vCPU 12 적정성 (현재 `nproc` 결과 미확보)
- [ ] CPU 토폴로지 `threads='1'` 의도 (HT 비활성 의도 vs 단순 기본값)
- [ ] InternalNet 브리지 구성 (NAT/Routed/Isolated 여부)
- [ ] 두 번째 VM(`Win11-25h2-noapp`)에도 동일 가이드 반영 여부
- [ ] 백업/스냅샷 정책

---

## 8. 참고 명령 모음

```bash
# 도메인 시작/중지
virsh start Internal
virsh shutdown Internal
virsh destroy Internal             # 강제 종료

# XML 편집/조회
virsh edit Internal
virsh dumpxml Internal | less
virsh dominfo Internal

# 메모리/CPU 동적 조정
virsh setmaxmem Internal 16G --config
virsh setmem Internal 16G --config
virsh setvcpus Internal 12 --config --maximum
virsh setvcpus Internal 12 --config

# vCPU 분포 확인
virsh vcpuinfo Internal

# QEMU 기능 확인
qemu-system-x86_64 -device help 2>&1 | grep -iE "qxl|virtio-vga|virtio-gpu"

# 인터럽트 분포
cat /proc/interrupts

# 호스트 메모리/hugepage
free -h
cat /proc/meminfo | grep -iE "huge|swap"
```

---

문의/추가 점검 필요 시 회신 부탁드립니다.
