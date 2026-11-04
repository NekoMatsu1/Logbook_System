# Monitoring and student access

## Admin access without repeated reloads

Use [password login](deploy/PASSWORD-ADMIN.md). This needs one private console
setup and one Web-tab reload. After that, sign in at the same dashboard URL from
any network. No IP changes, Google OAuth setup or authenticator app is needed.
The server does not need restarting for normal monitoring. Dashboard data refreshes
every 10 seconds, reports a lost connection and retries automatically.

Code updates and credential resets still require a reload. PythonAnywhere free
hosting still needs monthly renewal and has capacity limits. An offline PC on
the dashboard means heartbeats stopped; it does not prove the student logged out.

## Why students can still use Windows

The portable client and `simulation: true` are for testing. They cannot stop
someone using the normal Windows desktop. Registration/login in a window is
not an OS access restriction. The app starts through its supervisor, but strict
enforcement needs a managed OS shell installed for the dedicated standard lab
account. Do not install that shell on the owner's everyday admin account.

On the actual lab PC, the administrator can run this read-only check from the
project folder (replace the account name):

```powershell
.\scripts\check-windows-kiosk.ps1 -LabUser 'COMPUTERNAME\LabStudent'
```

It checks edition, simulation settings, account membership and managed-shell
registration. It does not expose tokens or change Windows. Not-ready results
must be resolved using [KIOSK-SETUP.md](KIOSK-SETUP.md), with a separate recovery
administrator account. The current Windows installer supports Enterprise,
Education and IoT Enterprise. It does not enforce desktop access on Home/Pro.

Required acceptance on each target setup: registration alone does not open the
desktop; invalid IDs and no network cannot start a session; only the server's
confirmed active session opens it; client crash/restart returns to the gate;
normal sign-out ends access; other accounts/keyboard shortcuts/alternate startup
paths cannot bypass the lab's OS policies. These need actual-machine testing.

Simulation still offers the student Log out button. The native managed account
can use Windows Sign out; records use confirmed OS events when available. Never
invent a logout time when a crash or network outage prevents confirmation.
