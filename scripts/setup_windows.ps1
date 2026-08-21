$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is required for the desktop UI."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}
$Python = ".venv\Scripts\python.exe"

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Core dependency installation failed." }

& $Python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed." }

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Add only the provider keys you actually use."
} else {
    Write-Host "Existing .env preserved."
}

Push-Location desktop
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Desktop frontend build failed." }
}
finally {
    Pop-Location
}

& $Python -m scripts.run_release_verification --offline
if ($LASTEXITCODE -ne 0) { throw "Release verification failed." }

Write-Host "Setup complete. Launch Mary with:"
Write-Host "  .venv\Scripts\python.exe -m scripts.run_desktop"