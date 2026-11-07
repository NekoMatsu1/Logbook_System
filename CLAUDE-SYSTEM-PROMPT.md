# Lab Logbook system description

Build or redesign a secure, minimal computer-laboratory logbook system named **Lab Logbook**. The visual style is calm, practical, and human-made: restrained teal accents, off-white backgrounds, generous spacing, readable system fonts, modest borders, and no excessive gradients, cards, icons, or decorative effects.

## Purpose

The system records student use of shared laboratory PCs. It has two parts:

1. A central web-based administrator dashboard.
2. A Windows student desktop client installed separately on every lab PC.

The web dashboard is for the administrator. The desktop client is for students who use shared computers. Student logbook data must be precise because it is an official usage record.

## Administrator dashboard

Use a sticky top navigation with these pages:

- **Overview**: available, in-use, offline, and active-record counts; a live table of PCs, last connection, current student, and status.
- **Records**: filters for student ID, computer ID, and Manila date; paginated session history; CSV export. Show dates to the minute, not seconds. For completed sessions show `ended`; for interrupted sessions show the last confirmed online time and do not invent a logout time or duration.
- **Students**: the administrator imports official students from a UTF-8 CSV with `student_id,surname,first_name,middle_name`; can add one account; can edit a name, reset a password, activate/deactivate an account, or delete accounts that have no records. Keep secondary actions quiet text actions, not large buttons. If deletion is blocked because records exist, show a centered warning dialog saying the account must be deactivated instead.
- **Settings**: centered container for global or per-PC timers. Saving settings opens a centered `Settings saved` confirmation dialog.
- **Events**: readable audit log with columns Time, Computer, Event, Detail. Never show raw UUIDs, raw JSON, or technical event codes. Example: `Student session ended — Idle auto-logout`, `Settings updated — Global defaults: Idle limit: 10 seconds · Automatic logout: Enabled`.

Use a single administrator account with secure password sign-in, HTTPS-only cookies, CSRF protection, server-side sessions, and rate limits. Do not expose machine tokens or student passwords in the dashboard. Passwords are securely hashed; administrators can reset but never view them.

## Student account and login rules

- Students cannot self-register or change official identity details.
- Student IDs are exactly 10 digits.
- Official name format is `Surname, FirstName, Middle Name`.
- On first use, a student enters their issued ID and creates a private password.
- Later, a student enters ID and password.
- Invalid ID formats, duplicate IDs, weak passwords, invalid names, malformed CSV rows, and unauthorized requests must be rejected and recorded.
- Deactivation immediately blocks new sign-ins, revokes unused authentication tokens, and makes a currently connected client end its session on the next heartbeat.

## Student desktop app

Create a compact Windows desktop interface, not a browser page. It has these states:

1. Student ID entry page: computer name, short connection status, exactly-10-digit ID field, Continue button, and first-time-password setup path.
2. First-password page: student ID, password, confirm password, clear validation.
3. Password login page: student ID plus private password.
4. Session status window: student name, computer ID, connected status, and a clear manual `Log out` button. Closing the status window minimizes it; it can be reopened from the taskbar.
5. Inactivity warning: only clicking `Yes, I’m still here` cancels the warning. Mouse movement, random clicks, or keyboard activity must not dismiss the warning after it appears.

Students may manually log out without administrator approval. Automatic inactivity logout should be recorded as `ended` with the server timestamp. A lost heartbeat, sudden power loss, restart, or unexplained PC disappearance should be recorded as `interrupted`; show its last confirmed online time rather than pretending to know the exact power-off time.

## Strict kiosk context

The regular client can run in simulation/test mode. Strictly preventing desktop use before log-in requires a dedicated PC, a standard shared lab account, a separate recovery administrator, and OS-managed kiosk/shell configuration. Windows Home/Pro cannot provide the same Shell Launcher enforcement as Windows Education/Enterprise/IoT. Never claim that an ordinary app window or startup shortcut is a secure kiosk.

## Technical and UX priorities

- Data integrity and security are more important than visual effects.
- Responsive admin dashboard; desktop-first student client.
- Minimize page load work: do not load every table on every dashboard page; paginate records.
- Use readable labels, plain language, and clear confirmation/error dialogs.
- Preserve audit records. Accounts with records should normally be deactivated, not deleted.
- Use Asia/Manila display time while retaining precise server timestamps internally.
