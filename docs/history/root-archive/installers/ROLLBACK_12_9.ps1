param(
    [Parameter(Mandatory=$true)][string]$Backup,
    [string]$Target = "C:\Users\Melvin\Documents\GitHub\MaryV2"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $Backup)) { throw "Backup folder not found: $Backup" }
if (-not (Test-Path (Join-Path $Target "mary"))) { throw "Target does not look like MaryV2." }
Write-Host "Restoring files from $Backup" -ForegroundColor Yellow
Get-ChildItem $Backup -Recurse -File | ForEach-Object {
    $Relative = $_.FullName.Substring($Backup.Length).TrimStart('\','/')
    $Destination = Join-Path $Target $Relative
    $Parent = Split-Path $Destination -Parent
    New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    Copy-Item $_.FullName $Destination -Force
}
Write-Host "Rollback source files restored. .env/data were never part of the patch." -ForegroundColor Green
Write-Host "Rebuild desktop if needed: cd desktop; npm ci; npm run build"
