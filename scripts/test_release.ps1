$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

$PreviousMaryDataDirectory = $env:MARY_DATA_DIR
$PreviousMaryEnvironmentFile = $env:MARY_ENV_FILE
$PreviousMaryReservoirStorage = $env:MARY_RESERVOIR_STORAGE
$PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
$PreviousPytestAddopts = $env:PYTEST_ADDOPTS
$ResolvedSystemTempRoot = [System.IO.Path]::GetTempPath().TrimEnd('\','/')
$ReleaseGateRoot = Join-Path $ResolvedSystemTempRoot ("maryv2-release-gate-" + [guid]::NewGuid().ToString("N"))
$ReleaseGateDataDirectory = Join-Path $ReleaseGateRoot "state"
$ReleaseGatePytestTempRoot = Join-Path $ReleaseGateRoot "pytest"
$ReleaseGateEnvironmentFile = Join-Path $ReleaseGateRoot "no-live-config"
New-Item -ItemType Directory -Path $ReleaseGateDataDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $ReleaseGatePytestTempRoot -Force | Out-Null
if (Test-Path -LiteralPath $ReleaseGateEnvironmentFile) { throw "Isolation env file must not exist." }
try {
    $env:MARY_DATA_DIR = $ReleaseGateDataDirectory
    $env:MARY_ENV_FILE = $ReleaseGateEnvironmentFile
    $env:MARY_RESERVOIR_STORAGE = "memory"
    $env:PYTEST_DEBUG_TEMPROOT = $ReleaseGatePytestTempRoot
    $env:PYTEST_ADDOPTS = "-p no:cacheprovider"
    & $Python -m scripts.run_release_verification --offline
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "RELEASE GATE PASS" -ForegroundColor Green
}
finally {
    if ($null -eq $PreviousMaryDataDirectory) { Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue } else { $env:MARY_DATA_DIR = $PreviousMaryDataDirectory }
    if ($null -eq $PreviousMaryEnvironmentFile) { Remove-Item Env:MARY_ENV_FILE -ErrorAction SilentlyContinue } else { $env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile }
    if ($null -eq $PreviousMaryReservoirStorage) { Remove-Item Env:MARY_RESERVOIR_STORAGE -ErrorAction SilentlyContinue } else { $env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage }
    if ($null -eq $PreviousPytestTempRoot) { Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue } else { $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot }
    if ($null -eq $PreviousPytestAddopts) { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue } else { $env:PYTEST_ADDOPTS = $PreviousPytestAddopts }
    if (Test-Path -LiteralPath $ReleaseGateRoot) {
        $ResolvedReleaseGateRoot = (Resolve-Path -LiteralPath $ReleaseGateRoot).Path
        $ResolvedReleaseGateParent = Split-Path -Parent $ResolvedReleaseGateRoot
        $ReleaseGateLeaf = Split-Path -Leaf $ResolvedReleaseGateRoot
        $attrs = [System.IO.File]::GetAttributes($ResolvedReleaseGateRoot)
        if (-not $ResolvedReleaseGateParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe release cleanup." }
        if (-not $ReleaseGateLeaf.StartsWith("maryv2-release-gate-", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe release cleanup prefix." }
        if (($attrs -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing reparse-point cleanup." }
        Remove-Item -LiteralPath $ResolvedReleaseGateRoot -Recurse -Force
    }
}
