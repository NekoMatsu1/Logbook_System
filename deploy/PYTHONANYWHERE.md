# Free hosting alternative: Google owner sign-in, lab-only student access

This alternative keeps student access restricted to configured public lab networks and uses Google sign-in for the dashboard. It does not match the no-application-sign-in, administrator-IP-restricted dashboard requirement. For PCs at unrelated locations and a dashboard limited to one administrator public IP, use the [Linux VM deployment](README.md).

This deployment preserves Flask + SQLite. It does not run Tkinter on the hosting service. Student clients remain installed on lab PCs. The application code is prepared and locally tested; no PythonAnywhere account has been connected and no live site has been provisioned in this session.

## Accounts you control

1. Create a free account at https://www.pythonanywhere.com/registration/register/beginner/ and verify your email. No card is requested by this free registration form. Do not enable a paid plan. Free accounts have limited resources and a web-app expiry that you must extend in the Web tab; this is not guaranteed production uptime.
2. Choose your sole administrator Gmail/Google Workspace identity. Students do not need Google accounts and never use this administrator sign-in.
3. In Google Cloud Console, create/select a project, configure the OAuth consent screen, and create an **OAuth client ID → Web application**. Use only OpenID/email identity scopes; this app does not request Drive/Gmail content or billing services. No cloud VM or paid API is needed for Google identity.
4. Set the authorized redirect URI to `https://YOUR_USERNAME.pythonanywhere.com/auth/callback`. It must match exactly. If the consent app is in Testing, add only your administrator email as a test user. Keep the client secret private; enter it only in the hosting console when prompted below. Do not paste it into chat or commit it.
5. Enable strong authentication/recovery on your administrator Google account. The logbook has no administrator username/password form; Google authenticates the owner and the server verifies the signed token and configured owner identity.

