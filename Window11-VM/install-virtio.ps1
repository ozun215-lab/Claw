#Requires -RunAsAdministrator
<#
.SYNOPSIS
    virtio-win 드라이버 전체 자동 설치 스크립트
.DESCRIPTION
    QEMU/KVM Windows 11 VM에 필요한 모든 virtio 드라이버를 자동 설치합니다.
    autounattend.xml의 FirstLogonCommands에서 자동 호출되거나 수동 실행 가능.
.PARAMETER VirtioPath
    virtio-win ISO 마운트 경로 (기본값: D:\)
.PARAMETER Force
    이미 설치된 드라이버도 강제 재설치
.PARAMETER Reboot
    설치 완료 후 자동 재부팅
.EXAMPLE
    .\install-virtio.ps1 -VirtioPath "E:\" -Reboot
#>

param(
    [string]$VirtioPath = "D:\",
    [switch]$Force,
    [switch]$Reboot
)

# ── 설정 ──────────────────────────────────────────────
$OS_VERSION = "w11"
$ARCH       = "amd64"
$LOG_FILE   = "$env:TEMP\virtio-install.log"
# ───────────────────────────────────────────────────────

# ── 출력 함수 ─────────────────────────────────────────
function Write-Step { param($msg) Write-Host "`n[>>] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "     [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "     [!!] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "     [XX] $msg" -ForegroundColor Red }
function Write-Log  { param($msg) Add-Content $LOG_FILE "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $msg" }

# ── 드라이버 INF 설치 함수 ────────────────────────────
function Install-VirtioDriver {
    param(
        [string]$Name,
        [string]$InfPath
    )
    if (-not (Test-Path $InfPath)) {
        Write-Warn "$Name — INF 없음, 건너뜀: $InfPath"
        Write-Log "SKIP $Name — $InfPath"
        return
    }
    Write-Host "     설치 중: $Name ..." -NoNewline
    $result = & pnputil /add-driver "$InfPath" /install 2>&1
    $exit   = $LASTEXITCODE
    if ($exit -eq 0 -or $exit -eq 3010) {
        Write-Host " 완료" -ForegroundColor Green
        Write-Log "OK   $Name"
    } else {
        Write-Host " 실패 (exit: $exit)" -ForegroundColor Red
        Write-Log "FAIL $Name — exit:$exit — $result"
    }
}

# ── MSI 설치 함수 ─────────────────────────────────────
function Install-VirtioMSI {
    param(
        [string]$Name,
        [string]$MsiPath,
        [string]$ExtraArgs = "/quiet /norestart"
    )
    if (-not (Test-Path $MsiPath)) {
        Write-Warn "$Name — MSI 없음, 건너뜀: $MsiPath"
        return
    }
    Write-Host "     설치 중: $Name ..." -NoNewline
    $proc = Start-Process msiexec `
        -ArgumentList "/i `"$MsiPath`" $ExtraArgs" `
        -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
        Write-Host " 완료" -ForegroundColor Green
        Write-Log "OK   $Name (MSI)"
    } else {
        Write-Host " 실패 (exit: $($proc.ExitCode))" -ForegroundColor Red
        Write-Log "FAIL $Name (MSI) — exit:$($proc.ExitCode)"
    }
}

# ══════════════════════════════════════════════════════
#  메인 실행
# ══════════════════════════════════════════════════════

Clear-Host
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   virtio-win 드라이버 자동 설치 스크립트      ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host "  경로: $VirtioPath | OS: $OS_VERSION | ARCH: $ARCH"
Write-Log "=== 설치 시작 === 경로:$VirtioPath OS:$OS_VERSION ARCH:$ARCH"

# virtio ISO 마운트 확인
$checkPath = "${VirtioPath}viostor\${OS_VERSION}\${ARCH}\viostor.inf"
if (-not (Test-Path $checkPath)) {
    Write-Host ""
    Write-Fail "virtio-win ISO가 마운트되지 않았습니다."
    Write-Host "  확인 경로: $checkPath"
    Write-Host "  -VirtioPath 매개변수로 드라이브 문자를 지정하세요."
    Write-Host "  예: .\install-virtio.ps1 -VirtioPath 'E:\'"
    exit 1
}

# ── 스토리지 드라이버 ──────────────────────────────────
Write-Step "스토리지 드라이버"
Install-VirtioDriver "viostor (virtio SCSI)" `
    "${VirtioPath}viostor\${OS_VERSION}\${ARCH}\viostor.inf"
Install-VirtioDriver "vioscsi (SCSI passthrough)" `
    "${VirtioPath}vioscsi\${OS_VERSION}\${ARCH}\vioscsi.inf"
Install-VirtioDriver "vioblk (Block)" `
    "${VirtioPath}vioblk\${OS_VERSION}\${ARCH}\vioblk.inf"

# ── 네트워크 드라이버 ─────────────────────────────────
Write-Step "네트워크 드라이버"
Install-VirtioDriver "NetKVM (virtio-net)" `
    "${VirtioPath}NetKVM\${OS_VERSION}\${ARCH}\netkvm.inf"

# ── 메모리 드라이버 ───────────────────────────────────
Write-Step "메모리 드라이버"
Install-VirtioDriver "Balloon (메모리 벌룬)" `
    "${VirtioPath}Balloon\${OS_VERSION}\${ARCH}\balloon.inf"
Install-VirtioDriver "viopmem (Persistent Memory)" `
    "${VirtioPath}viopmem\${OS_VERSION}\${ARCH}\viopmem.inf"

# ── 직렬 드라이버 ─────────────────────────────────────
Write-Step "직렬/시리얼 드라이버"
Install-VirtioDriver "vioserial (virtio-serial)" `
    "${VirtioPath}vioserial\${OS_VERSION}\${ARCH}\vioser.inf"

# ── 입력 드라이버 ─────────────────────────────────────
Write-Step "입력 장치 드라이버"
Install-VirtioDriver "vioinput (Mouse/Keyboard)" `
    "${VirtioPath}vioinput\${OS_VERSION}\${ARCH}\vioinput.inf"

# ── 그래픽 드라이버 ───────────────────────────────────
Write-Step "그래픽 드라이버"
Install-VirtioDriver "viogpudo (virtio Display)" `
    "${VirtioPath}viogpudo\${OS_VERSION}\${ARCH}\viogpudo.inf"
Install-VirtioDriver "qxldod (QXL Display)" `
    "${VirtioPath}qxldod\${OS_VERSION}\${ARCH}\qxldod.inf"

# ── 기타 드라이버 ─────────────────────────────────────
Write-Step "기타 드라이버"
Install-VirtioDriver "pvpanic (패닉 장치)" `
    "${VirtioPath}pvpanic\${OS_VERSION}\${ARCH}\pvpanic.inf"
Install-VirtioDriver "fwcfg (펌웨어 설정)" `
    "${VirtioPath}fwcfg\${OS_VERSION}\${ARCH}\fwcfg.inf"
Install-VirtioDriver "qemupciserial" `
    "${VirtioPath}qemupciserial\${OS_VERSION}\${ARCH}\qemupciserial.inf"

# ── QEMU Guest Agent MSI ──────────────────────────────
Write-Step "QEMU Guest Agent"
Install-VirtioMSI "QEMU Guest Agent" `
    "${VirtioPath}guest-agent\qemu-ga-x86_64.msi"

# ── virtio-win-gt 통합 패키지 (선택) ─────────────────
Write-Step "virtio-win GT 통합 패키지 (선택사항)"
$virtioMsi = "${VirtioPath}virtio-win-gt-x64.msi"
if (Test-Path $virtioMsi) {
    $choice = Read-Host "  virtio-win-gt-x64.msi도 설치하시겠습니까? (y/N)"
    if ($choice -match '^[Yy]') {
        Install-VirtioMSI "virtio-win-gt-x64" $virtioMsi
    }
} else {
    Write-Warn "virtio-win-gt-x64.msi 없음 (선택사항)"
}

# ── SPICE Guest Tools (선택) ──────────────────────────
Write-Step "SPICE Guest Tools (선택사항)"
$spiceExe = Get-Item "${VirtioPath}spice-guest-tools\spice-guest-tools*.exe" `
    -ErrorAction SilentlyContinue | Select-Object -First 1
if ($spiceExe) {
    Write-Host "     설치 중: SPICE Guest Tools ..." -NoNewline
    $proc = Start-Process $spiceExe.FullName -ArgumentList "/S" -Wait -PassThru
    if ($proc.ExitCode -eq 0) {
        Write-Host " 완료" -ForegroundColor Green
    } else {
        Write-Host " 실패" -ForegroundColor Red
    }
} else {
    Write-Warn "SPICE Guest Tools 없음 (선택사항)"
}

# ── 설치 결과 확인 ────────────────────────────────────
Write-Step "설치된 virtio 드라이버 목록"
Get-WmiObject Win32_PnPSignedDriver |
    Where-Object { $_.DeviceName -match "VirtIO|QEMU|Red Hat" } |
    Select-Object DeviceName, DriverVersion, Manufacturer |
    Format-Table -AutoSize

# 오류 장치 확인
$errorDevices = Get-WmiObject Win32_PnPEntity |
    Where-Object { $_.ConfigManagerErrorCode -ne 0 }
if ($errorDevices) {
    Write-Warn "오류 장치 감지됨:"
    $errorDevices | Select-Object Name, ConfigManagerErrorCode | Format-Table -AutoSize
}

Write-Host ""
Write-Host "  로그 파일: $LOG_FILE" -ForegroundColor Gray
Write-Log "=== 설치 완료 ==="

# ── 재부팅 처리 ───────────────────────────────────────
if ($Reboot) {
    Write-Host ""
    Write-Host "  10초 후 자동 재부팅..." -ForegroundColor Yellow
    Start-Sleep 10
    Restart-Computer -Force
} else {
    Write-Host ""
    $r = Read-Host "  재부팅이 필요할 수 있습니다. 지금 재부팅하시겠습니까? (y/N)"
    if ($r -match '^[Yy]') {
        Restart-Computer -Force
    }
}
