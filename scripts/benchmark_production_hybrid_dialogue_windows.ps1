param(
    [ValidateRange(1, 10)]
    [int]$Runs = 3,
    [string]$Report = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BenchmarkExitCode = 1
$PathSeparators = [char[]]@('\', '/')
$SystemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd($PathSeparators)
$IsolationRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $SystemTempRoot ("maryv2-production-hybrid-" + [guid]::NewGuid().ToString("N")))
)

$EnvironmentNames = @(
    "MARY_DATA_DIR",
    "MARY_WORKSPACE_ROOT",
    "MARY_ENV_FILE",
    "MARY_LLM_PROVIDER",
    "MARY_LLM_MODEL",
    "MARY_LLM_FALLBACKS",
    "MARY_LLM_ROUTING_STRATEGY",
    "MARY_LLM_FREE_ORDER",
    "MARY_LLM_CONVERSATION_ORDER",
    "MARY_LLM_EXPERT_PROVIDER",
    "MARY_LOCAL_MIND_ENABLED",
    "MARY_LOCAL_DIALOGUE_ENABLED",
    "MARY_RESERVOIR_STORAGE",
    "MARY_QWEN_SHADOW_ENABLED",
    "MARY_LOCAL_MIND_SHADOW_ENABLED",
    "MARY_HYBRID_QWEN_SHADOW_ENABLED",
    "MARY_AUTONOMOUS",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONPYCACHEPREFIX",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_HOST",
    "OLLAMA_BASE_URL"
)

$PreviousEnvironment = @{}
foreach ($Name in $EnvironmentNames) {
    $Existing = Get-Item -LiteralPath ("Env:" + $Name) -ErrorAction SilentlyContinue
    $PreviousEnvironment[$Name] = [pscustomobject]@{
        Exists = ($null -ne $Existing)
        Value = if ($null -ne $Existing) { $Existing.Value } else { $null }
    }
}

function Set-ProcessEnvironmentValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][string]$Value
    )
    [System.Environment]::SetEnvironmentVariable(
        $Name,
        $Value,
        [System.EnvironmentVariableTarget]::Process
    )
}

New-Item -ItemType Directory -Path $IsolationRoot | Out-Null

try {
    Set-ProcessEnvironmentValue "MARY_DATA_DIR" (Join-Path $IsolationRoot "state")
    Set-ProcessEnvironmentValue "MARY_WORKSPACE_ROOT" (Join-Path $IsolationRoot "workspace")
    Set-ProcessEnvironmentValue "MARY_ENV_FILE" (Join-Path $IsolationRoot "no-live-config")
    Set-ProcessEnvironmentValue "MARY_LLM_PROVIDER" "benchmark"
    Set-ProcessEnvironmentValue "MARY_LLM_MODEL" "production-benchmark-in-process"
    Set-ProcessEnvironmentValue "MARY_LLM_FALLBACKS" ""
    Set-ProcessEnvironmentValue "MARY_LLM_ROUTING_STRATEGY" "configured"
    Set-ProcessEnvironmentValue "MARY_LLM_FREE_ORDER" "benchmark"
    Set-ProcessEnvironmentValue "MARY_LLM_CONVERSATION_ORDER" "benchmark"
    Set-ProcessEnvironmentValue "MARY_LLM_EXPERT_PROVIDER" "benchmark"
    Set-ProcessEnvironmentValue "MARY_LOCAL_MIND_ENABLED" "true"
    Set-ProcessEnvironmentValue "MARY_LOCAL_DIALOGUE_ENABLED" "true"
    Set-ProcessEnvironmentValue "MARY_RESERVOIR_STORAGE" "memory"
    Set-ProcessEnvironmentValue "MARY_QWEN_SHADOW_ENABLED" "0"
    Set-ProcessEnvironmentValue "MARY_LOCAL_MIND_SHADOW_ENABLED" "0"
    Set-ProcessEnvironmentValue "MARY_HYBRID_QWEN_SHADOW_ENABLED" "0"
    Set-ProcessEnvironmentValue "MARY_AUTONOMOUS" "false"
    Set-ProcessEnvironmentValue "PYTHONDONTWRITEBYTECODE" "1"
    Set-ProcessEnvironmentValue "PYTHONPYCACHEPREFIX" (Join-Path $IsolationRoot "pycache")

    foreach ($Name in @(
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_HOST",
        "OLLAMA_BASE_URL"
    )) {
        Set-ProcessEnvironmentValue $Name $null
    }

    if (-not $Report) {
        $Stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss-fffffff'Z'")
        $Report = "production-hybrid-dialogue-$Stamp.json"
    }

    $PythonExecutable = if (Test-Path -LiteralPath (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) {
        Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    } else {
        "python"
    }

    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "MARYV2 12.12.3 PRODUCTION HYBRID DIALOGUE BENCHMARK" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Cases: 13; runs per case: $Runs"
    Write-Host "Entrypoint: MaryApplication.run"
    Write-Host "Provider: benchmark (counting, in-process, no network)"
    Write-Host "Qwen shadow: disabled; live dotenv/data: disabled" -ForegroundColor DarkGray

    Push-Location $ProjectRoot
    try {
        & $PythonExecutable @(
            "-m", "scripts.benchmark_production_hybrid_dialogue",
            "--runs", $Runs,
            "--save", $Report,
            "--isolation-root", $IsolationRoot
        )
        $BenchmarkExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    try {
        foreach ($Name in $EnvironmentNames) {
            $Previous = $PreviousEnvironment[$Name]
            if ($Previous.Exists) {
                Set-ProcessEnvironmentValue $Name $Previous.Value
            } else {
                Set-ProcessEnvironmentValue $Name $null
            }
        }
    } finally {
        if (Test-Path -LiteralPath $IsolationRoot) {
            $ResolvedIsolationRoot = [System.IO.Path]::GetFullPath($IsolationRoot)
            $ResolvedParent = [System.IO.Path]::GetDirectoryName($ResolvedIsolationRoot).TrimEnd($PathSeparators)
            $LeafName = [System.IO.Path]::GetFileName($ResolvedIsolationRoot)
            if (-not $ResolvedParent.Equals($SystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove a benchmark path outside the direct system-temp root."
            }
            if (-not $LeafName.StartsWith("maryv2-production-hybrid-", [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove a benchmark path without the required isolation prefix."
            }
            $IsolationItem = Get-Item -LiteralPath $ResolvedIsolationRoot -Force
            if (($IsolationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing to recursively remove a reparse-point benchmark path."
            }
            Remove-Item -LiteralPath $ResolvedIsolationRoot -Recurse -Force
        }
    }
}

if ($BenchmarkExitCode -ne 0) {
    exit $BenchmarkExitCode
}

Write-Host "Production hybrid benchmark completed without external/model calls." -ForegroundColor Green
