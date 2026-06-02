#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windows 11 VM 설치 후 검증 스크립트
.DESCRIPTION
    파티션 레이아웃, WinRE 상태, virtio 드라이버,
    QEMU Guest Agent, 오류 장치를 한 번에 확인합니다.
.EXAMPLE
    .\post-install.ps1
#>

# ── 출력 함수 ─────────────────────────────────────────
function Write-Section {
    param($title)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
}

function Write-OK   { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "  [XX] $msg" -ForegroundColor Red }

# ══════════════════════════════════════════════════════
#  헤더
# ══════════════════════════════════════════════════════
Clear-Host
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   Windows 11 VM 설치 후 검증 스크립트         ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host "  실행 시각: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# ══════════════════════════════════════════════════════
#  1. 파티션 레이아웃 확인
# ══════════════════════════════════════════════════════
Write-Section "1. 파티션 레이아웃"

Get-Partition |
    Select-Object DiskNumber, PartitionNumber,
        @{N="유형";       E={ $_.Type }},
        @{N="크기(MB)";   E={ [math]::Round($_.Size / 1MB) }},
        @{N="드라이브";   E={ $_.DriveLetter }},
        @{N="GPT Type";   E={ $_.GptType }} |
    Format-Table -AutoSize

# 예상 레이아웃 확인
$recovery = Get-Partition | Where-Object {
    $_.GptType -eq "{de94bba4-06d1-4d40-a16a-bfd50179d6ac}"
}
$windows = Get-Partition | Where-Object { $_.DriveLetter -eq "C" }
$efi     = Get-Partition | Where-Object { $_.Type -eq "System" }

if ($recovery) {
    Write-OK "복구 파티션 감지됨 (파티션 #$($recovery.PartitionNumber))"
    if ($windows -and ($recovery.PartitionNumber -lt $windows.PartitionNumber)) {
        Write-OK "레이아웃 정상: EFI → Recovery → C: (커스텀 순서)"
    } else {
        Write-Warn "레이아웃 주의: Recovery가 C: 뒤에 있습니다 (일반 배치)"
    }
} else {
    Write-Fail "복구 파티션을 찾을 수 없습니다."
    Write-Host "  GUID: {de94bba4-06d1-4d40-a16a-bfd50179d6ac}"
}

# ══════════════════════════════════════════════════════
#  2. WinRE (Windows Recovery Environment) 상태
# ══════════════════════════════════════════════════════
Write-Section "2. WinRE (Windows Recovery Environment)"

$reagentOutput = & reagentc /info 2>&1
$reagentOutput | ForEach-Object { Write-Host "  $_" }

$isEnabled = $reagentOutput | Select-String "사용|Enabled"
if ($isEnabled) {
    Write-OK "WinRE 활성화됨"
} else {
    Write-Warn "WinRE 비활성화 상태. 활성화 시도..."
    $enableResult = & reagentc /enable 2>&1
    $enableResult | ForEach-Object { Write-Host "  $_" }

    $recheck = & reagentc /info 2>&1
    if ($recheck | Select-String "사용|Enabled") {
        Write-OK "WinRE 활성화 성공"
    } else {
        Write-Fail "WinRE 활성화 실패. 수동으로 확인이 필요합니다."
    }
}

# ══════════════════════════════════════════════════════
#  3. virtio 드라이버 확인
# ══════════════════════════════════════════════════════
Write-Section "3. virtio 드라이버"

$virtioDrivers = Get-WmiObject Win32_PnPSignedDriver |
    Where-Object { $_.Manufacturer -match "Red Hat|VirtIO" }

if ($virtioDrivers) {
    $virtioDrivers |
        Select-Object DeviceName, DriverVersion, Manufacturer |
        Format-Table -AutoSize
    Write-OK "virtio 드라이버 $($virtioDrivers.Count)개 설치됨"
} else {
    Write-Fail "virtio 드라이버가 설치되지 않았습니다."
    Write-Host "  install-virtio.ps1 또는 post-install.bat을 실행하세요."
}

