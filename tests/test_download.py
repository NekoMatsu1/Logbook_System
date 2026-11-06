import hashlib
import pytest
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
        assert 'Logbook/scripts/install-windows-kiosk.ps1' in names
        assert 'Logbook/scripts/check-windows-kiosk.ps1' in names
        assert not any(name.endswith('client.json') or '/server/' in name or '/data/' in name for name in names)
    assert output.with_suffix('.zip.sha256').read_text().split()[0] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_explicit_config_is_resolved_from_caller_directory(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import client.__main__ as desktop
    import client.kiosk as kiosk
    received = []
    shared_root=SimpleNamespace(withdraw=lambda:None,destroy=lambda:None)
    monkeypatch.setattr(launcher.tk,'Tk',lambda:shared_root)
    monkeypatch.setattr(kiosk, 'main', lambda args: received.append(args))
    monkeypatch.chdir(tmp_path)
    assert launcher.main(['--config', 'private.json']) == 0
    assert received == [['--config', str((tmp_path / 'private.json').resolve())]]

def test_first_run_picker_reuses_one_tk_root(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import client.kiosk as kiosk
    roots=[]
    received=[]
    def create_root():
        root=SimpleNamespace(withdraw=lambda:None,destroy=lambda:None)
        roots.append(root)
        return root
    monkeypatch.setattr(launcher.tk,'Tk',create_root)
    monkeypatch.setattr(launcher,'default_config',lambda:tmp_path/'missing.json')
    monkeypatch.setattr(launcher.messagebox,'showinfo',lambda *args,**kwargs:None)
    monkeypatch.setattr(launcher.filedialog,'askopenfilename',lambda **kwargs:str(tmp_path/'selected.json'))
    monkeypatch.setattr(kiosk,'main',lambda args:received.append(args))
    assert launcher.main([])==0
    assert len(roots)==1
    assert received==[['--config',str((tmp_path/'selected.json').resolve())]]

def test_shell_child_runs_desktop_without_starting_another_supervisor(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import client.__main__ as desktop
    received=[]
    root=SimpleNamespace(withdraw=lambda:None,destroy=lambda:None)
    monkeypatch.setattr(launcher.tk,'Tk',lambda:root)
    config = tmp_path/'client.json'
    config.write_text('{}')
    monkeypatch.setattr(launcher,'default_config',lambda:config)
    monkeypatch.setattr(desktop,'main',lambda args,root=None:received.append((args,root)))
    assert launcher.main(['--shell-child'])==0
    assert received==[(['--config',str(config.resolve()),'--shell-child'],root)]


def test_installer_sealing_does_not_open_student_ui(monkeypatch, tmp_path):
    import client.credentials as credentials
    received=[]
    monkeypatch.setattr(credentials,'protect_config',lambda path:received.append(path))
    monkeypatch.setattr(launcher.tk,'Tk',lambda:pytest.fail('Installer must not open student UI'))
    config=tmp_path/'client.json'
    assert launcher.main(['--protect-config',str(config)]) == 0
    assert received == [config]


def test_installer_sealing_failure_is_reported_without_private_data(monkeypatch):
    import client.credentials as credentials
    def fail(path): raise ValueError('private token must not be printed')
    monkeypatch.setattr(credentials,'protect_config',fail)
    assert launcher.main(['--protect-config','missing.json']) == 1


def test_startup_messages_are_actionable_without_revealing_credentials():
    assert 'already running' in launcher.startup_message(RuntimeError('Another supervisor agent is already running'))
    assert 'different PC' in launcher.startup_message(RuntimeError('Machine credential could not be opened/protected on this PC'))
    assert 'client.json' in launcher.startup_message(FileNotFoundError())
    assert 'token' not in launcher.startup_message(ValueError('machine_token=private-value'))
