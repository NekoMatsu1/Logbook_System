# Require student identification before desktop use

Implemented: a supervised shell, server-confirmed authorization, Windows isolated login desktop, deferred Explorer launch, Mint X11 deferred Cinnamon session, work-desktop inactivity warnings, lock-on-client-exit/restart, machine-bound Windows credential sealing, and separate deliberate installation/rollback paths. **No kiosk policy, shell, account, startup or power setting was applied to the development laptop.** Actual enforced operation still requires a dedicated standard account, supported OS edition, protected installation, deployment-policy review and real-machine testing.

## Safe simulation on the development laptop

Keep `simulation: true`. From the project directory:

```powershell
.\.venv\bin\python.exe -m client.kiosk --config config/client.json
```

Close any previously running desktop agent first; one agent is permitted. Simulation does not switch OS desktops, start/kill Explorer or Cinnamon, sign out, or shut down. It logs intended gate/power actions and uses the real student UI/API. It is a demonstration, not an enforced lock. The client config may be sealed with Windows DPAPI; this changes only that credential file, not OS trust/settings or session data. A protected credential file copied to another Windows machine cannot be decrypted there. The server also restricts client API source networks when configured/in production.

The supervisor starts locked and verifies `/api/sessions/<id>` for the same machine/run before permitting desktop access. It does not grant access on registration, unknown IDs, failed/ambiguous network results, stale sessions or a client UI crash. It does not relock a legitimately active student merely for a heartbeat failure. A due inactivity end emits a lock before requesting OS sign-out. Desktop availability and database status remain separate facts; normal OS sign-out is best-effort recorded, while crashes retain unknown end times.

## Windows 10/11 enforcement

The enforced installer uses Microsoft's **Shell Launcher**, available on **Enterprise, Education and IoT Enterprise** editions. Windows Home/Pro can run the student prototype but this installer refuses to claim enforced shell support there. Do not substitute a startup shortcut/fullscreen window and call it secure. [Microsoft edition and security requirements](https://learn.microsoft.com/en-us/windows/configuration/shell-launcher/).

1. Use a dedicated lab PC or disposable VM with a separate administrator recovery account. Create a **standard shared lab account**, not the laptop owner's account. Students use IDs in the app, not administrator/SSH/provider credentials.
2. Put reviewed code and a fresh CPython virtual environment under `C:\Program Files\LabLogbook`. Administrators/SYSTEM must own and be the only writers of code, interpreter, launchers and config. Give the lab account read/execute access only. Review nested ACLs, group membership, profile startup entries, removable media/boot settings and application allowlisting; the installer checks the root ACL, not every effective permission.
3. Provision that machine centrally and install its config at `config\client.json`. Keep simulation while testing basic networking. Explicitly set `simulation: false` only when ready for **real** OS logout/shutdown on this dedicated machine. The installer will not make that change for you.
4. Enable the supported OS component deliberately in an elevated administrator PowerShell, then reboot if Windows requests it:

```powershell
Enable-WindowsOptionalFeature -FeatureName Client-DeviceLockdown,Client-EmbeddedShellLauncher -Online
```

5. Sign into the lab account once to create/load its profile, then switch to the separate administrator. From the protected installation, review and run:

```powershell
.\scripts\install-windows-kiosk.ps1 -LabUser 'COMPUTERNAME\LabStudent'
.\scripts\install-windows-kiosk.ps1 -LabUser 'COMPUTERNAME\LabStudent' -Install
```

It refuses the installing account as the target, requires enabled Shell Launcher/protected location, backs up shell/policy settings under `C:\ProgramData\LabLogbook`, seals the machine token, and installs a per-account supervised shell plus task-manager/Run/hotkey restrictions. Other accounts retain Explorer for recovery. Changes apply on next lab-account logon; it does not forcibly sign out/reboot. Review failures and roll back before using the account; installation is not an all-or-nothing OS transaction.

Before authorization, the UI runs on an isolated Windows desktop and the normal work desktop is not made interactive by this supervisor. After server confirmation it switches to the normal desktop and launches Explorer. A separate no-content warning process shows inactivity countdowns on the work desktop. The global input sampler uses a worker thread attached to the active input desktop, not just Tkinter events. Secure Winlogon/UAC desktops are not bypassed; unavailable global input pauses automatic actions.

**Security limit:** Shell Launcher alone does not prevent access to other apps/system components, as Microsoft explicitly documents. The same shared OS identity can run code after authorization; malicious persistence, modified startup programs, alternative boot/logon paths or compromised clients require institutional application-control/profile/boot policies. DPAPI and desktop isolation are not TPM attestation or a separate student security principal. Validate bypass attempts with your network/Windows administrator before deployment. This code is not a Windows credential provider and does not display cancellable warnings on the secure OS sign-in screen.

Rollback from the separate administrator account:

```powershell
.\scripts\install-windows-kiosk.ps1 -LabUser 'COMPUTERNAME\LabStudent' -Uninstall
```

It restores the backed-up per-user restrictions/custom shell and previous default shell, retaining the backup. Never delete the recovery administrator or disable its access. Install/review the separate boot helper only after interactive kiosk validation; see the main README. No actual Windows shell switching, installation, shutdown or sign-out has been executed in tests here.

## Linux Mint X11 enforcement

Use LightDM + Cinnamon X11 and a dedicated standard shared lab account with no sudo privileges. Wayland is not implemented. Keep the code and venv root-owned at `/opt/lab-logbook` and credentials in `/etc/lab-logbook/client.json`. Other users must not be able to modify code launched by LightDM/root helpers. Keep a separate administrator recovery account/console.

After the account, network and simulation tests, explicitly change `simulation: false` on that dedicated machine, review the installer, and run:

```bash
sudo sh scripts/install-linux-kiosk.sh --install labstudent
```

The installer refuses the invoking administrator/root as the target, checks root-owned/non-writable code, installs a LightDM session wrapper specifically for the lab account, and preserves the normal Xsession for other accounts. The wrapper runs the student supervisor regardless of that lab user's selected greeter session, so selecting a normal Cinnamon entry does not intentionally bypass it. Cinnamon is launched only after central authorization. Ending the managed session returns to LightDM. No display-manager restart/power action happens during installation.

For rollback, as the recovery administrator, remove `/etc/lightdm/lightdm.conf.d/60-lab-logbook.conf` or restore its previous contents from `/etc/lab-logbook/kiosk-backup/lightdm.conf` if one existed. Changes take effect at a subsequent logon. Do not restart LightDM while users have unsaved work.

Review existing custom session-wrapper configuration, profile/autostart executables, alternate virtual-terminal access, display-server permissions, standard-account credentials and physical/boot policy. X11 is not a security boundary against arbitrary code already running under the shared account. This installer does not configure display-manager automatic login, greeter mouse-cancellation warnings, PAM identity gates, or every distribution policy. Actual LightDM/Cinnamon logout, wrapper selection, alternate-session bypass and recovery must be tested on a real Mint machine. They were not tested on this Windows laptop.

## Required live acceptance

Test with a separate recovery account first: OS logon shows student login instead of an interactive work desktop; registration alone does not open apps; valid confirmed ID opens the desktop; no network prevents new sessions; repeated focus cannot bypass timers; keyboard/Alt+Tab/Win+R/Task Manager/greeter selection do not bypass your chosen OS policies; client crash/restart remains gated; inactivity warnings appear while another app is open; confirmed sign-out returns to the login flow; machine/network revocation rejects future logins; and administrator history cannot be reached with lab-PC credentials. Fake-adapter tests validate the protocol/state logic, not successful OS deployment.
