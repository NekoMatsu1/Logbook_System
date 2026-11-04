param([string]$LabUser, [string]$ConfigPath)
# Read-only diagnostics. This script never changes a shell, account, policy or config.
$ErrorActionPreference = 'Stop'
if (-not $ConfigPath) { $ConfigPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'config\client.json' }
$issues = 0
function Report-Problem([string]$Message) { Write-Output "NOT READY: $Message"; $script:issues++ }
$os = Get-CimInstance Win32_OperatingSystem
Write-Output "Windows: $($os.Caption)"
if ($os.Caption -notmatch 'Enterprise|Education|IoT') {
    Report-Problem 'This installer requires Windows Enterprise/Education/IoT Enterprise with Shell Launcher. A normal startup app cannot enforce sign-in.'
}
if (Test-Path -LiteralPath $ConfigPath) {
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
    if ($config.simulation -ne $false) { Report-Problem 'Simulation is enabled. It does not block the desktop.' }
    if ($config.kiosk_shell_installed -ne $true) { Report-Problem 'The managed shell has not been marked installed.' }
} else { Report-Problem 'No private client configuration at the specified path.' }
if ($LabUser) {
    $account = New-Object Security.Principal.NTAccount($LabUser)
    $sid = $account.Translate([Security.Principal.SecurityIdentifier]).Value
} else { $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value }
try {
    if (Get-LocalGroupMember -SID 'S-1-5-32-544' | Where-Object { $_.SID.Value -eq $sid }) {
        Report-Problem 'The lab account belongs to Administrators. Use a dedicated standard account.'
    }
    $launcher = [wmiclass]'\\localhost\root\standardcimv2\embedded:WESL_UserSetting'
    $enabled = $launcher.IsEnabled()
    $shell = $launcher.GetCustomShell($sid)
    if ($enabled.ReturnValue -ne 0 -or -not $enabled.Enabled) { Report-Problem 'Windows Shell Launcher is not enabled.' }
    if ($shell.ReturnValue -ne 0 -or $shell.Shell -notmatch 'kiosk_entry\.py|Logbook\.exe') {
        Report-Problem 'The target account does not have the Logbook managed shell.'
    }
} catch { Report-Problem 'Could not verify account/Shell Launcher. Ask the lab administrator to run this check elevated with -LabUser.' }
if ($issues) { Write-Output 'Do not treat this PC as enforced. Follow KIOSK-SETUP.md on a dedicated lab PC.'; exit 2 }
Write-Output 'Basic setup checks passed. Bypass, crash recovery, network and real sign-out tests are still required.'
