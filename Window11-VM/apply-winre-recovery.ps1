#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Create a Windows recovery partition at the end of C: and register an existing winre.wim.
.DESCRIPTION
    This script assumes winre.wim has already been extracted.
    It will optionally shrink C: to make room at the end of the disk, create a GPT recovery partition,
    copy winre.wim, set the WinRE image path, enable WinRE, and hide the recovery drive letter.

    Safety features:
      - Confirms before making changes unless -Force is used
      - Refuses to proceed if a recovery partition already exists
      - Verifies the system disk and available shrink room before resizing C:
.PARAMETER WinReWimPath
    Path to an already extracted winre.wim file.
.PARAMETER RecoverySizeMB
    Size of the recovery partition in MB. Default: 1024.
.PARAMETER DriveLetter
    Temporary drive letter used for the recovery partition while copying files. Default: R
.PARAMETER ShrinkOSDrive
    If set, the script shrinks the C: partition to make room at the end of the disk if necessary.
.PARAMETER Force
    Skip the confirmation prompt.
.EXAMPLE
    .\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim -ShrinkOSDrive
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path $_ })]
    [string]$WinReWimPath,

    [ValidateRange(512, 4096)]
    [int]$RecoverySizeMB = 1024,

    [ValidatePattern('^[A-Z]$')]
    [string]$DriveLetter = 'R',

    [switch]$ShrinkOSDrive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$RecoveryGuid = 'de94bba4-06d1-4d40-a16a-bfd50179d6ac'
$RecoveryAttr = '0x8000000000000001'

function Write-Step {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Cyan
}

function Write-OK {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '관리자 권한으로 실행해야 합니다.'
    }
}

function Get-SystemDiskNumber {
    $cPart = Get-Partition -DriveLetter C -ErrorAction Stop
    return $cPart.DiskNumber
}

function Confirm-Action {
    if ($Force) { return }
    Write-Host ""
    Write-Warn "이 작업은 디스크 파티션을 변경합니다."
    $answer = Read-Host "계속하려면 YES를 입력하세요"
    if ($answer -ne 'YES') {
        throw '사용자 취소.'
    }
}

function Test-RecoveryPartitionExists {
    $existing = Get-Partition -ErrorAction SilentlyContinue | Where-Object {
        $_.GptType -eq "{$RecoveryGuid}" -or $_.GptType -eq $RecoveryGuid
    }
    return [bool]$existing
}

function Ensure-FreeSpaceAtEnd {
    param(
        [int]$DiskNumber,
        [int]$NeededMB
    )

    $cPart = Get-Partition -DriveLetter C -ErrorAction Stop
    $supported = Get-PartitionSupportedSize -DriveLetter C
    $currentSize = $cPart.Size
    $minSize = $supported.SizeMin
    $targetSize = $currentSize - ($NeededMB * 1MB)

    if ($targetSize -lt $minSize) {
        throw ("C:를 {0}MB 만큼 줄일 수 없습니다. 최소 허용 크기보다 작아집니다. (현재: {1}MB, 최소: {2}MB)" -f $NeededMB, [math]::Round($currentSize/1MB), [math]::Round($minSize/1MB))
    }

    if ($currentSize -eq $supported.SizeMax) {
        Write-Warn "C:가 이미 최대 크기입니다. 필요하면 줄입니다."
    }

    if ($ShrinkOSDrive) {
        Write-Warn ("C:의 마지막 부분에서 약 {0}MB를 확보합니다..." -f $NeededMB)
        Resize-Partition -DriveLetter C -Size $targetSize
        Write-OK "C: resized to make room at the end of the disk."
    }
    else {
        Write-Warn "추가 여유 공간이 필요할 수 있습니다. -ShrinkOSDrive를 사용하면 C:를 줄여 자동으로 공간을 만듭니다."
    }
}

function Create-RecoveryPartition {
    param(
        [int]$DiskNumber,
        [int]$SizeMB,
        [string]$Letter
    )

    $dp = @"
select disk $DiskNumber
create partition primary size=$SizeMB
format quick fs=ntfs label="Recovery"
assign letter=$Letter
set id=$RecoveryGuid
gpt attributes=$RecoveryAttr
exit
"@

    $tmp = Join-Path $env:TEMP "create-recovery-$DiskNumber.txt"
    Set-Content -Path $tmp -Value $dp -Encoding ASCII
    diskpart /s $tmp | Out-Host
}

function Remove-DriveLetter {
    param([string]$Letter)

    $dp = @"
select volume $Letter
remove letter=$Letter
exit
"@

    $tmp = Join-Path $env:TEMP "remove-letter-$Letter.txt"
    Set-Content -Path $tmp -Value $dp -Encoding ASCII
    diskpart /s $tmp | Out-Host
}

Assert-Admin
$WinReWimPath = (Resolve-Path $WinReWimPath).Path
$TargetRoot = 'C:\Windows'
$RecoveryVolume = "$DriveLetter:`"

Write-Step 'Input'
Write-Host "WinRE source : $WinReWimPath"
Write-Host "Recovery size: $RecoverySizeMB MB"
Write-Host "Drive letter : $DriveLetter"
Write-Host "Shrink C:    : $ShrinkOSDrive"

if (Test-RecoveryPartitionExists) {
    throw '이미 복구 파티션이 존재합니다. 기존 파티션을 제거한 뒤 다시 시도하세요.'
}

Confirm-Action

Write-Step 'Disable WinRE'
reagentc /disable | Out-Host

Write-Step 'Detect system disk'
$diskNumber = Get-SystemDiskNumber
Write-OK "System disk number: $diskNumber"

Write-Step 'Make sure space exists'
Ensure-FreeSpaceAtEnd -DiskNumber $diskNumber -NeededMB $RecoverySizeMB

Write-Step 'Create recovery partition at the end of C:'
Create-RecoveryPartition -DiskNumber $diskNumber -SizeMB $RecoverySizeMB -Letter $DriveLetter

Write-Step 'Prepare WinRE folder'
New-Item -ItemType Directory -Path "$RecoveryVolume\Recovery\WindowsRE" -Force | Out-Null
Copy-Item -Path $WinReWimPath -Destination "$RecoveryVolume\Recovery\WindowsRE\winre.wim" -Force
Write-OK "Copied winre.wim to $RecoveryVolume\Recovery\WindowsRE\winre.wim (C: 뒤쪽 복구 파티션)"

Write-Step 'Register WinRE'
reagentc /setreimage /path "$RecoveryVolume\Recovery\WindowsRE" /target $TargetRoot | Out-Host
reagentc /enable | Out-Host
reagentc /info | Out-Host

Write-Step 'Hide recovery drive letter'
Remove-DriveLetter -Letter $DriveLetter

Write-Step 'Done'
Write-OK 'Recovery partition created and WinRE registered.'
