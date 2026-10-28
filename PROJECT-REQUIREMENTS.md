# Project requirements

## Student flow

- A student registers once, then signs in with the student ID and confirms the name.
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

Keep the working flow. The next design pass should be minimal, stylish, and easy on the eyes: a quiet slate/teal palette, clear text, consistent spacing, and obvious login/logout actions. Keep warning/error states readable and distinct. This audit does not redesign the screens.

## Deployment status

Automated tests support the covered behavior; they do not prove every real-PC or hosting failure mode is resolved. Before production, validate another PC/network, native kiosk restrictions, real sign-out/shutdown and recovery, database restore using a real backup, expected PC load, and outside-network admin rejection. Keep simulation enabled until those checks pass.
