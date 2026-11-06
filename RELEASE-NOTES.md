Portable laboratory logbook client for controlled testing on Windows 10/11 x64.

New in this release:

- Administrators can permanently delete an unused student account from the Students page. Accounts with saved session records cannot be deleted; deactivate them instead so official logbook records remain intact.
- Starting Logbook a second time now brings the existing student window forward. A wrong-PC, missing, locked, or damaged client configuration gives a safe, specific recovery message without exposing credentials.
- `admin-interface.html` is a complete one-file local admin UI preview with sign-in, Overview, Records, Students, Settings, Events, CSV import, password reset, and delete-account controls for design work.

- Administrators import official student accounts from a strict UTF-8 CSV or add one account manually. Invalid and duplicate imports are rejected atomically and logged.
- Student self-registration is disabled. First login creates a private password; later logins require ID and password.
- Passwords use scrypt hashes. Failed attempts are throttled, and a short-lived one-time authorization is required before a session can start.
- Administrators can reset but never view student passwords. Existing data is preserved by the schema v3 migration.

- Student IDs must contain exactly 10 digits. Invalid input shows a clear error before a request is sent; server checks also apply to older clients. Leading zeros are preserved.
- Imported accounts require `Surname, FirstName, Middle Name`. Invalid existing records need admin correction before a new login; historical records are retained.
- ID entry and password screens are separate. Student access, active-session and warning windows share a minimal teal style with readable text and clear actions. Test mode explicitly says it does not block the desktop.

- The Windows download now includes the strict-shell installer and read-only setup checker. The installer supports the bundled app without a separate Python installation, checks edition before making changes, and marks setup complete only after Windows accepts the managed shell. Enterprise/Education/IoT Enterprise and a separate standard lab account are still required; Home/Pro remain unsupported by this installer.

- Optional admin password login replaces changing IP allowlists. Set it privately with `python -m deploy.enable_password_admin` in PythonAnywhere, then reload once. No Google or authenticator app is needed.
- Monitoring updates without a full page reload, marks connection loss and retries automatically.
- Fixed packaged supervisor/child/warning launch paths and added read-only Windows kiosk setup checks. Desktop restriction still needs a supported OS-managed installation; simulation does not lock Windows.

- Students can log out without admin approval, or be logged out after the inactivity warning. Closing the session window still minimizes it.
- Inactivity and interactive shutdown warnings require **Yes, I'm still here**. Mouse movement, typing, and random clicks no longer cancel them. Confirmation at or after the deadline cannot revive a session.
- Manual logout now explains server/version failures and handles already-interrupted records without making up an end time.
- The server rejects backward logout timestamps instead of silently storing a zero duration.
- Added verified SQLite backups and tests for restoration, concurrent logout retries, permissions, and fractional record values. Failed PC setup-file creation now rolls back enrollment.
- First-run configuration and the desktop share one Tk root to avoid repeated GUI initialization.
- The dashboard uses a slate/teal theme, clearer tables and status badges.

**Update the server before using this client:** in the PythonAnywhere Bash console, run `cd ~/lab-logbook && git pull --ff-only`, then click **Web > Reload**. Existing settings and records are preserved. Older servers reject the new manual logout reasons.

- Download **Logbook-Windows-x64.zip**, extract everything, and run **Logbook.exe**. Python is bundled.
- Each PC requires a separate private configuration from the central server administrator. No machine credentials or student data are included in this public download.
- **logbook-deploy.zip** is server source for administrator deployment; it is not the Windows client.
- **pythonanywhere-server.zip** is source for the card-free PythonAnywhere hosting option.
- See **DOWNLOAD.md** in the repository for setup and second-PC checks.

The current PythonAnywhere server has received a registration and active session from the first Windows PC. See DOWNLOAD.md to enroll another PC with a separate private configuration. PCs can use different internet connections; the server is hosted outside the lab. Monthly host renewal is required.

This is a testing prerelease. A second-PC test on another internet connection, native kiosk enforcement, live power operations, outside-network admin rejection, and backup recovery still need validation. Secure sign-in/greeter shutdown warnings are incomplete. Simulation remains the provisioning default.
