$ErrorActionPreference = "Stop"

$Root = (Split-Path -Parent $PSScriptRoot)
$Launcher = Join-Path $Root "scripts\launch_home_node_windows.ps1"
$TaskName = "MaryV2 Home Capability Node"
$LegacyTaskName = "MaryV2 Windows Capability Node"

$legacy = Get-ScheduledTask -TaskName $LegacyTaskName -ErrorAction SilentlyContinue
if ($null -ne $legacy) {
    Unregister-ScheduledTask -TaskName $LegacyTaskName -Confirm:$false
    Write-Host "Removed legacy scheduled task: $LegacyTaskName"
}

if (-not (Test-Path $Launcher)) {
    throw "MaryV2 Windows node launcher was not found: $Launcher"
}

$UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Launcher`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $UserId
$Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "MaryV2 canonical Windows home capability node. Uses the bounded hardware profile, exposes approved local capabilities to Mary Core, and never owns Mary state." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "The task starts the canonical home capability node at Windows logon."
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"
