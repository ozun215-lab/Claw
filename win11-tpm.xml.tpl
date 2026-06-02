<!--
  Windows 11 vTPM VM 템플릿 (시나리오 B 용)
  
  배치 경로: /etc/libvirt/templates/win11-tpm.xml.tpl
  사용처:    deploy-instance.sh
  
  치환 변수:
    __VM_NAME__    : VM 이름 (예: win11-vdi-01)
    __UUID__       : UUID (uuidgen)
    __MAC__        : MAC 주소 (52:54:00:xx:xx:xx)
    __MEMORY_KB__  : 메모리 (KB 단위)
    __VCPU__       : vCPU 개수
  
  참조: INFRA-VM-DEPLOY-007 (Scenario B)
-->
<domain type='kvm'>
  <name>__VM_NAME__</name>
  <uuid>__UUID__</uuid>
  <memory unit='KiB'>__MEMORY_KB__</memory>
  <currentMemory unit='KiB'>__MEMORY_KB__</currentMemory>
  <vcpu placement='static'>__VCPU__</vcpu>
  <os>
    <type arch='x86_64' machine='pc-q35-9.0'>hvm</type>
    <loader readonly='yes' secure='yes' type='pflash'>
      /usr/share/OVMF/OVMF_CODE_4M.ms.fd
    </loader>
    <nvram template='/usr/share/OVMF/OVMF_VARS_4M.ms.fd'>
      /var/lib/libvirt/qemu/nvram/__VM_NAME___VARS.fd
    </nvram>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <smm state='on'/>
    <hyperv mode='custom'>
      <relaxed state='on'/>
      <vapic state='on'/>
      <spinlocks state='on' retries='8191'/>
    </hyperv>
  </features>
  <cpu mode='host-passthrough' check='none' migratable='on'/>
  <clock offset='localtime'>
    <timer name='rtc' tickpolicy='catchup'/>
    <timer name='pit' tickpolicy='delay'/>
    <timer name='hpet' present='no'/>
    <timer name='hypervclock' present='yes'/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>

    <!-- Overlay 디스크 (backing file = golden) -->
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2' cache='none' discard='unmap'/>
      <source file='/var/lib/libvirt/images/__VM_NAME__.qcow2'/>
      <target dev='vda' bus='virtio'/>
      <address type='pci' domain='0x0000' bus='0x05' slot='0x00' function='0x0'/>
    </disk>

    <!-- 네트워크 (인스턴스별 신규 MAC) -->
    <interface type='network'>
      <mac address='__MAC__'/>
      <source network='default'/>
      <model type='virtio'/>
      <address type='pci' domain='0x0000' bus='0x02' slot='0x00' function='0x0'/>
    </interface>

    <!-- vTPM (인스턴스별 신규 EK) -->
    <tpm model='tpm-crb'>
      <backend type='emulator' version='2.0'/>
    </tpm>

    <!-- 그래픽 -->
    <graphics type='spice' autoport='yes' listen='127.0.0.1'>
      <listen type='address' address='127.0.0.1'/>
      <image compression='off'/>
    </graphics>
    <video>
      <model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/>
    </video>

    <!-- 입력 -->
    <input type='tablet' bus='usb'/>
    <input type='mouse' bus='ps2'/>
    <input type='keyboard' bus='ps2'/>

    <!-- USB / 컨트롤러 -->
    <controller type='usb' index='0' model='qemu-xhci' ports='15'/>
    <controller type='pci' index='0' model='pcie-root'/>
    <controller type='pci' index='1' model='pcie-root-port'/>
    <controller type='pci' index='2' model='pcie-root-port'/>
    <controller type='pci' index='3' model='pcie-root-port'/>
    <controller type='pci' index='4' model='pcie-root-port'/>
    <controller type='pci' index='5' model='pcie-root-port'/>
    <controller type='pci' index='6' model='pcie-root-port'/>

    <!-- 가상 시리얼 (콘솔) -->
    <serial type='pty'>
      <target type='isa-serial' port='0'>
        <model name='isa-serial'/>
      </target>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>

    <!-- 오디오 -->
    <sound model='ich9'/>
    <audio id='1' type='spice'/>

    <!-- RNG (Windows random 향상) -->
    <rng model='virtio'>
      <backend model='random'>/dev/urandom</backend>
    </rng>

    <!-- Memballoon -->
    <memballoon model='virtio'/>
  </devices>
</domain>
