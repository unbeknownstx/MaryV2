param(
    [int]$WarmRuns = 2,
    [string[]]$Models = @("qwen3:1.7b", "qwen3:4b-instruct"),
    [string]$Report = "",
    [string]$BaseUrl = "http://127.0.0.1:11434",
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
        $Report = Join-Path $ReportDirectory "qwen-surface-realizer-v3-$Stamp.json"
    }

    $PreviousDataDirectory = $env:MARY_DATA_DIR
    $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $IsolatedDataDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $TempRoot ("maryv2-surface-v3-" + [guid]::NewGuid().ToString("N")))
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
    Write-Host "MARYV2 SEMANTIC SURFACE REALIZER V3 - BENCHMARK ONLY" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Models: $($Models -join ', ')"
    Write-Host "Cases: core 10 plus 8 adversarial; warm runs per case: $WarmRuns"
    Write-Host "Ollama endpoint: $EndpointDisplay"
    Write-Host "Thinking: disabled; streaming: enabled; context: 1024; output ceiling: 48 tokens"
    Write-Host "The model receives only speaker-relative semantic units and surface constraints." -ForegroundColor DarkGray
    Write-Host "Cold measurement temporarily unloads only requested tags; initial residency is restored best-effort." -ForegroundColor DarkGray
    Write-Host "No model will be selected, promoted, or connected to production routing." -ForegroundColor DarkGray

    try {
        $BenchmarkArguments = @(
            "-m", "scripts.benchmark_qwen_micro_cortex",
            "--prompt-profile", "surface_v3",
            "--warm-runs", $WarmRuns,
            "--save", $Report,
            "--base-url", $BaseUrl,
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
            Remove-Item -LiteralPath $ResolvedIsolatedDataDirectory -Recurse -Force
        }
    }
} finally {
    Pop-Location
}

if ($BenchmarkExitCode -ne 0) {
    exit $BenchmarkExitCode
}

Write-Host "Report: $Report" -ForegroundColor Green
Write-Host "Review raw, repaired, and rejected samples before judging either model." -ForegroundColor DarkGray
