$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MARYV2 V2 HARD TEST (NO PAID/LIVE API FLAGS)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Remove-Item Env:MARY_RUN_LIVE_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:MARY_RUN_OPENAI_TESTS -ErrorAction SilentlyContinue

Write-Host "[1/5] Python compile"
python -m compileall -q mary scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/5] Desktop frontend rebuild"
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location desktop
    try {
        if (-not (Test-Path "node_modules")) {
            npm ci
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }
} else {
    throw "npm was not found. Install/restore Node.js before the final V2 hard test."
}

Write-Host "[3/5] Deterministic pytest"
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/5] Diagnostics"
python -m scripts.run_diagnostics
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/5] Complete deterministic/offline release gate"
python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

node --check desktop\src\main.js
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "MARYV2 V2 HARD TEST PASS" -ForegroundColor Green
