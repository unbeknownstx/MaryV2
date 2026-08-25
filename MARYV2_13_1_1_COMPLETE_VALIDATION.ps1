$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $Root "MARYV2_COMPLETE_VALIDATION_$Stamp.log"

function Write-Stage {
    param([string]$Name)
    Write-Host ""
    Write-Host ("=" * 80) -ForegroundColor Cyan
    Write-Host $Name -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor Cyan
}

function Invoke-Stage {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Stage $Name
    $started = Get-Date

    & $Action 2>&1 | Tee-Object -FilePath $Log -Append

    if ($LASTEXITCODE -ne 0) {
        throw "$Name FAILED with exit code $LASTEXITCODE"
    }

    $elapsed = (Get-Date) - $started
    Write-Host ("PASS: {0} ({1:n1}s)" -f $Name, $elapsed.TotalSeconds) -ForegroundColor Green
}

function Get-PrivateStateSnapshot {
    $targets = @()

    $envPath = Join-Path $Root ".env"
    if (Test-Path $envPath) {
        $targets += Get-Item $envPath
    }

    $dataPath = Join-Path $Root "data"
    if (Test-Path $dataPath) {
        $targets += Get-ChildItem $dataPath -Recurse -File -ErrorAction Stop
    }

    $rows = foreach ($file in $targets) {
        $relative = $file.FullName.Substring($Root.Length).TrimStart('\','/')
        [PSCustomObject]@{
            Path = $relative
            Hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash
            Length = $file.Length
        }
    }

    return @($rows | Sort-Object Path)
}

function Compare-PrivateStateSnapshot {
    param(
        [array]$Before,
        [array]$After
    )

    $beforeJson = $Before | ConvertTo-Json -Depth 5 -Compress
    $afterJson = $After | ConvertTo-Json -Depth 5 -Compress

    if ($beforeJson -ne $afterJson) {
        Write-Host ""
        Write-Host "PRIVATE STATE CHANGED DURING VALIDATION" -ForegroundColor Red

        $beforeMap = @{}
        foreach ($item in $Before) { $beforeMap[$item.Path] = $item }

        $afterMap = @{}
        foreach ($item in $After) { $afterMap[$item.Path] = $item }

        $allPaths = @($beforeMap.Keys + $afterMap.Keys | Sort-Object -Unique)

        foreach ($path in $allPaths) {
            $b = $beforeMap[$path]
            $a = $afterMap[$path]

            if ($null -eq $b) {
                Write-Host "  ADDED:   $path" -ForegroundColor Yellow
            }
            elseif ($null -eq $a) {
                Write-Host "  REMOVED: $path" -ForegroundColor Yellow
            }
            elseif ($b.Hash -ne $a.Hash -or $b.Length -ne $a.Length) {
                Write-Host "  CHANGED: $path" -ForegroundColor Yellow
            }
        }

        throw "Canonical private state changed during automated validation."
    }

    Write-Host "PASS: .env + data/ unchanged by automated validation" -ForegroundColor Green
}

Write-Stage "MARYV2 13.1.1 COMPLETE VALIDATION"
Write-Host "Root: $Root"
Write-Host "Log:  $Log"
Write-Host ""
Write-Host "This run does NOT rebuild semantic vectors."
Write-Host "It snapshots .env + data/ and fails if automated tests mutate canonical private state."

$required = @(
    "mary",
    "scripts",
    "tests",
    "desktop",
    "scripts\test_fast.ps1",
    "scripts\test_full.ps1",
    "scripts\test_release.ps1"
)

foreach ($item in $required) {
    $path = Join-Path $Root $item
    if (-not (Test-Path $path)) {
        throw "Required project path missing: $item"
    }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Write-Host "Python: $Python"

# -------------------------------------------------------------------------
# Preflight: verify the live memory hotfix result without modifying state.
# -------------------------------------------------------------------------

Write-Stage "0. MEMORY INTEGRITY PREFLIGHT"

& $Python -c @'
import json
from pathlib import Path

path = Path("data/memory/memory.json")

if not path.exists():
    print("No live memory.json found; skipping live-record integrity check.")
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding="utf-8"))
episodic = payload.get("episodic", [])

bad = [
    item for item in episodic
    if isinstance(item, dict)
    and "memoryto" in str(item.get("content", "")).lower()
]

