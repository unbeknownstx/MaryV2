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
$FullTestRoot = Join-Path $ResolvedSystemTempRoot ("maryv2-full-tests-" + [guid]::NewGuid().ToString("N"))
$FullTestDataDirectory = Join-Path $FullTestRoot "state"
$FullTestPytestTempRoot = Join-Path $FullTestRoot "pytest"
$FullTestEnvironmentFile = Join-Path $FullTestRoot "no-live-config"
New-Item -ItemType Directory -Path $FullTestDataDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $FullTestPytestTempRoot -Force | Out-Null
if (Test-Path -LiteralPath $FullTestEnvironmentFile) { throw "Isolation env file must not exist." }

try {
    $env:MARY_DATA_DIR = $FullTestDataDirectory
    $env:MARY_ENV_FILE = $FullTestEnvironmentFile
    $env:MARY_RESERVOIR_STORAGE = "memory"
    $env:PYTEST_DEBUG_TEMPROOT = $FullTestPytestTempRoot
    $env:PYTEST_ADDOPTS = "-p no:cacheprovider"
    & $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host "FULL SUITE PASS" -ForegroundColor Green
}
finally {
    if ($null -eq $PreviousMaryDataDirectory) { Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue } else { $env:MARY_DATA_DIR = $PreviousMaryDataDirectory }
    if ($null -eq $PreviousMaryEnvironmentFile) { Remove-Item Env:MARY_ENV_FILE -ErrorAction SilentlyContinue } else { $env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile }
    if ($null -eq $PreviousMaryReservoirStorage) { Remove-Item Env:MARY_RESERVOIR_STORAGE -ErrorAction SilentlyContinue } else { $env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage }
    if ($null -eq $PreviousPytestTempRoot) { Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue } else { $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot }
    if ($null -eq $PreviousPytestAddopts) { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue } else { $env:PYTEST_ADDOPTS = $PreviousPytestAddopts }

    if (Test-Path -LiteralPath $FullTestRoot) {
        $ResolvedFullTestRoot = (Resolve-Path -LiteralPath $FullTestRoot).Path
        $ResolvedFullTestParent = Split-Path -Parent $ResolvedFullTestRoot
        $FullTestLeaf = Split-Path -Leaf $ResolvedFullTestRoot
        $attrs = [System.IO.File]::GetAttributes($ResolvedFullTestRoot)
        if (-not $ResolvedFullTestParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe full-test cleanup." }
        if (-not $FullTestLeaf.StartsWith("maryv2-full-tests-", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe full-test cleanup prefix." }
        if (($attrs -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing reparse-point cleanup." }
        Remove-Item -LiteralPath $ResolvedFullTestRoot -Recurse -Force
    }
}
