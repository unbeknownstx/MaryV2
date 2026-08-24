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
$ReleaseGateRoot = [System.IO.Path]::GetFullPath(
  (Join-Path $SystemTempRoot ("maryv2-release-gate-" + [guid]::NewGuid().ToString("N")))
)
$ReleaseGateDataDirectory = Join-Path $ReleaseGateRoot "state"
$ReleaseGatePytestTempRoot = Join-Path $ReleaseGateRoot "pytest"
$ReleaseGateEnvironmentFile = Join-Path $ReleaseGateRoot "no-live-config"
$ReleaseGateExitCode = 1

try {
  New-Item -ItemType Directory -Path $ReleaseGateDataDirectory -Force | Out-Null
  New-Item -ItemType Directory -Path $ReleaseGatePytestTempRoot -Force | Out-Null
  if (Test-Path -LiteralPath $ReleaseGateEnvironmentFile) {
    throw "Release Gate isolation requires a nonexistent MARY_ENV_FILE target."
  }
  $env:MARY_DATA_DIR = $ReleaseGateDataDirectory
  $env:MARY_ENV_FILE = $ReleaseGateEnvironmentFile
  $env:MARY_RESERVOIR_STORAGE = "memory"
  $env:PYTEST_DEBUG_TEMPROOT = $ReleaseGatePytestTempRoot
  $env:PYTEST_ADDOPTS = "-p no:cacheprovider"

  Write-Host "============================================================" -ForegroundColor Cyan
  Write-Host "MARYV2 RELEASE GATE" -ForegroundColor Cyan
  Write-Host "============================================================" -ForegroundColor Cyan
  & $Python -m scripts.run_release_verification --offline
  $ReleaseGateExitCode = $LASTEXITCODE
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

  if (Test-Path -LiteralPath $ReleaseGateRoot) {
    $ResolvedReleaseGateRoot = [System.IO.Path]::GetFullPath($ReleaseGateRoot)
    $PathSeparators = [char[]]@('\', '/')
    $ResolvedReleaseGateParent = [System.IO.Path]::GetDirectoryName($ResolvedReleaseGateRoot).TrimEnd($PathSeparators)
    $ResolvedSystemTempRoot = $SystemTempRoot.TrimEnd($PathSeparators)
    $ReleaseGateLeaf = [System.IO.Path]::GetFileName($ResolvedReleaseGateRoot)
    if (
      -not $ResolvedReleaseGateParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
      -not $ReleaseGateLeaf.StartsWith("maryv2-release-gate-", [System.StringComparison]::OrdinalIgnoreCase)
    ) {
      throw "Refusing to remove a Release Gate path outside the bounded system temp location."
    }
    $ReleaseGateRootItem = Get-Item -LiteralPath $ResolvedReleaseGateRoot -Force
    if (($ReleaseGateRootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      throw "Refusing to recursively remove a reparse-point Release Gate path."
    }
    Remove-Item -LiteralPath $ResolvedReleaseGateRoot -Recurse -Force
  }
}

if ($ReleaseGateExitCode -ne 0) { exit $ReleaseGateExitCode }
Write-Host "RELEASE GATE PASS" -ForegroundColor Green
