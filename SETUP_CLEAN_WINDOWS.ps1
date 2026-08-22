param(
    [switch]$SkipFullSuite,
    [switch]$SkipReleaseGate
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

Write-Host "============================================================"
Write-Host "MARYV2 12.9 CLEAN PROJECT - WINDOWS SETUP + VERIFICATION"
Write-Host "============================================================"
Write-Host "Root: $Root"
Write-Host ""

if (-not (Test-Path ".env")) {
    Write-Warning "No .env is present. Run MIGRATE_PRIVATE_STATE.ps1 first if you want your existing provider configuration."
}
if (-not (Test-Path "data")) {
    Write-Warning "No data/ is present. Run MIGRATE_PRIVATE_STATE.ps1 first if you want your existing Mary state."
}

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PyLauncher -and -not $PythonCommand) {
    throw "Python is required."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is required for the desktop UI."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/8] Creating clean virtual environment"
    if ($PyLauncher) {
        & py -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Python 3.11 launcher failed; trying default Python."
            & python -m venv .venv
        }
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
} else {
    Write-Host "[1/8] Existing clean .venv found - reusing it"
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"

Write-Host "[2/8] Installing Python dependencies"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Core dependency installation failed." }
& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed." }

Write-Host "[3/8] Building frontend from lockfile"
Push-Location desktop
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "frontend syntax check failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend production build failed." }
}
finally { Pop-Location }

Write-Host "[4/8] 12.9 targeted regression suite"
& $Python -m pytest tests/desktop/test_desktop_uplift_12_9.py tests/llm/test_provider_timing_12_9.py tests/voice/test_voice_timing_12_9.py -q
if ($LASTEXITCODE -ne 0) { throw "12.9 targeted regression suite failed." }

Write-Host "[5/8] 12.9 offline verifier"
& $Python -m scripts.verify_uplift_12_9
if ($LASTEXITCODE -ne 0) { throw "12.9 uplift verifier failed." }

if (-not $SkipFullSuite) {
    Write-Host "[6/8] Full canonical repository suite"
    # Explicit canonical test roots prevent any unrelated directory from ever
    # being collected even if someone later unpacks an archive next to source.
    & $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
    if ($LASTEXITCODE -ne 0) { throw "Full canonical pytest suite failed." }
} else {
    Write-Host "[6/8] Full suite skipped by request"
}

if (-not $SkipReleaseGate) {
    Write-Host "[7/8] Deterministic/offline release gate"
    & $Python -m scripts.run_release_verification --offline
    if ($LASTEXITCODE -ne 0) { throw "Offline release verification failed." }
} else {
    Write-Host "[7/8] Release gate skipped by request"
}

Write-Host "[8/8] Persistent state integrity"
if (Test-Path "data") {
    & $Python -m scripts.verify_state_integrity
    if ($LASTEXITCODE -ne 0) { throw "Persistent state integrity verification failed." }
} else {
    Write-Warning "No data/ directory is present, so state-integrity verification was skipped."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "MARYV2 12.9 CLEAN PROJECT READY"
Write-Host "============================================================"
Write-Host "Direct Desktop:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1"
Write-Host "Launcher:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1"
Write-Host "Terminal Mary:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_mary_windows.ps1"
