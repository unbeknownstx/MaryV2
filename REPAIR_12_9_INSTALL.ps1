param(
    [string]$Target = "C:\Users\Melvin\Documents\GitHub\MaryV2"
)

$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "MARYV2 12.9 INSTALL DISCOVERY REPAIR" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "Target: $Target"

if (-not (Test-Path (Join-Path $Target "mary"))) {
    throw "Target does not look like a MaryV2 repository: mary/ is missing."
}

$LocalRoot = Join-Path $env:LOCALAPPDATA "MaryV2"
$ExternalBackups = Join-Path $LocalRoot "upgrade_backups"
$ArtifactsRoot = Join-Path $LocalRoot "installer_artifacts\12.9-$Timestamp"
New-Item -ItemType Directory -Path $ExternalBackups -Force | Out-Null
New-Item -ItemType Directory -Path $ArtifactsRoot -Force | Out-Null

# The first 12.9 installer placed upgrade backups below the repository. Pytest
# correctly treated those copied tests as another test tree. Preserve every
# backup, but move it outside the source tree where it belongs.
$RepoBackups = Join-Path $Target "upgrade_backups"
if (Test-Path $RepoBackups) {
    Write-Host "Moving repository-local upgrade backups out of the test tree..." -ForegroundColor Cyan
    Get-ChildItem $RepoBackups -Directory | ForEach-Object {
        $Destination = Join-Path $ExternalBackups $_.Name
        if (Test-Path $Destination) {
            $Destination = Join-Path $ExternalBackups ("{0}-{1}" -f $_.Name, $Timestamp)
        }
        Move-Item $_.FullName $Destination
        Write-Host "  preserved: $Destination"
    }
    if (-not (Get-ChildItem $RepoBackups -Force -ErrorAction SilentlyContinue)) {
        Remove-Item $RepoBackups -Force
    }
}

# If the upgrade ZIP was unpacked directly into MaryV2, payload/tests becomes a
# second copy of the same test modules. Preserve the payload as an installer
# artifact rather than deleting it blindly.
$RepoPayload = Join-Path $Target "payload"
if (Test-Path $RepoPayload) {
    $Marker = Join-Path $RepoPayload "tests\desktop\test_desktop_uplift_12_9.py"
    $PackageMarker = Join-Path $RepoPayload "PACKAGE_INFO.json"
    if ((Test-Path $Marker) -and (Test-Path $PackageMarker)) {
        $Destination = Join-Path $ArtifactsRoot "payload"
        Move-Item $RepoPayload $Destination
        Write-Host "Preserved unpacked patch payload at:" -ForegroundColor Cyan
        Write-Host "  $Destination"
    } else {
        throw "A payload folder exists in the MaryV2 repo but does not match the 12.9 installer payload. It was left untouched for safety."
    }
}

# Install a permanent collection boundary so future payload/backup folders can
# never be mistaken for the canonical test suite.
$PytestIni = Join-Path $Target "pytest.ini"
$PytestContent = @'
[pytest]
# Non-source/generated folders must never become part of canonical collection.
norecursedirs =
    .git
    .venv
    __pycache__
    .pytest_cache
    node_modules
    dist
    build
    payload
    upgrade_backups
    MaryV2_12_9_Uplift_PATCH*
'@
if (-not (Test-Path $PytestIni)) {
    Set-Content -Path $PytestIni -Value $PytestContent -Encoding UTF8
    Write-Host "Installed pytest collection boundary: pytest.ini" -ForegroundColor Green
} else {
    Write-Host "pytest.ini already exists; leaving it unchanged." -ForegroundColor Yellow
}

# Stale bytecode is harmless after duplicate trees are removed, but clearing
# test caches makes this repair deterministic and avoids confusing old paths.
Get-ChildItem $Target -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.venv\*" -and $_.FullName -notlike "*\node_modules\*" } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Target ".pytest_cache") -Recurse -Force -ErrorAction SilentlyContinue

$Python = Join-Path $Target ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host ""
Write-Host "Rechecking frontend production build..." -ForegroundColor Cyan
Push-Location (Join-Path $Target "desktop")
try {
    npm run check
    if ($LASTEXITCODE -ne 0) { throw "npm run check failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed." }
}
finally { Pop-Location }

Write-Host ""
Write-Host "Running complete canonical repository suite..." -ForegroundColor Cyan
Push-Location $Target
try {
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Full pytest suite failed." }

    Write-Host ""
    Write-Host "Running deterministic/offline release gate..." -ForegroundColor Cyan
    & $Python -m scripts.run_release_verification --offline
    if ($LASTEXITCODE -ne 0) { throw "Offline release verification failed." }
}
finally { Pop-Location }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "MARYV2 12.9 REPAIR + VERIFICATION COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "External backups: $ExternalBackups"
Write-Host "Installer artifacts: $ArtifactsRoot"
Write-Host "Launch Mary with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1"
