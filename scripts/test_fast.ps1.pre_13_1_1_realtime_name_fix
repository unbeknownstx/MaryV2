$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$PreviousMaryDataDirectory = $env:MARY_DATA_DIR
$PreviousMaryEnvironmentFile = $env:MARY_ENV_FILE
$PreviousMaryReservoirStorage = $env:MARY_RESERVOIR_STORAGE
$PreviousPytestTempRoot = $env:PYTEST_DEBUG_TEMPROOT
$PreviousPytestAddopts = $env:PYTEST_ADDOPTS
$ResolvedSystemTempRoot = [System.IO.Path]::GetTempPath().TrimEnd('\','/')
$FastCheckRoot = Join-Path $ResolvedSystemTempRoot ("maryv2-fast-check-" + [guid]::NewGuid().ToString("N"))
$FastCheckDataDirectory = Join-Path $FastCheckRoot "state"
$FastCheckPytestTempRoot = Join-Path $FastCheckRoot "pytest"
$FastCheckEnvironmentFile = Join-Path $FastCheckRoot "no-live-config"
New-Item -ItemType Directory -Path $FastCheckDataDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $FastCheckPytestTempRoot -Force | Out-Null
if (Test-Path -LiteralPath $FastCheckEnvironmentFile) { throw "Isolation env file must not exist." }
try {
    $env:MARY_DATA_DIR = $FastCheckDataDirectory
    $env:MARY_ENV_FILE = $FastCheckEnvironmentFile
    $env:MARY_RESERVOIR_STORAGE = "memory"
    $env:PYTEST_DEBUG_TEMPROOT = $FastCheckPytestTempRoot
    $env:PYTEST_ADDOPTS = "-p no:cacheprovider"
    & $Python -m pytest `
      tests/mind/test_reservoir_12_12.py `
      tests/mind/test_local_dialogue_12_12.py `
      tests/mind/test_hybrid_dialogue_runtime.py `
      tests/mind/test_production_local_mind_v2.py `
      tests/llm/test_hybrid_dialogue_shadow.py `
      tests/conversation/test_fast_path_12_11.py `
      tests/expression/test_natural_conversation_12_12_2.py `
      tests/development/test_mary_13_growth.py `
      tests/realtime/test_attention_bus_13_1.py -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m scripts.verify_character_runtime_12_12
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m scripts.verify_natural_conversation_12_12_2
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m scripts.verify_production_hybrid_dialogue_12_12_3
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m scripts.verify_mary_13_1
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Push-Location desktop
    try { npm run check; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } } finally { Pop-Location }
    Write-Host "FAST CHECK PASS" -ForegroundColor Green
}
finally {
    if ($null -eq $PreviousMaryDataDirectory) { Remove-Item Env:MARY_DATA_DIR -ErrorAction SilentlyContinue } else { $env:MARY_DATA_DIR = $PreviousMaryDataDirectory }
    if ($null -eq $PreviousMaryEnvironmentFile) { Remove-Item Env:MARY_ENV_FILE -ErrorAction SilentlyContinue } else { $env:MARY_ENV_FILE = $PreviousMaryEnvironmentFile }
    if ($null -eq $PreviousMaryReservoirStorage) { Remove-Item Env:MARY_RESERVOIR_STORAGE -ErrorAction SilentlyContinue } else { $env:MARY_RESERVOIR_STORAGE = $PreviousMaryReservoirStorage }
    if ($null -eq $PreviousPytestTempRoot) { Remove-Item Env:PYTEST_DEBUG_TEMPROOT -ErrorAction SilentlyContinue } else { $env:PYTEST_DEBUG_TEMPROOT = $PreviousPytestTempRoot }
    if ($null -eq $PreviousPytestAddopts) { Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue } else { $env:PYTEST_ADDOPTS = $PreviousPytestAddopts }
    if (Test-Path -LiteralPath $FastCheckRoot) {
        $ResolvedFastCheckRoot = (Resolve-Path -LiteralPath $FastCheckRoot).Path
        $ResolvedFastCheckParent = Split-Path -Parent $ResolvedFastCheckRoot
        $FastCheckLeaf = Split-Path -Leaf $ResolvedFastCheckRoot
        $attrs = [System.IO.File]::GetAttributes($ResolvedFastCheckRoot)
        if (-not $ResolvedFastCheckParent.Equals($ResolvedSystemTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe fast-check cleanup." }
        if (-not $FastCheckLeaf.StartsWith("maryv2-fast-check-", [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing unsafe fast-check cleanup prefix." }
        if (($attrs -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing reparse-point cleanup." }
        Remove-Item -LiteralPath $ResolvedFastCheckRoot -Recurse -Force
    }
}
