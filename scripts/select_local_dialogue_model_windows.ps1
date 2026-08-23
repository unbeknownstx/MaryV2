param(
    [Parameter(Mandatory=$true)][string]$Model
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"
if (-not (Test-Path $EnvPath)) { throw ".env not found at $EnvPath" }
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama is not available on PATH." }
$list = (& ollama list | Out-String)
if ($list -notmatch [regex]::Escape($Model.Split(':')[0])) { throw "Model '$Model' does not appear to be installed. Pull/benchmark it first." }
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item $EnvPath "$EnvPath.12.12-local-model-$stamp.bak" -Force
$lines = Get-Content $EnvPath
$key = "MARY_OLLAMA_CONVERSATION_MODEL"
$found = $false
$updated = foreach ($line in $lines) {
    if ($line -match "^\s*$key=") { $found = $true; "$key=$Model" } else { $line }
}
if (-not $found) { $updated += "$key=$Model" }
Set-Content -Path $EnvPath -Value $updated -Encoding UTF8
Write-Host "Fast local Ollama conversation fallback set to $Model" -ForegroundColor Green
Write-Host "This does not change Groq-first normal conversation; it changes the Ollama fast-purpose model when Ollama is selected/fallback." -ForegroundColor DarkGray
