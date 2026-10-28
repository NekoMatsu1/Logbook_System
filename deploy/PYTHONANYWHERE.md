# Free internet server

PythonAnywhere can host this Flask/SQLite server. PCs can connect from different internet connections, and your laptop can be off. No LAN or router port forwarding is needed.

The [free signup](https://www.pythonanywhere.com/registration/register/beginner/) asks for no card. The free web app needs renewal each month in the Web tab. Capacity is limited; use this for a small test first. See [free-plan limits](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/). PythonAnywhere also [cautions about SQLite performance](https://help.pythonanywhere.com/pages/KindsOfDatabases/) on its shared filesystem. Test the expected PC load before keeping real records.

## 1. Create your account

Sign up and verify your email. Keep your password private. Your server address will be `https://YOUR_USERNAME.pythonanywhere.com`.

## 2. Upload the server

On the development PC, run `python -m deploy.package_pythonanywhere` with the existing project Python environment. Upload `dist/pythonanywhere-server.zip` in PythonAnywhere's Files tab. This package has no machine tokens, local records, database, or server secrets.

In a PythonAnywhere Bash console:

```bash
mkdir -p ~/lab-logbook
python3 -m zipfile -e ~/pythonanywhere-server.zip ~/lab-logbook
cd ~/lab-logbook
python3 -m venv ~/.virtualenvs/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m pip install -r requirements-server.txt
```

Use Python 3.11 or newer. In Web, add a web app using Manual configuration and the same Python version as the venv. Set its virtualenv to `/home/YOUR_USERNAME/.virtualenvs/lab-logbook`. Enable **Force HTTPS**.

## 3. Set the admin IP and allow remote PCs

Get the public IPv4 used by the admin PC's internet connection. Private addresses such as `192.168.x.x` will not work. In the hosting console:

```bash
cd ~/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m deploy.configure_pythonanywhere --username YOUR_USERNAME --admin-ip YOUR_ADMIN_PUBLIC_IPV4 --remote-clients --force-https-confirmed
```

This creates private settings and a server secret. It refuses to overwrite an existing setup. No Google OAuth setup is needed for this mode. To use the optional Google owner sign-in instead, replace `--admin-ip` with `--admin-email`; the command will ask for your Google Web OAuth credentials. Keep `--remote-clients` for PCs at different locations.

## 4. Start the web app

Replace the Web-tab WSGI file with:

```python
import sys
sys.path.insert(0, '/home/YOUR_USERNAME/lab-logbook')
from deploy.pythonanywhere_wsgi import build_application
application = build_application('/home/YOUR_USERNAME/.config/lab-logbook/server.json')
```

Click **Reload**. Do not start Waitress or Caddy in the console. Do not add static mappings for the source folder, private configuration, or database.

Open `https://YOUR_USERNAME.pythonanywhere.com/admin/overview` from the allowed admin network. Check that the same page returns 403 from another network. A student API request without a valid machine token must return 401.

The adapter uses the final item in PythonAnywhere's managed `X-Real-IP` header, following its [client IP documentation](https://help.pythonanywhere.com/pages/WebAppClientIPAddresses). It removes other forwarding headers and rejects a missing or invalid provider address. This adapter is only for PythonAnywhere's managed gateway with Force HTTPS enabled. Do not serve it from a directly reachable HTTP socket or put another proxy in front.

## 5. Connect each PC

In the hosting Bash console:

```bash
cd ~/lab-logbook
mkdir -p ~/private-client-configs
chmod 700 ~/private-client-configs
~/.virtualenvs/lab-logbook/bin/python -m server provision --database ~/.local/share/lab-logbook/logbook.sqlite --computer LAB-PC-01 --output ~/private-client-configs/LAB-PC-01.json --server-url https://YOUR_USERNAME.pythonanywhere.com
```

Download the JSON through your authenticated Files tab. Put it on that PC as `config/client.json`, beside the Windows app. Use a different computer ID and JSON for each PC. Never upload private client JSON files to GitHub or reuse a Windows-protected config on another machine. Keep simulation enabled during testing.

Check a PC on another internet connection can register and sign in. Turn off the development laptop and check again. Verify idle warnings, network recovery, and central records. Live power actions and kiosk policies still need tests on dedicated PCs.

The admin allowlist checks a public IP, not a device. Other devices sharing the same public IP can reach the dashboard. If that IP changes, update `ADMIN_ADDRESSES` in the private `~/.config/lab-logbook/server.json` and Reload. Client tokens never grant dashboard access.

## Keep it running

- Extend the web app before its monthly expiry.
- Use SQLite's backup API to make consistent backups. Keep a protected copy outside the hosting account and test a restore.
- Keep private settings, records, and client credentials out of public downloads.
- Monitor disk space, errors, response times, and SQLite write contention. A free account does not guarantee uptime or enough capacity for a large lab.

No PythonAnywhere account or running server has been created by preparing these files. Deployment and live internet checks remain pending until the account is ready.
