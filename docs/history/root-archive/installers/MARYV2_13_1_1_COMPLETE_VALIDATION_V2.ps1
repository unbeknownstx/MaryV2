$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Log = Join-Path $Root "MARYV2_COMPLETE_VALIDATION_V2_$Stamp.log"

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
            Path   = $relative
            Hash   = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash
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

    $beforeMap = @{}
    foreach ($item in $Before) {
        $beforeMap[$item.Path] = $item
    }

    $afterMap = @{}
    foreach ($item in $After) {
        $afterMap[$item.Path] = $item
    }

    $allPaths = @($beforeMap.Keys + $afterMap.Keys | Sort-Object -Unique)
    $changes = @()

    foreach ($path in $allPaths) {
        $b = $beforeMap[$path]
        $a = $afterMap[$path]

        if ($null -eq $b) {
            $changes += "ADDED: $path"
        }
        elseif ($null -eq $a) {
            $changes += "REMOVED: $path"
        }
        elseif ($b.Hash -ne $a.Hash -or $b.Length -ne $a.Length) {
            $changes += "CHANGED: $path"
        }
    }

    if ($changes.Count -gt 0) {
        Write-Host ""
        Write-Host "PRIVATE STATE CHANGED DURING VALIDATION" -ForegroundColor Red
        foreach ($change in $changes) {
            Write-Host "  $change" -ForegroundColor Yellow
        }
        throw "Canonical private state changed during automated validation."
    }

    Write-Host "PASS: .env + data/ unchanged by automated validation" -ForegroundColor Green
}

Write-Stage "MARYV2 13.1.1 COMPLETE VALIDATION V2"
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
# 0. Read-only live memory integrity preflight (PowerShell-native).
# -------------------------------------------------------------------------

Write-Stage "0. MEMORY INTEGRITY PREFLIGHT"

$MemoryFile = Join-Path $Root "data\memory\memory.json"

if (Test-Path $MemoryFile) {
    $MemoryObject = Get-Content -Raw -Path $MemoryFile | ConvertFrom-Json
    $Episodic = @($MemoryObject.episodic)

    $Bad = @(
        $Episodic | Where-Object {
            $_ -and $_.content -and
            ([string]$_.content).ToLowerInvariant().Contains("memoryto")
        }
    )

    $Promise = @(
        $Episodic | Where-Object {
            if (-not $_ -or -not $_.content) {
                return $false
            }

            $content = ([string]$_.content).ToLowerInvariant()

            return (
                $content.StartsWith("me and you are all in mary promise me that.") -and
                $content.Contains("i will support you always")
            )
        }
    )

    Write-Host ("Episodic count: {0}" -f $Episodic.Count)
    Write-Host ("Legacy 'memoryto' records: {0}" -f $Bad.Count)
    Write-Host ("Matching promise records: {0}" -f $Promise.Count)

    if ($Bad.Count -gt 0) {
        throw (
            "Legacy 'memoryto' corruption remains. " +
            "Run MARYV2_13_1_1_MEMORY_INTEGRITY_HOTFIX_V2.ps1 first."
        )
    }

    if ($Promise.Count -gt 1) {
        throw (
            "Duplicate promise memories remain. " +
            "Run MARYV2_13_1_1_MEMORY_INTEGRITY_HOTFIX_V2.ps1 first."
        )
    }

    Write-Host "MEMORY INTEGRITY PREFLIGHT: PASS" -ForegroundColor Green
}
else {
    Write-Host "No live memory.json found; skipping live-record integrity check." -ForegroundColor Yellow
}

$PrivateBefore = Get-PrivateStateSnapshot

# -------------------------------------------------------------------------
# 1. Doctor
# -------------------------------------------------------------------------

$DoctorScript = Join-Path $Root "scripts\check_mary_13_1.py"
if (Test-Path $DoctorScript) {
    Invoke-Stage "1. MARY 13.1 DOCTOR" {
        & $Python -m scripts.check_mary_13_1
    }
}
else {
    Write-Host "SKIP: scripts\check_mary_13_1.py not present." -ForegroundColor Yellow
}

# -------------------------------------------------------------------------
# 2. Fast
# -------------------------------------------------------------------------

Invoke-Stage "2. FAST TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
}

# -------------------------------------------------------------------------
# 3. Full
# -------------------------------------------------------------------------

Invoke-Stage "3. FULL TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
}

# -------------------------------------------------------------------------
# 4. Release
# -------------------------------------------------------------------------

Invoke-Stage "4. RELEASE TEST TIER" {
    powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
}

# -------------------------------------------------------------------------
# 5. Explicit Production Hybrid verifier
# -------------------------------------------------------------------------

$HybridVerifier = Join-Path $Root "scripts\verify_production_hybrid_dialogue_12_12_3.py"
if (Test-Path $HybridVerifier) {
    Invoke-Stage "5. PRODUCTION HYBRID 12.12.3 VERIFIER" {
        & $Python -m scripts.verify_production_hybrid_dialogue_12_12_3
    }
}
else {
    Write-Host "SKIP: Production Hybrid verifier not present." -ForegroundColor Yellow
}

# -------------------------------------------------------------------------
# Private state must still be unchanged after all Python/release validation.
# -------------------------------------------------------------------------

$PrivateAfterPython = Get-PrivateStateSnapshot
Compare-PrivateStateSnapshot -Before $PrivateBefore -After $PrivateAfterPython

# -------------------------------------------------------------------------
# 6. Desktop host-native build
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

$PrivateAfterAll = Get-PrivateStateSnapshot
Compare-PrivateStateSnapshot -Before $PrivateBefore -After $PrivateAfterAll

# -------------------------------------------------------------------------
# 7. Vector status only -- no rebuild.
# -------------------------------------------------------------------------

$VectorStatusScript = Join-Path $Root "scripts\rebuild_semantic_vectors.py"
if (Test-Path $VectorStatusScript) {
    Invoke-Stage "7. VECTOR STATUS (READ-ONLY)" {
        & $Python -m scripts.rebuild_semantic_vectors --status
    }
}
else {
    Write-Host "SKIP: semantic-vector status script not present." -ForegroundColor Yellow
}

Write-Stage "COMPLETE AUTOMATED BASELINE: PASS"
Write-Host "All automated tiers completed successfully." -ForegroundColor Green
Write-Host ".env + data/ remained unchanged." -ForegroundColor Green
Write-Host "Desktop npm ci/check/build passed." -ForegroundColor Green
Write-Host ""
Write-Host "Manual smokes remaining after this:"
Write-Host "  - terminal conversation + recall"
Write-Host "  - desktop launch + text conversation"
Write-Host "  - microphone/STT + ElevenLabs playback + interruption/anti-echo"
Write-Host "  - mobile/native iPhone connection + voice"
Write-Host ""
Write-Host "Do not rebuild semantic vectors until the live smokes are satisfactory."
Write-Host "Validation log: $Log"