Official references: [PythonAnywhere free features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [SQLite availability](https://help.pythonanywhere.com/pages/KindsOfDatabases/), [Google OIDC setup](https://developers.google.com/identity/openid-connect/openid-connect). PythonAnywhere cautions that SQLite on its shared filesystem is slower and not its recommended production database; use this free deployment for a small supervised test and monitor write contention. Free resources are not a 24/7 SLA.

## Upload the prepared source

`dist/pythonanywhere-server.zip` contains only server source, templates, static assets, requirements, and these deployment helpers. It contains no student-PC config, machine token, database, Google secret, or local records. Rebuild locally if needed:

```powershell
.\.venv\bin\python.exe -m deploy.package_pythonanywhere
```

Upload that ZIP with PythonAnywhere's **Files** tab. Open a Bash console there and extract it into `/home/YOUR_USERNAME/lab-logbook`:

```bash
mkdir -p ~/lab-logbook
python3 -m zipfile -e ~/pythonanywhere-server.zip ~/lab-logbook
cd ~/lab-logbook
python3 -m venv ~/.virtualenvs/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m pip install -r requirements-server.txt
```

Python must be 3.11+. Use the same version for the web app and venv. Do not upload the Windows `.venv`. In **Web → Add a new web app**, choose **Manual configuration**, matching Python, and set the virtualenv path to `/home/YOUR_USERNAME/.virtualenvs/lab-logbook`. Do not start Waitress/Caddy in a console to publish this site; PythonAnywhere loads the WSGI application directly.

## Restrict students to the laboratory network

Obtain the lab's **public outgoing IP address** from its network administrator. In cloud hosting, `192.168.x.x` is not the source address the server sees: all lab clients usually share the lab router's public address. Configure that public address as `/32`, or the institution's explicit approved CIDR. For dual-stack lab networks configure the approved IPv6 prefix too. Do not use `0.0.0.0/0` or `::/0`. A changed lab public IP requires a deliberate configuration update; the app fails closed rather than accepting outside PCs.

The server requires both an enabled provisioned machine token and a permitted lab source network for every student API request, including registration, lookup, heartbeats and session start. Google administrator routes do not use the lab-network restriction, so the owner can authenticate from another network. A copied token used from an outside network is rejected. PCs sharing the lab's public NAT cannot be distinguished by IP alone; protect lab machines, network access and machine credentials. This is not a hardware attestation system or protection against a compromised authorized lab PC acting as a proxy.

## HTTPS and private configuration

In **Web → Security**, enable **Force HTTPS**. The default `YOUR_USERNAME.pythonanywhere.com` hostname already has a provider certificate. Then run in the hosting Bash console, substituting your real values:

```bash
cd ~/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m deploy.configure_pythonanywhere \
  --username YOUR_USERNAME \
  --admin-email YOUR_OWNER_ADDRESS@gmail.com \
  --lab-network YOUR_LAB_PUBLIC_IP/32 \
  --force-https-confirmed
```

It prompts for the Google client ID and a hidden client secret in that console. It writes mode-0600 `/home/YOUR_USERNAME/.config/lab-logbook/server.json`, generates a persistent signing secret, and places the database outside the code directory. It refuses to overwrite an existing configuration. Keep an encrypted backup of that private configuration separately from the upload ZIP.

Edit the **Web-tab WSGI configuration file** to contain:

```python
import sys
sys.path.insert(0, '/home/YOUR_USERNAME/lab-logbook')
from deploy.pythonanywhere_wsgi import build_application
application = build_application('/home/YOUR_USERNAME/.config/lab-logbook/server.json')
```

The hosted adapter assumes that the provider's Force HTTPS setting is enabled, normalizes the TLS-offloaded WSGI scheme, and discards caller-supplied forwarding headers. It uses the provider's native `REMOTE_ADDR` for lab-network restrictions. Do not use this adapter with an arbitrary directly reachable HTTP server. If your platform does not supply the actual client in `REMOTE_ADDR`, access stays denied: establish the platform's exact trusted gateway configuration before changing IP handling. Do not work around this by trusting arbitrary forwarded headers or allowing all networks.

Remove any automatically created static mapping that exposes the entire source/home directory. The app serves only its `/static/` directory. Do not map `.config`, database paths, or client output folders to web URLs. Click **Reload** in the Web tab.

PythonAnywhere free accounts use their configured outbound proxy. The app's server-side OAuth/certificate fetches honor those proxy environment variables, use verified HTTPS, explicit endpoints and bounded timeouts. Google domains are on the provider's [allowlist](https://www.pythonanywhere.com/whitelist/). If this changes, sign-in fails closed; do not disable TLS verification.

## Administrator access from any location

Open `https://YOUR_USERNAME.pythonanywhere.com/admin/overview` and choose **Continue with Google**. Only the exact configured, verified Gmail/Workspace identity can be admitted. The first verified login pins its stable Google subject; a changed subject requires owner-controlled hosting recovery. Login state, nonce, PKCE, Google RS256 signature/issuer/audience/expiry and authorized party are checked. Server-side browser sessions expire after one hour and are invalidated on sign-out. CSV and all admin writes use the same guard; writes also require CSRF and matching browser origin. Machine tokens never grant admin access.

To revoke all browser sessions from the hosting console:

```bash
cd ~/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m server revoke-admin-sessions \
  --database ~/.local/share/lab-logbook/logbook.sqlite
```

Changing the allowed owner email invalidates old sessions on the next guarded request after Web-tab Reload. Do not delete the pinned identity casually; recovery should happen only from the hosting account you control.

## Provision a Windows lab PC

In the hosting Bash console:

```bash
cd ~/lab-logbook
mkdir -p ~/private-client-configs
chmod 700 ~/private-client-configs
~/.virtualenvs/lab-logbook/bin/python -m server provision \
  --database ~/.local/share/lab-logbook/logbook.sqlite \
  --computer LAB-PC-01 --output ~/private-client-configs/LAB-PC-01.json \
  --server-url https://YOUR_USERNAME.pythonanywhere.com
```

Download that private file only through your authenticated Files tab and transfer it to the designated PC as `config/client.json` within a student-only package. Do not share it publicly or reuse it on another PC. Publicly issued cloud HTTPS does not need the LAN-test CA setting; the generated config has no `ca_bundle`. Preserve `simulation: true` until the deliberate kiosk installation on a dedicated lab PC is ready. At first Windows client launch the token is sealed with machine-bound DPAPI and removed from plaintext config. Delete temporary transfer copies/ZIPs after enrollment; an original plaintext provisioning file remains a credential until revoked.

To revoke a lost/stolen lab credential:

```bash
~/.virtualenvs/lab-logbook/bin/python -m server disable-computer \
  --database ~/.local/share/lab-logbook/logbook.sqlite --computer LAB-PC-01
```

Revocation rejects new client API requests. A student already using a PC is not forcibly signed out for an apparent connection failure; cached inactivity rules still apply. Re-enable only after investigation with `enable-computer`, or provision a fresh machine ID/credential. IDs remain strings and all records stay central.

## Acceptance tests before calling deployment complete

- Owner Google identity can view/export records on a different network; another Google identity and machine tokens are rejected.
- A correctly provisioned PC on the lab network can register/log in; the same credential from an outside network is rejected.
- Wrong hostname/certificate, forged forwarding headers, replayed/expired callbacks, missing CSRF and expired/revoked sessions fail closed.
- Reload the app and verify data/identity pins persist. Test a separate SQLite backup/restore and ensure no database/config file is publicly accessible.
- On a dedicated lab account, install the native shell/session integration described in `KIOSK-SETUP.md`, validate ordinary bypass prevention, and test OS logout/startup behavior. Do not infer this from a normal desktop window.
- Turn the development laptop off and verify an actual lab client still reaches the hosted API.

These account-dependent/live tests remain pending. The source package and automated tests do not create a hosting account, Google OAuth application, or deployed website.
