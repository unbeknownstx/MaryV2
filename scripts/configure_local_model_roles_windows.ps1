param(
    [string]$GeneralModel = "qwen3:4b-instruct",
    [string]$FastModel = "qwen3:1.7b",
    [string]$UtilityModel = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"

if (-not $UtilityModel) { $UtilityModel = $FastModel }
if (-not (Test-Path $EnvPath)) { throw ".env not found at $EnvPath" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama is not available on PATH." }

$installed = @()
$lines = (& ollama list | Out-String) -split "`r?`n"
foreach ($line in $lines) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed -match '^NAME\s+') { continue }
    $parts = $trimmed -split '\s+'
    if ($parts.Count -gt 0) { $installed += $parts[0] }
}

foreach ($model in @($GeneralModel, $FastModel, $UtilityModel)) {
    if ($installed -notcontains $model) {
        throw "Model '$model' is not installed. Available: $($installed -join ', ')"
    }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$EnvPath.13.2-local-roles-$stamp.bak"
Copy-Item $EnvPath $backup -Force

$updates = [ordered]@{
    "MARY_OLLAMA_MODEL" = $GeneralModel
    "MARY_OLLAMA_CONVERSATION_MODEL" = $FastModel
    "MARY_OLLAMA_UTILITY_MODEL" = $UtilityModel
}

$current = Get-Content $EnvPath
foreach ($key in $updates.Keys) {
    $value = $updates[$key]
    $found = $false
    $next = @()
    foreach ($line in $current) {
        if ($line -match "^\s*$([regex]::Escape($key))=") {
            if (-not $found) { $next += "$key=$value" }
            $found = $true
        } else {
            $next += $line
        }
    }
    if (-not $found) { $next += "$key=$value" }
    $current = $next
}

Set-Content -Path $EnvPath -Value $current -Encoding UTF8

Write-Host "MaryV2 local model roles updated." -ForegroundColor Green
Write-Host "  general/conversation : $GeneralModel"
Write-Host "  fast                 : $FastModel"
Write-Host "  utility              : $UtilityModel"
Write-Host "Backup: $backup" -ForegroundColor DarkGray
Write-Host "Restart Mary Desktop so the capability node re-advertises the new role mapping." -ForegroundColor Yellow
