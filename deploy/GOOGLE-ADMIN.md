# Admin login from any network

Use your exact Google account instead of a public IP. Only the configured,
verified account can view records or download exports. A student PC token does
not grant admin access. There is no public admin registration.

## One-time setup

1. Open [Google Cloud Console](https://console.cloud.google.com/). Create or select
   your project. Open Google Auth Platform and complete Branding and Audience.
   If the app is in Testing, add your administrator Google email as a test user.
2. Under Clients, create an OAuth client of type **Web application**. Add this
   exact Authorized redirect URI:
   `https://nekomatsui.pythonanywhere.com/auth/callback`.
   Use your own hostname for a different deployment.
3. Keep the client secret private. In PythonAnywhere Bash, run:

   ```bash
   cd ~/lab-logbook
   git pull --ff-only
   ~/.virtualenvs/lab-logbook/bin/python -m deploy.enable_google_admin
   ```

   Enter your administrator email, client ID, and hidden client secret when
   asked. Do not paste the secret into chat or a shell command. The helper
   preserves the database, machine settings, and session secret, and replaces
   the private config atomically with owner-only file permissions.
4. In PythonAnywhere **Web**, check Force HTTPS is enabled and click **Reload**
   once. Open the usual `/admin/overview` link and choose Continue with Google.
5. Check a different Google account is denied. Check an incognito browser cannot
   read `/admin/records` or `/admin/export.csv` before sign-in. Then sign in from
   another network; an IP update must not be needed.

The old IP restriction remains active until the helper is run and the app is
reloaded. If sign-in fails, check the exact callback and configured email in the
private hosting settings. Do not remove authentication to work around an error.

## Protect the records

Enable two-step verification on Google, GitHub, and PythonAnywhere. Use the admin
Sign out button on shared PCs. Admin sessions expire after one hour. Student
IDs and machine configs are not admin passwords.

Never add static mappings for the project root, private configs, database, or
backups. Never upload these to public GitHub or release downloads. Keep backup
copies private; see [BACKUPS.md](../BACKUPS.md). Hosting account owners can access
server files, so protect that account too. These controls reduce risk; they do
not guarantee protection against every attack.

Google setup reference: [OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect).
