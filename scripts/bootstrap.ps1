<#
.SYNOPSIS
Create .venv and install the package in editable mode with development extras.
.EXAMPLE
.\scripts\bootstrap.ps1 -WithModeling
#>
param(
    [string]$PythonLauncher = 'py',
    [string]$PythonVersion = '3.11',
    [switch]$WithModeling,
    [switch]$WithLlm,
    [switch]$WithApi
)
. "$PSScriptRoot\_common.ps1"
Push-Location $RepoRoot
try {
    $venv = Join-Path $RepoRoot '.venv'
    if (-not (Test-Path $venv)) {
        & $PythonLauncher "-$PythonVersion" -m venv $venv
        Assert-LastExit 'virtual environment creation'
    }
    $py = Get-RepoPython
    & $py -m pip install --upgrade pip
    Assert-LastExit 'pip upgrade'
    $extras = @('dev')
    if ($WithModeling) { $extras += 'modeling' }
    if ($WithLlm) { $extras += 'llm' }
    if ($WithApi) { $extras += 'api' }
    & $py -m pip install -c (Join-Path $RepoRoot 'requirements\constraints.txt') -e ".[$($extras -join ',')]"
    Assert-LastExit 'package install'
    Write-Host "Ready. Activate with: .\.venv\Scripts\Activate.ps1"
}
finally { Pop-Location }
