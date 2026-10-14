<#
.SYNOPSIS
Run ruff (required) and mypy (reported, non-blocking unless -StrictTypes).
#>
param([switch]$StrictTypes)
. "$PSScriptRoot\_common.ps1"
Push-Location $RepoRoot
try {
    $py = Get-RepoPython
    & $py -m ruff check src tests
    Assert-LastExit 'ruff'
    & $py -m mypy src
    if ($StrictTypes) { Assert-LastExit 'mypy' }
    elseif ($LASTEXITCODE -ne 0) { Write-Warning 'mypy reported issues (non-blocking without -StrictTypes)' }
}
finally { Pop-Location }
