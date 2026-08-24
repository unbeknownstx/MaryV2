$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MARYV2 RELEASE GATE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
& $Python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "RELEASE GATE PASS" -ForegroundColor Green
