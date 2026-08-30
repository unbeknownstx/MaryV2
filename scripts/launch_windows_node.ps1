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

# The headless node is independent of Mary Desktop. If Ollama is installed but
# its local server is not currently listening, start it in the background unless
# explicitly disabled with MARY_NODE_START_OLLAMA=false.
$StartOllama = $true
if ($env:MARY_NODE_START_OLLAMA -and $env:MARY_NODE_START_OLLAMA.ToLowerInvariant() -in @("0", "false", "no", "off")) {
    $StartOllama = $false
}
if ($StartOllama) {
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
            Start-Process -FilePath $Ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
            Start-Sleep -Seconds 2
        }
    }
}

& $Python -m scripts.run_windows_node
exit $LASTEXITCODE