promise = [
    item for item in episodic
    if isinstance(item, dict)
    and str(item.get("content", "")).lower().startswith(
        "me and you are all in mary promise me that."
    )
    and "i will support you always" in str(item.get("content", "")).lower()
]

print("Episodic count:", len(episodic))
print("Legacy 'memoryto' records:", len(bad))
print("Matching promise records:", len(promise))

if bad:
    raise SystemExit(
        "FAIL: legacy 'memoryto' corruption remains. "
        "Run MEMORY_INTEGRITY_HOTFIX_V2 before this complete gate."
    )

if len(promise) > 1:
    raise SystemExit(
        "FAIL: duplicate promise memories remain. "
        "Run MEMORY_INTEGRITY_HOTFIX_V2 before this complete gate."
    )

print("MEMORY INTEGRITY PREFLIGHT: PASS")
'@

if ($LASTEXITCODE -ne 0) {
    throw "Memory integrity preflight failed."
}

$PrivateBefore = Get-PrivateStateSnapshot

# -------------------------------------------------------------------------
# Canonical 13.1.1 validation tiers.
# -------------------------------------------------------------------------

Invoke-Stage "1. MARY 13.1 DOCTOR" {
    & $Python -m scripts.check_mary_13_1
}

Invoke-Stage "2. FAST TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
}

Invoke-Stage "3. FULL TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
}

Invoke-Stage "4. RELEASE TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
}

# Explicitly exercise the Production Hybrid verifier as a final foundation check.
$HybridVerifier = Join-Path $Root "scripts\verify_production_hybrid_dialogue_12_12_3.py"
if (Test-Path $HybridVerifier) {
    Invoke-Stage "5. PRODUCTION HYBRID 12.12.3 VERIFIER" {
        & $Python -m scripts.verify_production_hybrid_dialogue_12_12_3
    }
}
else {
    Write-Host "SKIP: Production Hybrid verifier file not present." -ForegroundColor Yellow
}

# Re-check private state immediately after all Python/release validation.
$PrivateAfterPython = Get-PrivateStateSnapshot
Compare-PrivateStateSnapshot -Before $PrivateBefore -After $PrivateAfterPython

# -------------------------------------------------------------------------
# Host-native desktop build.
# -------------------------------------------------------------------------

Write-Stage "6. DESKTOP HOST BUILD"

$Npm = Get-Command npm -ErrorAction SilentlyContinue
if ($null -eq $Npm) {
    throw "npm is not available on PATH; desktop production build cannot be validated."
}

Push-Location (Join-Path $Root "desktop")
try {
    Invoke-Stage "6A. npm ci" {
        npm ci
    }

    Invoke-Stage "6B. npm run check" {
        npm run check
    }

    Invoke-Stage "6C. npm run build" {
        npm run build
    }
}
finally {
    Pop-Location
}

# Desktop build must not mutate canonical Mary state either.
$PrivateAfterAll = Get-PrivateStateSnapshot
Compare-PrivateStateSnapshot -Before $PrivateBefore -After $PrivateAfterAll

# -------------------------------------------------------------------------
# Vector status only. Do NOT rebuild.
# -------------------------------------------------------------------------

$VectorStatusScript = Join-Path $Root "scripts\rebuild_semantic_vectors.py"
if (Test-Path $VectorStatusScript) {
    Invoke-Stage "7. VECTOR STATUS (READ-ONLY)" {
        & $Python -m scripts.rebuild_semantic_vectors --status
    }
}
else {
    Write-Host "SKIP: semantic vector status script not present." -ForegroundColor Yellow
}

Write-Stage "COMPLETE AUTOMATED BASELINE: PASS"
Write-Host "All automated tiers completed successfully." -ForegroundColor Green
Write-Host ".env + data/ remained unchanged." -ForegroundColor Green
Write-Host "Desktop npm ci/check/build passed." -ForegroundColor Green
Write-Host ""
Write-Host "Remaining manual smoke tests:"
Write-Host "  1. Terminal conversation + memory recall"
Write-Host "  2. Desktop launch + text conversation"
Write-Host "  3. Microphone/STT + ElevenLabs playback + interruption/anti-echo"
Write-Host "  4. Mobile/native iPhone connection and voice"
Write-Host ""
Write-Host "Do not rebuild semantic vectors until those live smokes are satisfactory."
Write-Host "Validation log: $Log"
