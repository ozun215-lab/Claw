param(
  [string]$ScriptPath = 'D:\Claw\workspace\scripts\backup-and-push.ps1',
  [string]$TaskName = 'Claw Backup And Push',
  [string]$Time = '18:00'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $ScriptPath)) {
  throw "루틴 스크립트를 찾지 못했습니다: $ScriptPath"
}

$psExe = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $psExe)) {
  throw "PowerShell 실행 파일을 찾지 못했습니다: $psExe"
}

$argument = "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

cmd /c "schtasks /Delete /TN \"$TaskName\" /F >nul 2>&1"
schtasks.exe /Create /F /SC DAILY /ST $Time /TN $TaskName /TR "`"$psExe`" $argument" | Out-Host

Write-Host "작업 스케줄러 등록 완료: $TaskName"
Write-Host "실행 시간: $Time"
Write-Host "스크립트: $ScriptPath"
