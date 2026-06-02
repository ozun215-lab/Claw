# libvirt KVM Windows 11 VM 부팅 속도 개선 방안

> 작성일: 2026-04-30  
> 환경: Debian Linux / libvirt + QEMU-KVM / Windows 11 Guest

---

## 목차

1. [펌웨어 — OVMF (UEFI) + Secure Boot](#1-펌웨어--ovmf-uefi--secure-boot)
2. [머신 타입 — q35 + 최신 QEMU](#2-머신-타입--q35--최신-qemu)
3. [CPU 설정](#3-cpu-설정)
4. [Hyper-V Enlightenments](#4-hyper-v-enlightenments-windows-전용-최적화)
5. [스토리지 — VirtIO + 캐시 전략](#5-스토리지--virtio--캐시-전략)
6. [메모리 — HugePage + Balloon 비활성화](#6-메모리--hugepage--balloon-비활성화)
7. [네트워크 — VirtIO + multiqueue](#7-네트워크--virtio--multiqueue)
8. [VirtIO 채널 (Guest Agent)](#8-virtio-채널-guest-agent)
9. [Windows 게스트 내부 설정](#9-windows-게스트-내부-설정)
10. [완성 XML 골격](#10-완성-xml-골격)
11. [효과 요약](#효과-요약)

---

## 1. 펌웨어 — OVMF (UEFI) + Secure Boot

```xml
<os firmware="efi">
  <type arch="x86_64" machine="q35">hvm</type>
  <firmware>
    <feature enabled="yes" name="secure-boot"/>
    <feature enabled="yes" name="enrolled-keys"/>
  </firmware>
  <loader readonly="yes" secure="yes" type="pflash">
    /usr/share/OVMF/OVMF_CODE_4M.secboot.fd
  </loader>
  <nvram template="/usr/share/OVMF/OVMF_VARS_4M.ms.fd">
    /var/lib/libvirt/qemu/nvram/win11_VARS.fd
  </nvram>
  <bootmenu enable="no"/>       <!-- 부팅 메뉴 스킵 -->
</os>
```

> **`bootmenu enable="no"`** 만으로도 UEFI POST 대기 시간 2~3초 단축

---

## 2. 머신 타입 — q35 + 최신 QEMU

```xml
<type arch="x86_64" machine="pc-q35-8.2">hvm</type>
```

- `i440fx` → `q35` 전환 시 PCIe 네이티브, NVMe 직접 지원으로 I/O 초기화 빨라짐
- QEMU 버전이 낮으면 `pc-q35-7.2` 등으로 맞춤

---

## 3. CPU 설정

```xml
<cpu mode="host-passthrough" check="none" migratable="off">
  <topology sockets="1" dies="1" cores="4" threads="2"/>
  <feature policy="require" name="topoext"/>     <!-- AMD일 때 -->
  <feature policy="disable" name="hypervisor"/>  <!-- Hyper-V 충돌 방지 -->
</cpu>

<vcpu placement="static">8</vcpu>
<cputune>
  <vcpupin vcpu="0" cpuset="2"/>
  <vcpupin vcpu="1" cpuset="3"/>
  <vcpupin vcpu="2" cpuset="4"/>
  <vcpupin vcpu="3" cpuset="5"/>
  <vcpupin vcpu="4" cpuset="6"/>
  <vcpupin vcpu="5" cpuset="7"/>
  <vcpupin vcpu="6" cpuset="8"/>
  <vcpupin vcpu="7" cpuset="9"/>
  <emulatorpin cpuset="0-1"/>   <!-- 에뮬레이터는 별도 코어 -->
</cputune>
```

**핵심:** `host-passthrough` + CPU 피닝으로 스케줄러 오버헤드 제거

---

## 4. Hyper-V Enlightenments (Windows 전용 최적화)

```xml
<features>
  <acpi/>
  <apic/>
  <hyperv mode="custom">
    <relaxed   state="on"/>
    <vapic     state="on"/>
    <spinlocks state="on" retries="8191"/>
    <vpindex   state="on"/>
    <runtime   state="on"/>
    <synic     state="on"/>
    <stimer    state="on" direct="on"/>
    <frequencies state="on"/>
    <reenlightenment state="on"/>
    <tlbflush  state="on"/>
    <ipi       state="on"/>
    <evmcs     state="on"/>   <!-- Intel VMX 환경만 -->
  </hyperv>
  <kvm>
    <hidden state="on"/>      <!-- KVM 숨김, 일부 앱 호환성 향상 -->
  </kvm>
  <vmport state="off"/>
</features>

<clock offset="localtime">
  <timer name="rtc"  tickpolicy="catchup"/>
  <timer name="pit"  tickpolicy="delay"/>
  <timer name="hpet" present="no"/>
  <timer name="hypervclock" present="yes"/>  <!-- Windows 시간 동기화 -->
</clock>
```

> `stimer direct`, `tlbflush`, `ipi` 는 부팅 중 커널 초기화 속도에 직접 영향

---

## 5. 스토리지 — VirtIO + 캐시 전략

```xml
<disk type="file" device="disk">
  <driver name="qemu" type="qcow2"
          cache="none"          <!-- O_DIRECT: 호스트 캐시 우회 -->
          io="native"           <!-- AIO 네이티브 (io_uring 도 가능) -->
          discard="unmap"       <!-- TRIM 지원 -->
          detect_zeroes="unmap"/>
  <source file="/var/lib/libvirt/images/win11.qcow2"/>
  <target dev="vda" bus="virtio"/>
  <address type="pci" domain="0x0000" bus="0x04" slot="0x00" function="0x0"/>
</disk>
```

**추가 옵션 — io_uring (QEMU 5.0+, 커널 5.1+)**

```xml
<driver name="qemu" type="qcow2" cache="none" io="io_uring" discard="unmap"/>
```

**이미지 사전 할당 (단편화 방지)**

```bash
# qcow2 생성 시
qemu-img create -f qcow2 -o preallocation=metadata,cluster_size=2M win11.qcow2 100G

# 기존 이미지 최적화
qemu-img convert -O qcow2 -o preallocation=metadata win11.qcow2 win11_opt.qcow2
```

---

## 6. 메모리 — HugePage + Balloon 비활성화

```xml
<memory unit="GiB">16</memory>
<currentMemory unit="GiB">16</currentMemory>

<memoryBacking>
  <hugepages>
    <page size="2048" unit="KiB"/>   <!-- 부팅 시 hugepage 스크립트로 사전 확보 -->
  </hugepages>
  <nosharepages/>    <!-- KSM 비활성 → 예측 가능한 성능 -->
  <locked/>          <!-- 메모리 스왑 방지 -->
  <source type="memfd"/>   <!-- memfd 백엔드 (QEMU 4.0+) -->
  <access mode="shared"/>
</memoryBacking>

<!-- balloon 비활성: 부팅 중 메모리 회수 인터럽트 제거 -->
<memballoon model="none"/>
```

> HugePage 사전 확보는 별도 작성된 `hugepages-setup.sh` / `hugepages-setup.service` 참고

---

## 7. 네트워크 — VirtIO + multiqueue

```xml
<interface type="network">
  <source network="default"/>
  <model type="virtio"/>
  <driver name="vhost" queues="4"/>   <!-- vCPU 수만큼 설정 -->
</interface>
```

---

## 8. VirtIO 채널 (Guest Agent)

```xml
<!-- QEMU Guest Agent: Windows 측 정보 수집 및 최적 종료 -->
<channel type="unix">
  <target type="virtio" name="org.qemu.guest_agent.0"/>
</channel>

<!-- Spice / 디스플레이 최적화 -->
<channel type="spicevmc">
  <target type="virtio" name="com.redhat.spice.0"/>
</channel>
```

---

## 9. Windows 게스트 내부 설정

관리자 PowerShell에서 실행:

```powershell
# 1. Fast Startup (최대 절전 기반 빠른 시작) 활성화
powercfg /hibernate on
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" `
    -Name HiberbootEnabled -Value 1

# 2. 불필요한 부팅 서비스 비활성화
$services = @("SysMain","WSearch","DiagTrack","TabletInputService","WerSvc")
foreach ($svc in $services) {
    Set-Service -Name $svc -StartupType Disabled -ErrorAction SilentlyContinue
}

# 3. 부팅 타임아웃 단축 (기본 30초 → 3초)
bcdedit /timeout 3

# 4. VirtIO 드라이버 설치 확인
Get-PnpDevice | Where-Object { $_.FriendlyName -match "VirtIO" } |
    Select-Object FriendlyName, Status
```

> VirtIO 드라이버: https://github.com/virtio-win/virtio-win-pkg-scripts (최신 버전 권장)

---

## 10. 완성 XML 골격

`virsh edit win11` 참고용 전체 구조:

```xml
<domain type="kvm">
  <name>win11</name>
  <memory unit="GiB">16</memory>
  <currentMemory unit="GiB">16</currentMemory>
  <vcpu placement="static">8</vcpu>

  <os firmware="efi">
    <type arch="x86_64" machine="pc-q35-8.2">hvm</type>
    <loader readonly="yes" secure="yes" type="pflash">
      /usr/share/OVMF/OVMF_CODE_4M.secboot.fd
    </loader>
    <nvram template="/usr/share/OVMF/OVMF_VARS_4M.ms.fd">
      /var/lib/libvirt/qemu/nvram/win11_VARS.fd
    </nvram>
    <bootmenu enable="no"/>
  </os>

  <features>
    <acpi/>
    <apic/>
    <hyperv mode="custom">
      <relaxed   state="on"/>
      <vapic     state="on"/>
      <spinlocks state="on" retries="8191"/>
      <vpindex   state="on"/>
      <runtime   state="on"/>
      <synic     state="on"/>
      <stimer    state="on" direct="on"/>
      <frequencies state="on"/>
      <reenlightenment state="on"/>
      <tlbflush  state="on"/>
      <ipi       state="on"/>
    </hyperv>
    <kvm><hidden state="on"/></kvm>
    <vmport state="off"/>
  </features>

  <cpu mode="host-passthrough" check="none" migratable="off">
    <topology sockets="1" dies="1" cores="4" threads="2"/>
  </cpu>

  <cputune>
    <vcpupin vcpu="0" cpuset="2"/>
    <vcpupin vcpu="1" cpuset="3"/>
    <vcpupin vcpu="2" cpuset="4"/>
    <vcpupin vcpu="3" cpuset="5"/>
    <vcpupin vcpu="4" cpuset="6"/>
    <vcpupin vcpu="5" cpuset="7"/>
    <vcpupin vcpu="6" cpuset="8"/>
    <vcpupin vcpu="7" cpuset="9"/>
    <emulatorpin cpuset="0-1"/>
  </cputune>

  <clock offset="localtime">
    <timer name="rtc"  tickpolicy="catchup"/>
    <timer name="pit"  tickpolicy="delay"/>
    <timer name="hpet" present="no"/>
    <timer name="hypervclock" present="yes"/>
  </clock>

  <memoryBacking>
    <hugepages>
      <page size="2048" unit="KiB"/>
    </hugepages>
    <nosharepages/>
    <locked/>
    <source type="memfd"/>
    <access mode="shared"/>
  </memoryBacking>

  <devices>
    <!-- 디스크 -->
    <disk type="file" device="disk">
      <driver name="qemu" type="qcow2"
              cache="none" io="native"
              discard="unmap" detect_zeroes="unmap"/>
      <source file="/var/lib/libvirt/images/win11.qcow2"/>
      <target dev="vda" bus="virtio"/>
    </disk>

    <!-- 네트워크 -->
    <interface type="network">
      <source network="default"/>
      <model type="virtio"/>
      <driver name="vhost" queues="4"/>
    </interface>

    <!-- Guest Agent -->
    <channel type="unix">
      <target type="virtio" name="org.qemu.guest_agent.0"/>
    </channel>
    <channel type="spicevmc">
      <target type="virtio" name="com.redhat.spice.0"/>
    </channel>

    <!-- Balloon 비활성 -->
    <memballoon model="none"/>
  </devices>

</domain>
```

---

## 효과 요약

| 항목 | 개선 내용 | 예상 효과 |
|------|-----------|-----------|
| UEFI 부팅 메뉴 제거 | `bootmenu enable="no"` | -2~3초 |
| Hyper-V Enlightenments | stimer/tlbflush/ipi 등 | 커널 초기화 -20~40% |
| `host-passthrough` + CPU 피닝 | 스케줄러 오버헤드 제거 | 안정적 레이턴시 |
| HugePage + `cache=none` | TLB 미스 감소, I/O 직접 | 스토리지 초기화 -15~30% |
| `memballoon none` | 부팅 중 메모리 인터럽트 제거 | 초기화 안정화 |
| Windows Fast Startup | 최대 절전 기반 복귀 | 재부팅 후 -40~60% |
| VirtIO 전 스택 | 디스크·네트워크·입력 드라이버 | 드라이버 로딩 안정화 |
| q35 머신 타입 | PCIe 네이티브 버스 | PCI 열거 시간 단축 |

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `hugepages-setup.sh` | 부팅 시 HugePage 런타임 할당 스크립트 |
| `hugepages.conf` | HugePage 설정 파일 |
| `hugepages-setup.service` | systemd 유닛 파일 |
| `install.sh` | HugePage 설치 스크립트 |

---

*참고: virtio-win 드라이버 최신 버전 — https://github.com/virtio-win/virtio-win-pkg-scripts*
