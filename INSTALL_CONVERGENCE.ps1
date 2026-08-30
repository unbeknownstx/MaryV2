param(
    [string]$RepoPath = "C:\Users\Melvin\Documents\GitHub\MaryV2",
    [switch]$SkipTests,
    [switch]$FullSuite
)
$ErrorActionPreference = "Stop"
$argsList = @("$PSScriptRoot\install_convergence.py", "--repo", $RepoPath)
if ($SkipTests) { $argsList += "--skip-tests" }
if ($FullSuite) { $argsList += "--full-suite" }
& python @argsList
exit $LASTEXITCODE
