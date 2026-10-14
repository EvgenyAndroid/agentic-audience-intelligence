<#
.SYNOPSIS
Validate every example and registry document, and confirm each invalid case fails for its stated reason.
#>
param([string]$Report = (Join-Path (Get-ReportDir) 'conformance.json'))
. "$PSScriptRoot\_common.ps1"
Push-Location $RepoRoot
try {
    & (Get-RepoPython) -m aip.cli conformance --report $Report
    Assert-LastExit 'conformance'
}
finally { Pop-Location }
