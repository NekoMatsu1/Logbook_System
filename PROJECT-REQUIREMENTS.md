# Project requirements

## Reference reviewed (2026-11-04)

The owner supplied the full earlier design conversation as reference. The
owner's direct instructions take precedence over suggestions in that conversation.

- Each PC uses one shared OS account. After valid student identification, the
  student uses the normal desktop and installed applications.
- Require identification before desktop use, not merely before creating a log
  record. An app window, startup shortcut or simulation is not that restriction.
- Support Windows 10/11 and Linux Mint X11 through platform-specific adapters.
  Exact Windows edition is still unknown; the reference does not supply it.
- Default timing is five minutes idle, then a 60-second logout warning; after
  returning to the ready state, ten minutes without a new session starts the
  separate shutdown warning. Administrators can configure these values.
- Track global inactivity without storing keystrokes, screenshots, application
  contents or unrelated student activity. Keep operational events and accurate
  session records. Recovery must retain unknown endings rather than guess.
- Treat OS startup, sign-out, shutdown, crash recovery and bypass resistance as
  separate real-machine acceptance checks. Keep a recovery administrator.

Older reference suggestions to cancel warnings on mouse/keyboard activity are
superseded by the owner's explicit-button requirement below. Identification
may pause the ready-state countdown before a warning, but it cannot dismiss an
already visible warning. Older suggestions for local databases/offline session
sync do not change the current central-only design: no offline session starts
or additional local student-record storage are being introduced from reference
material alone. Alternative commercial products are background research, not
instructions to replace this project.

Password admin login is implemented to remove recurring IP updates without
making student records public. The private hosting setup and one reload are
still required; see [OPERATIONS.md](OPERATIONS.md). Strict native desktop access
still requires the managed lab-account installation and actual target-PC tests.

## Student flow

- A student registers once, then signs in with the student ID and confirms the name.
- Student IDs must contain exactly 10 ASCII digits (0–9), with leading zeros preserved.
  Letters, symbols, internal spaces and alternate Unicode digit characters are
  rejected by both the client and server. The owner confirmed this length.
  Existing invalid test IDs cannot start new sessions; their stored history is
  retained, and administrators may deactivate them.
- Registration requires `Surname, FirstName, Middle Name`, using comma-space
  separators and full name parts. Names may include letters with accents,
  multiword parts, and internal apostrophes/hyphens. Digits, missing parts,
  initials with periods, HTML and incorrect delimiters are rejected. Invalid
  existing names need admin correction before a new login; history is retained.
- Login and registration have separate screens. The login screen has no name
  field. Registration alone does not grant desktop access.
- A student may end their own session with **Log out**. No admin account, password, or admin approval is required.
- Automatic logout follows the inactivity warning. Once a warning appears, only **Yes, I'm still here** cancels it. Mouse movement, typing, random clicks, or focusing the registration form must not dismiss a warning. This also applies to the interactive shutdown warning.
- Closing the portable session window minimizes it; it does not end the session.
- An enrolled PC uses its own machine credential. That credential is not admin permission.
- Manual logout waits for the server to save the record. If the server is unavailable, show the actual failure and keep the session active for retry; never claim an unsaved logout succeeded.
- If the server has already marked a session interrupted, the student can leave it without inventing a logout time or changing the historical record into a completed session.
- Simulation ends the logbook session without signing out of Windows. Live mode also requests OS sign-out. Native kiosk installation is a separate deployment step.

## Record accuracy

- Preserve leading-zero student IDs, historical names, PC IDs, session IDs, and distinct logout reasons.
- Store server timestamps in UTC; show local dates in Asia/Manila. Login/logout times mean server acceptance of the session changes, not proof that Windows signed out at that instant.
- Calculate duration from the stored timestamps. Reject a logout timestamp earlier than its login instead of writing a made-up zero duration.
- Retries must not change the first saved end time or produce duplicate sessions/logout events. One PC may have only one active session.
- A different PC or agent run must not end another session. No admin approval is part of a student's valid end request.
- Offline status alone is not proof of logout. Interrupted records keep unknown logout times and durations when the ending was not saved.
- Do not fabricate an exact ending after an outage, crash, or unacknowledged Windows sign-out. The current central-only design cannot reconstruct that event afterward.
- Keep consistent database backups outside the host and test restoring them. See [BACKUPS.md](BACKUPS.md).

## UI direction

Keep the working flow. Use a minimal, stylish, comfortable slate/teal palette,
clear text, consistent spacing, and obvious login/logout actions. Keep warning
and error states readable and distinct. The web dashboard has received this
styling; the native student login, registration, active-session and warning
windows now use the corresponding slate/teal theme as well.

## Deployment status

Automated tests support the covered behavior; they do not prove every real-PC or hosting failure mode is resolved. Before production, validate another PC/network, native kiosk restrictions, real sign-out/shutdown and recovery, database restore using a real backup, expected PC load, and unauthorized admin rejection. In password mode, valid admin login must work from another network while signed-out browsers remain blocked. Keep simulation enabled until those checks pass.
