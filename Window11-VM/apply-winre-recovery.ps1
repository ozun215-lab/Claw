#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Create a recovery partition at the end of C: and register an existing winre.wim.
.PARAMETER WinReWimPath
    Path to an already extracted winre.wim file.
.PARAMETER RecoverySizeMB
    Size of the recovery partition in MB. Default: 1024.
.PARAMETER DriveLetter
    Temporary drive letter for the recovery partition. Default: R
.PARAMETER ShrinkOSDrive
    Shrink C: to make room at the end of the disk if necessary.
.PARAMETER Force
    Skip the confirmation prompt.
.EXAMPLE
    .\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim -ShrinkOSDrive
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateScript({ Test-Path $_ })]
    [string]$WinReWimPath,
    [ValidateRange(512,4096)]
    [int]$RecoverySizeMB = 1024,
    [ValidatePattern('^[A-Z]$')]
    [string]$DriveLetter = 'R',
    [switch]$ShrinkOSDrive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$RecoveryGuid = 'de94bba4-06d1-4d40-a16a-bfd50179d6ac'
$RecoveryAttr = '0x8000000000000001'

function Write-Step   { param([string]$M); Write-Host "`n=== $M ===" -ForegroundColor Cyan }
function Write-OK     { param([string]$M); Write-Host "[OK] $M"  -ForegroundColor Green }
function Write-Warn   { param([string]$M); Write-Host "[!]  $M"  -ForegroundColor Yellow }

function Assert-Admin {
    $id  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pri = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pri.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '관리자 권한으로 실행해야 합니다.'
    }
}

function Confirm-Action {
    if ($Force) { return }
    Write-Host ''
    Write-Warn '이 작업은 디스크 파티션을 변경합니다.'
    $ans = Read-Host '계속하려면 YES를 입력하세요'
    if ($ans -ne 'YES') { throw '사용자 취소.' }
}

function Test-RecoveryExists {
    $found = Get-Partition -ErrorAction SilentlyContinue |
             Where-Object { $_.GptType -match $RecoveryGuid }
    return [bool]$found
}

function Ensure-FreeSpaceAtEnd {
    param([int]$NeededMB)
    $part    = Get-Partition -DriveLetter C -ErrorAction Stop
    $support = Get-PartitionSupportedSize -DriveLetter C
    $cur     = $part.Size
    $target  = $cur - ($NeededMB * 1MB)
    if ($target -lt $support.SizeMin) {
        throw ('C: 를 {0}MB 줄일 수 없습니다. (현재:{1}MB / 최소:{2}MB)' -f
               $NeededMB, [math]::Round($cur/1MB), [math]::Round($support.SizeMin/1MB))
    }
    if ($ShrinkOSDrive) {
        Write-Warn ('C: 마지막 부분에서 {0}MB 확보합니다...' -f $NeededMB)
        Resize-Partition -DriveLetter C -Size $target
        Write-OK 'C: 축소 완료'
    } else {
        Write-Warn '-ShrinkOSDrive 없이 실행 중 — 디스크 끝에 충분한 여유가 있는지 확인하세요.'
    }
}

function Invoke-Diskpart {
    param([string[]]$Lines, [string]$Tag)
    $tmp = Join-Path $env:TEMP ('diskpart-{0}-{1}.txt' -f $Tag, [Guid]::NewGuid().ToString('N'))
    $Lines | Set-Content -Path $tmp -Encoding ASCII
    diskpart /s $tmp | Out-Host
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}

Assert-Admin

$WinReWimPath = (Resolve-Path $WinReWimPath).Path
$TargetRoot   = 'C:\Windows'
$RecVol       = $DriveLetter + ':'

Write-Step 'Input'
Write-Host "WinRE      : $WinReWimPath"
Write-Host "Size       : $RecoverySizeMB MB"
Write-Host "Letter     : $DriveLetter"
Write-Host "ShrinkOS   : $ShrinkOSDrive"

if (Test-RecoveryExists) {
    throw '복구 파티션이 이미 존재합니다. 먼저 제거한 뒤 재실행하세요.'
}

Confirm-Action

Write-Step 'Disable WinRE'
reagentc /disable | Out-Host

Write-Step 'System disk'
$diskNum = (Get-Partition -DriveLetter C -ErrorAction Stop).DiskNumber
Write-OK "Disk #$diskNum"

Write-Step 'Space check'
Ensure-FreeSpaceAtEnd -NeededMB $RecoverySizeMB

Write-Step 'Create recovery partition'
Invoke-Diskpart -Tag 'create' -Lines @(
    "select disk $diskNum",
    "create partition primary size=$RecoverySizeMB",
    "format quick fs=ntfs label=Recovery",
    "assign letter=$DriveLetter",
    "set id=$RecoveryGuid",
    "gpt attributes=$RecoveryAttr",
    "exit"
)

Write-Step 'Copy winre.wim'
New-Item -ItemType Directory -Path "$RecVol\Recovery\WindowsRE" -Force | Out-Null
Copy-Item -Path $WinReWimPath -Destination "$RecVol\Recovery\WindowsRE\winre.wim" -Force
Write-OK "복사 완료: $RecVol\Recovery\WindowsRE\winre.wim"

Write-Step 'Register WinRE'
reagentc /setreimage /path "$RecVol\Recovery\WindowsRE" /target $TargetRoot | Out-Host
reagentc /enable | Out-Host
reagentc /info   | Out-Host

Write-Step 'Hide drive letter'
Invoke-Diskpart -Tag 'remove' -Lines @(
    "select volume $DriveLetter",
    "remove letter=$DriveLetter",
    "exit"
)

Write-Step 'Done'
Write-OK '복구 파티션 생성 및 WinRE 등록이 완료되었습니다.'