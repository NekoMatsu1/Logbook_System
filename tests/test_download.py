import hashlib
from pathlib import Path
from zipfile import ZipFile

from client import launcher
from scripts.build_windows import package


def test_frozen_default_config_is_beside_executable_not_working_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(launcher.sys, 'executable', str(tmp_path / 'Logbook.exe'))
    monkeypatch.chdir(tmp_path.parent)
    assert launcher.default_config() == tmp_path / 'config/client.json'


def test_download_contains_runtime_and_placeholder_without_local_credentials(tmp_path):
    bundle = tmp_path / 'bundle'
    (bundle / '_internal').mkdir(parents=True)
    (bundle / 'Logbook.exe').write_bytes(b'test executable')
    (bundle / '_internal/python313.dll').write_bytes(b'test runtime')
    output = package(bundle, tmp_path / 'download.zip')
    with ZipFile(output) as archive:
        names = archive.namelist()
        assert 'Logbook/Logbook.exe' in names
        assert 'Logbook/_internal/python313.dll' in names
        assert 'Logbook/READ-ME.md' in names
        assert 'Logbook/config/client.example.json' in names
        assert not any(name.endswith('client.json') or '/server/' in name or '/data/' in name for name in names)
    assert output.with_suffix('.zip.sha256').read_text().split()[0] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_explicit_config_is_resolved_from_caller_directory(tmp_path, monkeypatch):
    import client.__main__ as desktop
    received = []
    monkeypatch.setattr(desktop, 'main', lambda args: received.append(args))
    monkeypatch.chdir(tmp_path)
    assert launcher.main(['--config', 'private.json']) == 0
    assert received == [['--config', str((tmp_path / 'private.json').resolve())]]
