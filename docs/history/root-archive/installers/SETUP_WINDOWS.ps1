param(
    [switch]$SkipFullSuite,
    [switch]$SkipReleaseGate
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Step($n, $label) { Write-Host "[$n/11] $label" -ForegroundColor Cyan }
function Pass($label) { Write-Host "  PASS: $label" -ForegroundColor Green }

function Remove-BoundedTemporaryDirectory {
    param([Parameter(Mandatory=$true)][string]$Target, [Parameter(Mandatory=$true)][string]$ExpectedLeafPrefix)
    if (-not (Test-Path -LiteralPath $Target)) { return }
    $ResolvedSystemTempRoot = [System.IO.Path]::GetTempPath().TrimEnd('\','/')
    $ResolvedTarget = (Resolve-Path -LiteralPath $Target).Path
    $ResolvedTargetParent = Split-Path -Parent $ResolvedTarget
    $TargetLeaf = Split-Path -Leaf $ResolvedTarget
    $Attributes = [System.IO.File]::GetAttributes($ResolvedTarget)
    if (-not $ResolvedTargetParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing cleanup outside system temp." }
    if (-not $TargetLeaf.StartsWith($ExpectedLeafPrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing cleanup with unexpected prefix." }
    if (($Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing cleanup of a reparse point." }
    Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force
}

function Invoke-IsolatedPythonStage {
    param(
        [Parameter(Mandatory=$true)][string]$StageName,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    $SafeStageName = ($StageName -replace '[^A-Za-z0-9_-]', '-')
    $PreviousMaryDataDirectory = $env:MARY_DATA_DIR
    $PreviousMaryEnvironmentFile = $env:MARY_ENV_FILE
    $PreviousMaryReservoirStorage = $env:MARY_RESERVOIR_STORAGE
    $PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
    $PreviousPytestAddopts = $env:PYTEST_ADDOPTS
    $SystemTempRoot = [System.IO.Path]::GetTempPath().TrimEnd('\','/')
    $IsolationRoot = Join-Path $SystemTempRoot ("maryv2-setup-$SafeStageName-" + [guid]::NewGuid().ToString("N"))
    $IsolatedDataDirectory = Join-Path $IsolationRoot "state"
    $IsolatedPytestTempRoot = Join-Path $IsolationRoot "pytest"
    $IsolatedEnvironmentFile = Join-Path $IsolationRoot "no-live-config"
    New-Item -ItemType Directory -Path $IsolatedDataDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $IsolatedPytestTempRoot -Force | Out-Null
    if (Test-Path -LiteralPath $IsolatedEnvironmentFile) { throw "Isolation env file must not exist." }
    try {
        $env:MARY_DATA_DIR = $IsolatedDataDirectory
        $env:MARY_ENV_FILE = $IsolatedEnvironmentFile
        $env:MARY_RESERVOIR_STORAGE = "memory"
        $env:PYTEST_DEBUG_TEMPROOT = $IsolatedPytestTempRoot
        $env:PYTEST_ADDOPTS = "-p no:cacheprovider"
        & $Python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Isolated stage failed: $StageName" }
    }
    finally {
        if ($null -eq $PreviousMaryDataDirectory) { Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue } else { $env:MARY_DATA_DIR = $PreviousMaryDataDirectory }
        if ($null -eq $PreviousMaryEnvironmentFile) { Remove-Item Env:MARY_ENV_FILE -ErrorAction SilentlyContinue } else { $env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile }
        if ($null -eq $PreviousMaryReservoirStorage) { Remove-Item Env:MARY_RESERVOIR_STORAGE -ErrorAction SilentlyContinue } else { $env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage }
        if ($null -eq $PreviousPytestTempRoot) { Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue } else { $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot }
        if ($null -eq $PreviousPytestAddopts) { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue } else { $env:PYTEST_ADDOPTS = $PreviousPytestAddopts }
        Remove-BoundedTemporaryDirectory -Target $IsolationRoot -ExpectedLeafPrefix "maryv2-setup-$SafeStageName-"
    }
}

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "MARYV2 13.1.1 WINDOWS SETUP + VERIFICATION" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "Root: $Root"

if (-not (Test-Path ".env")) { Write-Warning "No .env found. Preserve/copy your existing private .env before live provider testing." }
$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PyLauncher -and -not $PythonCommand) { throw "Python is required." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js/npm is required." }

Step 1 "Python environment"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if ($PyLauncher) { & py -3.11 -m venv .venv; if ($LASTEXITCODE -ne 0) { & python -m venv .venv } }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Pass "virtual environment"

Step 2 "Python dependencies"
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "core dependency installation failed." }
& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "desktop dependency installation failed." }
Pass "Python dependencies"

Step 3 "Frontend install / syntax / production build"
Push-Location desktop
try {
    npm ci; if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check; if ($LASTEXITCODE -ne 0) { throw "frontend syntax check failed." }
    npm run build; if ($LASTEXITCODE -ne 0) { throw "frontend production build failed." }
} finally { Pop-Location }
Pass "frontend production build"

Step 4 "Character / hybrid dialogue regressions"
Invoke-IsolatedPythonStage -StageName "step-4-character-regressions" -Arguments @("-m","pytest","tests/mind/test_production_local_mind_v2.py","tests/core/test_production_hybrid_core_12_12_3.py","-q")

Step 5 "Character runtime + natural conversation"
Invoke-IsolatedPythonStage -StageName "step-5-character-runtime" -Arguments @("-m","scripts.verify_character_runtime_12_12")
Invoke-IsolatedPythonStage -StageName "step-5-natural-conversation" -Arguments @("-m","scripts.verify_natural_conversation_12_12_2")

Step 6 "Connected companion"
Invoke-IsolatedPythonStage -StageName "step-6-connected-companion" -Arguments @("-m","scripts.verify_connected_companion_12_11")

Step 7 "Presence / presentation / uplift"
Invoke-IsolatedPythonStage -StageName "step-7-presence-presentation" -Arguments @("-m","scripts.verify_presence_presentation_12_10")
Invoke-IsolatedPythonStage -StageName "step-7-uplift" -Arguments @("-m","scripts.verify_uplift_12_9")

Step 8 "Full canonical repository suite"
if (-not $SkipFullSuite) {
    Invoke-IsolatedPythonStage -StageName "step-8-full-suite" -Arguments @("-m","pytest","tests","test_breakthrough_11.py","test_breakthrough_12.py","-q")
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 9 "Deterministic/offline release gate"
if (-not $SkipReleaseGate) {
    Invoke-IsolatedPythonStage -StageName "step-9-release-gate" -Arguments @("-m","scripts.run_release_verification","--offline")
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 10 "Persistent state integrity"
$RepoLocalDataDirectory = Join-Path $Root "data"
if (Test-Path $RepoLocalDataDirectory) {
    & $Python -m scripts.verify_state_integrity --data-dir $RepoLocalDataDirectory
    if ($LASTEXITCODE -ne 0) { throw "Persistent state integrity verification failed." }
    Pass "repo-local state integrity"
}

Step 11 "Local mind/model lab status"
Invoke-IsolatedPythonStage -StageName "step-11-mind-status" -Arguments @("-m","scripts.mind_status")

Write-Host "MARYV2 13.1.1 READY" -ForegroundColor Green
Write-Host "Launch: powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1"
Write-Host "Fast: powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1"
