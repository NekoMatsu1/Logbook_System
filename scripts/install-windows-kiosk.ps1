param([Parameter(Mandatory=$true)][string]$LabUser, [switch]$Install, [switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $Install -and -not $Uninstall) {
    Write-Output 'Review first. On a dedicated lab PC, run elevated with -LabUser COMPUTER\LabStudent -Install or -Uninstall.'
    exit
}
if ($Install -and $Uninstall) { throw 'Choose one action.' }
$identity = New-Object Security.Principal.NTAccount($LabUser)
$sid = $identity.Translate([Security.Principal.SecurityIdentifier]).Value
if ($sid -eq [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) { throw 'Refusing to replace the shell of the account running this installer. Use a separate standard lab account.' }
$protectedRoot = [IO.Path]::GetFullPath($env:ProgramFiles) + [IO.Path]::DirectorySeparatorChar
if (-not ([IO.Path]::GetFullPath($root)).StartsWith($protectedRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Install a protected administrator-owned copy under Program Files first.' }
$feature = Get-WindowsOptionalFeature -Online -FeatureName Client-EmbeddedShellLauncher
if ($feature.State -ne 'Enabled') { throw 'Shell Launcher is unavailable/not enabled. Requires Windows Enterprise/Education/IoT; enable it deliberately and reboot first.' }
$launcher = [wmiclass]'\\localhost\root\standardcimv2\embedded:WESL_UserSetting'
$backupDir = Join-Path $env:ProgramData 'LabLogbook'
$backup = Join-Path $backupDir "kiosk-$sid.json"
$hive = "Registry::HKEY_USERS\$sid"
if (-not (Test-Path -LiteralPath $hive)) { throw 'Lab account registry hive is not loaded. Sign into that account once, switch to an administrator, then retry.' }
$policies = @(
    @{Path="$hive\Software\Microsoft\Windows\CurrentVersion\Policies\System";Name='DisableTaskMgr'},
    @{Path="$hive\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer";Name='NoRun'},
    @{Path="$hive\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer";Name='NoWinKeys'}
)
if ($Uninstall) {
    if (-not (Test-Path -LiteralPath $backup)) { throw 'No rollback backup found.' }
    $saved = Get-Content -LiteralPath $backup -Raw | ConvertFrom-Json
    $result = $launcher.RemoveCustomShell($sid)
    if ($result.ReturnValue -ne 0) { throw "RemoveCustomShell failed: $($result.ReturnValue)" }
    if ($saved.PreviousShell.Shell) {
        $result = $launcher.SetCustomShell($sid,$saved.PreviousShell.Shell,$saved.PreviousShell.CustomReturnCodes,$saved.PreviousShell.CustomReturnCodesAction,$saved.PreviousShell.DefaultAction)
        if ($result.ReturnValue -ne 0) { throw 'Restoring previous lab shell failed.' }
    }
    foreach ($value in $saved.Policies) {
        if ($value.Exists) { Set-ItemProperty -LiteralPath $value.Path -Name $value.Name -Value $value.Value -Type DWord }
        else { Remove-ItemProperty -LiteralPath $value.Path -Name $value.Name -ErrorAction SilentlyContinue }
    }
    if ($saved.PreviousDefault.Shell) { $result = $launcher.SetDefaultShell($saved.PreviousDefault.Shell,$saved.PreviousDefault.DefaultAction) }
    Write-Output 'Lab shell/policies restored. Backup retained for audit; no forced logoff/reboot.'
    exit
}
if (Test-Path -LiteralPath $backup) { throw 'Rollback backup already exists. Review the existing installation before changing it.' }
$localAccount = Get-LocalUser -SID $sid -ErrorAction Stop
if (Get-LocalGroupMember -SID 'S-1-5-32-544' | Where-Object { $_.SID.Value -eq $sid }) { throw 'The lab account must be a standard local account, not an administrator.' }
$python = Join-Path $root '.venv\Scripts\python.exe'
$configPath = Join-Path $root 'config\client.json'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create a standard CPython venv in the protected installation.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.simulation -ne $false) { throw 'Live kiosk installation requires the administrator to explicitly set simulation=false on this dedicated lab PC first.' }
# Reject broad write permissions on the root. Effective nested ACLs still require administrator review.
$unsafeSids = @($sid,'S-1-1-0','S-1-5-11','S-1-5-32-545')
foreach ($rule in (Get-Acl -LiteralPath $root).Access) {
    $ruleSid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
    if ($rule.AccessControlType -eq 'Allow' -and $unsafeSids -contains $ruleSid -and ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Write)) { throw 'Installation directory is writable by the lab account or a broad user group.' }
}
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$previous = foreach ($value in $policies) {
    $item = Get-ItemProperty -LiteralPath $value.Path -Name $value.Name -ErrorAction SilentlyContinue
    @{Path=$value.Path;Name=$value.Name;Exists=($null -ne $item);Value=if ($item) {$item.($value.Name)} else {$null}}
}
@{Policies=$previous;PreviousShell=$launcher.GetCustomShell($sid);PreviousDefault=$launcher.GetDefaultShell()} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $backup -Encoding UTF8
Set-Location -LiteralPath $root
& $python -m client.credentials --protect $configPath
if ($LASTEXITCODE) { throw 'Machine credential sealing failed.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$config | Add-Member -NotePropertyName kiosk_shell_installed -NotePropertyValue $true -Force
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
foreach ($value in $policies) {
    New-Item -Path $value.Path -Force | Out-Null
    New-ItemProperty -LiteralPath $value.Path -Name $value.Name -Value 1 -PropertyType DWord -Force | Out-Null
}
$shell = '"' + $python + '" "' + (Join-Path $root 'scripts\kiosk_entry.py') + '" --config "' + $configPath + '"'
$result = $launcher.SetDefaultShell('explorer.exe',0)
if ($result.ReturnValue -ne 0) { throw 'Could not preserve the normal administrator shell.' }
$result = $launcher.SetCustomShell($sid,$shell,$null,$null,0)
if ($result.ReturnValue -ne 0) { throw "SetCustomShell failed: $($result.ReturnValue). Roll back using the saved backup." }
$result = $launcher.SetEnabled($true)
if ($result.ReturnValue -ne 0) { throw 'Enabling Shell Launcher failed.' }
Write-Output 'Installed for next lab-account logon. No forced sign-out/reboot. Keep a separate administrator account for recovery.'
