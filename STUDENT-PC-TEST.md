# Test a second PC as a student client

This setup uses **your laptop as the only central server/admin host**. The second PC runs only the student desktop program. No cloud account is needed for this LAN test. Both computers must be powered on and connected to the same trusted LAN; Wi-Fi client/AP isolation or a guest network can prevent communication. Your laptop must remain awake during this particular test.

Prepared package: `dist/student-LAB-PC-02.zip`. Your laptop's detected Wi-Fi IP at preparation time was **192.168.1.128**. Check `ipconfig` before testing. If the address changes, the endpoint/certificate/package must be prepared again for that address; use a reserved LAN address to avoid this. Do not publish this ZIP: it contains a unique machine token. Give it only to the PC designated `LAB-PC-02`.

## On your laptop

Open two PowerShell terminals in this workspace:

```powershell
# Terminal 1: central backend + local-only administrator dashboard
.\scripts\run-lan-server.ps1 -ServerIP 192.168.1.128
```

```powershell
# Terminal 2: encrypted, API-only LAN gateway
.\scripts\run-lan-gateway.ps1
```

Keep both terminals running. If they were already started during verification and are still running, do not start duplicates. Backend port 5001 and gateway port 5443 must each have only one listener. The normal development server on port 5000 may remain separate; both backends use the same central SQLite database. For this test use only the dashboard URL below, to avoid cookies from separate development-server instances overwriting each other.

Open the administrator dashboard **on your laptop**:

**http://127.0.0.1:5001/admin/overview**

The backend binds only to loopback. Caddy accepts HTTPS on the laptop LAN address at port 5443 and forwards only `/api/*`. Every other gateway path returns 403. The app also refuses proxied admin requests. Student machine tokens do not authorize administrator routes.

## Allow the test connection deliberately

No firewall or network profile settings were changed automatically. If Windows blocks the gateway, first make sure this really is your trusted private home/lab LAN. Use Windows Settings to mark that network Private if appropriate. Then run this once in an **Administrator PowerShell on your laptop**, using the actual project path:

```powershell
$gatewayPath = (Resolve-Path -LiteralPath 'C:\Users\User\$HOME\Documents\Logbook_System\.tools\lan\caddy.exe').Path
New-NetFirewallRule -DisplayName 'Logbook student API LAN test' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5443 -Profile Private -RemoteAddress LocalSubnet -Program $gatewayPath
```

This permits only the gateway program/port on Private networks from the local subnet. Do not open backend ports 5000/5001, expose the dashboard, disable the firewall, or configure router internet port forwarding for this test. An elevated shell is required for firewall changes. If a managed school network blocks peer traffic, its administrator must provide an appropriate test network.

## On the other Windows PC

1. Install standard Python 3.11+ with Tcl/Tk and the `py` launcher. Internet is needed for its initial `requests` dependency installation.
2. Copy **only** `dist/student-LAB-PC-02.zip` from your laptop, through a trusted transfer such as a USB drive. Do not copy the whole repository, `.venv`, database, laptop client config or TLS private keys.
3. Extract the ZIP completely into its own folder.
4. Double-click **start-student.cmd**. It creates a client-only virtual environment, installs `requirements-client.txt`, and runs the Tkinter student program. Keep its console open.
5. The window should show `LAB-PC-02` and **SIMULATION**. Register a student, select Login, confirm the displayed name, and start a session.
6. On your laptop, refresh Overview/Records to see the centrally recorded session. Wait for inactivity to test a simulated logout. No actual OS sign-out/shutdown occurs.

The package contains the student modules, common timer defaults, public CA certificate, one client config and launchers. It does **not** contain Flask/server modules, dashboard templates, a student database, helper service, SSH credentials, CA private key or server private key. The certificate is trusted only by this client's requests session; nothing is installed into either OS certificate store. TLS certificate and hostname/IP verification remain enabled.

## Check connectivity and administrator blocking

On the second PC, in PowerShell:

```powershell
Test-NetConnection 192.168.1.128 -Port 5443
```

`TcpTestSucceeded` should be `True`. If false, check both laptop terminals, the laptop IP, Private firewall rule, and Wi-Fi peer isolation.

The student package's endpoint is **https://192.168.1.128:5443**. Opening `/admin/overview` through that endpoint must return **403**, not dashboard content. A browser may first show a certificate warning because the private test CA is configured only in the student app; do not disable certificate checking or install broad browser trust to work around that. For a verified check, run this inside the extracted student folder:

```powershell
.\.venv\Scripts\python.exe -c "import requests; r=requests.get('https://192.168.1.128:5443/admin/overview',verify='config/lan-ca.pem',timeout=5); print(r.status_code); assert r.status_code == 403"
```

On the second PC, `127.0.0.1:5001` means that second PC itself; there is no local admin server in this package. Student users should never receive your SSH credentials or a server installation. This setup does not establish individual administrator identity against other users/processes on your own laptop: loopback access trusts that laptop's OS account/device. Secure that device separately.

## Prepare additional computers

Run on your laptop, once per new unique computer ID:

```powershell
.\.venv\bin\python.exe -m scripts.prepare_lan_test --server-ip 192.168.1.128 --computer LAB-PC-03
```

Use `.venv\Scripts\python.exe` instead if you later switch to standard CPython on the laptop. Preserve the generated `.tools/lan/certs` CA on the laptop; only its public `ca.pem` goes into student packages. The script refuses to overwrite an existing ZIP/computer registration. It issues a 90-day test server certificate; it does not perform automatic renewal. It requires a current OpenSSL executable. The prepared Caddy executable was downloaded from the official Caddy release; no system installation/startup changes were performed. Restart the gateway after regenerating its certificate/configuration.

To remove the optional firewall rule after testing, run elevated:

```powershell
Get-NetFirewallRule -DisplayName 'Logbook student API LAN test' | Remove-NetFirewallRule
```

This is a supervised LAN prototype test, not secure kiosk deployment or cloud hosting. A real second-device test still needs to be performed by you; a same-laptop TLS check cannot prove that Windows firewall and your Wi-Fi permit the other PC.