# 핵심 드라이버 개별 확인
$keyDrivers = @{
    "viostor (SCSI)"  = "VirtIO SCSI"
    "NetKVM (Network)"= "VirtIO Ethernet"
    "Balloon (Memory)"= "VirtIO Balloon"
}
Write-Host ""
foreach ($key in $keyDrivers.Keys) {
    $found = Get-WmiObject Win32_PnPSignedDriver |
        Where-Object { $_.DeviceName -match $keyDrivers[$key] }
    if ($found) {
        Write-OK "$key — v$($found.DriverVersion)"
    } else {
        Write-Warn "$key — 미설치 또는 이름 불일치"
    }
}

# ══════════════════════════════════════════════════════
#  4. QEMU Guest Agent 서비스 확인
# ══════════════════════════════════════════════════════
Write-Section "4. QEMU Guest Agent"

$guestAgent = Get-Service -Name "QEMU-GA" -ErrorAction SilentlyContinue
if ($guestAgent) {
    if ($guestAgent.Status -eq "Running") {
        Write-OK "QEMU Guest Agent 실행 중 (상태: $($guestAgent.Status))"
    } else {
        Write-Warn "QEMU Guest Agent 설치됨, 미실행 (상태: $($guestAgent.Status))"
        Write-Host "  시작 시도..."
        Start-Service -Name "QEMU-GA" -ErrorAction SilentlyContinue
    }
} else {
    Write-Fail "QEMU Guest Agent 미설치"
    Write-Host "  install-virtio.ps1을 다시 실행하거나 MSI를 수동 설치하세요."
}

# ══════════════════════════════════════════════════════
#  5. 오류 장치 확인
# ══════════════════════════════════════════════════════
Write-Section "5. 장치 오류 확인"

$errorDevices = Get-WmiObject Win32_PnPEntity |
    Where-Object { $_.ConfigManagerErrorCode -ne 0 }

if ($errorDevices) {
    Write-Warn "오류 장치 $($errorDevices.Count)개 감지됨:"
    $errorDevices |
        Select-Object Name,
            @{N="오류코드"; E={ $_.ConfigManagerErrorCode }},
            @{N="상태";    E={ $_.Status }} |
        Format-Table -AutoSize
} else {
    Write-OK "장치 오류 없음"
}

# ══════════════════════════════════════════════════════
#  6. 시스템 정보 요약
# ══════════════════════════════════════════════════════
Write-Section "6. 시스템 정보"

$os  = Get-WmiObject Win32_OperatingSystem
$cpu = Get-WmiObject Win32_Processor | Select-Object -First 1
$mem = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)

Write-Host "  OS      : $($os.Caption) (빌드: $($os.BuildNumber))"
Write-Host "  CPU     : $($cpu.Name)"
Write-Host "  메모리  : ${mem} GB"
Write-Host "  호스트명: $env:COMPUTERNAME"
Write-Host "  사용자  : $env:USERNAME"

# TPM 확인
$tpm = Get-WmiObject -Namespace "root\cimv2\Security\MicrosoftTpm" -Class Win32_Tpm -ErrorAction SilentlyContinue
if ($tpm) {
    Write-OK "TPM 감지됨 (활성화: $($tpm.IsEnabled_InitialValue), 버전: $($tpm.SpecVersion))"
} else {
    Write-Warn "TPM 정보를 가져올 수 없습니다."
}

# Secure Boot 확인
try {
    $sb = Confirm-SecureBootUEFI -ErrorAction Stop
    if ($sb) { Write-OK "Secure Boot: 활성화" }
    else      { Write-Warn "Secure Boot: 비활성화" }
} catch {
    Write-Warn "Secure Boot 상태 확인 불가 (UEFI 환경 아닐 수 있음)"
}

# ══════════════════════════════════════════════════════
#  요약
# ══════════════════════════════════════════════════════
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  검증 완료: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
