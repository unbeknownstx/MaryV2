$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "MaryV2 .venv was not found. Run scripts\setup_windows.ps1 first."
}

# The launcher and source desktop share the same future frozen-app state.
if (-not $env:MARY_DATA_DIR) {
    if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is not available." }
    $env:MARY_DATA_DIR = Join-Path $env:LOCALAPPDATA "MaryV2\data"
}
if (-not $env:MARY_ENV_FILE -and (Test-Path ".env")) {
    $env:MARY_ENV_FILE = Join-Path $Root ".env"
}

& $Python -m scripts.run_launcher
exit $LASTEXITCODE
