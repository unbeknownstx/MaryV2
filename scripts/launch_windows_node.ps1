param(
    [string]$HardwareProfile = "",
    [string]$BenchmarkProfile = ""
)

$ErrorActionPreference = "Stop"
$Canonical = Join-Path $PSScriptRoot "launch_home_node_windows.ps1"
if (-not (Test-Path $Canonical)) {
    throw "Canonical Windows home-node launcher was not found: $Canonical"
}

& $Canonical -HardwareProfile $HardwareProfile -BenchmarkProfile $BenchmarkProfile
exit $LASTEXITCODE
