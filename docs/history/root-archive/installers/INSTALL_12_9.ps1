param(
    [string]$Target = "C:\Users\Melvin\Documents\GitHub\MaryV2",
    [switch]$Fast
)

$ErrorActionPreference = "Stop"
$PatchRoot = $PSScriptRoot
$PayloadRoot = Join-Path $PatchRoot "payload"
$ManifestPath = Join-Path $PatchRoot "MANIFEST_12_9.json"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "MARYV2 12.9 UPLIFT INSTALLER v2" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "Target: $Target"

if (-not (Test-Path $ManifestPath)) { throw "Missing MANIFEST_12_9.json." }
if (-not (Test-Path $PayloadRoot)) { throw "Missing payload folder." }
if (-not (Test-Path (Join-Path $Target "mary"))) { throw "Target does not look like a MaryV2 repository: mary/ is missing." }
if (-not (Test-Path (Join-Path $Target "desktop"))) { throw "Target does not look like a MaryV2 repository: desktop/ is missing." }

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.version -ne "12.9.0") { throw "Unexpected patch version: $($Manifest.version)" }

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $env:LOCALAPPDATA "MaryV2\upgrade_backups\12.9-$Timestamp"
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

Write-Host "Backing up replaced source files OUTSIDE the repository:" -ForegroundColor Cyan
Write-Host "  $BackupRoot"

foreach ($Entry in $Manifest.files) {
    $Relative = [string]$Entry.path
    $Normalized = $Relative.Replace('/', '\')
    $Lower = $Normalized.ToLowerInvariant()

    if ($Lower -eq ".env" -or $Lower.StartsWith("data\") -or $Lower.StartsWith(".git\")) {
        throw "Safety boundary refused payload path: $Relative"
    }

    $Source = Join-Path $PayloadRoot $Normalized
    $Destination = Join-Path $Target $Normalized
    if (-not (Test-Path $Source)) { throw "Payload file missing: $Relative" }

    $SourceHash = (Get-FileHash -Algorithm SHA256 $Source).Hash.ToLowerInvariant()
    if ($SourceHash -ne ([string]$Entry.sha256).ToLowerInvariant()) {
        throw "Patch hash mismatch before copy: $Relative"
    }

    if (Test-Path $Destination) {
        $Backup = Join-Path $BackupRoot $Normalized
        $BackupParent = Split-Path $Backup -Parent
        New-Item -ItemType Directory -Path $BackupParent -Force | Out-Null
        Copy-Item $Destination $Backup -Force
    }

    $Parent = Split-Path $Destination -Parent
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    Copy-Item $Source $Destination -Force

    $DestinationHash = (Get-FileHash -Algorithm SHA256 $Destination).Hash.ToLowerInvariant()
    if ($DestinationHash -ne $SourceHash) {
        throw "Patch hash mismatch after copy: $Relative"
    }
}

Write-Host "Source overlay complete. .env and data/ were not touched." -ForegroundColor Green

$Python = Join-Path $Target ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host ""
Write-Host "Rebuilding frontend from the target PC lockfile..." -ForegroundColor Cyan
Push-Location (Join-Path $Target "desktop")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "npm run check failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
}
finally { Pop-Location }

Write-Host ""
Write-Host "Running installed 12.9 checks..." -ForegroundColor Cyan
Push-Location $Target
try {
    & $Python -m pytest tests\desktop\test_desktop_uplift_12_9.py tests\llm\test_provider_timing_12_9.py -q
    if ($LASTEXITCODE -ne 0) { throw "12.9 targeted tests failed." }

    & $Python -m scripts.verify_uplift_12_9
    if ($LASTEXITCODE -ne 0) { throw "12.9 uplift verifier failed." }

    if (-not $Fast) {
        Write-Host ""
        Write-Host "Running complete repository suite..." -ForegroundColor Cyan
        # pytest.ini excludes installer payloads/backups even if the ZIP was
        # unpacked under MaryV2. Explicit ignores add a second safety layer.
        & $Python -m pytest -q --ignore=payload --ignore=upgrade_backups
        if ($LASTEXITCODE -ne 0) { throw "Full pytest suite failed." }

        Write-Host ""
        Write-Host "Running deterministic/offline release gate..." -ForegroundColor Cyan
        & $Python -m scripts.run_release_verification --offline
        if ($LASTEXITCODE -ne 0) { throw "Offline release verification failed." }
    }
}
finally { Pop-Location }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "MARYV2 12.9 INSTALL VERIFIED" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Backup: $BackupRoot"
Write-Host "Launch with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1"
Write-Host "Open Runtime in Mary's left navigation after a turn to inspect timing."
