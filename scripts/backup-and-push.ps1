param(
  [string]$CommitMessage = $null,
  [switch]$SkipBackup,
  [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$git = 'C:\Program Files\Git\cmd\git.exe'
$ssh = 'C:\Program Files\Git\usr\bin\ssh.exe'
$backupScript = 'D:\Claw\workspace\scripts\onedrive-backup.ps1'
$repoRoot = 'D:\Claw\workspace'

if (-not (Test-Path -LiteralPath $git)) { throw "Git 실행 파일을 찾지 못했습니다: $git" }
if (-not (Test-Path -LiteralPath $ssh)) { throw "SSH 실행 파일을 찾지 못했습니다: $ssh" }
if (-not (Test-Path -LiteralPath $repoRoot)) { throw "작업공간을 찾지 못했습니다: $repoRoot" }

Push-Location $repoRoot
try {
  if (-not $SkipBackup) {
    if (-not (Test-Path -LiteralPath $backupScript)) {
      throw "백업 스크립트를 찾지 못했습니다: $backupScript"
    }
    Write-Host '== OneDrive backup =='
    & 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File $backupScript
  }

  Write-Host '== Git status =='
  & $git status --short

  $status = & $git status --porcelain
  if ($status) {
    Write-Host '== Git add / commit =='
    & $git add -A

    if (-not $CommitMessage) {
      $CommitMessage = 'Sync workspace'
    }

    & $git commit -m $CommitMessage
  }
  else {
    Write-Host 'No Git changes to commit.'
  }

  if (-not $SkipPush) {
    Write-Host '== Git push =='
    $env:GIT_SSH_COMMAND = '"C:/Program Files/Git/usr/bin/ssh.exe"'
    & $git push
  }
}
finally {
  Pop-Location
}
