param(
    [switch]$ListVoices,
    [switch]$Synthesize,
    [string[]]$Voices = @()
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$argsList = @("-m", "scripts.voice_lab")
if ($ListVoices) { $argsList += "--list-account-voices" }
if ($Synthesize) { $argsList += "--synthesize" }
if ($Voices.Count -gt 0) { $argsList += "--voices"; $argsList += $Voices }
& $Python @argsList
exit $LASTEXITCODE
