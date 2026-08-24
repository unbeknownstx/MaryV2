$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$PreviousMaryDataDirectory = $env:MARY_DATA_DIR
$PreviousMaryEnvironmentFile = $env:MARY_ENV_FILE
$PreviousMaryReservoirStorage = $env:MARY_RESERVOIR_STORAGE
$PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
$PreviousPytestAddopts = $env:PYTEST_ADDOPTS
$SystemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$FullTestRoot = [System.IO.Path]::GetFullPath(
  (Join-Path $SystemTempRoot ("maryv2-full-tests-" + [guid]::NewGuid().ToString("N")))
)
$FullTestDataDirectory = Join-Path $FullTestRoot "state"
$FullTestPytestTempRoot = Join-Path $FullTestRoot "pytest"
$FullTestEnvironmentFile = Join-Path $FullTestRoot "no-live-config"
$FullSuiteExitCode = 1

try {
  New-Item -ItemType Directory -Path $FullTestDataDirectory -Force | Out-Null
  New-Item -ItemType Directory -Path $FullTestPytestTempRoot -Force | Out-Null
  if (Test-Path -LiteralPath $FullTestEnvironmentFile) {
    throw "Full Tests isolation requires a nonexistent MARY_ENV_FILE target."
  }
  $env:MARY_DATA_DIR = $FullTestDataDirectory
  $env:MARY_ENV_FILE = $FullTestEnvironmentFile
  $env:MARY_RESERVOIR_STORAGE = "memory"
  $env:PYTEST_DEBUG_TEMPROOT = $FullTestPytestTempRoot
  $env:PYTEST_ADDOPTS = "-p no:cacheprovider"

  Write-Host "============================================================" -ForegroundColor Cyan
  Write-Host "MARYV2 FULL PYTHON SUITE" -ForegroundColor Cyan
  Write-Host "============================================================" -ForegroundColor Cyan
  & $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
  $FullSuiteExitCode = $LASTEXITCODE
} finally {
  if ($null -eq $PreviousMaryDataDirectory) {
    Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:MARY_DATA_DIR = $PreviousMaryDataDirectory
  }
  if ($null -eq $PreviousMaryEnvironmentFile) {
    Remove-Item Env:MARY_ENV_FILE -ErrorAction SilentlyContinue
  } else {
    $env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile
  }
  if ($null -eq $PreviousMaryReservoirStorage) {
    Remove-Item Env:MARY_RESERVOIR_STORAGE -ErrorAction SilentlyContinue
  } else {
    $env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage
  }
  if ($null -eq $PreviousPytestTempRoot) {
    Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue
  } else {
    $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot
  }
  if ($null -eq $PreviousPytestAddopts) {
    Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
  } else {
    $env:PYTEST_ADDOPTS = $PreviousPytestAddopts
  }

  if (Test-Path -LiteralPath $FullTestRoot) {
    $ResolvedFullTestRoot = [System.IO.Path]::GetFullPath($FullTestRoot)
    $PathSeparators = [char[]]@('\', '/')
    $ResolvedFullTestParent = [System.IO.Path]::GetDirectoryName($ResolvedFullTestRoot).TrimEnd($PathSeparators)
    $ResolvedSystemTempRoot = $SystemTempRoot.TrimEnd($PathSeparators)
    $FullTestLeaf = [System.IO.Path]::GetFileName($ResolvedFullTestRoot)
    if (
      -not $ResolvedFullTestParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
      -not $FullTestLeaf.StartsWith("maryv2-full-tests-", [System.StringComparison]::OrdinalIgnoreCase)
    ) {
      throw "Refusing to remove a Full Tests path outside the bounded system temp location."
    }
    $FullTestRootItem = Get-Item -LiteralPath $ResolvedFullTestRoot -Force
    if (($FullTestRootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "Refusing to recursively remove a reparse-point Full Tests path."
    }
    Remove-Item -LiteralPath $ResolvedFullTestRoot -Recurse -Force
  }
}

if ($FullSuiteExitCode -ne 0) { exit $FullSuiteExitCode }
Write-Host "FULL SUITE PASS" -ForegroundColor Green
