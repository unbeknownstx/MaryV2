param([switch]$Fast)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Push-Location (Join-Path $Root "desktop")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "frontend source check failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
}
finally { Pop-Location }

Push-Location $Root
try {
    & $Python -m scripts.verify_uplift_12_9
    if ($LASTEXITCODE -ne 0) { throw "12.9 verifier failed" }
    if (-not $Fast) {
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
        & $Python -m scripts.run_release_verification --offline
        if ($LASTEXITCODE -ne 0) { throw "release gate failed" }
    }
}
finally { Pop-Location }
Write-Host "MaryV2 12.9 source/build verification passed." -ForegroundColor Green
