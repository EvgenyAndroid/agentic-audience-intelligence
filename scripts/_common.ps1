# Shared helpers for repository scripts. Dot-source from other scripts: . "$PSScriptRoot\_common.ps1"
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Get-RepoPython {
    $venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) { return $venvPython }
    return 'python'  # CI and pre-provisioned environments
}

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

function Get-ReportDir {
    $dir = Join-Path $RepoRoot 'reports\local'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}
