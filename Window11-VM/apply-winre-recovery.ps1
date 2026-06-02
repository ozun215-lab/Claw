#Requires -RunAsAdministrator
<#!
.SYNOPSIS
    Create a Windows recovery partition and register an existing winre.wim.
.DESCRIPTION
    This script assumes winre.wim has already been extracted.
    It will optionally shrink C:, create a GPT recovery partition, copy winre.wim,
    set the WinRE image path, enable WinRE, and hide the recovery drive letter.

    Recommended to run on the target Windows installation in an elevated PowerShell.
.PARAMETER WinReWimPath
    Path to an already extracted winre.wim file.
.PARAMETER RecoverySizeMB
    Size of the recovery partition in MB. Default: 1024.
.PARAMETER DriveLetter
    Temporary drive letter used for the recovery partition while copying files. Default: R
.PARAMETER ShrinkOSDrive
    If set, the script shrinks the C: partition to make room if necessary.
.EXAMPLE
    .\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim -ShrinkOSDrive
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path $_ })]
    [string]$WinReWimPath,

    [int]$RecoverySizeMB = 1024,

    [ValidatePattern('^[A-Z]$')]
    [string]$DriveLetter = 'R',

    [switch]$ShrinkOSDrive
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

function Ensure-FreeSpace {
    param(
        [int]$DiskNumber,
        [int]$NeededMB
    )

    $disk = Get-Disk -Number $DiskNumber
    $unallocatedMB = [math]::Round(($disk.Size - ($disk.AllocatedSize ?? 0)) / 1MB)

    if ($unallocatedMB -ge $NeededMB) {
        Write-OK "Enough unallocated space already available: $unallocatedMB MB"
        return
    }

    if (-not $ShrinkOSDrive) {
        throw "Not enough unallocated space ($unallocatedMB MB). Re-run with -ShrinkOSDrive to shrink C:."
    }

    Write-Warn "Shrinking C: to free about $NeededMB MB..."
    $supported = Get-PartitionSupportedSize -DriveLetter C
    $current = (Get-Partition -DriveLetter C).Size
    $target = $current - ($NeededMB * 1MB)

    if ($target -lt $supported.SizeMin) {
        throw "Cannot shrink C: enough. Supported minimum is too large."
    }

    Resize-Partition -DriveLetter C -Size $target
    Write-OK "C: resized."
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

Write-Step 'Disable WinRE'
reagentc /disable | Out-Host

Write-Step 'Detect system disk'
$diskNumber = Get-SystemDiskNumber
Write-OK "System disk number: $diskNumber"

Write-Step 'Make sure space exists'
Ensure-FreeSpace -DiskNumber $diskNumber -NeededMB $RecoverySizeMB

Write-Step 'Create recovery partition'
Create-RecoveryPartition -DiskNumber $diskNumber -SizeMB $RecoverySizeMB -Letter $DriveLetter

Write-Step 'Prepare WinRE folder'
New-Item -ItemType Directory -Path "$RecoveryVolume\Recovery\WindowsRE" -Force | Out-Null
Copy-Item -Path $WinReWimPath -Destination "$RecoveryVolume\Recovery\WindowsRE\winre.wim" -Force
Write-OK "Copied winre.wim to $RecoveryVolume\Recovery\WindowsRE\winre.wim"

Write-Step 'Register WinRE'
reagentc /setreimage /path "$RecoveryVolume\Recovery\WindowsRE" /target $TargetRoot | Out-Host
reagentc /enable | Out-Host
reagentc /info | Out-Host

Write-Step 'Hide recovery drive letter'
Remove-DriveLetter -Letter $DriveLetter

Write-Step 'Done'
Write-OK 'Recovery partition created and WinRE registered.'
