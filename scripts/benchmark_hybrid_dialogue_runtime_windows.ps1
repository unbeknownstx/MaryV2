param(
    [int]$Runs = 3,
    [string]$SocialModel = "qwen3:1.7b",
    [string]$StrongerModel = "qwen3:4b",
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
        $Report = Join-Path $ReportDirectory "hybrid-dialogue-runtime-$Stamp.json"
    }

    $PreviousDataDirectory = $env:MARY_DATA_DIR
    $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $IsolatedDataDirectory = [System.IO.Path]::GetFullPath(
        (Join-Path $TempRoot ("maryv2-hybrid-shadow-" + [guid]::NewGuid().ToString("N")))
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
    Write-Host "MARYV2 HYBRID DIALOGUE RUNTIME - BENCHMARK/SHADOW ONLY" -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "Social shadow: $SocialModel"
    Write-Host "Explicit stronger comparison: $StrongerModel"
    Write-Host "Cases: 18; runs per eligible case: $Runs"
    Write-Host "Ollama endpoint: $EndpointDisplay"
    Write-Host "1.7B thinking: disabled; streaming: enabled; context: 768; ceiling: 40 tokens"
    Write-Host "Only SOCIAL_LOW_RISK cases run 1.7B by default; precision probes are explicitly labeled." -ForegroundColor DarkGray
    Write-Host "No candidate is displayed, spoken, persisted into Mary state, ranked, promoted, or routed." -ForegroundColor DarkGray
    Write-Host "Exact qwen3:4b may expose its known thinking/template incompatibility; no substitute is selected." -ForegroundColor DarkGray

    try {
        $BenchmarkArguments = @(
            "-m", "scripts.benchmark_hybrid_dialogue_runtime",
            "--runs", $Runs,
            "--social-model", $SocialModel,
            "--stronger-model", $StrongerModel,
            "--base-url", $BaseUrl,
            "--save", $Report
        )
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
Write-Host "Review preserved samples and fill the null human-review fields before drawing character conclusions." -ForegroundColor DarkGray
