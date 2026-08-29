$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: MaryV2 .venv was not found at .\.venv" -ForegroundColor Red
    exit 1
}

$python = ".\.venv\Scripts\python.exe"

Write-Host "========================================"
Write-Host "MARYV2 13.2 FULL-PASS VERIFICATION"
Write-Host "========================================"

& $python -c "import mary; print('PASS: mary import ->', mary.__file__)"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m compileall -q mary scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Get-Command node -ErrorAction SilentlyContinue) {
    node --check desktop\src\main.js
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    node --check desktop\src\runtime\httpBridge.js
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    node --check mobile_web\app.js
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "WARN: node is not on PATH; JavaScript syntax checks skipped." -ForegroundColor Yellow
}

cmd /c fc /b mobile_web\app.js mobile_native\MaryMobile\www\app.js > $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: mobile app.js bundles differ" -ForegroundColor Red
    exit 1
}

cmd /c fc /b mobile_web\style.css mobile_native\MaryMobile\www\style.css > $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: mobile style.css bundles differ" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "MARYV2 FULL PASS VERIFIED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
