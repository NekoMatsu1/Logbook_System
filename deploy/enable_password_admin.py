"""Set an admin password privately in the hosting console, without Google setup."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import tempfile

from werkzeug.security import generate_password_hash


def enable(config_path, username, password):
    path = Path(config_path).resolve(strict=True)
    config = json.loads(path.read_text(encoding='utf-8'))
    username = username.strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', username):
        raise ValueError('Username must be 3–64 letters, numbers, dots, hyphens or underscores')
    if not 15 <= len(password) <= 1024:
        raise ValueError('Use a password or passphrase of at least 15 characters (maximum 1024)')
    if config.get('PLATFORM_HTTPS_ENFORCED') is not True or config.get('SESSION_COOKIE_SECURE') is not True:
        raise ValueError('Enable Force HTTPS and Secure cookies first')
    if not config.get('DATABASE') or len(config.get('SECRET_KEY','')) < 32:
        raise ValueError('Existing database and persistent session secret are required')
    config.update(ADMIN_AUTH_MODE='password', ADMIN_USERNAME=username,
                  ADMIN_PASSWORD_HASH=generate_password_hash(password, method='scrypt:32768:8:1'),
                  ADMIN_ADDRESSES=[], ADMIN_DIRECT_ONLY=False, SECRET_KEY=secrets.token_hex(48))
    # Remove unused Google credentials; the database and machine settings stay intact.
    for key in ('GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REDIRECT_URI','ADMIN_EMAIL'):
        config.pop(key, None)
    descriptor, temporary = tempfile.mkstemp(prefix='.password-admin-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(config, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home()/'.config/lab-logbook/server.json')
    args = parser.parse_args()
    username = input('Choose admin username: ')
    password = getpass.getpass('Choose admin passphrase (at least 15 characters, hidden): ')
    if password != getpass.getpass('Repeat passphrase (hidden): '):
        parser.exit(1, 'Passphrases did not match. Configuration unchanged.\n')
    try:
        enable(args.config, username, password)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    except OSError:
        parser.exit(1, 'Could not save private config. Check its path and permissions.\n')
    print('Admin password configured. Reload the web app once, then use your usual dashboard link.')


if __name__ == '__main__':
    main()
