import argparse
import hashlib
import json
import os
import secrets
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from .app import create_app, DEFAULTS
from .db import connect, initialize

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'provision', 'serve', 'backup', 'dev-timers', 'disable-computer', 'enable-computer', 'revoke-admin-sessions'])
    parser.add_argument('--database', default='data/logbook.sqlite')
    parser.add_argument('--computer', default='LAB-PC-01')
    parser.add_argument('--output')
    parser.add_argument('--server-url', default='http://127.0.0.1:5000')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    if args.command == 'backup':
        if not args.output:
            parser.error('Backup requires an explicit --output path')
        from .backup import backup_database
        destination=backup_database(args.database,args.output)
        print(f'Database backup created and integrity checked: {destination}')
        return
    initialize(args.database)
    if args.command == 'provision':
        url = urlsplit(args.server_url)
        try:
            loopback = ipaddress.ip_address(url.hostname or '').is_loopback
        except ValueError:
            loopback = url.hostname == 'localhost'
        if not url.hostname or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment or not (
            url.scheme == 'https' or url.scheme == 'http' and loopback):
            parser.error('Server URL must be HTTPS, or HTTP loopback for development, without credentials/path')
        destination = Path(args.output or 'config/client.json')
        if destination.exists():
            parser.error('Output exists; choose a new path to avoid overwriting credentials')
        token = secrets.token_urlsafe(48)
        destination.parent.mkdir(parents=True, exist_ok=True)
        created=False
        try:
            with connect(args.database) as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM computers WHERE computer_id=?', (args.computer,)).fetchone():
                    parser.error('Computer already provisioned')
                db.execute('INSERT INTO computers(computer_id,token_hash) VALUES(?,?)',
                           (args.computer, hashlib.sha256(token.encode()).hexdigest()))
                descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                created=True
                with os.fdopen(descriptor,'w',encoding='utf-8') as output:
                    json.dump(dict(server_url=args.server_url.rstrip('/'),computer_id=args.computer,
                                   machine_token=token,simulation=True,allow_loopback_http=url.scheme=='http'),output,indent=2)
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise
        print(f'Credential written to {destination}; protect with account ACLs. Token not printed.')
    elif args.command in ('disable-computer','enable-computer'):
        with connect(args.database) as db:
            if not db.execute('UPDATE computers SET enabled=? WHERE computer_id=?',
                              (int(args.command=='enable-computer'),args.computer)).rowcount:
                parser.error('Unknown computer')
        print(f'{args.computer}: {args.command}')
    elif args.command == 'revoke-admin-sessions':
        with connect(args.database) as db:
            db.execute('DELETE FROM admin_sessions')
            db.execute('DELETE FROM oauth_states')
        print('All administrator browser sessions revoked')
    elif args.command == 'dev-timers':
        settings = DEFAULTS | dict(inactivity_seconds=15, logout_warning_seconds=10,
                                  shutdown_wait_seconds=30, shutdown_warning_seconds=10, identification_timeout_seconds=15)
        with connect(args.database) as db:
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET value=excluded.value', ('*', json.dumps(settings)))
        print('Development timers applied to this database')
    elif args.command == 'serve':
        from waitress import serve
        # The app accepts forwarded headers only from one explicitly configured peer.
        serve(create_app({'DATABASE': args.database}), host=args.host, port=args.port,
              clear_untrusted_proxy_headers=False)
    else:
        print(f'Initialized/migrated schema v2: {args.database}')

if __name__ == '__main__':
    main()
