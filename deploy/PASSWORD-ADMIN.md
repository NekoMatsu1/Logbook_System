# Monitor from any network

The old IP check needs a config update whenever the admin network's public IP
changes. Password mode removes that dependency without making records public.
No Google app or authenticator app is required.

Run in PythonAnywhere Bash:

```bash
cd ~/lab-logbook
git pull --ff-only
~/.virtualenvs/lab-logbook/bin/python -m deploy.enable_password_admin
```

Choose a username and a unique passphrase of at least 15 characters. Password
entry is hidden. Never send it in chat or put it in a shell command. The helper
saves a salted scrypt hash in the private server config, preserves records and
machine settings, and replaces the config atomically with owner-only permissions.
It also rotates the browser signing key, invalidating previous browser sessions.

Click **Web → Reload** once. Open your usual `/admin/overview` link and sign in.
Normal logins and changing internet connections need no further server reload.
Sessions last one hour; then sign in again. Use Sign out on shared computers.
Changing/resetting the password uses the same console command and one reload.
No public registration or password-reset endpoint is provided.

Check with an incognito browser: no student records or CSV export before login.
After login, check monitoring from a different network and after a normal server
reload. Sign out and confirm records are blocked again.

This does not remove PythonAnywhere free-plan monthly renewal or capacity limits.
Monitoring needs each student agent running and an internet connection; stale
heartbeats show offline. An outage does not prove logout. See BACKUPS.md for
private backups. Do not add static mappings to the project, database or secrets.
