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
    param(
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$SystemTempRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedLeafPrefix
    )

    if (-not (Test-Path -LiteralPath $Target)) { return }

    $ResolvedTarget = [System.IO.Path]::GetFullPath($Target)
    $PathSeparators = [char[]]@('\', '/')
    $ResolvedTargetParent = [System.IO.Path]::GetDirectoryName($ResolvedTarget).TrimEnd($PathSeparators)
    $ResolvedSystemTempRoot = [System.IO.Path]::GetFullPath($SystemTempRoot).TrimEnd($PathSeparators)
    $TargetLeaf = [System.IO.Path]::GetFileName($ResolvedTarget)
    if (
        -not $ResolvedTargetParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $TargetLeaf.StartsWith($ExpectedLeafPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Refusing to remove an isolated verification path outside the bounded system temp location."
    }

    $TargetItem = Get-Item -LiteralPath $ResolvedTarget -Force
    if (($TargetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Refusing to recursively remove a reparse-point verification path."
    }
    Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force
}

function Invoke-IsolatedPythonStage {
    param(
        [Parameter(Mandatory = $true)][string]$StageName,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $PreviousMaryDataDirectory = $env:MARY_DATA_DIR
    $PreviousMaryEnvironmentFile = $env:MARY_ENV_FILE
    $PreviousMaryReservoirStorage = $env:MARY_RESERVOIR_STORAGE
    $PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
    $PreviousPytestAddopts = $env:PYTEST_ADDOPTS
    $SystemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $SafeStageName = ($StageName -replace '[^A-Za-z0-9-]', '-').Trim([char[]]@('-'))
    if (-not $SafeStageName) { $SafeStageName = "stage" }
    $IsolationLeafPrefix = "maryv2-setup-$SafeStageName-"
    $IsolationRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $SystemTempRoot ($IsolationLeafPrefix + [guid]::NewGuid().ToString("N")))
    )
    $IsolatedDataDirectory = Join-Path $IsolationRoot "state"
    $IsolatedPytestTempRoot = Join-Path $IsolationRoot "pytest"
    $IsolatedEnvironmentFile = Join-Path $IsolationRoot "no-live-config"
    $StageExitCode = 1

    try {
        New-Item -ItemType Directory -Path $IsolatedDataDirectory -Force | Out-Null
        New-Item -ItemType Directory -Path $IsolatedPytestTempRoot -Force | Out-Null
        if (Test-Path -LiteralPath $IsolatedEnvironmentFile) {
            throw "Isolated Python stage requires a nonexistent MARY_ENV_FILE target."
        }
        $env:MARY_DATA_DIR = $IsolatedDataDirectory
        $env:MARY_ENV_FILE = $IsolatedEnvironmentFile
        $env:MARY_RESERVOIR_STORAGE = "memory"
        $env:PYTEST_DEBUG_TEMPROOT = $IsolatedPytestTempRoot
        $env:PYTEST_ADDOPTS = "-p no:cacheprovider"

        & $script:Python @Arguments
        $StageExitCode = $LASTEXITCODE
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

        Remove-BoundedTemporaryDirectory `
            -Target $IsolationRoot `
            -SystemTempRoot $SystemTempRoot `
            -ExpectedLeafPrefix $IsolationLeafPrefix
    }

    if ($StageExitCode -ne 0) {
        throw "$FailureMessage (exit code $StageExitCode)."
    }
}

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "MARYV2 12.12.2 WINDOWS SETUP + VERIFICATION" -ForegroundColor Magenta
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
} else { Write-Host "  Existing .venv found - reusing it" }
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

Step 3 "Frontend install / syntax / production build"
Push-Location desktop
try {
    npm ci; if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check; if ($LASTEXITCODE -ne 0) { throw "frontend syntax check failed." }
    npm run build; if ($LASTEXITCODE -ne 0) { throw "frontend production build failed." }
} finally { Pop-Location }
Pass "frontend production build"

Step 4 "12.12.2 character / voice / latency regressions"
Invoke-IsolatedPythonStage -StageName "step-4-character-regressions" -Arguments @(
    "-m"
    "pytest"
    "tests/mind/test_reservoir_12_12.py"
    "tests/mind/test_reservoir_thread_safety_12_12.py"
    "tests/mind/test_reservoir_lifecycle_12_12_1.py"
    "tests/mind/test_local_dialogue_12_12.py"
    "tests/mind/test_character_behavior_12_12.py"
    "tests/expression/test_expression_director_12_12.py"
    "tests/voice/test_expression_delivery_12_12.py"
    "tests/llm/test_local_model_roles_12_12.py"
    "tests/runtime/test_cognitive_reservoir_persistence_12_12.py"
    "tests/desktop/test_cognitive_mind_ui_12_12.py"
    "tests/expression/test_natural_conversation_12_12_2.py"
    "tests/desktop/test_audio_transport_12_12_2.py"
    "tests/llm/test_local_model_lab_12_12_2.py"
    "tests/voice/test_voice_lab_12_12_2.py"
    "-q"
) -FailureMessage "12.12.2 targeted regression suite failed"
Pass "12.12.2 regressions"

Step 5 "12.12 + 12.12.2 deterministic verifiers"
Invoke-IsolatedPythonStage -StageName "step-5-character-runtime" -Arguments @(
    "-m", "scripts.verify_character_runtime_12_12"
) -FailureMessage "12.12 verifier failed"
Invoke-IsolatedPythonStage -StageName "step-5-natural-conversation" -Arguments @(
    "-m", "scripts.verify_natural_conversation_12_12_2"
) -FailureMessage "12.12.2 verifier failed"
Pass "12.12 + 12.12.2 verifiers"

Step 6 "12.11 compatibility verifier"
Invoke-IsolatedPythonStage -StageName "step-6-connected-companion" -Arguments @(
    "-m", "scripts.verify_connected_companion_12_11"
) -FailureMessage "12.11 compatibility verifier failed"
Pass "12.11 compatibility"

Step 7 "12.10 / 12.9 compatibility verifiers"
Invoke-IsolatedPythonStage -StageName "step-7-presence-presentation" -Arguments @(
    "-m", "scripts.verify_presence_presentation_12_10"
) -FailureMessage "12.10 compatibility verifier failed"
Invoke-IsolatedPythonStage -StageName "step-7-uplift" -Arguments @(
    "-m", "scripts.verify_uplift_12_9"
) -FailureMessage "12.9 compatibility verifier failed"
Pass "12.10 + 12.9 compatibility"

Step 8 "Full canonical repository suite"
if (-not $SkipFullSuite) {
    Invoke-IsolatedPythonStage -StageName "step-8-full-suite" -Arguments @(
        "-m"
        "pytest"
        "tests"
        "test_breakthrough_11.py"
        "test_breakthrough_12.py"
        "-q"
    ) -FailureMessage "Full canonical pytest suite failed"
    Pass "full canonical suite"
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 9 "Deterministic/offline release gate"
if (-not $SkipReleaseGate) {
    Invoke-IsolatedPythonStage -StageName "step-9-release-gate" -Arguments @(
        "-m", "scripts.run_release_verification", "--offline"
    ) -FailureMessage "Offline release verification failed"
    Pass "offline release gate"
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 10 "Persistent state integrity"
$RepoLocalDataDirectory = [System.IO.Path]::GetFullPath((Join-Path $Root "data"))
if (Test-Path -LiteralPath $RepoLocalDataDirectory) {
    & $Python -m scripts.verify_state_integrity --data-dir $RepoLocalDataDirectory
    if ($LASTEXITCODE -ne 0) { throw "Persistent state integrity verification failed." }
    Pass "repo-local state integrity"
} else { Write-Host "  Repo-local data/ absent; Desktop/frozen state may live in LocalAppData by design." }

Step 11 "Local model lab availability (no downloads, no model calls)"
Invoke-IsolatedPythonStage -StageName "step-11-mind-status" -Arguments @(
    "-m", "scripts.mind_status"
) -FailureMessage "Mind status failed"
Pass "local mind/model lab status"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "MARYV2 12.12.2 READY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Launch: powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1"
Write-Host "Fast: powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1"
Write-Host "Character: powershell -ExecutionPolicy Bypass -File .\scripts\test_character.ps1"
Write-Host "Local model benchmark: powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_local_models_windows.ps1"

Write-Host "Small local model pull: powershell -ExecutionPolicy Bypass -File .\scripts\pull_local_model_candidates.ps1"
Write-Host "Voice lab plan: powershell -ExecutionPolicy Bypass -File .\scripts\run_voice_lab_windows.ps1"
