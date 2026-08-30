param(
    [Parameter(Mandatory=$true)]
    [string]$BackupPath
)

$ErrorActionPreference = 'Stop'
$Target = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupPath = (Resolve-Path $BackupPath).Path

Write-Host "============================================================"
Write-Host "MARYV2 PRIVATE STATE RESTORE"
Write-Host "============================================================"
Write-Host "Source backup: $BackupPath"
Write-Host "Target MaryV2: $Target"

$envSource = Join-Path $BackupPath '.env'
$dataSource = Join-Path $BackupPath 'data'

if (Test-Path $envSource) {
    Copy-Item $envSource (Join-Path $Target '.env') -Force
    Write-Host "[OK] .env copied"
} else {
    Write-Warning "No .env found at $envSource"
}

if (Test-Path $dataSource) {
    $targetData = Join-Path $Target 'data'
    if (Test-Path $targetData) {
        Remove-Item $targetData -Recurse -Force
    }
    Copy-Item $dataSource $targetData -Recurse -Force
    Write-Host "[OK] data/ copied"
} else {
    Write-Warning "No data folder found at $dataSource"
}

Write-Host "Private state restore complete."
