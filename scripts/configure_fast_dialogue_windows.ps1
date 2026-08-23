param(
    [string]$EnvPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $EnvPath) { $EnvPath = Join-Path $root ".env" }
if (-not (Test-Path $EnvPath)) {
    throw "Private .env not found at $EnvPath. This helper never creates API keys; restore your existing .env first."
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$EnvPath.12.11-fast-dialogue-$stamp.bak"
Copy-Item $EnvPath $backup -Force

$updates = [ordered]@{
    "MARY_GROQ_CONVERSATION_MODEL" = "llama-3.1-8b-instant"
    "MARY_TTS_PROVIDER" = "auto_fast"
    "MARY_ELEVENLABS_MODEL" = "eleven_flash_v2_5"
}

$lines = [System.Collections.Generic.List[string]]::new()
Get-Content $EnvPath | ForEach-Object { [void]$lines.Add($_) }

foreach ($key in $updates.Keys) {
    $value = $updates[$key]
    $matched = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$([regex]::Escape($key))\s*=") {
            $lines[$i] = "$key=$value"
            $matched = $true
        }
    }
    if (-not $matched) { [void]$lines.Add("$key=$value") }
}

Set-Content -Path $EnvPath -Value $lines -Encoding UTF8
Write-Host "MaryV2 12.11 fast dialogue profile applied." -ForegroundColor Green
Write-Host "Backup: $backup"
Write-Host "No API key or voice ID value was changed." -ForegroundColor Cyan
Write-Host "Conversation model: llama-3.1-8b-instant"
Write-Host "Voice policy: auto_fast (ElevenLabs when configured, local fallback)"
