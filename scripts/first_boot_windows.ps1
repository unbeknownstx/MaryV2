param(
    [switch]$SkipTests,
    [switch]$SkipFrontend,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "============================================================"
Write-Host "MARYV2 12.8 FIRST BOOT - WINDOWS"
Write-Host "============================================================"
Write-Host "This script never deletes or replaces your existing data/ or .env."
Write-Host ""

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PyLauncher -and -not $PythonCommand) {
    throw "Python 3.11 is required. Install Python, then run this script again."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1] Creating project virtual environment"
    if ($PyLauncher) {
        & py -3.11 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
} else {
    Write-Host "[1] Existing .venv found - preserving it"
}
$Python = ".venv\Scripts\python.exe"

Write-Host "[2] Installing/updating Python dependencies"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Core dependency install failed." }
& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Desktop dependency install failed." }

if (-not (Test-Path ".env")) {
    Write-Warning "No .env is present. Copy your real backed-up .env here before live provider testing."
} else {
    Write-Host "[3] Existing .env detected - preserved"
}

Write-Host "[4] Doctor"
& $Python -m scripts.doctor
if ($LASTEXITCODE -ne 0) { Write-Warning "Doctor reported items to review." }

Write-Host "[5] LLM route check"
& $Python -m scripts.check_llm_routes
if ($LASTEXITCODE -ne 0) { Write-Warning "Some providers may not be configured yet." }

if (-not $SkipTests) {
    Write-Host "[6] Canonical tests"
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed. Stop here before frontend troubleshooting." }

    Write-Host "[7] Deterministic/offline release verification"
    & $Python -m scripts.run_release_verification --offline
    if ($LASTEXITCODE -ne 0) { throw "Release verification failed. Stop here." }
} else {
    Write-Host "[6-7] Tests skipped by request"
}

if (-not $SkipFrontend) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Warning "Node/npm is not installed. Python Mary is ready, but install Node.js before building the game shell."
    } else {
        Write-Host "[8] Installing/building host-native desktop frontend"
        Push-Location desktop
        try {
            npm ci
            if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
            npm run check
            if ($LASTEXITCODE -ne 0) { throw "frontend syntax check failed." }
            npm run build
            if ($LASTEXITCODE -ne 0) { throw "frontend build failed." }
        }
        finally { Pop-Location }
    }
} else {
    Write-Host "[8] Frontend skipped by request"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "FIRST BOOT BASELINE COMPLETE"
Write-Host "============================================================"
Write-Host "Terminal Mary:  powershell -ExecutionPolicy Bypass -File scripts\run_mary_windows.ps1"
Write-Host "Desktop Mary:   powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1"
Write-Host "Game launcher:  powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1"
Write-Host ""
Write-Host "External skills (Twitch/OBS/Vision/Ren'Py) remain disabled by default."

if ($Launch) {
    if (Test-Path "desktop\dist\index.html") {
        & powershell -ExecutionPolicy Bypass -File scripts\launch_launcher_windows.ps1
    } else {
        Write-Warning "Frontend dist is not built yet, so launcher was not started."
    }
}
