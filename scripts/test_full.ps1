$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MARYV2 FULL PYTHON SUITE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
& $Python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "FULL SUITE PASS" -ForegroundColor Green
