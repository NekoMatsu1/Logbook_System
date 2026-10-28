"""Build a public, credential-free Windows client with its Python/Tk runtime."""
import hashlib
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent


def package(bundle, output):
    bundle, output = Path(bundle), Path(output)
    if not (bundle / 'Logbook.exe').is_file():
        raise RuntimeError('Build is missing Logbook.exe')
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                archive.write(path, 'Logbook/' + path.relative_to(bundle).as_posix())
        archive.write(ROOT / 'DOWNLOAD.md', 'Logbook/READ-ME.md')
        archive.write(ROOT / 'config/client.example.json', 'Logbook/config/client.example.json')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    return output


def main():
    if sys.platform != 'win32' or 'mingw' in sys.version.lower():
        raise SystemExit('Build on Windows using standard python.org CPython, not MSYS2.')
    # Use a fresh work directory so private local files never enter the executable.
    work = ROOT / '.tools' / 'windows-build'
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                    '--windowed', '--noupx', '--name', 'Logbook', '--paths', str(ROOT),
                    '--distpath', str(work / 'dist'), '--workpath', str(work / 'work'),
                    '--specpath', str(work), '--collect-data', 'certifi',
                    '--exclude-module', 'server', str(ROOT / 'scripts/desktop_entry.py')], check=True, cwd=ROOT)
    output = ROOT / 'dist' / 'Logbook-Windows-x64.zip'
    package(work / 'dist' / 'Logbook', output)
    # A clean extraction is what users receive; test it from an unrelated working directory.
    smoke = work / 'smoke'
    smoke.mkdir(exist_ok=True)
    with ZipFile(output) as archive:
        archive.extractall(smoke)
    report = work / 'smoke-result.json'
    report.unlink(missing_ok=True)
    subprocess.run([str(smoke / 'Logbook/Logbook.exe'), '--self-test', str(report)],
                   check=True, timeout=60, cwd=work)
    import json
    if not json.loads(report.read_text(encoding='utf-8')).get('ok'):
        raise RuntimeError('Bundled runtime self-test failed')
    print(f'Built and smoke-tested: {output}')


if __name__ == '__main__':
    main()
