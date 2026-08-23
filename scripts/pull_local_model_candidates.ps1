param(
    [switch]$Minimal,
    [switch]$Extended,
    [switch]$Reasoning,
    [switch]$Embeddings,
    [switch]$All
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama is not installed or not on PATH." }

if ($All) {
    $models = @("qwen3:1.7b", "llama3.2:1b", "gemma3:1b", "smollm2:1.7b", "llama3.2:3b", "phi4-mini", "nomic-embed-text")
} elseif ($Reasoning) {
    $models = @("phi4-mini")
} elseif ($Embeddings) {
    $models = @("nomic-embed-text")
} elseif ($Extended) {
    $models = @("qwen3:1.7b", "llama3.2:1b", "gemma3:1b", "smollm2:1.7b", "llama3.2:3b")
} else {
    # Smallest useful dialogue lab for the current host. Existing qwen3:4b is
    # deliberately left untouched as Mary's known quality baseline.
    $models = @("qwen3:1.7b", "llama3.2:1b", "gemma3:1b")
}

Write-Host "MaryV2 local candidate install" -ForegroundColor Cyan
Write-Host "Existing qwen3:4b remains the character-quality baseline." -ForegroundColor DarkGray
foreach ($model in $models) {
    Write-Host "Pulling $model ..." -ForegroundColor Yellow
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) { throw "ollama pull failed for $model" }
}
Write-Host "Done. Benchmark with scripts\benchmark_local_models_windows.ps1" -ForegroundColor Green
