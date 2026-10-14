<#
.SYNOPSIS
Run the pytest suite. Extra arguments are passed to pytest.
.EXAMPLE
.\scripts\test.ps1 -JUnitXml reports\local\pytest.xml -- -k routing
#>
param([string]$JUnitXml, [Parameter(ValueFromRemainingArguments = $true)][string[]]$PytestArgs)
. "$PSScriptRoot\_common.ps1"
Push-Location $RepoRoot
try {
    $argsList = @('-m', 'pytest', '-p', 'no:cacheprovider')
    if ($JUnitXml) { $argsList += "--junitxml=$JUnitXml" }
    if ($PytestArgs) { $argsList += $PytestArgs }
    & (Get-RepoPython) @argsList
    Assert-LastExit 'pytest'
}
finally { Pop-Location }
