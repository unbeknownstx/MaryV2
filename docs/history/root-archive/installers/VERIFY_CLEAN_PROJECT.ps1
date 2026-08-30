$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "No clean .venv found. Run SETUP_CLEAN_WINDOWS.ps1 first."
}

Push-Location desktop
try {
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "frontend check failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed." }
}
finally { Pop-Location }

& $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
if ($LASTEXITCODE -ne 0) { throw "pytest failed." }

& $Python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { throw "offline release verification failed." }

Write-Host "CLEAN PROJECT VERIFICATION COMPLETE"
