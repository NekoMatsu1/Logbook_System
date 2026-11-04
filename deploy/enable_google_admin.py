"""Switch an existing private server config to owner-only Google sign-in."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import tempfile


def enable(config_path, email, client_id, client_secret):
    path = Path(config_path).resolve(strict=True)
    config = json.loads(path.read_text(encoding='utf-8'))
    email, client_id, client_secret = email.strip().lower(), client_id.strip(), client_secret.strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Enter your exact Gmail or Google Workspace administrator email')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client_id) or not client_secret:
        raise ValueError('Google Web client ID and client secret are required')
    hosts = config.get('TRUSTED_HOSTS', [])
    if len(hosts) != 1 or not re.fullmatch(r'[a-z0-9_-]+\.pythonanywhere\.com', hosts[0]):
        raise ValueError('Expected one lowercase PythonAnywhere hostname in TRUSTED_HOSTS')
    if config.get('PLATFORM_HTTPS_ENFORCED') is not True or config.get('SESSION_COOKIE_SECURE') is not True:
        raise ValueError('Enable Force HTTPS and Secure cookies before switching')
    # Validate before replacing the config. Never reset machine tokens, records, or session secret.
    if not config.get('DATABASE') or len(config.get('SECRET_KEY', '')) < 32:
        raise ValueError('Existing database and persistent session secret are required')
    callback = f'https://{hosts[0]}/auth/callback'
    config.update(ADMIN_AUTH_MODE='google', ADMIN_EMAIL=email,
                  GOOGLE_CLIENT_ID=client_id, GOOGLE_CLIENT_SECRET=client_secret,
                  GOOGLE_REDIRECT_URI=callback, ADMIN_ADDRESSES=[], ADMIN_DIRECT_ONLY=False)
    descriptor, temporary = tempfile.mkstemp(prefix='.google-admin-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(config, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return callback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home()/'.config/lab-logbook/server.json')
    args = parser.parse_args()
    try:
        enable(args.config, input('Your Google administrator email: '),
               input('Google Web client ID: '),
               getpass.getpass('Google Web client secret (hidden): '))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Setup stopped ({type(error).__name__}). Check the private config and entered values.\n')
    print('Google admin sign-in configured. No secrets printed. Reload the web app once.')


if __name__ == '__main__':
    main()
