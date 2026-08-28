$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "MaryV2 .venv was not found. Run scripts\setup_windows.ps1 first."
}

if (-not $env:MARY_ENV_FILE -and (Test-Path ".env")) {
    $env:MARY_ENV_FILE = Join-Path $Root ".env"
}

& $Python -m scripts.run_windows_node
exit $LASTEXITCODE
