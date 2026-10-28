# Full setup guide

The portable client now has manual **Log out** in its session window. Closing the window minimizes it to the taskbar. Older references below to having no End Session control describe the earlier version; see [current logout instructions](DOWNLOAD.md#student-logout).

Latest implementation: owner-only Google administrator sign-in from any network, lab-source-network checks plus revocable machine credentials for students, Windows machine-bound credential protection, and a supervised native shell/session gate are implemented. See [KIOSK-SETUP.md](KIOSK-SETUP.md) for deliberate lab-account installation and [deploy/PYTHONANYWHERE.md](deploy/PYTHONANYWHERE.md) for free hosting. Those accounts/OS policies are not configured automatically: a normal portable test window still does not enforce kiosk access, and no cloud host has been created. The local/LAN prototype instructions below remain available.

For remote hosting that continues when this laptop is off, see [deploy/README.md](deploy/README.md). It includes the free-hosting constraints, production security boundary, persistent Docker deployment and SSH-only administrator access. Deployment files are prepared; no cloud host has been provisioned. Production mode now enforces stricter rules than the local-development defaults below.

Local Flask/SQLite server, private web administrator dashboard, and installed Tkinter student agent. Student registration and ID-only login live in the desktop program. OS operations default to **simulation**. No password screens, End Session button, offline login, client student database, local session journal, screenshots, screen viewing, or keystroke recording.

## Run the already-prepared workspace

This laptop's `python` command is a Windows Store alias. An existing MSYS2 Python 3.12 with Tkinter was found and used to create `.venv`. Its executable lives in `bin`, unlike a standard Windows CPython virtual environment. Dependencies are installed. From this workspace, run these in **separate VS Code PowerShell terminals**:

```powershell
# Terminal 1: central server (keep running)
.\.venv\bin\python.exe -m server serve
```

```powershell
# Terminal 2: student program
.\.venv\bin\python.exe -m client --config config/client.json
```

Dashboard: **http://127.0.0.1:5000/admin/overview**. Default computer: `LAB-PC-01`.

Local credentials and a fresh database have been provisioned. Short development timers are applied to this local database: 15-second inactivity, 10-second logout warning, 30-second no-session wait, 10-second shutdown warning, 15-second identification timeout. Production defaults in code remain 300/60/600/60/60 seconds. The token is in ignored `config/client.json`; do not publish it. No student records are preloaded.

```powershell
# Run the automated suite, including real Tk windows with simulated input/power
$env:LOGBOOK_GUI_TEST = '1'
.\.venv\bin\python.exe -m pytest -q
.\.venv\bin\python.exe -m compileall -q server client common.py tests
git diff --check
```

The MSYS2 interpreter needed interpreter-compatible builds of MarkupSafe and charset-normalizer. These were built in a temporary environment outside this workspace, whose literal `$HOME` directory name confuses setuptools source builds, and installed into the local venv. Use standard CPython for a new Windows installation; its normal pip commands below do not need that workaround. `python -m pip check` verifies the local environment.

## Fresh Windows 10/11 setup

Install standard 64-bit Python **3.11 or newer** from python.org with Tcl/Tk and the `py` launcher. Git/VS Code are optional. No Node dependency is needed. From the project directory:

```powershell
py -3 --version
py -3 -m tkinter
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m server init
.\.venv\Scripts\python.exe -m server provision --computer LAB-PC-01 --output config/client.json
.\.venv\Scripts\python.exe -m server dev-timers
.\.venv\Scripts\python.exe -m pytest -q
```

Close the Tcl/Tk test window. Provision once: the command deliberately refuses to overwrite a credential file or an already-provisioned computer. For a clean installation, `scripts/setup.ps1` performs environment creation, dependency installation, database initialization, and provisioning; it does not change OS configuration. Run it only on a fresh checkout. Existing environments should use their current executable rather than rerunning setup over them.

Separate VS Code terminals:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m server serve
```

```powershell
# Terminal 2
.\.venv\Scripts\python.exe -m client --config config/client.json
```

## Fresh Linux Mint setup

Use a Cinnamon **X11** session. Wayland global input monitoring is not implemented, including through XWayland. The desktop program refuses new sessions if global activity monitoring fails.

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk libx11-6 libxss1
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m server init
.venv/bin/python -m server provision --computer LAB-PC-01 --output config/client.json
chmod 600 config/client.json
.venv/bin/python -m server dev-timers
.venv/bin/python -m pytest -q
```

Separate terminals:

```bash
# Terminal 1
.venv/bin/python -m server serve
```

```bash
# Terminal 2
.venv/bin/python -m client --config config/client.json
```

For the opt-in Tk integration test on an interactive desktop:

```bash
LOGBOOK_GUI_TEST=1 .venv/bin/python -m pytest -q
```

`sh scripts/setup-linux.sh` automates the non-sudo environment/provisioning steps on a fresh checkout. It does not install startup integration or modify accounts/policies.

## One-laptop manual walkthrough

1. Keep `simulation: true` in `config/client.json`. Start server and agent. The program visibly labels simulation. Open the dashboard; `LAB-PC-01` should become available after a heartbeat.
2. Select Register. Enter student ID `000123` and a full name. Registration must succeed once and reject a duplicate. Select Login, enter that ID, and verify the displayed registered name before confirming. An unknown ID must be rejected.
3. Confirm login. The login window withdraws so normal applications can be used. Overview should show the student and computer in use. Records should contain one active session with no logout time.
4. Leave keyboard and mouse idle for 15 seconds with development timers. The “Are you still working?” warning appears with a 10-second countdown and an unsaved-work warning. Activity anywhere on the desktop cancels it. Repeat and do nothing: the central record completes with `simulated_inactivity`, the console logs simulated OS logout, and the login window returns for another student. Nothing signs out the actual OS account.
5. With no student active, leave the form alone. After 30 seconds the shutdown warning appears. A key or stationary mouse click must not cancel it. Moving the mouse resets the wait. Ignore it on the next attempt: simulation is shown/logged and no actual shutdown occurs. Move the mouse away from the form while testing to avoid starting identification accidentally.
6. Begin typing identification partway through the shutdown wait. The wait pauses. Cancel resumes the remaining wait. Repeated focus changes must not extend the 15-second identification timeout; abandon the form to test resumption.
7. Stop the server while a student is active. The agent keeps the session and cached timers, and rejects registration/new sessions. A heartbeat failure alone never logs the student out. If inactivity ends while disconnected, the UI states that the end was not saved. Restart the server: the next heartbeat flags an unfinished central record as interrupted if the agent no longer has that session. No logout time is invented.
8. For an agent-crash test, terminate only the agent process from its terminal while active, then restart it. The new run ID marks the old record interrupted with unknown logout/duration. Closing a normal window is not reported as OS sign-out.
9. Filter records by exact student/computer ID and Manila login date. Export CSV and inspect only matching rows. Spreadsheet formula prefixes are neutralized. Import student ID columns as text in spreadsheet applications to retain leading zeros.
10. Edit a student name/deactivate the registration; old session names remain unchanged, while deactivated IDs cannot start new sessions. Test per-computer settings overrides and operational events. Allow up to 10 seconds for a settings heartbeat or dashboard refresh.

## Configuration and central persistence

`config/client.example.json` documents a placeholder-only configuration. Provisioning generates a random per-machine token, stores only its SHA-256 hash centrally, and writes the actual token into an ignored local config. Protect that file with OS ACLs. The example token is unusable. For production, provision each PC centrally with a distinct computer ID and transfer its config securely; edit `server_url` to the HTTPS origin and set `allow_loopback_http: false`. Certificate verification is always enabled. No certificate-verification bypass exists.

Only an **explicit JSON boolean** `"simulation": false` enables real OS operations. Do not make that change on your development laptop. Live logout/shutdown commands are implemented but were not executed in development or tests. Logs make simulated actions explicit. On Windows, real logout uses `ExitWindowsEx`; shutdown uses `shutdown.exe`. On Mint Cinnamon, logout uses `cinnamon-session-quit`; shutdown uses `systemctl poweroff`. OS permissions and cancellation behavior require real-machine validation.

The SQLite schema is version 2, initialized/upgraded idempotently by `python -m server init`. Its transactional v1→v2 migration preserves registrations, machines and session history while adding machine revocation and administrator identity/session tables. Unsupported versions are rejected; back up before migration. SQLite transactions, unique session IDs, and a partial unique index enforce one active session per computer. Start retries reuse the original session ID. A lost start acknowledgement blocks further identification/shutdown while that same request is resolved. Ending an ended record is idempotent. Retired agent runs cannot reclaim the machine with delayed heartbeats.

All stored timestamps are UTC; dashboard and date filters use Asia/Manila. Offline status is derived from the effective heartbeat timeout (45 seconds by default). An offline PC may still have an active central record: offline is not proof of sign-out. A new agent run, same-run report of no local session, or privileged helper observation of no OS session establishes interruption. Interrupted rows retain null logout time and duration.

There is no client session log or delayed synchronization. If the client/OS disappears before an acknowledged end, the exact end time, unsaved end reason, and outage events are unrecoverable. Communication failures are logged to the terminal immediately; an in-memory count is sent centrally on recovery, and is lost on agent crash. Logical inactivity completion is stored before requesting OS logout; a rejected/cancelled OS logout does not imply the machine actually signed out. Actual OS failures are shown locally; inspect OS logs as part of deployment validation.

Settings fields are seconds, range 1–86400. Global scope is `*`; a per-computer scope replaces only that computer's explicitly supplied values. Blank computer fields inherit globals; saving all blanks removes effective overrides. `python -m server dev-timers` changes the database's global settings for demonstrations, not production defaults. Restore defaults through the dashboard or initialize a separate production database.

## Administrator access and deployment

Environment settings for the server process:

| Variable | Default / meaning |
| --- | --- |
| `LOGBOOK_ADMIN_ADDRESSES` | `127.0.0.1,::1`; comma-separated exact designated addresses |
| `LOGBOOK_SECRET` | Random per-process secret if absent; set a stable external random value for persistent CSRF sessions |
| `LOGBOOK_HTTPS` | `0`; set `1` behind production HTTPS to make admin session cookies Secure |
| `LOGBOOK_TRUSTED_PROXY` | Unset; optionally one exact reverse-proxy peer address |
| `LOGBOOK_TRUSTED_HOSTS` | `localhost,127.0.0.1,[::1]`; add the real HTTPS hostname for hosting |
| `LOGBOOK_SECRET_FILE` | Optional protected file containing a persistent session secret |
| `LOGBOOK_PRODUCTION` | `0`; set `1` for fail-closed production configuration validation |
| `LOGBOOK_ADMIN_DIRECT_ONLY` | `0`; production requires `1`, denying proxied administrator requests |

Database path is selected with `--database` on every CLI command, default `data/logbook.sqlite`. The Flask factory also accepts `LOGBOOK_DATABASE` when used directly; the CLI's explicit/default `--database` takes precedence.

Use Waitress (`python -m server serve`), not Flask debug mode. The default bind is loopback. For multiple PCs, put a TLS reverse proxy in front of Waitress and keep the backend bound to loopback/private host firewall rules. The server can run on any suitable central machine, independently of the administrator computer. Set the designated admin computer's fixed private address in `LOGBOOK_ADMIN_ADDRESSES`. Remote plain HTTP is rejected; client HTTP is allowed only with explicit loopback development configuration.

No forwarded headers are trusted by default. If there is a reverse proxy, configure its **exact peer address** with `LOGBOOK_TRUSTED_PROXY`; only requests from that peer get one-hop `X-Forwarded-For`/`X-Forwarded-Proto` handling. Configure that proxy to **overwrite** both headers from its actual connection and TLS state, block direct backend access, and restrict `/admin/` at the proxy/firewall as defense in depth. Do not expose a default loopback-restricted backend through an unconfigured proxy, because the backend would see the proxy's loopback address as the visitor. Multiple proxy hops are not supported by this configuration.

Admin writes require an address-authorized browser session plus CSRF token. Machine credential headers are rejected on administrator routes, including CSV export. Browser rendering escapes data; queries are parameterized; API input, timer bounds, timeouts and CSV formula prefixes are validated. Machine tokens never appear in frontend JavaScript.

Address restrictions **do not distinguish users on the same computer** or PCs sharing a public NAT address. On the one-laptop prototype, anyone able to use its browser can reach the dashboard. A student can claim another registered ID because ID-only login intentionally provides no identity proof. A shared-account user who can read the machine token can impersonate that client. These constraints require a private lab network, designated administrator workstation, protected client install/config, and appropriate institutional OS policies. Do not publish this dashboard on the public internet. Firewall/VLAN/VPN rules must restrict API access to lab PCs and administrator paths to the administrator workstation.

Production server startup examples are in `scripts/logbook-server.service.example`. Create its dedicated standard service account, protected code directory, writable database directory and external environment file deliberately. Never commit that environment file. Database backup should use SQLite's backup API or a stopped service rather than copying a live database without its WAL.

## OS startup, helper and access control

An interactive Tkinter program dies during real OS sign-out. Two separate processes are supplied:

- `python -m client`: portable student interface with global input warnings and heartbeats. In enforced installations `python -m client.kiosk` supervises it as the OS shell. On Windows, `WM_ENDSESSION` distinguishes confirmed OS session ending from closing the window; `WM_QUERYENDSESSION` alone does not end a record. In the managed Mint X11 session, the supervisor observes Cinnamon session exit and attempts to save the confirmed OS sign-out. Both end calls may lose acknowledgement; helper/new-run recovery then retains unknown end times instead of fabricating them.
- `python -m client.helper`: start at boot as SYSTEM/root, outside the student's OS session. Windows WTS enumeration / Linux `loginctl` detects any interactive OS user (including a disconnected Windows user). While any user is present it leaves timers and power control to the interactive agent. With no OS user, it reports OS absence, loads settings centrally, waits the configured no-session period, logs a countdown and requests simulated shutdown. It cannot initiate shutdown before its first acknowledged settings load; it keeps loaded settings across later failures. It rechecks interactive presence before an action. Only one helper/desktop process is allowed per machine by OS mutex/abstract socket locks. No local student/session data is stored.

**Pre-login limitation:** a SYSTEM service cannot show a Tkinter warning on Windows' secure sign-in desktop. This helper's pre-login countdown is visible only in service logs, and cannot be cancelled by secure-desktop mouse motion. Linux greeter input/warnings are likewise not integrated. User-visible pre-login warnings with mouse cancellation require a reviewed Windows credential-provider/sign-in-desktop integration or a Mint display-manager greeter extension; neither is implemented. Keep real automatic shutdown disabled until this deployment gap is resolved if visible pre-login cancellation is required. Interactive, logged-on no-student warnings fully support the mouse-only cancellation rule.

**Access control limitation:** the prototype's normal window is not a secure login barrier. It does not stop a shared-account user launching applications before student identification, killing their own process, or bypassing autostart. Cancelling a warning never creates a student session or changes OS permissions. Ordinary bypass prevention requires a protected kiosk shell/session launcher, application allowlisting, a supervised agent, blocked alternate shells/task tools, controlled logoff and boot options, and OS-specific policy testing. These are deployment prerequisites, not capabilities claimed by this Tkinter window. No accounts, registry, services, tasks, firewall, startup or security policy were changed automatically.

### Deliberate Windows startup installation

Prepare an administrator-owned copy under `C:\Program Files\LabLogbook`, with a freshly created standard CPython venv at that location. The code, interpreter, and startup scripts must be writable only by administrators/SYSTEM; the shared lab account needs read/execute access and read access to its machine config. Do not run SYSTEM code from this user-writable development workspace. Review effective ACLs, including inherited and custom-group permissions. The script refuses installation outside Program Files, but that path check is not an ACL audit.

Create a separate standard shared account using Windows administration tools; do not give it administrator privileges. Then, from an elevated PowerShell in the protected installation:

```powershell
# Review only; makes no changes
.\scripts\install-windows-startup.ps1 -LabUser 'COMPUTERNAME\LabStudent'
# Deliberately install logon agent + boot helper tasks after ACL/policy review
.\scripts\install-windows-startup.ps1 -LabUser 'COMPUTERNAME\LabStudent' -Install
```

The scheduled tasks use Interactive/Limited for the desktop and SYSTEM for the helper, ignore duplicate starts, and restart on process failure. They do not start immediately. Keep simulation enabled during initial logon/boot tests. Windows shutdown privileges and Task Scheduler behavior across actual sign-out still need real-machine testing. There is no MSI installer or credential-provider implementation.

### Deliberate Linux startup installation

Prepare root-owned `/opt/lab-logbook` and create its venv there (do not relocate the development venv). Create `/etc/lab-logbook/client.json`, owned by root and readable only by the shared lab account's dedicated group (`0640`). The shared account must not be able to modify code run by the root helper. Review these templates and substitute paths for the protected installation before copying:

```bash
# Only after preparing the protected installation and config
sudo cp scripts/logbook-helper.service.example /etc/systemd/system/logbook-helper.service
sudo systemctl daemon-reload
sudo systemctl enable --now logbook-helper.service
# Run the following as the shared lab user, inside its session
mkdir -p ~/.config/autostart
cp scripts/logbook-desktop.desktop.example ~/.config/autostart/logbook-desktop.desktop
# Inspect service-only countdown warnings
sudo journalctl -u logbook-helper.service -f
```

Use a standard user account and a managed Cinnamon X11 session. Desktop autostart alone is not a tamper-resistant kiosk launcher; deploy an appropriate supervised session and policy before enforcement. Polkit/systemd power permissions and Cinnamon logout behavior need validation. Root helper code/config integrity is critical. Do not enable a server service on every PC: the central database belongs only on the central server.

## Verification and remaining validation

Latest verification on this laptop: **69 tests passed**, including real Tk workflows with and without supervisor authorization, real RSA/JWKS token verification and rejection cases, DPAPI credential sealing, network/machine restrictions, migrations and source-only deployment packaging. Dependency checks, Python compilation, JavaScript/PowerShell/shell syntax and `git diff --check` passed. Verified LAN HTTPS heartbeats succeed while admin/export/auth paths return 403; the local dashboard returns 200. Live Google-account sign-in, cloud/container deployment and native kiosk installation have not been executed.

Automated tests use fake clocks and simulated OS adapters; no tests wait real inactivity periods or call actual power commands. Coverage includes duplicate registration/unknown IDs/name lookup, concurrent and idempotent sessions, one-active-session constraint, inactivity cancellation, mouse-only shutdown cancellation, paused/cancelled/abandoned identification, active-session shutdown prevention, settings inheritance, heartbeat recovery/offline handling, address/CSRF/token separation, trusted proxy boundaries, interruptions and null end times, historical names/deactivation, CSV filtering/formula protection and Manila date boundaries. A real loopback Waitress/requests test exercises the API over HTTP. The opt-in Tk test renders actual windows and follows registration → confirmed login → central session → simulated inactivity logout → simulated shutdown with fake time/input.

Windows global input sampling (including its input-desktop worker), WTS presence, sign-out-hook attachment and DPAPI were smoke-tested on this laptop. **Actual desktop switching, sign-out/shutdown, Windows edition behavior, service/Shell Launcher installation, Linux Mint/X11 session installation, real multi-PC firewall/network access, cloud HTTPS and institutional kiosk policies require live validation.** Native gate/session code and installers now exist; portable windows still do not enforce OS access. Wayland and cancellable secure-sign-in/greeter warnings remain unimplemented. See KIOSK-SETUP.md for shared-account/persistence limits. Sampling can miss mouse motion that returns to the same position between 200ms samples. A due timer action may wait for a bounded network operation to finish.

See [REFERENCES.md](REFERENCES.md) for inspected source paths, revision IDs, license checks and reference-specific decisions. No reference code was reused.
