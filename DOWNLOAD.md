# Download and run

## Windows 10/11, 64-bit

1. Open this repository's **Releases** page and select the newest testing release.
2. Under **Assets**, download **Logbook-Windows-x64.zip**. The GitHub **Code > Download ZIP** button downloads source code instead.
3. Extract the entire ZIP to a writable folder such as `Documents\Logbook`. Keep `Logbook.exe` and its `_internal` folder together.
4. Ask the laboratory administrator for a **new configuration for this PC**. Put it in `Logbook\config\client.json`, then double-click **Logbook.exe**. You can also select the JSON when prompted.
5. Confirm the window shows the correct computer ID and **SIMULATION**. Complete the second-PC checklist below before enabling real OS operations.

## Student logout

When an inactivity warning appears, click **Yes, I'm still here** before the countdown ends to keep working. Mouse movement, typing, and other clicks will not dismiss it. If you do nothing, automatic logout follows. Interactive shutdown warnings also need that button to cancel.

After login, the portable Windows app shows a session window with a **Log out** button. Click it and confirm. Closing the session window now minimizes it; click its taskbar button to reopen it.

The server must confirm the session ending before manual logout proceeds. If the connection fails or the server is too old, the session stays active and the app asks you to retry. In simulation mode, logout ends the logbook session while Windows stays signed in. In live mode, it also requests OS sign-out, which closes applications; save your work first.

No admin approval is needed to end a student's own session. Server confirmation means the record was saved. If a session is already marked interrupted, the app lets the student leave while preserving its unknown end time. It does not invent a completed record.

**Existing PythonAnywhere server:** manual logout needs the updated server too. In its Bash console, run `cd ~/lab-logbook && git pull --ff-only`, then click **Web > Reload**. This updates code without replacing private settings or the database. Do this before using the new client. Native Windows kiosk sessions still use Windows sign-out; the new button is in the portable desktop client's session window.

Python, pip, Git and VS Code are not required for this Windows download. An administrator must first run the central server and provision each client. This is a networked laboratory client; downloading it does not create a hosted server or allow offline sign-in.

The executable is unsigned. School policy may require administrator review or signing before it can run. Do not disable endpoint protections. Linux Mint users should follow the Python/X11 setup in README.md; this Windows ZIP does not run on Linux or macOS.

For PCs at different locations, deploy the central service on an internet-reachable host and set `LOGBOOK_ALLOW_REMOTE_CLIENTS=1`. Keep that host running; the student PCs and the administrator's designated-IP-restricted dashboard then connect over HTTPS without sharing a LAN. Follow the [Linux VM deployment guide](deploy/README.md); the local second-PC checklist is only for a same-LAN test.

## Administrator: provision another PC

For the current PythonAnywhere server, open its **Bash console** and run:

```bash
cd ~/lab-logbook
mkdir -p ~/private-client-configs
chmod 700 ~/private-client-configs
~/.virtualenvs/lab-logbook/bin/python -m server provision \
  --database ~/.local/share/lab-logbook/logbook.sqlite \
  --computer LAB-PC-02 \
  --output ~/private-client-configs/LAB-PC-02.json \
  --server-url https://nekomatsui.pythonanywhere.com
```

Use `LAB-PC-03`, `LAB-PC-04`, and so on for more PCs. Download that PC's JSON through the signed-in PythonAnywhere **Files** tab, in the `private-client-configs` folder. On the target PC, extract the Windows app and put the JSON in `Logbook/config/client.json`. Then open `Logbook.exe`. The admin must do the provisioning; public downloads contain no usable PC credentials.

Do not copy `LAB-PC-01`'s config to another PC. Its Windows credential is tied to the first PC that opened it. Keep the original downloads private too.

### Other server installations

On another **central server**, using its existing Python environment and database:

```powershell
python -m server provision --computer LAB-PC-02 --output config/LAB-PC-02.json --server-url https://YOUR-SERVER-HOSTNAME
```

Use your environment's Python executable in place of `python`. Transfer that JSON privately to the target PC and rename its copy to `client.json`. Never put it in a public release, commit, issue or chat. Provision a distinct computer ID/configuration for every PC. Do not copy a Windows-protected configuration from another machine: its token becomes machine-bound when first loaded. If you select a JSON outside the default folder, select it again next launch, or move it to the default folder on the same PC.

For a private LAN test with a local CA, follow STUDENT-PC-TEST.md; transfer the CA certificate with the private config and preserve its configured path. Never turn off certificate checking. `127.0.0.1` points to the PC running the client, so it cannot identify a server on a different PC.

Hosting instructions: [PythonAnywhere](deploy/PYTHONANYWHERE.md) or [persistent Linux server](deploy/README.md). Secure kiosk installation is a separate administrator task described in KIOSK-SETUP.md; the portable client does not install an OS shell or service.

## Second-PC acceptance checklist

- Start the server and client on separate PCs; verify the configured HTTPS endpoint and computer ID. Register a test ID with leading zeros and confirm its name before login.
- Check the central dashboard contains that PC and session. Verify another PC uses a distinct ID/configuration.
- In simulation, verify idle warnings, cancellation, simulated logout and simulated shutdown. Confirm no real power action occurs.
- Disconnect the network while a session is active: it continues; new logins/registrations must fail. Reconnect and check the central records.
- Restart the client and server; verify existing records persist. Test a database backup restore separately.
- Validate live sign-out, shutdown, native kiosk policies and recovery on a dedicated test PC before production. Secure greeter shutdown warnings remain incomplete; unattended production is not approved.

## Maintainers: rebuild downloads

Use standard Windows CPython 3.13, 64-bit, with Tkinter:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-venv\Scripts\python.exe scripts/build_windows.py
```

The output is `dist/Logbook-Windows-x64.zip` and its SHA-256 checksum. The build extracts and launches a runtime self-test without network or power actions. GitHub Actions runs the full tests on Windows and Linux, builds this ZIP, and publishes it with the server source package when a `v*` tag is pushed. All published releases remain marked as testing releases until production validation is complete.
