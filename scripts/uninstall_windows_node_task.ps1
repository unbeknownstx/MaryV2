$ErrorActionPreference = "Stop"

$TaskNames = @(
    "MaryV2 Home Capability Node",
    "MaryV2 Windows Capability Node"
)

$removed = $false
foreach ($TaskName in $TaskNames) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        continue
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task: $TaskName"
    $removed = $true
}

if (-not $removed) {
    Write-Host "No MaryV2 Windows capability-node scheduled task is installed."
}
