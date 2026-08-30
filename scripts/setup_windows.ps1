param(
    [switch]$SkipFullSuite,
    [switch]$SkipReleaseGate
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Step($n, $label) { Write-Host "[$n/10] $label" -ForegroundColor Cyan }
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
Write-Host "MARYV2 WINDOWS SETUP + VERIFICATION" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "Root: $Root"

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PyLauncher -and -not $PythonCommand) { throw "Python is required." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js/npm is required for the desktop UI." }

Step 1 "Python environment"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if ($PyLauncher) { & py -3.11 -m venv .venv; if ($LASTEXITCODE -ne 0) { & python -m venv .venv } }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Pass "virtual environment"

Step 2 "Python dependencies"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "core dependency installation failed." }
& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "desktop dependency installation failed." }
Pass "Python dependencies"

Step 3 "Private environment template"
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env from .env.example; add only your private provider values."
} else { Write-Host "  Existing .env preserved." }

Step 4 "Frontend install / syntax / production build"
Push-Location desktop
try {
    npm ci; if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check; if ($LASTEXITCODE -ne 0) { throw "frontend syntax check failed." }
    npm run build; if ($LASTEXITCODE -ne 0) { throw "frontend production build failed." }
} finally { Pop-Location }
Pass "frontend production build"

Step 5 "Repository structure / one-Mary convergence"
Invoke-IsolatedPythonStage -StageName "step-5-structure" -Arguments @("-m","scripts.verify_repository_structure")
Invoke-IsolatedPythonStage -StageName "step-5-convergence" -Arguments @("-m","scripts.verify_maryv2_convergence")

Step 6 "Character / conversation regressions"
Invoke-IsolatedPythonStage -StageName "step-6-character-runtime" -Arguments @("-m","scripts.verify_character_runtime_12_12")
Invoke-IsolatedPythonStage -StageName "step-6-natural-conversation" -Arguments @("-m","scripts.verify_natural_conversation_12_12_2")

Step 7 "Full deterministic suite"
if (-not $SkipFullSuite) {
    Invoke-IsolatedPythonStage -StageName "step-7-full-suite" -Arguments @("-m","pytest","-q")
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 8 "Deterministic/offline release gate"
if (-not $SkipReleaseGate) {
    Invoke-IsolatedPythonStage -StageName "step-8-release-gate" -Arguments @("-m","scripts.run_release_verification","--offline")
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 9 "Standalone/build readiness"
Invoke-IsolatedPythonStage -StageName "step-9-standalone" -Arguments @("-m","scripts.verify_standalone_readiness")

Step 10 "Local capability node status"
Write-Host "  Headless node launcher: scripts\launch_windows_node.ps1"
Write-Host "  Optional logon task: scripts\install_windows_node_task.ps1"

Write-Host "MARYV2 READY" -ForegroundColor Green
Write-Host "Terminal: python -m scripts.run_mary"
Write-Host "Desktop: powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1"
