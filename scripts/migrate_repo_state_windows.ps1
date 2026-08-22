param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is not available." }
$RepoData = Join-Path $Root "data"
$StateParent = Join-Path $env:LOCALAPPDATA "MaryV2"
$AppData = Join-Path $StateParent "data"

if (-not (Test-Path $RepoData)) { throw "Repository data directory was not found: $RepoData" }

$RepoCount = @(Get-ChildItem $RepoData -Recurse -File -ErrorAction SilentlyContinue).Count
$AppCount = if (Test-Path $AppData) { @(Get-ChildItem $AppData -Recurse -File -ErrorAction SilentlyContinue).Count } else { 0 }

Write-Host "MARYV2 WINDOWS STATE MIGRATION"
Write-Host "Repository state: $RepoData ($RepoCount files)"
Write-Host "Desktop state:    $AppData ($AppCount files)"
Write-Host ""

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. No files changed." -ForegroundColor Yellow
    Write-Host "Close Mary Desktop, then run again with -Apply."
    exit 0
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force -Path $StateParent | Out-Null

if (Test-Path $AppData) {
    $Backup = Join-Path $StateParent "data.before_repo_migration_$stamp"
    Move-Item -LiteralPath $AppData -Destination $Backup
    Write-Host "Preserved current desktop state at: $Backup" -ForegroundColor Cyan
}

New-Item -ItemType Directory -Force -Path $AppData | Out-Null
Copy-Item -Path (Join-Path $RepoData "*") -Destination $AppData -Recurse -Force

$CopiedCount = @(Get-ChildItem $AppData -Recurse -File -ErrorAction SilentlyContinue).Count
if ($CopiedCount -ne $RepoCount) { throw "Migration count mismatch: repo=$RepoCount desktop=$CopiedCount" }

Write-Host "Migration complete: $CopiedCount files copied." -ForegroundColor Green
Write-Host "Repository data was not deleted or modified."
