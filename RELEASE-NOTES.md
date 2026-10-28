Portable laboratory logbook client for controlled testing on Windows 10/11 x64.

New in this release:

- **Log out** in the portable client's session window, with confirmation.
- Closing that window minimizes it so it can be reopened from the taskbar.
- Manual logout keeps the session active if the server cannot confirm its ending. Simulation ends only the logbook session; live mode requests OS sign-out too.

**Update the server before using this client:** in the PythonAnywhere Bash console, run `cd ~/lab-logbook && git pull --ff-only`, then click **Web > Reload**. Existing settings and records are preserved. Older servers reject the new manual logout reasons.

- Download **Logbook-Windows-x64.zip**, extract everything, and run **Logbook.exe**. Python is bundled.
- Each PC requires a separate private configuration from the central server administrator. No machine credentials or student data are included in this public download.
- **logbook-deploy.zip** is server source for administrator deployment; it is not the Windows client.
- **pythonanywhere-server.zip** is source for the card-free PythonAnywhere hosting option.
- See **DOWNLOAD.md** in the repository for setup and second-PC checks.

The current PythonAnywhere server has received a registration and active session from the first Windows PC. See DOWNLOAD.md to enroll another PC with a separate private configuration. PCs can use different internet connections; the server is hosted outside the lab. Monthly host renewal is required.

This is a testing prerelease. A second-PC test on another internet connection, native kiosk enforcement, live power operations, outside-network admin rejection, and backup recovery still need validation. Secure sign-in/greeter shutdown warnings are incomplete. Simulation remains the provisioning default.
