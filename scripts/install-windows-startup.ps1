param([Parameter(Mandatory=$true)][string]$LabUser, [switch]$Install)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$config = Join-Path $workspace 'config\client.json'
if (-not $Install) {
    Write-Output 'Review this script. To create startup tasks deliberately, rerun elevated with -LabUser COMPUTER\LabStudent -Install.'
    exit
}
$protectedRoot = [IO.Path]::GetFullPath($env:ProgramFiles) + [IO.Path]::DirectorySeparatorChar
$resolvedRoot = [IO.Path]::GetFullPath($workspace)
if (-not $resolvedRoot.StartsWith($protectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Install a reviewed, administrator-owned copy under Program Files first; SYSTEM must not execute code from a user-writable workspace.'
}
if (-not (Test-Path -LiteralPath $python)) { throw 'Create a standard CPython virtual environment first.' }
$desktop = New-ScheduledTaskAction -Execute $python -Argument "-m client --config `"$config`"" -WorkingDirectory $workspace
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $LabUser
$principal = New-ScheduledTaskPrincipal -UserId $LabUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'LabLogbookDesktop' -Action $desktop -Trigger $trigger -Principal $principal -Settings $settings
$helper = New-ScheduledTaskAction -Execute $python -Argument "-m client.helper --config `"$config`"" -WorkingDirectory $workspace
$system = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'LabLogbookHelper' -Action $helper -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $system -Settings $settings
Write-Output 'Tasks installed. They start on next logon/boot. No account, firewall, registry, or policy changes made.'
