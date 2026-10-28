"""Prepare an API-only LAN TLS gateway and one provisioned student-only ZIP.

No account, startup, firewall, certificate-store or OS power changes are made.
"""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import secrets
import shutil
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED
from server.db import connect, initialize

ROOT = Path(__file__).resolve().parent.parent

def generate_certificates(folder, address, openssl):
    folder.mkdir(parents=True, exist_ok=True)
    ca, key = folder/'ca.pem', folder/'ca.key'
    def run(arguments):
        subprocess.run([str(openssl), *arguments],check=True,capture_output=True,text=True,cwd=folder)
    if not ca.exists() or not key.exists():
        if ca.exists() or key.exists():
            raise RuntimeError('Incomplete existing CA; preserve/review certificate files before retrying')
        run(['req','-x509','-newkey','rsa:2048','-nodes','-days','365','-sha256',
             '-keyout','ca.key','-out','ca.pem','-subj','/CN=Logbook LAN Test CA',
             '-addext','basicConstraints=critical,CA:TRUE,pathlen:0',
             '-addext','keyUsage=critical,keyCertSign,cRLSign'])
    certificate = folder/'server.pem'
    private_key = folder/'server.key'
    extension = folder/'server.ext'
    extension.write_text(f'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:{address}\n',encoding='ascii')
    run(['req','-new','-newkey','rsa:2048','-nodes','-keyout','server.key','-out','server.csr','-subj',f'/CN={address}'])
    run(['x509','-req','-in','server.csr','-CA','ca.pem','-CAkey','ca.key','-set_serial',
         '0x'+secrets.token_hex(16),'-out','server.pem','-days','90','-sha256','-extfile','server.ext'])
    for path in (key,private_key):
        path.chmod(0o600)
    return ca,certificate,private_key

def gateway_config(address, certificate, private_key):
    return f'''{{
    admin off
    auto_https off
}}
https://{address}:5443 {{
    bind {address}
    tls "{certificate.as_posix()}" "{private_key.as_posix()}"
    handle /api/* {{
        request_body {{
            max_size 16KB
        }}
        reverse_proxy 127.0.0.1:5001 {{
            header_up X-Forwarded-For {{remote_host}}
            header_up X-Forwarded-Proto {{scheme}}
        }}
    }}
    handle {{
        respond "Administrator dashboard is private" 403
    }}
}}
'''

def build_package(destination, config, ca):
    # Explicit client-only allowlist: no server code, database, helper, or private TLS keys.
    files = ['common.py','requirements-client.txt','client/__init__.py','client/__main__.py',
             'client/api.py','client/state.py','client/instance.py','client/credentials.py','client/gate.py',
             'client/kiosk.py','client/kiosk_warning.py','client/platforms/desktop_gate.py','client/platforms/__init__.py',
             'client/platforms/base.py','client/platforms/windows.py','client/platforms/linux.py',
             'scripts/kiosk_entry.py','scripts/install-windows-kiosk.ps1','scripts/install-linux-kiosk.sh','KIOSK-SETUP.md']
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(ROOT/name,name)
        archive.writestr('config/client.json',json.dumps(config,indent=2))
        archive.write(ca,'config/lan-ca.pem')
        archive.writestr('start-student.cmd',r'''@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
if not exist ".venv\client-ready" (
    .venv\Scripts\python.exe -m pip install -r requirements-client.txt
    if errorlevel 1 goto failed
    echo ready> .venv\client-ready
)
.venv\Scripts\python.exe -m client --config config/client.json
if errorlevel 1 goto failed
exit /b 0
:failed
echo Student client failed. Install Python 3.11+ with Tcl/Tk and the py launcher, then retry.
pause
exit /b 1
'''.replace('\n','\r\n'))
        archive.writestr('start-student.sh','#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\n[ -d .venv ] || python3 -m venv .venv\n.venv/bin/python -m pip install -r requirements-client.txt\nexec .venv/bin/python -m client --config config/client.json\n')
        archive.writestr('READ-ME.txt',f'''STUDENT CLIENT ONLY — {config['computer_id']}
Server: {config['server_url']}

1. Install Python 3.11+ with Tcl/Tk and the py launcher on Windows.
2. Extract this entire ZIP into its own folder. Do not run inside the ZIP.
3. Double-click start-student.cmd. Keep its console open.
4. Register/login in the desktop program. All student/session records stay on the laptop server.

The laptop and this PC must be awake and on the same LAN. The laptop's backend and HTTPS gateway must be running; allow gateway TCP 5443 only on the trusted private network.
SIMULATION is enabled: no real sign-out or shutdown occurs.
This ZIP does not contain the server, dashboard or database. Network dashboard requests return 403.
The CA certificate is public and is used only by this program. Nothing is added to the OS certificate store.
The machine token in config/client.json is private; do not publish this ZIP or reuse it on multiple PCs.
Use a separate provisioned package/computer ID for each PC. Do not give students SSH credentials.

Linux Mint: install python3-venv and python3-tk, use X11, then run sh start-student.sh.
''')
    return destination

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--server-ip',required=True)
    parser.add_argument('--computer',default='LAB-PC-02')
    parser.add_argument('--database',default='data/logbook.sqlite')
    bundled_openssl = r'C:\msys64\ucrt64\bin\openssl.exe'
    parser.add_argument('--openssl',default=bundled_openssl if Path(bundled_openssl).is_file() else shutil.which('openssl'))
    args=parser.parse_args()
    if not args.openssl:
        parser.error('OpenSSL 1.1.1+ is required; pass its executable with --openssl')
    address=ipaddress.ip_address(args.server_ip)
    if address.version != 4 or address.is_loopback or not address.is_private:
        parser.error('Use the laptop LAN IPv4 address')
    if not args.computer or len(args.computer)>64 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.computer):
        parser.error('Computer ID must use 1–64 letters, digits, hyphens or underscores')
    output=ROOT/'dist'/f'student-{args.computer}.zip'
    if output.exists():
        parser.error('Package already exists; preserve it or provision a different computer ID')
    folder=ROOT/'.tools'/'lan'
    ca,certificate,key=generate_certificates(folder/'certs',str(address),args.openssl)
    (folder/'Caddyfile').write_text(gateway_config(str(address),certificate,key),encoding='utf-8')
    initialize(args.database)
    token=secrets.token_urlsafe(48)
    with connect(args.database) as db:
        if db.execute('SELECT 1 FROM computers WHERE computer_id=?',(args.computer,)).fetchone():
            parser.error('Computer already provisioned; use a fresh unique computer ID')
        db.execute('INSERT INTO computers(computer_id,token_hash) VALUES(?,?)',(args.computer,hashlib.sha256(token.encode()).hexdigest()))
        build_package(output,dict(server_url=f'https://{address}:5443',computer_id=args.computer,
                                 machine_token=token,simulation=True,allow_loopback_http=False,ca_bundle='config/lan-ca.pem'),ca)
    print(f'Created {output}. Contains a private machine token: transfer securely, never publish.')

if __name__ == '__main__':
    main()
