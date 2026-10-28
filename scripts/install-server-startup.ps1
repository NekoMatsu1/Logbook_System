param([switch]$Install)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$python = Join-Path $workspace '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $workspace '.venv\bin\python.exe'
}
if (-not (Test-Path -LiteralPath $python)) { throw 'Create the project virtual environment first.' }
if (-not $Install) {
    Write-Output 'Run with -Install to register the boot task. Administrator privileges may be required.'
    exit
}
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument '-m server serve' -WorkingDirectory $workspace
$trigger = New-ScheduledTaskTrigger -AtStartup
# S4U runs as this account without storing a password or requiring an interactive login.
# It has local-file access, but no network credentials; the server uses local SQLite.
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden
Register-ScheduledTask -TaskName 'Logbook Server' -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description 'Local Flask/SQLite laboratory logbook; starts at boot and restarts on failure.' -ErrorAction Stop | Out-Null
Write-Output "Registered Logbook Server for $account. Start it with Start-ScheduledTask -TaskName 'Logbook Server'."
