param(
    [switch]$SkipFullSuite,
    [switch]$SkipReleaseGate
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Step($n, $label) { Write-Host "[$n/10] $label" -ForegroundColor Cyan }
function Pass($label) { Write-Host "  PASS: $label" -ForegroundColor Green }

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "MARYV2 12.11 WINDOWS SETUP + VERIFICATION" -ForegroundColor Magenta
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

Step 4 "12.11 fast-dialogue + connected-media regressions"
& $Python -m pytest `
    tests/conversation/test_fast_path_12_11.py `
    tests/voice/test_auto_fast_voice_12_11.py `
    tests/integration/test_connected_media_12_11.py `
    tests/desktop/test_neon_connected_ui_12_11.py `
    tests/desktop/test_presence_presentation_12_10.py `
    tests/integration/test_presence_pathways_12_10.py `
    tests/desktop/test_desktop_uplift_12_9.py `
    tests/llm/test_provider_timing_12_9.py `
    tests/voice/test_voice_timing_12_9.py -q
if ($LASTEXITCODE -ne 0) { throw "12.11 targeted regression suite failed." }
Pass "targeted regressions"

Step 5 "12.11 deterministic verifier"
& $Python -m scripts.verify_connected_companion_12_11
if ($LASTEXITCODE -ne 0) { throw "12.11 verifier failed." }
Pass "12.11 verifier"

Step 6 "12.10 compatibility verifier"
& $Python -m scripts.verify_presence_presentation_12_10
if ($LASTEXITCODE -ne 0) { throw "12.10 compatibility verifier failed." }
Pass "12.10 compatibility"

Step 7 "12.9 compatibility verifier"
& $Python -m scripts.verify_uplift_12_9
if ($LASTEXITCODE -ne 0) { throw "12.9 compatibility verifier failed." }
Pass "12.9 compatibility"

Step 8 "Full canonical repository suite"
if (-not $SkipFullSuite) {
    & $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
    if ($LASTEXITCODE -ne 0) { throw "Full canonical pytest suite failed." }
    Pass "full canonical suite"
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 9 "Deterministic/offline release gate"
if (-not $SkipReleaseGate) {
    & $Python -m scripts.run_release_verification --offline
    if ($LASTEXITCODE -ne 0) { throw "Offline release verification failed." }
    Pass "offline release gate"
} else { Write-Host "  SKIPPED by request" -ForegroundColor Yellow }

Step 10 "Persistent state integrity"
if (Test-Path "data") {
    & $Python -m scripts.verify_state_integrity
    if ($LASTEXITCODE -ne 0) { throw "Persistent state integrity verification failed." }
    Pass "repo-local state integrity"
} else { Write-Host "  Repo-local data/ absent; Desktop/frozen state may live in LocalAppData by design." }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "MARYV2 12.11 READY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Launch: powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1"
Write-Host "Fast check: powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1"
