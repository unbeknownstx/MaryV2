param(
    [switch]$Persist,
    [switch]$RestartOllama
)

$ErrorActionPreference = "Stop"

$settings = [ordered]@{
    OLLAMA_CONTEXT_LENGTH    = "4096"
    OLLAMA_NUM_PARALLEL      = "1"
    OLLAMA_MAX_LOADED_MODELS = "1"
    OLLAMA_GPU_OVERHEAD      = "1073741824"
}

Write-Host "MARYV2 RX580 4GB OLLAMA SAFETY PROFILE"
Write-Host ("=" * 64)
foreach ($entry in $settings.GetEnumerator()) {
    Set-Item -Path ("Env:" + $entry.Key) -Value $entry.Value
    if ($Persist) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "User")
    }
    Write-Host ("{0,-26} {1}" -f $entry.Key, $entry.Value)
}

# Mary may expose its own llama.cpp runtime on PATH for capability discovery.
# Ollama ships its own ggml/runtime libraries and must not inherit Mary's
# llama.cpp DLL directory, otherwise Windows can resolve an incompatible
# ggml-base.dll before Ollama's own libraries. This terminal is dedicated to
# Ollama, so keep only unrelated PATH entries for the server lifetime.
$PathSeparator = [IO.Path]::PathSeparator
$OriginalPathEntries = @($env:PATH -split [regex]::Escape([string]$PathSeparator))
$SafePathEntries = @(
    $OriginalPathEntries | Where-Object {
        $entry = [string]$_
        $normalized = $entry.Replace('/', '\').TrimEnd('\').ToLowerInvariant()
        -not ($normalized -match '\\maryv2\\runtimes\\llama\.cpp(?:\\|$)')
    }
)
if ($SafePathEntries.Count -ne $OriginalPathEntries.Count) {
    $env:PATH = ($SafePathEntries -join $PathSeparator)
    Write-Host "OLLAMA_PATH_ISOLATION       removed MaryV2 llama.cpp runtime DLL directory"
}

$running = @(Get-Process ollama -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    if (-not $RestartOllama) {
        Write-Host ""
        Write-Host "Ollama is already running, so these server settings are not active yet."
        Write-Host "Re-run with -RestartOllama to stop the current Ollama process and start a safe server."
        exit 2
    }
    Write-Host ""
    Write-Host "Stopping existing Ollama process so the safety settings take effect..."
    $running | Stop-Process -Force
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Starting Ollama with the RX580 safety settings."
Write-Host "Leave this terminal running."
Write-Host ""
Write-Host "In a second PowerShell terminal run:"
Write-Host 'python -m scripts.run_home_node --hardware-profile windows-rx580-4gb --benchmark-profile "$HOME\.maryv2\node_benchmark_13_11.json"'
Write-Host ""

ollama serve
