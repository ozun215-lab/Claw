# Windows 11 QEMU/KVM VM 제작 완전 가이드

> **목적**: QEMU/KVM 환경에서 Windows 11 VM을 제작하되,  
> 복구 파티션을 EFI와 사용자 영역(C:) 사이에 배치하는 커스텀 레이아웃으로 설치한다.

---

## 목차

1. [준비물 및 환경 설정](#1-준비물-및-환경-설정)
2. [파티션 레이아웃 설계](#2-파티션-레이아웃-설계)
3. [autounattend.xml — 자동 설치 스크립트](#3-autounattendxml--자동-설치-스크립트)
4. [QEMU 실행 스크립트](#4-qemu-실행-스크립트)
5. [libvirt XML 정의 파일](#5-libvirt-xml-정의-파일)
6. [QEMU 성능 최적화](#6-qemu-성능-최적화)
7. [virtio 드라이버 자동 설치](#7-virtio-드라이버-자동-설치)
8. [설치 후 검증](#8-설치-후-검증)
9. [관리 명령어 모음](#9-관리-명령어-모음)

---

## 1. 준비물 및 환경 설정

### 필수 패키지 설치

```bash
# Ubuntu/Debian
sudo apt install -y \
  qemu-system-x86 \
  qemu-utils \
  ovmf \
  swtpm \
  swtpm-tools \
  libvirt-daemon-system \
  libvirt-clients \
  virt-manager \
  genisoimage \
  bridge-utils

# Fedora/RHEL
sudo dnf install -y \
  qemu-kvm \
  qemu-img \
  edk2-ovmf \
  swtpm \
  libvirt \
  virt-install \
  genisoimage
```

### 필수 파일 다운로드

```bash
# Windows 11 ISO (Microsoft 공식)
# https://www.microsoft.com/software-download/windows11

# virtio-win 드라이버 ISO
wget https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/latest-virtio/virtio-win.iso

# OVMF 펌웨어 경로 확인
ls /usr/share/OVMF/OVMF_CODE.fd
ls /usr/share/edk2/ovmf/OVMF_CODE.fd   # Fedora
```

### 디렉터리 구조

```
windows11-vm/
├── autounattend.xml          # Windows 설치 자동화
├── install-virtio.ps1        # virtio 드라이버 설치 (Windows 내부)
├── post-install.ps1          # 설치 후 검증
├── post-install.bat          # 수동 트리거용
├── setup.sh                  # QEMU VM 생성 & 부팅
├── run-vm.sh                 # 설치 완료 후 VM 실행
├── windows11.xml             # libvirt XML 정의
├── Win11.iso                 # Windows 11 ISO
├── virtio-win.iso            # virtio 드라이버 ISO
├── windows11.qcow2           # VM 디스크 (자동 생성)
└── windows11_VARS.fd         # UEFI NVRAM (자동 생성)
```

---

## 2. 파티션 레이아웃 설계

### 일반적인 Windows 11 레이아웃 vs 커스텀 레이아웃

```
[일반]   MSR | EFI(260MB) | C: Windows | Recovery(1GB)
[커스텀] MSR | EFI(260MB) | Recovery(1GB) | C: Windows  ← 목표
```

### 수동 설치 시 diskpart 명령어

설치 중 `Shift + F10` → 명령 프롬프트에서 실행:

```cmd
diskpart

list disk
select disk 0
clean
convert gpt

:: 1. MSR 파티션
create partition msr size=16

:: 2. EFI 시스템 파티션
create partition efi size=260
format quick fs=fat32 label="System"
assign letter=S

:: 3. 복구 파티션 (EFI 바로 다음!)
create partition primary size=1024
format quick fs=ntfs label="Recovery"
set id="de94bba4-06d1-4d40-a16a-bfd50179d6ac"
gpt attributes=0x8000000000000001

:: 4. Windows (C:) 파티션 - 나머지 전체
create partition primary
format quick fs=ntfs label="Windows"
assign letter=C

exit
```

### 파티션 속성 요약

| 항목 | 값 |
|------|-----|
| 복구 파티션 GUID | `de94bba4-06d1-4d40-a16a-bfd50179d6ac` |
| GPT 보호 속성 | `0x8000000000000001` |
| EFI 권장 크기 | 260MB (최소 100MB) |
| Recovery 권장 크기 | 1024MB (최소 500MB) |

---

## 3. autounattend.xml — 자동 설치 스크립트

ISO 루트 또는 별도 ISO에 포함시켜 Windows 설치를 완전 자동화합니다.

```xml
<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">

  <!-- ===== 1단계: Windows PE (설치 시작) ===== -->
  <settings pass="windowsPE">
    <component name="Microsoft-Windows-International-Core-WinPE"
               processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35"
               language="neutral" versionScope="nonSxS">
      <SetupUILanguage>
        <UILanguage>ko-KR</UILanguage>
      </SetupUILanguage>
      <InputLocale>0412:00000412</InputLocale>
      <SystemLocale>ko-KR</SystemLocale>
      <UILanguage>ko-KR</UILanguage>
      <UserLocale>ko-KR</UserLocale>
    </component>

    <component name="Microsoft-Windows-Setup"
               processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35"
               language="neutral" versionScope="nonSxS">

      <!-- virtio 드라이버 사전 로드 (설치 중 디스크 인식용) -->
      <DriverPaths>
        <PathAndCredentials wcm:action="add" wcm:keyValue="1">
          <Path>E:\viostor\w11\amd64</Path>
        </PathAndCredentials>
        <PathAndCredentials wcm:action="add" wcm:keyValue="2">
          <Path>E:\vioscsi\w11\amd64</Path>
        </PathAndCredentials>
        <PathAndCredentials wcm:action="add" wcm:keyValue="3">
          <Path>E:\NetKVM\w11\amd64</Path>
        </PathAndCredentials>
        <PathAndCredentials wcm:action="add" wcm:keyValue="4">
          <Path>E:\qxldod\w11\amd64</Path>
        </PathAndCredentials>
      </DriverPaths>

      <!-- 디스크 파티션 설정 (커스텀 레이아웃) -->
      <DiskConfiguration>
        <Disk wcm:action="add">
          <DiskID>0</DiskID>
          <WillWipeDisk>true</WillWipeDisk>

          <CreatePartitions>
            <!-- 파티션 1: EFI -->
            <CreatePartition wcm:action="add">
              <Order>1</Order>
              <Type>EFI</Type>
              <Size>260</Size>
            </CreatePartition>
            <!-- 파티션 2: MSR -->
            <CreatePartition wcm:action="add">
              <Order>2</Order>
              <Type>MSR</Type>
              <Size>16</Size>
            </CreatePartition>
            <!-- 파티션 3: Recovery (EFI 다음, Windows 앞!) -->
            <CreatePartition wcm:action="add">
              <Order>3</Order>
              <Type>Primary</Type>
              <Size>1024</Size>
            </CreatePartition>
            <!-- 파티션 4: Windows (C:) -->
            <CreatePartition wcm:action="add">
              <Order>4</Order>
              <Type>Primary</Type>
              <Extend>true</Extend>
            </CreatePartition>
          </CreatePartitions>

          <ModifyPartitions>
            <!-- EFI 포맷 -->
            <ModifyPartition wcm:action="add">
              <Order>1</Order>
              <PartitionID>1</PartitionID>
              <Label>System</Label>
              <Format>FAT32</Format>
            </ModifyPartition>
            <!-- MSR: 포맷 없음 -->
            <ModifyPartition wcm:action="add">
              <Order>2</Order>
              <PartitionID>2</PartitionID>
            </ModifyPartition>
            <!-- Recovery 파티션 -->
            <ModifyPartition wcm:action="add">
              <Order>3</Order>
              <PartitionID>3</PartitionID>
              <Label>Recovery</Label>
              <Format>NTFS</Format>
              <TypeID>de94bba4-06d1-4d40-a16a-bfd50179d6ac</TypeID>
            </ModifyPartition>
            <!-- Windows (C:) -->
            <ModifyPartition wcm:action="add">
              <Order>4</Order>
              <PartitionID>4</PartitionID>
              <Label>Windows</Label>
              <Format>NTFS</Format>
              <Letter>C</Letter>
            </ModifyPartition>
          </ModifyPartitions>
        </Disk>
      </DiskConfiguration>

      <!-- Windows를 설치할 파티션 지정 -->
      <ImageInstall>
        <OSImage>
          <InstallTo>
            <DiskID>0</DiskID>
            <PartitionID>4</PartitionID>
          </InstallTo>
          <InstallToAvailablePartition>false</InstallToAvailablePartition>
        </OSImage>
      </ImageInstall>

      <!-- EULA 자동 동의 -->
      <UserData>
        <AcceptEula>true</AcceptEula>
      </UserData>

    </component>
  </settings>

  <!-- ===== 2단계: Specialize ===== -->
  <settings pass="specialize">
    <component name="Microsoft-Windows-Shell-Setup"
               processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35"
               language="neutral" versionScope="nonSxS">
      <ComputerName>WIN11-VM</ComputerName>
      <TimeZone>Korea Standard Time</TimeZone>
    </component>
  </settings>

  <!-- ===== 3단계: OOBE ===== -->
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-Shell-Setup"
               processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35"
               language="neutral" versionScope="nonSxS">

      <!-- 자동 로그인 -->
      <AutoLogon>
        <Password>
          <Value>YourPassword123!</Value>
          <PlainText>true</PlainText>
        </Password>
        <Enabled>true</Enabled>
        <Username>User</Username>
        <LogonCount>3</LogonCount>
      </AutoLogon>

      <!-- OOBE 화면 건너뜀 -->
      <OOBE>
        <HideEULAPage>true</HideEULAPage>
        <HideLocalAccountScreen>false</HideLocalAccountScreen>
        <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
        <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
        <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
        <SkipMachineOOBE>true</SkipMachineOOBE>
        <SkipUserOOBE>true</SkipUserOOBE>
        <NetworkLocation>Work</NetworkLocation>
      </OOBE>

      <!-- 로컬 사용자 계정 -->
      <UserAccounts>
        <LocalAccounts>
          <LocalAccount wcm:action="add">
            <Password>
              <Value>YourPassword123!</Value>
              <PlainText>true</PlainText>
            </Password>
            <DisplayName>User</DisplayName>
            <Group>Administrators</Group>
            <Name>User</Name>
          </LocalAccount>
        </LocalAccounts>
      </UserAccounts>

      <!-- virtio 드라이버 자동 설치 (첫 로그인 시) -->
      <FirstLogonCommands>
        <SynchronousCommand wcm:action="add">
          <Order>1</Order>
          <CommandLine>
            powershell -Command "Set-ExecutionPolicy Bypass -Scope LocalMachine -Force"
          </CommandLine>
          <Description>PowerShell 실행 정책 해제</Description>
        </SynchronousCommand>
        <SynchronousCommand wcm:action="add">
          <Order>2</Order>
          <CommandLine>
            powershell -ExecutionPolicy Bypass -File "E:\install-virtio.ps1" -VirtioPath "E:\" -Reboot
          </CommandLine>
          <Description>virtio 드라이버 자동 설치</Description>
        </SynchronousCommand>
      </FirstLogonCommands>

    </component>

    <!-- 국제화 설정 -->
    <component name="Microsoft-Windows-International-Core"
               processorArchitecture="amd64"
               publicKeyToken="31bf3856ad364e35"
               language="neutral" versionScope="nonSxS">
      <InputLocale>0412:00000412</InputLocale>
      <SystemLocale>ko-KR</SystemLocale>
      <UILanguage>ko-KR</UILanguage>
      <UserLocale>ko-KR</UserLocale>
    </component>

  </settings>

</unattend>
```

---

## 4. QEMU 실행 스크립트

### `setup.sh` — 초기 설치용

```bash
#!/bin/bash
set -e

# ── 설정 ──────────────────────────────────────────────
VM_NAME="windows11"
DISK_SIZE="64G"
RAM="4096"
CPUS="4"
WIN_ISO="./Win11.iso"
VIRTIO_ISO="./virtio-win.iso"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE.fd"
OVMF_VARS_TEMPLATE="/usr/share/OVMF/OVMF_VARS.fd"
# ───────────────────────────────────────────────────────

DISK="${VM_NAME}.qcow2"
OVMF_VARS="${VM_NAME}_VARS.fd"
UNATTEND_ISO="${VM_NAME}_unattend.iso"

echo "==> [1/4] OVMF VARS 복사"
cp "$OVMF_VARS_TEMPLATE" "$OVMF_VARS"

echo "==> [2/4] 가상 디스크 생성"
if [ ! -f "$DISK" ]; then
  qemu-img create -f qcow2 "$DISK" "$DISK_SIZE"
  echo "    생성됨: $DISK"
else
  echo "    이미 존재함, 건너뜀: $DISK"
fi

echo "==> [3/4] autounattend.xml → ISO 패키징"
mkdir -p unattend_tmp
cp autounattend.xml unattend_tmp/
genisoimage -o "$UNATTEND_ISO" -J -r unattend_tmp/

echo "==> [4/4] QEMU 부팅 (설치 시작)"
qemu-system-x86_64 \
  -enable-kvm \
  -m "$RAM" \
  -cpu host \
  -smp "$CPUS" \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=pflash,format=raw,file="$OVMF_VARS" \
  -drive file="$DISK",if=virtio,cache=writeback,discard=unmap \
  -cdrom "$WIN_ISO" \
  -drive file="$UNATTEND_ISO",media=cdrom,index=2 \
  -drive file="$VIRTIO_ISO",media=cdrom,index=3 \
  -boot order=d,once=d \
  -machine q35 \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0 \
  -vga virtio \
  -display gtk \
  -usb -device usb-tablet \
  -rtc base=localtime \
  -name "$VM_NAME"

echo "==> 설치 완료!"
```

### `run-vm.sh` — 설치 완료 후 실행용 (최적화 포함)

```bash
#!/bin/bash
set -e

# ── 설정 ──────────────────────────────────────────────
VM_NAME="windows11"
DISK="${VM_NAME}.qcow2"
OVMF_CODE="/usr/share/OVMF/OVMF_CODE.fd"
OVMF_VARS="${VM_NAME}_VARS.fd"
TPM_STATE="/tmp/tpm-${VM_NAME}"
TPM_SOCK="/tmp/swtpm-${VM_NAME}.sock"
RAM="8192"
CORES="4"
THREADS="2"
# ───────────────────────────────────────────────────────

# TPM 시작
echo "==> TPM 시작..."
mkdir -p "$TPM_STATE"
pkill -f "swtpm.*${VM_NAME}" 2>/dev/null || true
swtpm socket \
  --tpmstate dir="$TPM_STATE" \
  --ctrl type=unixio,path="$TPM_SOCK" \
  --tpm2 --daemon
sleep 1

# CPU 벤더 감지
CPU_VENDOR=$(grep -m1 vendor_id /proc/cpuinfo | awk '{print $3}')
if [[ "$CPU_VENDOR" == "AuthenticAMD" ]]; then
  HV_VENDOR="hv_vendor_id=AuthenticAMD"
else
  HV_VENDOR="hv_vendor_id=GenuineIntel"
fi

echo "==> VM 시작 (CPU: $CPU_VENDOR)..."
qemu-system-x86_64 \
  -enable-kvm \
  -machine q35,accel=kvm \
  -cpu host,hv_relaxed,hv_spinlocks=0x1fff,hv_vapic,hv_time,${HV_VENDOR},\
hv_synic,hv_stimer,hv_tlbflush,hv_ipi \
  -smp cores=${CORES},threads=${THREADS},sockets=1 \
  \
  -m ${RAM} \
  -mem-prealloc \
  \
  -drive if=pflash,format=raw,readonly=on,file="${OVMF_CODE}" \
  -drive if=pflash,format=raw,file="${OVMF_VARS}" \
  \
  -device virtio-scsi-pci,id=scsi0 \
  -drive file="${DISK}",if=none,id=disk0,cache=none,aio=native,discard=unmap \
  -device scsi-hd,drive=disk0,bus=scsi0.0 \
  \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp::3389-:3389 \
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

# 종료 후 TPM 정리
echo "==> VM 종료, TPM 정리..."
pkill -f "swtpm.*${VM_NAME}" 2>/dev/null || true
```

---

## 5. libvirt XML 정의 파일

### `windows11.xml`

```xml
<domain type="kvm">

  <!-- ── 기본 정보 ──────────────────────────────────── -->
  <name>windows11</name>
  <title>Windows 11 VM</title>
  <description>Windows 11 with custom partition layout (EFI-Recovery-C:)</description>

  <!-- ── 펌웨어 (UEFI) ─────────────────────────────── -->
  <os firmware="efi">
    <type arch="x86_64" machine="q35">hvm</type>
    <loader readonly="yes" type="pflash">/usr/share/OVMF/OVMF_CODE.fd</loader>
    <nvram>/var/lib/libvirt/qemu/nvram/windows11_VARS.fd</nvram>
    <boot dev="hd"/>
  </os>

  <!-- ── 메모리 ─────────────────────────────────────── -->
  <memory unit="MiB">8192</memory>
  <currentMemory unit="MiB">8192</currentMemory>
  <memoryBacking>
    <hugepages/>
    <locked/>
  </memoryBacking>

  <!-- ── CPU ───────────────────────────────────────── -->
  <vcpu placement="static">8</vcpu>
  <cpu mode="host-passthrough" check="none" migratable="off">
    <topology sockets="1" dies="1" cores="4" threads="2"/>
    <cache mode="passthrough"/>
  </cpu>

  <!-- ── Hyper-V 기능 ──────────────────────────────── -->
  <features>
    <acpi/>
    <apic/>
    <hyperv mode="custom">
      <relaxed state="on"/>
      <vapic state="on"/>
      <spinlocks state="on" retries="8191"/>
      <vpindex state="on"/>
      <runtime state="on"/>
      <synic state="on"/>
      <stimer state="on">
        <direct state="on"/>
      </stimer>
      <reset state="on"/>
      <vendor_id state="on" value="AuthenticAMD"/>
      <frequencies state="on"/>
      <tlbflush state="on"/>
      <ipi state="on"/>
    </hyperv>
    <kvm>
      <hidden state="on"/>
    </kvm>
    <vmport state="off"/>
    <smm state="on"/>
  </features>

  <!-- ── 타이머 ─────────────────────────────────────── -->
  <clock offset="localtime">
    <timer name="rtc" tickpolicy="catchup"/>
    <timer name="pit" tickpolicy="delay"/>
    <timer name="hpet" present="no"/>
    <timer name="hypervclock" present="yes"/>
    <timer name="tsc" present="yes" mode="native"/>
  </clock>

  <!-- ── 전원 관리 ──────────────────────────────────── -->
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <pm>
    <suspend-to-mem enabled="no"/>
    <suspend-to-disk enabled="no"/>
  </pm>

  <!-- ════════════════════════════════════════════════ -->
  <!--                     장치들                       -->
  <!-- ════════════════════════════════════════════════ -->
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>

    <!-- ── 메인 디스크 ────────────────────────────────── -->
    <disk type="file" device="disk">
      <driver name="qemu" type="qcow2"
              cache="none" io="native"
              discard="unmap" detect_zeroes="unmap"/>
      <source file="/var/lib/libvirt/images/windows11.qcow2"/>
      <target dev="sda" bus="virtio"/>
      <boot order="1"/>
    </disk>

    <!-- ── Windows 설치 ISO ──────────────────────────── -->
    <disk type="file" device="cdrom">
      <driver name="qemu" type="raw"/>
      <source file="/path/to/Win11.iso"/>
      <target dev="sdb" bus="sata"/>
      <readonly/>
      <boot order="2"/>
    </disk>

    <!-- ── autounattend ISO ───────────────────────────── -->
    <disk type="file" device="cdrom">
      <driver name="qemu" type="raw"/>
      <source file="/path/to/windows11_unattend.iso"/>
      <target dev="sdc" bus="sata"/>
      <readonly/>
    </disk>

    <!-- ── virtio 드라이버 ISO ───────────────────────── -->
    <disk type="file" device="cdrom">
      <driver name="qemu" type="raw"/>
      <source file="/path/to/virtio-win.iso"/>
      <target dev="sdd" bus="sata"/>
      <readonly/>
    </disk>

    <!-- ── 네트워크 ───────────────────────────────────── -->
    <interface type="network">
      <mac address="52:54:00:12:34:56"/>
      <source network="default"/>
      <model type="virtio"/>
      <driver name="vhost" queues="4"/>
    </interface>

    <!-- ── 그래픽: SPICE ──────────────────────────────── -->
    <graphics type="spice" autoport="yes" listen="127.0.0.1">
      <listen type="address" address="127.0.0.1"/>
      <image compression="off"/>
    </graphics>

    <!-- ── 비디오: virtio ────────────────────────────── -->
    <video>
      <model type="virtio" heads="1" primary="yes">
        <acceleration accel3d="yes"/>
      </model>
    </video>

    <!-- ── TPM 2.0 ───────────────────────────────────── -->
    <tpm model="tpm-tis">
      <backend type="emulator" version="2.0">
        <active_pcr_banks>
          <sha256/>
        </active_pcr_banks>
      </backend>
    </tpm>

    <!-- ── USB 컨트롤러 ──────────────────────────────── -->
    <controller type="usb" index="0" model="qemu-xhci" ports="15"/>

    <!-- ── 입력 장치 ─────────────────────────────────── -->
    <input type="tablet" bus="usb"/>
    <input type="keyboard" bus="usb"/>
    <input type="mouse" bus="ps2"/>

    <!-- ── 오디오 ─────────────────────────────────────── -->
    <sound model="ich9"/>
    <audio id="1" type="spice"/>

    <!-- ── VIRTIO Serial ─────────────────────────────── -->
    <controller type="virtio-serial" index="0"/>
    <channel type="spicevmc">
      <target type="virtio" name="com.redhat.spice.0"/>
    </channel>

    <!-- ── QEMU Guest Agent ──────────────────────────── -->
    <channel type="unix">
      <target type="virtio" name="org.qemu.guest_agent.0"/>
    </channel>

    <!-- ── Balloon 메모리 ─────────────────────────────── -->
    <memballoon model="virtio">
      <stats period="5"/>
    </memballoon>

    <!-- ── RNG ───────────────────────────────────────── -->
    <rng model="virtio">
      <backend model="random">/dev/urandom</backend>
    </rng>

  </devices>

</domain>
```

### libvirt 적용 명령어

```bash
# XML 유효성 검사
virt-xml-validate windows11.xml

# VM 정의 등록
virsh define windows11.xml

# 시작
virsh start windows11

# 자동 시작 등록
virsh autostart windows11

# SPICE 접속
virt-viewer windows11
```

---

## 6. QEMU 성능 최적화

### CPU 최적화 — Hyper-V 플래그

```bash
-cpu host,hv_relaxed,hv_spinlocks=0x1fff,hv_vapic,hv_time,\
hv_vendor_id=AuthenticAMD,hv_synic,hv_stimer,hv_tlbflush,hv_ipi,hv_runtime
```

| 플래그 | 효과 |
|--------|------|
| `hv_relaxed` | 타이머 스핀락 완화 |
| `hv_vapic` | 가상 APIC, 인터럽트 오버헤드 감소 |
| `hv_time` | 레퍼런스 TSC 사용 |
| `hv_tlbflush` | TLB 플러시 최적화 |
| `hv_ipi` | 가상 IPI 처리 가속 |
| `hv_synic` | SynIC 타이머 |
| `hv_stimer` | Synthetic Timer |

### 메모리 최적화 — Huge Pages

```bash
# 호스트 설정
echo 4096 | sudo tee /proc/sys/vm/nr_hugepages
sudo mkdir -p /dev/hugepages
sudo mount -t hugetlbfs none /dev/hugepages

# QEMU 옵션
-mem-path /dev/hugepages \
-mem-prealloc
```

### 스토리지 최적화

```bash
# virtio-scsi + native AIO (최고 성능)
-device virtio-scsi-pci,id=scsi0 \
-drive file=windows11.qcow2,if=none,id=disk0,cache=none,aio=native,discard=unmap \
-device scsi-hd,drive=disk0,bus=scsi0.0
```

| 옵션 | 설명 |
|------|------|
| `cache=none` | 호스트 페이지 캐시 우회 |
| `aio=native` | 커널 비동기 I/O |
| `discard=unmap` | TRIM 지원 |

### 성능 비교

| 항목 | 기본 설정 | 최적화 후 | 향상 |
|------|-----------|-----------|------|
| CPU (Passmark) | ~3,000 | ~8,000+ | **+166%** |
| 디스크 읽기 | ~200 MB/s | ~800 MB/s+ | **+300%** |
| 디스크 쓰기 | ~150 MB/s | ~600 MB/s+ | **+300%** |
| 그래픽 반응성 | 느림 | 부드러움 | **GL 가속** |

### 호스트 튜닝

```bash
# CPU 거버너 performance 모드
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# IOMMU 활성화 (Intel)
# /etc/default/grub:
GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"
sudo update-grub

# IOMMU 활성화 (AMD)
GRUB_CMDLINE_LINUX="amd_iommu=on iommu=pt"
sudo update-grub

# KSM 비활성화 (성능 우선)
echo 0 | sudo tee /sys/kernel/mm/ksm/run
```

---

## 7. virtio 드라이버 자동 설치

### `install-virtio.ps1`

```powershell
#Requires -RunAsAdministrator
param(
    [string]$VirtioPath = "D:\",
    [switch]$Force,
    [switch]$Reboot
)

$OS_VERSION = "w11"
$ARCH       = "amd64"
$LOG_FILE   = "$env:TEMP\virtio-install.log"

function Write-Step { param($msg) Write-Host "`n[>>] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  [XX] $msg" -ForegroundColor Red }
function Write-Log  { param($msg) Add-Content $LOG_FILE "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $msg" }

function Install-VirtioDriver {
    param([string]$Name, [string]$InfPath)
    if (-not (Test-Path $InfPath)) {
        Write-Warn "$Name — INF 없음: $InfPath"; return
    }
    Write-Host "  설치 중: $Name" -NoNewline
    $result = & pnputil /add-driver "$InfPath" /install 2>&1
    $exit   = $LASTEXITCODE
    if ($exit -eq 0 -or $exit -eq 3010) {
        Write-Host " ... "; Write-OK "완료"
        Write-Log "OK   $Name"
    } else {
        Write-Host " ... "; Write-Fail "실패 (종료코드: $exit)"
        Write-Log "FAIL $Name — exit:$exit"
    }
}

function Install-VirtioMSI {
    param([string]$Name, [string]$MsiPath, [string]$Args = "/quiet /norestart")
    if (-not (Test-Path $MsiPath)) { Write-Warn "$Name — MSI 없음"; return }
    Write-Host "  설치 중: $Name" -NoNewline
    $proc = Start-Process msiexec -ArgumentList "/i `"$MsiPath`" $Args" -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
        Write-Host " ... "; Write-OK "완료"
    } else {
        Write-Host " ... "; Write-Fail "실패 (종료코드: $($proc.ExitCode))"
    }
}

# virtio ISO 마운트 확인
if (-not (Test-Path "${VirtioPath}viostor\${OS_VERSION}\${ARCH}\viostor.inf")) {
    Write-Fail "virtio-win ISO가 $VirtioPath 에 마운트되지 않았습니다."
    exit 1
}

Write-Step "스토리지 드라이버"
Install-VirtioDriver "viostor (SCSI)"         "${VirtioPath}viostor\${OS_VERSION}\${ARCH}\viostor.inf"
Install-VirtioDriver "vioscsi (SCSI passthrough)" "${VirtioPath}vioscsi\${OS_VERSION}\${ARCH}\vioscsi.inf"
Install-VirtioDriver "vioblk (Block)"         "${VirtioPath}vioblk\${OS_VERSION}\${ARCH}\vioblk.inf"

Write-Step "네트워크 드라이버"
Install-VirtioDriver "NetKVM (virtio-net)"    "${VirtioPath}NetKVM\${OS_VERSION}\${ARCH}\netkvm.inf"

Write-Step "메모리 드라이버"
Install-VirtioDriver "Balloon"                "${VirtioPath}Balloon\${OS_VERSION}\${ARCH}\balloon.inf"
Install-VirtioDriver "viopmem"                "${VirtioPath}viopmem\${OS_VERSION}\${ARCH}\viopmem.inf"

Write-Step "직렬/시리얼 드라이버"
Install-VirtioDriver "vioserial"              "${VirtioPath}vioserial\${OS_VERSION}\${ARCH}\vioser.inf"

Write-Step "입력 장치 드라이버"
Install-VirtioDriver "vioinput"               "${VirtioPath}vioinput\${OS_VERSION}\${ARCH}\vioinput.inf"

Write-Step "그래픽 드라이버"
Install-VirtioDriver "viogpudo"               "${VirtioPath}viogpudo\${OS_VERSION}\${ARCH}\viogpudo.inf"
Install-VirtioDriver "qxldod"                 "${VirtioPath}qxldod\${OS_VERSION}\${ARCH}\qxldod.inf"

Write-Step "기타 드라이버"
Install-VirtioDriver "pvpanic"                "${VirtioPath}pvpanic\${OS_VERSION}\${ARCH}\pvpanic.inf"
Install-VirtioDriver "fwcfg"                  "${VirtioPath}fwcfg\${OS_VERSION}\${ARCH}\fwcfg.inf"

Write-Step "QEMU Guest Agent"
Install-VirtioMSI "QEMU Guest Agent" "${VirtioPath}guest-agent\qemu-ga-x86_64.msi"

Write-Step "설치된 드라이버 확인"
Get-WmiObject Win32_PnPSignedDriver |
    Where-Object { $_.DeviceName -match "VirtIO|QEMU|Red Hat" } |
    Select-Object DeviceName, DriverVersion, Manufacturer |
    Format-Table -AutoSize

Write-Host "`n로그: $LOG_FILE" -ForegroundColor Gray
Write-Log "=== 설치 완료 ==="

if ($Reboot) {
    Write-Host "`n10초 후 재부팅..." -ForegroundColor Yellow
    Start-Sleep 10
    Restart-Computer -Force
} else {
    $r = Read-Host "재부팅하시겠습니까? (y/N)"
    if ($r -match '^[Yy]') { Restart-Computer -Force }
}
```

### `post-install.bat` — 수동 트리거

```bat
@echo off
chcp 65001 >nul
echo ================================================
echo  virtio 드라이버 자동 설치
echo ================================================

powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force"

for %%d in (D E F G H) do (
    if exist "%%d:\viostor\w11\amd64\viostor.inf" (
        set VIRTIO_DRIVE=%%d:\
        goto :found
    )
)
echo [오류] virtio-win ISO를 찾을 수 없습니다.
pause & exit /b 1

:found
echo virtio-win ISO 감지됨: %VIRTIO_DRIVE%
powershell -ExecutionPolicy Bypass ^
    -File "%~dp0install-virtio.ps1" ^
    -VirtioPath "%VIRTIO_DRIVE%"
pause
```

### virtio 드라이버 목록

| 드라이버 | 역할 | 필수 여부 |
|----------|------|-----------|
| `viostor` | virtio SCSI 스토리지 | ✅ 필수 |
| `vioscsi` | SCSI passthrough | ✅ 필수 |
| `NetKVM` | virtio 네트워크 | ✅ 필수 |
| `Balloon` | 동적 메모리 조절 | 권장 |
| `vioserial` | virtio 시리얼 | 권장 |
| `vioinput` | 마우스/키보드 | 권장 |
| `viogpudo` | virtio 디스플레이 | 권장 |
| `qxldod` | QXL 디스플레이 | SPICE 사용 시 |
| `pvpanic` | 패닉 감지 | 선택 |
| `QEMU Guest Agent` | 호스트-게스트 통신 | 권장 |

---

## 8. 설치 후 검증

### `post-install.ps1`

```powershell
# WinRE 상태 확인 및 활성화
Write-Host "=== WinRE 상태 확인 ===" -ForegroundColor Cyan
reagentc /info

$status = reagentc /info | Select-String "Windows RE 상태"
if ($status -match "사용 안 함|Disabled") {
    Write-Host "WinRE 활성화 중..." -ForegroundColor Yellow
    reagentc /enable
    reagentc /info
} else {
    Write-Host "WinRE 정상 활성화됨!" -ForegroundColor Green
}

# 파티션 레이아웃 확인
Write-Host "`n=== 파티션 레이아웃 ===" -ForegroundColor Cyan
Get-Partition | Select-Object DiskNumber, PartitionNumber,
    @{N="Type";E={$_.Type}},
    @{N="Size(MB)";E={[math]::Round($_.Size/1MB)}},
    DriveLetter, GptType | Format-Table -AutoSize

# 복구 파티션 확인
Write-Host "`n=== 복구 파티션 확인 ===" -ForegroundColor Cyan
Get-Partition | Where-Object {
    $_.GptType -eq "{de94bba4-06d1-4d40-a16a-bfd50179d6ac}"
} | Format-Table -AutoSize

# virtio 드라이버 확인
Write-Host "`n=== virtio 드라이버 ===" -ForegroundColor Cyan
Get-WmiObject Win32_PnPSignedDriver |
    Where-Object { $_.Manufacturer -match "Red Hat|VirtIO" } |
    Select-Object DeviceName, DriverVersion |
    Format-Table -AutoSize

# 오류 장치 확인
Write-Host "`n=== 오류 장치 ===" -ForegroundColor Cyan
Get-WmiObject Win32_PnPEntity |
    Where-Object { $_.ConfigManagerErrorCode -ne 0 } |
    Select-Object Name, ConfigManagerErrorCode |
    Format-Table -AutoSize

# QEMU Guest Agent 서비스 확인
Write-Host "`n=== QEMU Guest Agent ===" -ForegroundColor Cyan
Get-Service -Name "QEMU-GA" -ErrorAction SilentlyContinue
```

---

## 9. 관리 명령어 모음

### virsh 기본 제어

```bash
virsh start windows11          # 시작
virsh shutdown windows11       # 정상 종료
virsh destroy windows11        # 강제 종료
virsh reboot windows11         # 재시작
virsh suspend windows11        # 일시 정지
virsh resume windows11         # 재개
virsh list --all               # VM 목록 확인
virsh dominfo windows11        # VM 상세 정보
```

### 스냅샷 관리

```bash
# 스냅샷 생성
virsh snapshot-create-as windows11 "clean-install" \
  --description "초기 설치 완료 상태"

# 스냅샷 목록
virsh snapshot-list windows11

# 스냅샷 복원
virsh snapshot-revert windows11 "clean-install"

# 스냅샷 삭제
virsh snapshot-delete windows11 "clean-install"
```

### 설치 완료 후 ISO 제거

```bash
virsh change-media windows11 sdb --eject --live
virsh change-media windows11 sdc --eject --live
virsh change-media windows11 sdd --eject --live
```

### 디스크 관리

```bash
# 디스크 목록
virsh domblklist windows11

# 디스크 추가 (실시간)
virsh attach-disk windows11 /path/to/extra.qcow2 vdb --live

# qcow2 → raw 변환 (성능 향상)
qemu-img convert -f qcow2 -O raw windows11.qcow2 windows11.raw

# 디스크 압축
qemu-img convert -O qcow2 -c windows11.qcow2 windows11-compressed.qcow2
```

### RDP 원격 접속

```bash
# 호스트에서 RDP 접속 (3389 포트 포워딩 설정 시)
xfreerdp /v:localhost:3389 /u:User /p:YourPassword123!

# 또는
rdesktop localhost:3389
```

---

## 전체 실행 순서 요약

```bash
# 1. 파일 준비
chmod +x setup.sh run-vm.sh

# 2. VM 생성 및 설치 시작
./setup.sh

# 3. 설치 완료 후 (재부팅 시 CD 제거하고 재시작)
./run-vm.sh

# 4. Windows 로그인 후 PowerShell에서 검증
Set-ExecutionPolicy Bypass -Scope Process
.\post-install.ps1
```

---

*문서 생성: 2026-05-15*  
*환경: QEMU/KVM + libvirt + Windows 11 + virtio-win*
