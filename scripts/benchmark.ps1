<#
.SYNOPSIS
Score the deterministic rules router on a routing suite.
.NOTES
Now and TtlHours default to fixture values: the fixture policies are effective 2026-10-01 to 2027-01-01.
They are replay settings for the development suite, not platform defaults.
#>
param(
    [string]$Suite = 'fixtures\routing\development',
    [string]$Now = '2026-10-14T12:00:00Z',
    [double]$TtlHours = 168,
    [string]$Report = (Join-Path (Get-ReportDir) 'routing_benchmark_development.json')
)
. "$PSScriptRoot\_common.ps1"
Push-Location $RepoRoot
try {
    & (Get-RepoPython) -m aip.cli benchmark --suite $Suite --now $Now --ttl-hours $TtlHours --report $Report
    Assert-LastExit 'benchmark'
}
finally { Pop-Location }
