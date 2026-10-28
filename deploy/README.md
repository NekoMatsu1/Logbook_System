# Internet deployment with an administrator-IP-restricted dashboard

Starting without an Oracle account? Follow [the Oracle setup guide](ORACLE.md) first.

This Linux VM deployment supports student PCs at different locations. Each client connects over HTTPS to the central server using its own revocable machine credential; clients do not need to share a LAN or have a fixed public IP. The dashboard is available without an application username/password only from the designated administrator computer's public IP. The separate [PythonAnywhere option](PYTHONANYWHERE.md) uses Google owner sign-in and is network-restricted by default.

Status: deployment files prepared, **no cloud server created**. No provider account/VM or SSH connection is available in this session. Docker is not installed on this development laptop, so image building, Compose startup, live certificate issuance and cloud firewall behavior have not been tested here. Python security tests pass locally. Do not describe this as a completed or audited production deployment.

## Free hosting constraint

The user requires free hosting. A Linux VM on [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/) is a candidate that can retain this Flask + SQLite stack with persistent local storage. Only select resources explicitly labeled Always Free-eligible in the current console and remain within the account's current allowances; do not select a paid shape, upgrade to pay-as-you-go, or rely on expiring trial credits. Oracle's [FAQ](https://www.oracle.com/cloud/free/faq/) states signup requires card verification. Account creation and verification must be completed by the account owner; do not paste card details, passwords, or private SSH keys into chat.

Oracle documents [capacity limits and possible reclamation of idle Always Free VMs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). Therefore free hosting does not establish guaranteed 24/7 availability. Keep independent encrypted backups and check actual free eligibility at provisioning time. No cloud resource or paid subscription has been ordered. A school-provided persistent Linux server is another option if one becomes available.

[Render Free](https://render.com/docs/free) sleeps on idle and cannot attach persistent disks. Its ephemeral filesystem would lose this SQLite database during replacement/redeploy, so do not deploy this project there on the free plan. Render was considered before the free-only constraint was confirmed; no Render service was created. Sites hosting does not run this Flask/SQLite process model, so the stack was preserved rather than replaced.

## Security boundaries

- Flask listens only on the VM's `127.0.0.1:5000`. It never binds the administrator dashboard to the public network.
- Caddy exposes `/api/*` over HTTPS to clients at any location when `LOGBOOK_ALLOW_REMOTE_CLIENTS=1`. All student API operations still require the unique provisioned machine token and computer ID; disabling a computer revokes that token.
- Caddy and Flask both restrict browser/dashboard requests to the single `LOGBOOK_ADMIN_ADDRESS`. The public address must be the administrator computer's stable egress IP (or a stable VPN egress address). No application sign-in is used; clients from other IPs receive 403. SSH remains restricted to administrator addresses as a separate recovery channel.
- Caddy overwrites forwarded headers from the actual peer. Flask trusts those headers only from loopback Caddy and independently checks the allowlisted administrator IP. Allowed Host values, same-origin admin writes, CSRF tokens, signed HttpOnly/Secure cookies, CSP, frame blocking, no-sniff and no-store headers provide additional protections.
- The app container runs as an unprivileged user with a read-only root filesystem; SQLite lives on a persistent named volume. Only the proxy receives public HTTP/HTTPS traffic. No Docker socket or machine credentials are mounted in the proxy.

This does not make the application immune to threats. Anyone using the designated administrator computer/network can access the dashboard; a stolen client token can act as that computer until revoked. Do not share the VM with untrusted users/workloads. Use individual SSH keys, protect client configs, keep the OS/images/dependencies updated, restrict SSH in the provider firewall, and disable unused access methods after validating recovery access. API tokens identify enrolled computers, not individual students. ID-only login permits someone to claim a known student ID. A readable shared-account client token can be copied. The OS kiosk/access-control gaps in the main README remain.

No public API rate limiter or DDoS mitigation is implemented here. High-entropy tokens resist guessing, but a public endpoint can still consume resources or be abused with a stolen token. Use provider edge/network controls and promptly revoke lost machine credentials. Tests are not a penetration test. No automatic firewall/account/startup changes were made to the laptop.

## Prepare the upload on this laptop

```powershell
.\.venv\bin\python.exe deploy/package.py
```

This produces ignored `.tools/logbook-deploy.zip` using a code-only allowlist. It excludes the local database, all client configs/tokens, environments, caches, backups and secrets. Existing local students/sessions are not silently uploaded; remote provisioning starts fresh. If historical data must be moved, plan an explicit protected SQLite backup/restore instead of copying an active database.

After the account owner creates an Always Free Linux VM and establishes SSH key access, upload that archive using `scp` with the actual VM address and your administrative account. Use Ubuntu 24.04 LTS (amd64 or arm64) with persistent boot storage. Follow the provider's current Always Free labels rather than assuming fixed CPU/memory quotas. Do not share the SSH private key. A DNS hostname (including a suitable free DNS hostname) must point to the VM; no domain has been registered here.

## On the Linux VM

The commands below assume the extracted project is in `/opt/lab-logbook`, owned by the administrative account. Install Docker Engine and its Compose plugin using [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/) before running these commands. Configure the provider network/security rules deliberately: HTTP 80 and HTTPS 443; SSH 22 restricted to administrator addresses. Do not open 5000 or Caddy's management port 2019. Set `LOGBOOK_ADMIN_ADDRESS` in `.env` to the administrator computer's public IPv4 address (not its private `192.168.x.x`/`10.x.x.x` address). If the IP changes, update `.env` and recreate the services from the administrator's new address. Host networking is intentional and targets a dedicated Linux VM; do not substitute ordinary container port publishing without reviewing loopback/IP restrictions.

```bash
cd /opt/lab-logbook/deploy
cp .env.example .env
# Edit .env: set the real hostname and administrator public IP.
# Set LOGBOOK_ALLOW_REMOTE_CLIENTS=1 for clients at unrelated locations.
# Leave it 0 to require LOGBOOK_LAB_NETWORKS to list approved public CIDRs.
editor .env
python3 prepare.py
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 app edge
```

`prepare.py` generates a random session secret once, never prints it, and never overwrites it. Its host directory is mode 0700; the mounted secret file is readable by the unprivileged application UID. Preserve and protect that directory. The app starts at Docker boot and restarts on process failure using `unless-stopped`. An explicitly stopped service remains stopped until started again. Health checks report health; they do not independently restart a hung but still-running process.

The public hostname must resolve directly to this VM and ports 80/443 must be reachable for [Caddy's automatic HTTPS](https://caddyserver.com/docs/automatic-https). Do not disable certificate verification on clients to bypass a DNS/TLS error. Do not put another reverse proxy in front without explicitly reviewing peer and forwarded-header handling. Verify that the admin dashboard is reachable from the designated public IP and returns 403 from another network.

## Connect PCs from different locations

Set `LOGBOOK_ALLOW_REMOTE_CLIENTS=1` in `.env` only when clients need to connect from outside a fixed lab network. Keep `LOGBOOK_LAB_NETWORKS` blank in that mode. This removes the source-IP restriction for student API routes only; it does not expose admin routes, which remain restricted to `LOGBOOK_ADMIN_ADDRESS`. The default is `0`, which preserves CIDR restrictions. Restart with `sudo docker compose up -d` after a deliberate `.env` change.

Provision one distinct computer ID/configuration per PC. The generated config contains a private machine credential: transfer it securely, do not publish it, and never reuse it on another computer.

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

## Open the administrator dashboard

From the allowed administrator network, open **https://YOUR_REAL_HOSTNAME/admin/overview**. Caddy and Flask both check the administrator's public IP. Cookies require HTTPS. An HTTP SSH tunnel does not replace this address check or provide the HTTPS cookie connection.

The administrator PC can be off without stopping the VM. Other provisioned PCs can still connect to the server. Verify this from another PC before relying on it.

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

1. From a network outside the administrator allowlist, `/admin/overview`, `/admin/export.csv` and `/` return 403. `/api/students/unknown` returns 401 without a machine token.
2. The HTTPS dashboard works from the allowed administrator network; cross-site requests and forged forwarding headers do not open admin access.
3. A provisioned simulated client registers, confirms ID login, creates a central session, and simulates inactivity logout.
4. Restart app/container/VM and verify registrations and historical sessions persist; test an off-VM backup restore.
5. Turn off the development laptop and confirm another lab computer can still use the cloud API.

These deployment checks remain unperformed until a real VM, DNS and SSH access exist.
