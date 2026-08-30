$ErrorActionPreference = "Stop"
$TaskName = "MaryV2 Windows Capability Node"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existing) {
    Write-Host "Scheduled task is not installed: $TaskName"
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task: $TaskName"
