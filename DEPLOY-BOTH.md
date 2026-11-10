# Deploy Logbook on Windows and Linux Mint

The same central Logbook server supports Windows and Linux Mint clients. Provision a separate private `client.json` for every computer. Never reuse a computer credential or upload one to GitHub.

## Supported modes

| Computer | Mode | Result |
| --- | --- | --- |
| Linux Mint X11 dedicated lab PC | Strict kiosk | Logbook appears before the Cinnamon desktop. |
| Windows 11 Pro | Standard client | Student password sign-in, sessions, records, inactivity logout and automatic actions work. Windows Pro cannot use the strict Shell Launcher gate. |
| Windows Education or Enterprise | Strict kiosk | Supports the Windows strict installer. |

## 1. Update the central server

On the PythonAnywhere Bash console:

```bash
cd ~/lab-logbook
git pull --ff-only
touch /var/www/nekomatsui_pythonanywhere_com_wsgi.py
```

## 2. Provision each computer

Run this separately for every computer and change the computer name each time:

```bash
cd ~/lab-logbook
mkdir -p ~/private-client-configs
chmod 700 ~/private-client-configs
~/.virtualenvs/lab-logbook/bin/python -m server provision \
  --database ~/.local/share/lab-logbook/logbook.sqlite \
  --computer MINT-LAB-01 \
  --output ~/private-client-configs/MINT-LAB-01.json \
  --server-url https://nekomatsui.pythonanywhere.com
```

Download the JSON through the authenticated PythonAnywhere Files page. Repeat with names such as `WIN-LAB-01`, `WIN-LAB-02`, and `MINT-LAB-02`.

## 3. Linux Mint X11 strict kiosk

Use a dedicated PC with a separate recovery administrator and a standard `labstudent` account. Back up the PC first.

1. Install the reviewed project at `/opt/lab-logbook` and make the code root-owned and not writable by students.
2. Put the dedicated Mint credential at `/etc/lab-logbook/client.json`.
3. Set the explicit JSON value `"simulation": false` only after basic network testing passes.
4. Enable strict mode locally as the recovery administrator:

```bash
sudo sh /opt/lab-logbook/scripts/install-linux-kiosk.sh --install labstudent
```

At the next `labstudent` logon, Logbook must be completed before Cinnamon opens.

Disable strict mode locally as the recovery administrator:

```bash
sudo sh /opt/lab-logbook/scripts/install-linux-kiosk.sh --uninstall labstudent
```

The uninstall restores the previous LightDM setting at the next logon and keeps an audit backup. Do not restart LightDM while students have unsaved work.

## 4. Windows client

Download `Logbook-Windows-x64.zip`, extract it, and put that Windows PC's dedicated JSON in:

```text
Logbook\config\client.json
```

Run `Logbook.exe`. Keep `"simulation": true` during testing. On a dedicated Windows PC, `"simulation": false` enables real Windows sign-out and shutdown behavior.

Windows Pro connects to the same server as Mint and records the same student sessions. It does not provide strict Logbook-before-desktop enforcement. That specific Windows feature requires Education or Enterprise.

## 5. Required test for every computer

1. The PC appears in **Overview** after the client starts.
2. An imported student creates a password once, then signs in using ID and password.
3. Manual and idle logout create **ended** records.
4. Power loss, restart, or an unconfirmed stop creates an **interrupted** record with its last confirmed online time.
5. On Mint strict mode, confirm that the recovery administrator can still sign in normally.
