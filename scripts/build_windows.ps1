$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "============================================================"
Write-Host "MARYV2 WINDOWS STANDALONE BUILD"
Write-Host "============================================================"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "MaryV2 .venv was not found. Create/activate the project environment first."
}

$Python = ".venv\Scripts\python.exe"

Remove-Item Env:MARY_RUN_LIVE_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:MARY_RUN_OPENAI_TESTS -ErrorAction SilentlyContinue

Write-Host "[1/5] Desktop frontend build"

Push-Location desktop
try {
    # Always reconstruct host-native frontend dependencies. A copied
    # node_modules directory may contain binaries for another OS/CPU.
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Desktop frontend build failed." }
}
finally {
    Pop-Location
}

Write-Host "[2/5] Deterministic release verification"
& $Python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { throw "Release verification failed." }

Write-Host "[3/5] Build dependency"
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

Write-Host "[4/5] PyInstaller onedir build"
& $Python -m PyInstaller --noconfirm --clean MaryV2.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

Write-Host "[5/5] Result"

$Exe = Join-Path $Root "dist\MaryV2\MaryV2.exe"

if (-not (Test-Path $Exe)) {
    throw "Expected executable was not produced: $Exe"
}

Write-Host "PASS  $Exe"
Write-Host "Mary's writable data defaults to %LOCALAPPDATA%\MaryV2\data when frozen."
Write-Host "Set MARY_PORTABLE=1 to keep data in a data folder beside the executable."
Write-Host "Fresh packaged installs read .env from %LOCALAPPDATA%\MaryV2\.env by default."
Write-Host "A legacy .env beside MaryV2.exe is still honored; MARY_ENV_FILE overrides both."