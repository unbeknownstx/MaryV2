param(
    [string]$HardwareProfile = "",
    [string]$BenchmarkProfile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "MaryV2 .venv was not found. Run scripts\setup_windows.ps1 first."
}

if (-not $env:MARY_ENV_FILE -and (Test-Path ".env")) {
    $env:MARY_ENV_FILE = Join-Path $Root ".env"
}

if (-not $HardwareProfile) {
    $HardwareProfile = if ($env:MARY_WINDOWS_HARDWARE_PROFILE) {
        $env:MARY_WINDOWS_HARDWARE_PROFILE
    } else {
        "windows-rx580-4gb"
    }
}

if (-not $BenchmarkProfile) {
    $BenchmarkProfile = Join-Path $HOME ".maryv2\node_benchmark_13_11.json"
}

$StartOllama = $true
if ($env:MARY_NODE_START_OLLAMA -and $env:MARY_NODE_START_OLLAMA.ToLowerInvariant() -in @("0", "false", "no", "off")) {
    $StartOllama = $false
}

$RestartForSafety = $false
if ($HardwareProfile -eq "windows-rx580-4gb") {
    $env:OLLAMA_CONTEXT_LENGTH = "4096"
    $env:OLLAMA_NUM_PARALLEL = "1"
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
    $env:OLLAMA_GPU_OVERHEAD = "1073741824"

    $RestartForSafety = $true
    if ($env:MARY_NODE_RESTART_OLLAMA_SAFE -and $env:MARY_NODE_RESTART_OLLAMA_SAFE.ToLowerInvariant() -in @("0", "false", "no", "off")) {
        $RestartForSafety = $false
    }
}

if ($StartOllama) {
    $running = @(Get-Process ollama -ErrorAction SilentlyContinue)
    if ($RestartForSafety -and $running.Count -gt 0) {
        $running | Stop-Process -Force
        Start-Sleep -Seconds 1
    }

    $OllamaReady = $false
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 | Out-Null
        $OllamaReady = $true
    } catch {
        $OllamaReady = $false
    }

    if (-not $OllamaReady) {
        $Ollama = Get-Command ollama -ErrorAction SilentlyContinue
        if ($null -ne $Ollama) {
            # Ollama ships its own ggml/runtime DLLs. Mary may expose a separate
            # llama.cpp runtime on PATH for node capability discovery; do not let
            # that directory leak into the child Ollama process. Temporarily
            # scrub it only while Start-Process snapshots the environment, then
            # restore PATH so Mary's home node can still discover llama.cpp.
            $OriginalPath = $env:PATH
            $PathSeparator = [IO.Path]::PathSeparator
            $PathEntries = @($OriginalPath -split [regex]::Escape([string]$PathSeparator))
            $SafePathEntries = @(
                $PathEntries | Where-Object {
                    $entry = [string]$_
                    $normalized = $entry.Replace('/', '\').TrimEnd('\').ToLowerInvariant()
                    -not ($normalized -match '\\maryv2\\runtimes\\llama\.cpp(?:\\|$)')
                }
            )
            try {
                $env:PATH = ($SafePathEntries -join $PathSeparator)
                Start-Process -FilePath $Ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
            } finally {
                $env:PATH = $OriginalPath
            }
            Start-Sleep -Seconds 2
        }
    }
}

$NodeArgs = @(
    "-m", "scripts.run_home_node",
    "--hardware-profile", $HardwareProfile
)
if (Test-Path $BenchmarkProfile) {
    $NodeArgs += @("--benchmark-profile", $BenchmarkProfile)
}

& $Python @NodeArgs
exit $LASTEXITCODE
