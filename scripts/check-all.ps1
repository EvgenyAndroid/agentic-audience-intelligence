<#
.SYNOPSIS
Run every local verification step and write reports to reports\local.
#>
. "$PSScriptRoot\_common.ps1"
$reports = Get-ReportDir
& "$PSScriptRoot\verify-adcp-lock.ps1"
& "$PSScriptRoot\lint.ps1"
& "$PSScriptRoot\test.ps1" -JUnitXml (Join-Path $reports 'pytest.xml')
& "$PSScriptRoot\conformance.ps1" -Report (Join-Path $reports 'conformance.json')
& "$PSScriptRoot\benchmark.ps1" -Report (Join-Path $reports 'routing_benchmark_development.json')
Write-Host "All checks passed. Reports: $reports"
