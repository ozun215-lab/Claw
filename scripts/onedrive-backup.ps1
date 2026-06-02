param(
  [string]$Source = 'D:\Claw\workspace',
  [string]$DestinationRoot = $null,
  [string[]]$ExcludeDirs = @('.git','node_modules','dist','build','coverage','.next','.cache','tmp','temp','out','bin','obj'),
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-OneDriveRoot {
  $candidates = @(
    $env:OneDriveCommercial,
    $env:OneDrive,
    $env:OneDriveConsumer
  ) | Where-Object { $_ -and $_.Trim() -ne '' }

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }

  throw 'OneDrive 경로를 찾지 못했습니다. OneDrive가 로그인되어 있는지 확인하세요.'
}

if (-not (Test-Path -LiteralPath $Source)) {
  throw "원본 workspace를 찾지 못했습니다: $Source"
}

if (-not $DestinationRoot) {
  $DestinationRoot = Join-Path (Resolve-OneDriveRoot) 'Claw-backups'
}

$timestamp = Get-Date -Format 'yyyy-MM-dd'
$destination = Join-Path $DestinationRoot $timestamp
$logRoot = Join-Path $DestinationRoot 'logs'
$logFile = Join-Path $logRoot ("backup-$timestamp.log")

New-Item -ItemType Directory -Force -Path $destination | Out-Null
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$robocopyArgs = @(
  $Source,
  $destination,
  '/E',
  '/R:2',
  '/W:2',
  '/COPY:DAT',
  '/DCOPY:DAT',
  '/XJ',
  '/FFT',
  '/NP',
  "/LOG+:$logFile"
)

foreach ($dir in $ExcludeDirs) {
  $robocopyArgs += @('/XD', (Join-Path $Source $dir))
}

Write-Host "Source      : $Source"
Write-Host "Destination : $destination"
Write-Host "Log         : $logFile"

if ($DryRun) {
  Write-Host 'DryRun enabled. robocopy는 실행하지 않습니다.'
  exit 0
}

& robocopy @robocopyArgs | Out-Host
$code = $LASTEXITCODE

# Robocopy exit codes 0-7 are success/info, 8+ are failure.
if ($code -ge 8) {
  throw "Robocopy failed with exit code $code"
}

Write-Host "백업 완료. Robocopy exit code: $code"
