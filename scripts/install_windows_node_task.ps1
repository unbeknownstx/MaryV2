$ErrorActionPreference = "Stop"

$Root = (Split-Path -Parent $PSScriptRoot)
$Launcher = Join-Path $Root "scripts\launch_windows_node.ps1"
$TaskName = "MaryV2 Windows Capability Node"

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
    -Description "MaryV2 headless Windows capability node. Exposes approved local capabilities such as Ollama to canonical Mary Core; does not launch Desktop or own Mary state." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "The task starts at your Windows logon and runs the headless capability node only."
Write-Host "Run it now with: Start-ScheduledTask -TaskName '$TaskName'"
