param(
    [int]$Runs = 2,
    [string[]]$Models = @()
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$ReportDir = Join-Path $Root "runtime_reports"
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Report = Join-Path $ReportDir "local-model-lab-$Stamp.json"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MARYV2 LOCAL MODEL LAB - CURRENT WINDOWS PC" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
if ($Models.Count -gt 0) {
    & $Python -m scripts.benchmark_local_models --runs $Runs --models $Models --save $Report
} else {
    & $Python -m scripts.benchmark_local_models --runs $Runs --save $Report
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Report: $Report" -ForegroundColor Green
Write-Host "Do not auto-promote a model; compare sample wording against qwen3:4b and Mary's current Groq path." -ForegroundColor DarkGray
