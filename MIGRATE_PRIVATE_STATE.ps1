param(
    [string]$From = "C:\Users\Melvin\Documents\GitHub\MaryV2",
    [string]$To = $PSScriptRoot,
    [switch]$IncludeGitMetadata
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath([string]$PathValue) {
    return [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $PathValue).Path)
}

Write-Host "============================================================"
Write-Host "MARYV2 12.9 CLEAN PROJECT - PRIVATE STATE MIGRATION"
Write-Host "============================================================"
Write-Host "This copies ONLY private runtime state/configuration into the clean project."
Write-Host "It does not copy payload/, upgrade_backups/, node_modules/, .venv/, dist/, or caches."
Write-Host ""

if (-not (Test-Path -LiteralPath $From)) {
    throw "Old MaryV2 project was not found at: $From"
}
if (-not (Test-Path -LiteralPath $To)) {
    throw "Clean MaryV2 project was not found at: $To"
}

$FromFull = Resolve-FullPath $From
$ToFull = Resolve-FullPath $To
if ($FromFull -eq $ToFull) {
    throw "Source and destination are the same folder. Extract this clean package to a NEW folder first."
}

$PackageInfo = Join-Path $ToFull "PACKAGE_INFO.json"
if (-not (Test-Path -LiteralPath $PackageInfo)) {
    throw "Destination does not look like the clean MaryV2 package: PACKAGE_INFO.json is missing."
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SafetyRoot = Join-Path $env:LOCALAPPDATA "MaryV2\clean_migration_backups\$Timestamp"
New-Item -ItemType Directory -Force -Path $SafetyRoot | Out-Null

# Preserve any destination state before replacing it.
$DestinationEnv = Join-Path $ToFull ".env"
$DestinationData = Join-Path $ToFull "data"
if (Test-Path -LiteralPath $DestinationEnv) {
    Copy-Item -LiteralPath $DestinationEnv -Destination (Join-Path $SafetyRoot ".env") -Force
}
if (Test-Path -LiteralPath $DestinationData) {
    Copy-Item -LiteralPath $DestinationData -Destination (Join-Path $SafetyRoot "data") -Recurse -Force
}

$SourceEnv = Join-Path $FromFull ".env"
$SourceData = Join-Path $FromFull "data"

if (Test-Path -LiteralPath $SourceEnv) {
    Copy-Item -LiteralPath $SourceEnv -Destination $DestinationEnv -Force
    Write-Host "[OK] .env copied into clean project."
} else {
    Write-Warning "Old project has no .env. The clean project will use .env.example until you supply provider keys."
}

if (Test-Path -LiteralPath $SourceData) {
    if (Test-Path -LiteralPath $DestinationData) {
        Remove-Item -LiteralPath $DestinationData -Recurse -Force
    }
    Copy-Item -LiteralPath $SourceData -Destination $DestinationData -Recurse -Force
    Write-Host "[OK] data/ copied into clean project."
} else {
    Write-Warning "Old project has no data/ directory. Mary will create state as needed."
}

if ($IncludeGitMetadata) {
    $SourceGit = Join-Path $FromFull ".git"
    $DestinationGit = Join-Path $ToFull ".git"
    if (Test-Path -LiteralPath $SourceGit) {
        if (Test-Path -LiteralPath $DestinationGit) {
            Remove-Item -LiteralPath $DestinationGit -Recurse -Force
        }
        Copy-Item -LiteralPath $SourceGit -Destination $DestinationGit -Recurse -Force
        Write-Host "[OK] .git metadata copied. GitHub Desktop can treat the clean folder as the same repository lineage."
    } else {
        Write-Warning "-IncludeGitMetadata was requested, but the old project has no .git directory."
    }
}

Write-Host ""
Write-Host "Migration safety backup (destination pre-state only):"
Write-Host "  $SafetyRoot"
Write-Host ""
Write-Host "PRIVATE STATE MIGRATION COMPLETE"
Write-Host "Next run:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\SETUP_CLEAN_WINDOWS.ps1"
