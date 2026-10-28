"""Build an upload archive from an explicit allowlist; never include local credentials/data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent

def package(destination):
    files = [ROOT / 'common.py', ROOT / 'requirements-server.txt']
    files += [p for p in (ROOT / 'server').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    files += [ROOT / 'deploy' / name for name in (
        'Dockerfile', 'compose.yaml', 'Caddyfile', '.env.example', 'prepare.py', 'README.md',
        'configure_oracle.py', 'ORACLE.md')]
    files += [ROOT / '.dockerignore']
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    return destination

if __name__ == '__main__':
    print(package(ROOT / '.tools' / 'logbook-deploy.zip'))
