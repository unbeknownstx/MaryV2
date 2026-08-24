$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$PreviousMaryDataDirectory = $env:MARY_DATA_DIR
$PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
$PreviousPytestAddopts = $env:PYTEST_ADDOPTS
$SystemTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$FastCheckRoot = [System.IO.Path]::GetFullPath(
  (Join-Path $SystemTempRoot ("maryv2-fast-check-" + [guid]::NewGuid().ToString("N")))
)
New-Item -ItemType Directory -Path $FastCheckRoot -Force | Out-Null
$env:MARY_DATA_DIR = Join-Path $FastCheckRoot "state"
$env:PYTEST_DEBUG_TEMPROOT = $FastCheckRoot
$env:PYTEST_ADDOPTS = "-p no:cacheprovider"

try {
  Write-Host "============================================================" -ForegroundColor Cyan
  Write-Host "MARYV2 FAST CHECK - 12.12.2" -ForegroundColor Cyan
  Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "[1/5] Local character mind" -ForegroundColor Cyan
& $Python -m pytest `
  tests/mind/test_reservoir_12_12.py `
  tests/mind/test_reservoir_thread_safety_12_12.py `
  tests/mind/test_reservoir_lifecycle_12_12_1.py `
  tests/mind/test_local_dialogue_12_12.py `
  tests/mind/test_hybrid_dialogue_runtime.py `
  tests/mind/test_character_behavior_12_12.py `
  tests/runtime/test_cognitive_reservoir_persistence_12_12.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/5] Fast conversation + expression" -ForegroundColor Cyan
& $Python -m pytest `
  tests/conversation/test_fast_path_12_11.py `
  tests/expression/test_expression_director_12_12.py `
  tests/voice/test_expression_delivery_12_12.py `
  tests/voice/test_auto_fast_voice_12_11.py `
  tests/llm/test_local_model_roles_12_12.py `
  tests/expression/test_natural_conversation_12_12_2.py `
  tests/llm/test_local_model_lab_12_12_2.py `
  tests/llm/test_qwen_micro_cortex.py `
  tests/llm/test_qwen_micro_cortex_http.py `
  tests/llm/test_qwen_micro_cortex_quality.py `
  tests/llm/test_qwen_surface_realizer_v3.py `
  tests/llm/test_hybrid_dialogue_shadow.py `
  tests/mind/test_verbalization_plan_boundary.py `
  tests/voice/test_voice_lab_12_12_2.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/5] Desktop/presence boot regressions" -ForegroundColor Cyan
& $Python -m pytest `
  tests/desktop/test_cognitive_mind_ui_12_12.py `
  tests/desktop/test_audio_transport_12_12_2.py `
  tests/desktop/test_neon_connected_ui_12_11.py `
  tests/desktop/test_boot_resilience_12_11_1.py `
  tests/desktop/test_boot_stability_12_11_2.py `
  tests/desktop/test_js_console_diagnostics_12_11_2.py `
  tests/integration/test_connected_media_12_11.py `
  tests/integration/test_presence_pathways_12_10.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/5] 12.12.2 deterministic verifiers" -ForegroundColor Cyan
& $Python -m scripts.verify_character_runtime_12_12
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m scripts.verify_natural_conversation_12_12_2
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/5] Frontend syntax" -ForegroundColor Cyan
  Push-Location desktop
  try { npm run check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
  Write-Host "FAST CHECK PASS" -ForegroundColor Green
} finally {
  if ($null -eq $PreviousMaryDataDirectory) {
    Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue
  } else {
    $env:MARY_DATA_DIR = $PreviousMaryDataDirectory
  }
  if ($null -eq $PreviousPytestTempRoot) {
    Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue
  } else {
    $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot
  }
  if ($null -eq $PreviousPytestAddopts) {
    Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
  } else {
    $env:PYTEST_ADDOPTS = $PreviousPytestAddopts
  }
  if (Test-Path -LiteralPath $FastCheckRoot) {
    $ResolvedFastCheckRoot = [System.IO.Path]::GetFullPath($FastCheckRoot)
    $PathSeparators = [char[]]@('\', '/')
    $ResolvedFastCheckParent = [System.IO.Path]::GetDirectoryName($ResolvedFastCheckRoot).TrimEnd($PathSeparators)
    $ResolvedSystemTempRoot = $SystemTempRoot.TrimEnd($PathSeparators)
    if (-not $ResolvedFastCheckParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Refusing to remove a Fast Check path outside the system temp root."
    }
    Remove-Item -LiteralPath $ResolvedFastCheckRoot -Recurse -Force
  }
}
