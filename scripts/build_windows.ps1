$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "============================================================"
Write-Host "MARYV2 12.8 WINDOWS ECOSYSTEM BUILD"
Write-Host "============================================================"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "MaryV2 .venv was not found. Create/activate the project environment first."
}
$Python = ".venv\Scripts\python.exe"

Remove-Item Env:MARY_RUN_LIVE_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:MARY_RUN_OPENAI_TESTS -ErrorAction SilentlyContinue

Write-Host "[1/8] Desktop + launcher frontend build"
Push-Location desktop
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "Frontend JavaScript checks failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Desktop frontend build failed." }
}
finally { Pop-Location }

Write-Host "[2/8] Final build preflight"
& $Python -m scripts.final_preflight --build-ready
if ($LASTEXITCODE -ne 0) { throw "Final build preflight failed." }

Write-Host "[3/8] Deterministic release verification"
& $Python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { throw "Release verification failed." }

Write-Host "[4/8] Build dependency"
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

Write-Host "[5/8] Build MaryV2"
& $Python -m PyInstaller --noconfirm --clean MaryV2.spec
if ($LASTEXITCODE -ne 0) { throw "MaryV2 PyInstaller build failed." }

Write-Host "[6/8] Build Mary Launcher"
& $Python -m PyInstaller --noconfirm --clean MaryLauncher.spec
if ($LASTEXITCODE -ne 0) { throw "Mary Launcher PyInstaller build failed." }

Write-Host "[7/8] Verify artifacts"
$MaryExe = Join-Path $Root "dist\MaryV2\MaryV2.exe"
$LauncherExe = Join-Path $Root "dist\MaryLauncher\MaryLauncher.exe"
if (-not (Test-Path $MaryExe)) { throw "Expected Mary executable was not produced: $MaryExe" }
if (-not (Test-Path $LauncherExe)) { throw "Expected launcher executable was not produced: $LauncherExe" }

Write-Host "[8/8] Result"
Write-Host "PASS  $LauncherExe"
Write-Host "PASS  $MaryExe"
Write-Host ""
Write-Host "Normal use: launch MaryLauncher.exe, then press PLAY MARY."
Write-Host "The launcher finds dist\MaryV2\MaryV2.exe as its sibling application."
Write-Host "Mary's writable data defaults to %LOCALAPPDATA%\MaryV2\data when frozen."
Write-Host "Fresh packaged installs read .env from %LOCALAPPDATA%\MaryV2\.env by default."
Write-Host "Set MARY_PORTABLE=1 only if you deliberately want state beside the executable."
