param(
    [int]$WarmRuns = 2,
    [string[]]$Models = @("qwen3:1.7b"),
    [string]$Report = "",
    [string]$BaseUrl = "http://127.0.0.1:11434",
    [ValidateSet("compact_v1", "compact_v2")]
    [string]$PromptProfile = "compact_v2",
    [switch]$Include4BControl,
    [switch]$IncludeInstructControl,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BenchmarkExitCode = 1
Push-Location $ProjectRoot
try {
    $PythonExecutable = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
    $ReportDirectory = Join-Path $ProjectRoot "runtime_reports"
    New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null

    if (-not $Report) {
        $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $Report = Join-Path $ReportDirectory "qwen-micro-cortex-$Stamp.json"
    }

    # This Windows launcher is safe for the creator's 4 GB RX580 by default.
    # Larger controls remain available only through explicit switches or a
    # caller-supplied -Models list so an ordinary benchmark cannot surprise-load
    # a 4B model onto the display GPU.
    if ($Include4BControl -and $Models -notcontains "qwen3:4b") {
        $Models = @($Models) + "qwen3:4b"
    }
    if ($IncludeInstructControl -and $Models -notcontains "qwen3:4b-instruct") {
        $Models = @($Models) + "qwen3:4b-instruct"
    }

    $PreviousDataDirectory = $env:MARY_DATA_DIR
    $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $IsolatedDataDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $TempRoot ("maryv2-micro-cortex-" + [guid]::NewGuid().ToString("N")))
    )
    $env:MARY_DATA_DIR = $IsolatedDataDirectory

    try {
        $EndpointUri = [System.Uri]$BaseUrl
        $EndpointHost = if ($EndpointUri.Host.Contains(":")) { "[$($EndpointUri.Host)]" } else { $EndpointUri.Host }
        $EndpointPort = if ($EndpointUri.IsDefaultPort) { "" } else { ":$($EndpointUri.Port)" }
        $EndpointDisplay = ("{0}://{1}{2}{3}" -f $EndpointUri.Scheme, $EndpointHost, $EndpointPort, $EndpointUri.AbsolutePath).TrimEnd("/")
    } catch {
        $EndpointDisplay = "<invalid endpoint; benchmark will reject it>"
    }

    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "MARYV2 QWEN MICRO-CORTEX - BENCHMARK ONLY" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Models: $($Models -join ', ')"
    Write-Host "Warm runs per fixed case: $WarmRuns"
    Write-Host "Prompt profile: $PromptProfile"
    Write-Host "Ollama endpoint: $EndpointDisplay"
    Write-Host "Thinking: disabled; streaming: enabled; context: 1024; output ceiling: 48 tokens"
    if ($Models | Where-Object { $_ -match '^qwen3:4b' }) {
        Write-Warning "A 4B control was explicitly requested. On the RX580 4 GB display GPU this is experimental and may exhaust safe VRAM headroom."
    }
    Write-Host "Warm novel prompts and exact repeats are reported separately."
    Write-Host "Cold measurement temporarily unloads only the requested model tags; requested residency is restored best-effort." -ForegroundColor DarkGray
    Write-Host "No model will be selected, promoted, or connected to production routing." -ForegroundColor DarkGray

    try {
        $BenchmarkArguments = @(
            "-m", "scripts.benchmark_qwen_micro_cortex",
            "--warm-runs", $WarmRuns,
            "--save", $Report,
            "--base-url", $BaseUrl,
            "--prompt-profile", $PromptProfile,
            "--models"
        ) + $Models
        if ($Overwrite) {
            $BenchmarkArguments += "--overwrite"
        }
        & $PythonExecutable @BenchmarkArguments
        $BenchmarkExitCode = $LASTEXITCODE
    } finally {
        if ($null -eq $PreviousDataDirectory) {
            Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue
        } else {
            $env:MARY_DATA_DIR = $PreviousDataDirectory
        }
        if (Test-Path -LiteralPath $IsolatedDataDirectory) {
            $ResolvedIsolatedDataDirectory = [System.IO.Path]::GetFullPath($IsolatedDataDirectory)
            $PathSeparators = [char[]]@('\', '/')
            $ResolvedIsolatedParent = [System.IO.Path]::GetDirectoryName($ResolvedIsolatedDataDirectory).TrimEnd($PathSeparators)
            $ResolvedTempRoot = $TempRoot.TrimEnd($PathSeparators)
            if (-not $ResolvedIsolatedParent.Equals($ResolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove an isolated data path outside the system temp root."
            }
            Remove-Item -LiteralPath $IsolatedDataDirectory -Recurse -Force
        }
    }
} finally {
    Pop-Location
}

if ($BenchmarkExitCode -ne 0) {
    exit $BenchmarkExitCode
}

Write-Host "Report: $Report" -ForegroundColor Green
Write-Host "Read the preserved samples before deciding whether either model is useful." -ForegroundColor DarkGray
