# Remote deployment with a private administrator dashboard

For the free/no-card hosted WSGI option with owner-only Google sign-in, use [PYTHONANYWHERE.md](PYTHONANYWHERE.md). This file describes the separate Linux-VM/SSH deployment. Both now support lab-network checks and revocable machine credentials; the container environment requires `LOGBOOK_LAB_NETWORKS` to be set to the approved lab public IP/CIDR.

Status: deployment files prepared, **no cloud server created**. No provider account/VM or SSH connection is available in this session. Docker is not installed on this development laptop, so image building, Compose startup, live certificate issuance and cloud firewall behavior have not been tested here. Python security tests pass locally. Do not describe this as a completed or audited production deployment.

## Free hosting constraint

The user requires free hosting. A Linux VM on [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/) is a candidate that can retain this Flask + SQLite stack with persistent local storage. Only select resources explicitly labeled Always Free-eligible in the current console and remain within the account's current allowances; do not select a paid shape, upgrade to pay-as-you-go, or rely on expiring trial credits. Oracle's [FAQ](https://www.oracle.com/cloud/free/faq/) states signup requires card verification. Account creation and verification must be completed by the account owner; do not paste card details, passwords, or private SSH keys into chat.

Oracle documents [capacity limits and possible reclamation of idle Always Free VMs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). Therefore free hosting does not establish guaranteed 24/7 availability. Keep independent encrypted backups and check actual free eligibility at provisioning time. No cloud resource or paid subscription has been ordered. A school-provided persistent Linux server is another option if one becomes available.

[Render Free](https://render.com/docs/free) sleeps on idle and cannot attach persistent disks. Its ephemeral filesystem would lose this SQLite database during replacement/redeploy, so do not deploy this project there on the free plan. Render was considered before the free-only constraint was confirmed; no Render service was created. Sites hosting does not run this Flask/SQLite process model, so the stack was preserved rather than replaced.

## Security boundaries

- Flask listens only on the VM's `127.0.0.1:5000`. It never binds the administrator dashboard to the public network.
- Caddy exposes only `/api/*` over HTTPS. It denies every other public path, including `/`, `/admin/*`, exports, and dashboard assets. It overwrites forwarding headers from the actual peer and TLS state.
- Production Flask independently rejects administrator requests that passed through the trusted proxy, even if the forwarded address is loopback. An authorized administrator uses an SSH key and local port forwarding to reach the loopback listener. SSH is the identity/access boundary; there is no new app password screen.
- Allowed Host values, same-origin admin writes, CSRF tokens, signed HttpOnly/SameSite cookies, CSP, frame blocking, no-sniff and no-store headers provide additional protections. Production refuses startup without an external stable secret, private admin mode, and loopback-only admin addresses.
- The app container runs as an unprivileged user with a read-only root filesystem; SQLite lives on a persistent named volume. Only the proxy receives public HTTP/HTTPS traffic. No Docker socket or machine credentials are mounted in the proxy.

This does not make the application immune to threats. A compromised administrator device/SSH account can access admin; any untrusted process already running on the VM can reach loopback. Do not share the VM with untrusted users/workloads. Use individual SSH keys, protect private keys, keep the OS/images/dependencies updated, restrict SSH in the provider firewall to the administrator's source address where practical, and disable unused access methods after validating your recovery access. API tokens are machine credentials, not student identity proof. ID-only login permits someone to claim a known student ID. A readable shared-account client token can be copied. The OS kiosk/access-control gaps in the main README remain.

No public API rate limiter or DDoS mitigation is implemented here. High-entropy tokens resist guessing, but a public endpoint can still consume resources or be abused with a stolen token. Prefer private lab networking/VPN where feasible, or provider edge/network controls for public deployment. Tests are not a penetration test. No automatic firewall/account/startup changes were made to the laptop.

## Prepare the upload on this laptop

```powershell
.\.venv\bin\python.exe deploy/package.py
```

This produces ignored `.tools/logbook-deploy.zip` using a code-only allowlist. It excludes the local database, all client configs/tokens, environments, caches, backups and secrets. Existing local students/sessions are not silently uploaded; remote provisioning starts fresh. If historical data must be moved, plan an explicit protected SQLite backup/restore instead of copying an active database.

After the account owner creates an Always Free Linux VM and establishes SSH key access, upload that archive using `scp` with the actual VM address and your administrative account. Use Ubuntu 24.04 LTS (amd64 or arm64) with persistent boot storage. Follow the provider's current Always Free labels rather than assuming fixed CPU/memory quotas. Do not share the SSH private key. A DNS hostname (including a suitable free DNS hostname) must point to the VM; no domain has been registered here.

## On the Linux VM

The commands below assume the extracted project is in `/opt/lab-logbook`, owned by the administrative account. Install Docker Engine and its Compose plugin using [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/) before running these commands. Configure the provider network/security rules deliberately: HTTP 80 and HTTPS 443 for certificate/API traffic; SSH 22 restricted to administrator addresses. Do not open 5000 or Caddy's management port 2019. Host networking is intentional and targets a dedicated Linux VM; do not substitute ordinary container port publishing without reviewing loopback/IP restrictions.

```bash
cd /opt/lab-logbook/deploy
cp .env.example .env
# Edit .env: LOGBOOK_DOMAIN must be your real DNS hostname, not example.org.
editor .env
python3 prepare.py
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 app edge
```

`prepare.py` generates a random session secret once, never prints it, and never overwrites it. Its host directory is mode 0700; the mounted secret file is readable by the unprivileged application UID. Preserve and protect that directory. The app starts at Docker boot and restarts on process failure using `unless-stopped`. An explicitly stopped service remains stopped until started again. Health checks report health; they do not independently restart a hung but still-running process.

The public hostname must resolve to this VM and ports 80/443 must be reachable for [Caddy's automatic HTTPS](https://caddyserver.com/docs/automatic-https). Do not disable certificate verification on clients to bypass a DNS/TLS error. Do not put another reverse proxy in front without explicitly reviewing peer and forwarded-header handling.

## Provision a lab PC centrally

```bash
cd /opt/lab-logbook/deploy
sudo install -d -m 700 -o 10001 -g 10001 provisioned
sudo docker compose run --rm --no-deps -v "$PWD/provisioned:/provisioned" app \
  python -m server provision --database /app/data/logbook.sqlite \
  --computer LAB-PC-01 --output /provisioned/LAB-PC-01.json \
  --server-url https://YOUR_REAL_HOSTNAME
# Make a temporary account-readable copy for authenticated scp; do not print it.
sudo install -m 600 -o "$USER" provisioned/LAB-PC-01.json "$HOME/LAB-PC-01.json"
```

Retrieve that file through authenticated `scp` into an ignored local path such as `config/cloud-client.json`. Protect it with local ACLs, then remove the temporary home-directory transfer copy on the server. Run the desktop with `--config config/cloud-client.json`. Its `simulation` remains true and `allow_loopback_http` is false. Provision each additional machine separately with a distinct computer ID and config. Production defaults are used automatically; the laptop's shortened timer database is not uploaded.

## Open the administrator dashboard privately

From the designated administrator computer, keep this SSH tunnel running:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:5500:127.0.0.1:5000 ADMIN_USER@VM_ADDRESS
```

Then open **http://127.0.0.1:5500/admin/overview**. Only the local browser-to-local-SSH segment uses HTTP; the remote connection is encrypted/authenticated by SSH. Admin cookies are HttpOnly/SameSite and intentionally not Secure in this private-loopback mode so the forwarded HTTP session works. The public HTTPS endpoint cannot render or create an administrator browser session. Never forward this local tunnel to `0.0.0.0` or share it on the lab LAN. Other users/processes on the administrator computer can reach its loopback tunnel, so OS account/device access remains part of the trust boundary.

The tunnel/client computer can be off without stopping the remote server. Other lab PCs continue connecting to the remote API. If you turn off the administrator laptop, reconnect the tunnel when you next need the dashboard. Verify the server independently from a different device before claiming laptop-independent operation.

## Backup and operational checks

Create a consistent SQLite backup using its backup API, not a raw copy of a live WAL database:

```bash
cd /opt/lab-logbook/deploy
sudo install -d -m 700 -o 10001 -g 10001 backups
sudo docker compose run --rm --no-deps -v "$PWD/backups:/backups" app \
  python -c 'import sqlite3; from datetime import datetime, timezone; name=datetime.now(timezone.utc).strftime("/backups/logbook-%Y%m%dT%H%M%SZ.sqlite"); src=sqlite3.connect("file:/app/data/logbook.sqlite?mode=ro",uri=True); dst=sqlite3.connect(name); src.backup(dst); dst.close(); src.close()'
```

Protect backups as student data, transfer encrypted copies off the VM, and test a restore into a separate volume before relying on them. No backup schedule or off-site storage account has been configured. Do not use `docker compose down -v`: it deletes named volumes, including the central database.

Acceptance checks after actual deployment:

1. Public `/admin/overview`, `/admin/export.csv` and `/` return 403; public `/api/students/unknown` returns 401 without a machine token.
2. Private SSH dashboard works; cross-site requests and forged forwarding headers do not open admin access.
3. A provisioned simulated client registers, confirms ID login, creates a central session, and simulates inactivity logout.
4. Restart app/container/VM and verify registrations and historical sessions persist; test an off-VM backup restore.
5. Turn off the development laptop and confirm another lab computer can still use the cloud API.

These deployment checks remain unperformed until a real VM, DNS and SSH access exist.
