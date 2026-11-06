# Deployment readiness — 2026-10-29

## Functional audit (2026-10-29)

Student account update (2026-11-06): administrator-only CSV/manual account
creation, first-login password setup, hashed password verification, throttling,
password reset, and one-time session authorization are implemented. Student
self-registration is disabled. Schema v3 preserves existing accounts and
records. Automated and real-window tests pass; the hosted server and each
Windows client must be updated together before acceptance testing.

Student access update (2026-11-05): exactly 10-digit IDs and the owner-specified
three-part name format are enforced by client and server. Login/registration
have separate screens; student, session-status and warning windows share a
slate/teal theme. 194 local tests passed, including invalid inputs, no requests
on invalid forms, legacy-record correction, separate-page visibility and record
integrity. [Clean Windows/Linux build](https://github.com/NekoMatsu1/Logbook_System/actions/runs/41980706259)
passed; the v0.1.6-test.1 archives passed checksum, runtime and credential-exclusion
checks locally. The live host and existing PC installs still need updating.
Native desktop enforcement remains a target-OS installation/acceptance task.

Update (2026-11-05): the strict Windows installer supports the packaged app
without a separate Python runtime. The download includes the installer/checker.
[Clean CI build](https://github.com/NekoMatsu1/Logbook_System/actions/runs/41871782616)
passed on Windows/Linux, including bundled credential-sealing checks. The local
download passed checksum, archive and runtime validation. Read-only checks found
this development PC uses Windows 11 Home Single Language, simulation and an
administrator account; no managed shell is installed. No OS restrictions were
applied. This does not establish the edition or readiness of other lab PCs.

Update (2026-11-04): password-based administrator sessions and monitoring retry
are implemented; hosted activation still needs private password setup and one
reload. See [OPERATIONS.md](OPERATIONS.md). The portable simulation does not
enforce Windows access. Actual kiosk installation/acceptance remains required.

Validation: 154 local tests passed, including simulated GUI workflows. Clean
Windows and Linux jobs passed in [CI run 41855042428](https://github.com/NekoMatsu1/Logbook_System/actions/runs/41855042428).
The v0.1.4-test.1 Windows archive passed checksum, contents and bundled-runtime
checks locally; server archives exclude private config/data. Monitoring retry
and login-expiry JavaScript checks passed. Hosted password activation and real
lab-account shell enforcement have not been performed from this session.

- Full local suite, including GUI workflows: **114 passed**. Dependency, Python compilation, dashboard JavaScript, PowerShell installer, and Linux shell syntax checks passed.
- [Clean build runners](https://github.com/NekoMatsu1/Logbook_System/actions/runs/40755814061): **114 passed on Windows; 113 passed and 1 Windows-only test skipped on Linux**. The Windows runtime ZIP was built, extracted, and smoke-tested.
- Inactivity and interactive shutdown warnings now require **Yes, I'm still here** before the deadline. Mouse movement, typing, unrelated clicks, and form focus do not cancel them. Timer and GUI tests exercise acknowledgement and expiry, including the supervised warning protocol.
- Student manual/automatic logout is authorized by the enrolled PC credential, independently of administrator access. New tests end sessions from a network that is denied the admin dashboard.
- Corrected the client getting stuck on an already-interrupted session; its historical end time and duration stay unknown. Manual logout failures now show the actual connection/version issue instead of implying admin approval.
- Added tests for concurrent/repeated endings, fractional durations and UTC CSV values, wrong-PC/run rejection, backward server time, backup restoration, and failure during PC configuration-file creation.
- Added a verified online SQLite backup command. Enrollment rolls back if its credential file cannot be saved. The launcher shares one Tk root between first-run setup and the desktop.
- The live PythonAnywhere server still rejected a nonexistent manual-logout probe with **400: Invalid end reason** during this audit. No actual session was ended by that probe. Updating/reloading the hosted code is still required; local fixes are not proof of deployment.
- UI redesign is deferred. Owner requirements and the requested minimal slate/teal direction are recorded in [PROJECT-REQUIREMENTS.md](PROJECT-REQUIREMENTS.md). Native OS, second-network, expected-load and real-backup rollout checks remain required.

## Download release

The source is now on [GitHub](https://github.com/NekoMatsu1/Logbook_System). The Windows release build includes Python, Tkinter, HTTPS certificates, and the client libraries. Each PC still needs its own private server configuration. See [DOWNLOAD.md](DOWNLOAD.md).

The [first release build](https://github.com/NekoMatsu1/Logbook_System/actions/runs/40673824834) passed on standard Windows CPython (**75 passed**) and Linux (**74 passed, 1 Windows-only test skipped**), including the GUI tests. Its ZIP integrity, software licenses, and private-file exclusions were checked. See the newer functional audit above for current results. These checks do not replace testing on the actual lab PCs.

Earlier MSYS2 and Windows runner tests encountered Tk reinitialization errors. The launcher and GUI tests now share one Tk root; the current full suite passed. Use the bundled Windows release or standard CPython for a new PC.

**Verdict: cloud server and first Windows PC login are working in simulation. Ready for controlled testing; not approved for unattended production deployment.**

## Hosted check (2026-10-28)

- PythonAnywhere is serving the HTTPS administrator dashboard. The owner completed account setup, virtualenv selection, Force HTTPS, WSGI configuration, and reload.
- The first provisioned Windows client connected to the hosted API. The dashboard showed that PC in use with one active central session after registration and confirmed login.
- No PC credentials, owner IP address, student identity, or session database are included in this repository or the public downloads.
- A second PC on another internet connection, simulated inactivity completion, live power actions, outside-network administrator rejection, and backup restoration remain pending. The owner will test later. Keep simulation enabled.

The assessment below includes earlier development results. Statements about unavailable hosting refer to the earlier audit, before the hosted check above.

## Earlier local checks (2026-10-24)

- Final full suite with `LOGBOOK_GUI_TEST=1`: **72 passed in 34.18 seconds**. Includes real Tk windows with fake activity/power adapters, API/database tests, timer tests, access restrictions, OAuth validation, migration, packaging and hosted-wrapper tests.
- `pip check`: no broken requirements. Python compilation, dashboard JavaScript syntax and PowerShell installer parsing passed.
- Rebuilt student PC-02, PythonAnywhere and VPS ZIP archives; all ZIP CRC checks passed. Preserved existing student machine credentials. Hosted packages exclude machine credentials and local records.
- One earlier GUI run failed during a second Tk initialization with a theme-file read error. The referenced file exists; the final full run passed. This intermittent local MSYS2/Tk environment issue is not proven resolved. Test the target PC's standard CPython installation before use.
- No local listeners were found on ports 5000, 5001 or 5443 during this audit. Packaged source does not constitute a running server.

## Requirements assessment

| Requirement | Evidence / remaining work |
| --- | --- |
| Python, Tkinter, Flask, SQLite, HTML/CSS/JS | Implemented; no replacement stack or unrelated reservation/billing/remote-screen features. |
| Require student identification before normal desktop access | Packaged/source entry points now start the supervisor; the native OS shell installer is still required for actual whole-PC enforcement. The lab administrator must validate kiosk behavior and recovery on the target OS. |
| Central records only; reject offline signup/login | Implemented. Machine configuration stores credentials, not student/session records. |
| One active session per PC; idempotency; UTC/Manila; historical names | Transactional database and API tests pass. Interrupted sessions retain unknown end times. |
| Activity and shutdown timers, cancellation, identification pause, configurable defaults | Fake-clock and Tk tests pass. Desktop activity monitoring implemented for Windows and Mint X11; actual Mint behavior untested. |
| Network loss must not force sign-out | Tested; an authorized active session continues with cached settings. New sessions require acknowledgement. |
| Secure pre-identification desktop barrier | Native gate and installers implemented, but actual Shell Launcher/LightDM enforcement and bypass/recovery tests remain mandatory. Ordinary Tk windows do not enforce this requirement. Windows Home/Pro cannot use the supplied Shell Launcher installer. |
| No-OS-user warning and mouse cancellation | **Incomplete.** Secure Windows sign-in / Linux greeter integration is absent. Live boot-helper shutdown is now suppressed rather than acting without the required warning. Simulation still exercises the countdown. |
| Overview, records, filters/CSV, student management, settings/events | API/admin tests pass; real browser and owner acceptance remain necessary. |
| Only enrolled lab PCs on lab network can register/login | Token plus configured CIDR checks tested. Public lab egress CIDRs must be configured and verified from a real PC. |
| Only owner can access admin history from anywhere | Google owner-email/subject authentication, server sessions and CSRF protections tested with controlled responses. Real OAuth round trip is untested. Local development mode trusts the designated local machine and is not proof of owner identity. |
| HTTPS, proxy restrictions, credential protection | Transport/proxy tests pass. Hosted provider HTTPS settings, native client IP behavior and real certificates require deployment validation. DPAPI provides machine-bound storage, not protection from arbitrary code already running under the shared account. |
| Laptop-off availability, free hosting | **Not deployed.** Requires a PythonAnywhere account, owner Google identity/OAuth configuration and lab public CIDRs. Provider availability and free-plan renewal conditions must be checked at deployment time. |
| Reference source/license inspection | Recorded in REFERENCES.md with pinned revisions; no reference project code reused or projects executed. |

## Corrections made during this audit

- Input-monitor sampling failures now pause automatic actions without overwriting centrally configured settings; successful sampling restores availability.
- Explorer launch failures relock the Windows gate. Failure to acknowledge a newly opened desktop to the student UI also requests relocking.
- Live boot-helper shutdown is suppressed because its required visible, cancellable greeter warning is not implemented. Added regression tests for monitor recovery, Explorer failure and this suppression.

## Required before production

1. Configure and deploy the hosted server with persistent SQLite storage, HTTPS, restricted lab CIDRs, owner-only Google authentication and protected secrets. Verify actual client source addresses; confirm outside-lab student API rejection and owner admin access from a second network.
2. Back up the database and perform a restore drill. Establish disk/availability monitoring and any required free-host renewal procedure. No hosting reliability claim has been verified.
3. On dedicated standard-account lab PCs with a separate recovery administrator, validate the OS shell installer, blocked bypass paths, crash recovery, global input while other apps are open, actual sign-out/shutdown and rollback. Test Windows and Mint separately; no actual power operations or OS-policy installations were performed here.
4. Implement and test secure-greeter warning/mouse cancellation if shutdown while no OS user is signed in remains required. Until then, that requirement is incomplete and the helper cannot perform live shutdown.

Passing automated tests establishes the covered behavior; it does not establish a zero-error deployment or resistance to every threat.
