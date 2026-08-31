$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "MaryV2 .venv was not found. Run scripts\setup_windows.ps1 first."
}

$SecureGrant = Read-Host "Paste the one-time node enrollment grant" -AsSecureString
$GrantPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureGrant)
try {
    # Process scope only: the grant is never written to the Scheduled Task,
    # command line, user environment, or Mary credential store.
    $env:MARY_NODE_ENROLLMENT_GRANT = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($GrantPointer)
    Set-Location $Root
    & $Python -m scripts.run_windows_node --enroll-only
    if ($LASTEXITCODE -ne 0) {
        throw "MaryV2 durable node enrollment failed."
    }
    Write-Host "Migration complete. The existing Scheduled Task can now start without the enrollment grant."
}
finally {
    Remove-Item Env:MARY_NODE_ENROLLMENT_GRANT -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($GrantPointer)
}