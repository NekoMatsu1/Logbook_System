"""Build a public, credential-free Windows client with its Python/Tk runtime."""
import hashlib
from importlib.metadata import distribution
from pathlib import Path
import subprocess
import sys
import sysconfig
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent


def require_standard_windows_python():
    platform = sysconfig.get_platform().lower()
    runtime = Path(sys.base_prefix).as_posix().lower()
    if (sys.platform != 'win32' or 'mingw' in sys.version.lower()
            or any(marker in platform for marker in ('mingw', 'msys'))
            or any(marker in runtime for marker in ('/msys', '/mingw'))):
        raise SystemExit('Build on Windows using standard python.org CPython, not MSYS2.')


def write_licenses(bundle):
    notices = ['This download includes Python and these third-party packages.\n']
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Python runtime license was not found')
    notices.append('PYTHON\n' + python_license.read_text(encoding='utf-8'))
    for name in ('requests', 'urllib3', 'certifi', 'charset-normalizer', 'idna', 'pyinstaller'):
        metadata = distribution(name)
        notices.append(f'\n{name} {metadata.version}\n')
        for file in metadata.files or []:
            if any(part.lower().startswith(('license', 'copying')) for part in file.parts):
                path = Path(metadata.locate_file(file))
                if path.is_file():
                    notices.append(path.read_text(encoding='utf-8', errors='replace'))
    (bundle / 'THIRD-PARTY-LICENSES.txt').write_text('\n'.join(notices), encoding='utf-8')


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
        archive.write(ROOT / 'KIOSK-SETUP.md', 'Logbook/KIOSK-SETUP.md')
        for name in ('install-windows-kiosk.ps1','check-windows-kiosk.ps1'):
            archive.write(ROOT / 'scripts' / name, 'Logbook/scripts/' + name)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    return output


def main():
    require_standard_windows_python()
    # Use a fresh work directory so private local files never enter the executable.
    work = ROOT / '.tools' / 'windows-build'
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                    '--windowed', '--noupx', '--name', 'Logbook', '--paths', str(ROOT),
                    '--distpath', str(work / 'dist'), '--workpath', str(work / 'work'),
                    '--specpath', str(work), '--collect-data', 'certifi',
                    '--exclude-module', 'server', str(ROOT / 'scripts/desktop_entry.py')], check=True, cwd=ROOT)
    output = ROOT / 'dist' / 'Logbook-Windows-x64.zip'
    write_licenses(work / 'dist' / 'Logbook')
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
    # Test installer credential sealing with a disposable token, outside the public archive.
    installer_config = work / 'installer-smoke.json'
    installer_config.write_text(json.dumps({'machine_token':'build-test-token-only'}), encoding='utf-8')
    executable = str(smoke / 'Logbook/Logbook.exe')
    subprocess.run([executable, '--protect-config', str(installer_config)],
                   check=True, timeout=30, cwd=work)
    stored = json.loads(installer_config.read_text(encoding='utf-8'))
    if 'machine_token' in stored or not stored.get('machine_token_dpapi'):
        raise RuntimeError('Bundled installer credential sealing failed')
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from client.credentials import load_config
    if load_config(installer_config)['machine_token'] != 'build-test-token-only':
        raise RuntimeError('Bundled protected config could not be read on the same PC')
    installer_config.unlink()
    print(f'Built and smoke-tested: {output}')


if __name__ == '__main__':
    main()
