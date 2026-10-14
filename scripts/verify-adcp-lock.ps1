<#
.SYNOPSIS
Check the vendored AdCP schemas against the SHA-256 values in third_party\adcp\adcp.lock.json.
#>
. "$PSScriptRoot\_common.ps1"
$adcpDir = Join-Path $RepoRoot 'third_party\adcp'
$lock = Get-Content -Raw -Path (Join-Path $adcpDir 'adcp.lock.json') | ConvertFrom-Json
$failed = 0
foreach ($entry in $lock.files.PSObject.Properties) {
    $path = Join-Path $adcpDir ($entry.Name -replace '/', '\')
    $actual = (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value.sha256) {
        Write-Error "Hash mismatch for $($entry.Name): expected $($entry.Value.sha256), got $actual" -ErrorAction Continue
        $failed++
    }
    else { Write-Host "OK $($entry.Name)" }
}
if ($failed -gt 0) { throw "$failed vendored AdCP file(s) changed. Check .gitattributes line-ending rules or re-pin." }
Write-Host "AdCP lock verified at commit $($lock.commit)"
