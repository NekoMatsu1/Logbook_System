"""Generate an external session secret without printing it or overwriting one."""
import os
from pathlib import Path
import secrets

def main():
    folder = Path(__file__).resolve().parent / 'secrets'
    folder.mkdir(mode=0o700, exist_ok=True)
    destination = folder / 'flask_secret'
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        print('Existing deployment secret preserved.')
        return
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        output.write(secrets.token_hex(48))
    # Directory 0700 protects the host; mounted file must be readable by UID 10001.
    print('Deployment secret generated. No credential values printed.')

if __name__ == '__main__':
    main()
