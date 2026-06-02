#Requires -RunAsAdministrator
<#!
.SYNOPSIS
    Extract winre.wim from Windows installation media.
.DESCRIPTION
    Mounts install.wim or converts install.esd to WIM, then searches the mounted image
    for winre.wim and copies it to the output folder.
.PARAMETER SourceRoot
    Mounted Windows installation media drive or copied ISO folder.
.PARAMETER ImageIndex
    Image index inside install.wim/esd. Defaults to 1.
.PARAMETER OutputDir
    Folder where winre.wim will be saved.
.PARAMETER KeepTemp
    Keep temporary working files.
.EXAMPLE
    .\winre-extract.ps1 -SourceRoot F:\ -ImageIndex 6 -OutputDir C:\Temp\WinRE
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,

    [int]$ImageIndex = 1,

    [string]$OutputDir = (Join-Path $PWD "WinRE-Output"),

    [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=== {0} ===" -f $Title) -ForegroundColor Cyan
}

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator."
    }
}

function Invoke-LoggedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )
    Write-Host ("> {0} {1}" -f $FilePath, ($Arguments -join ' ')) -ForegroundColor DarkGray
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed: {0} (exit {1})" -f $FilePath, $LASTEXITCODE)
    }
}

function Get-FirstExistingPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

Assert-Admin

$SourceRoot = (Resolve-Path $SourceRoot).Path
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$TempRoot = Join-Path $env:TEMP ("winre_extract_" + [Guid]::NewGuid().ToString('N'))
$MountDir = Join-Path $TempRoot "mount"
$OutFile = Join-Path $OutputDir "winre.wim"
$ExportedWim = Join-Path $TempRoot "install.wim"

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
New-Item -ItemType Directory -Path $MountDir -Force | Out-Null

try {
    Write-Section "Input"
    Write-Host "SourceRoot : $SourceRoot"
    Write-Host "ImageIndex : $ImageIndex"
    Write-Host "OutputDir  : $OutputDir"

    $sourcesDir = Join-Path $SourceRoot 'sources'
    if (-not (Test-Path $sourcesDir)) {
        throw "sources folder not found: $sourcesDir"
    }

    $installWim = Join-Path $sourcesDir 'install.wim'
    $installEsd = Join-Path $sourcesDir 'install.esd'

    $workingImage = $null
    $cleanupExported = $false

    if (Test-Path $installWim) {
        $workingImage = $installWim
        Write-Host "Using install.wim: $workingImage"
    }
    elseif (Test-Path $installEsd) {
        Write-Host "install.wim not found, converting install.esd to WIM..." -ForegroundColor Yellow
        Invoke-LoggedCommand dism @(
            '/Export-Image',
            "/SourceImageFile:$installEsd",
            "/SourceIndex:$ImageIndex",
            "/DestinationImageFile:$ExportedWim",
            '/Compress:max',
            '/CheckIntegrity'
        )
        $workingImage = $ExportedWim
        $cleanupExported = $true
    }
    else {
        throw "Neither install.wim nor install.esd was found."
    }

    Write-Section "Mount image"
    Invoke-LoggedCommand dism @(
        '/Mount-Image',
        "/ImageFile:$workingImage",
        "/Index:$ImageIndex",
        "/MountDir:$MountDir",
        '/ReadOnly'
    )

    try {
        Write-Section "Search for winre.wim"
        $found = Get-FirstExistingPath @(
            (Join-Path $MountDir 'Windows\System32\Recovery\winre.wim'),
            (Join-Path $MountDir 'Recovery\WindowsRE\winre.wim')
        )

        if (-not $found) {
            $candidate = Get-ChildItem -Path $MountDir -Filter winre.wim -Recurse -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($candidate) {
                $found = $candidate.FullName
            }
        }

        if (-not $found) {
            throw "winre.wim was not found in the mounted image."
        }

        Write-Host "Found: $found" -ForegroundColor Green
        Copy-Item $found $OutFile -Force
        Write-Host "Saved to: $OutFile" -ForegroundColor Green
    }
    finally {
        Write-Section "Unmount image"
        Invoke-LoggedCommand dism @(
            '/Unmount-Image',
            "/MountDir:$MountDir",
            '/Discard'
        )
    }

    Write-Section "Done"
    Write-Host "Extracted file: $OutFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host '  1) Create a recovery partition on the target PC'
    Write-Host '  2) Copy winre.wim to R:\Recovery\WindowsRE\winre.wim'
    Write-Host '  3) reagentc /setreimage /path R:\Recovery\WindowsRE /target C:\Windows'
    Write-Host '  4) reagentc /enable'
    Write-Host '  5) reagentc /info'
}
finally {
    if (-not $KeepTemp) {
        Remove-Item $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
