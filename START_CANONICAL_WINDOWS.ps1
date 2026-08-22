$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "============================================================"
Write-Host "MARYV2 12.9 CANONICAL WINDOWS SETUP"
Write-Host "============================================================"

powershell -ExecutionPolicy Bypass -File (Join-Path $Root 'SETUP_CLEAN_WINDOWS.ps1')
