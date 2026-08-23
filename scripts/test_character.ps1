$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "MARYV2 CHARACTER RUNTIME CHECK" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "[1/4] Local mind + Cognitive Reservoir" -ForegroundColor Cyan
& $Python -m pytest `
  tests/mind/test_reservoir_12_12.py `
  tests/mind/test_reservoir_thread_safety_12_12.py `
  tests/mind/test_local_dialogue_12_12.py `
  tests/mind/test_character_behavior_12_12.py `
  tests/runtime/test_cognitive_reservoir_persistence_12_12.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/4] Expression + voice/avatar delivery" -ForegroundColor Cyan
& $Python -m pytest `
  tests/expression/test_expression_director_12_12.py `
  tests/voice/test_expression_delivery_12_12.py `
  tests/desktop/test_cognitive_mind_ui_12_12.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/4] Local model roles + deterministic verifier" -ForegroundColor Cyan
& $Python -m pytest tests/llm/test_local_model_roles_12_12.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m scripts.verify_character_runtime_12_12
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/4] Frontend syntax" -ForegroundColor Cyan
Push-Location desktop
try {
  npm run check
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

Write-Host "CHARACTER RUNTIME CHECK PASS" -ForegroundColor Green
