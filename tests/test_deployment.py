from zipfile import ZipFile
from deploy.package import package
from scripts import build_windows
import pytest

def test_windows_builder_rejects_msys_python(monkeypatch):
    monkeypatch.setattr(build_windows.sys, 'platform', 'win32')
    monkeypatch.setattr(build_windows.sysconfig, 'get_platform', lambda: 'mingw_x86_64_ucrt_gnu')
    with pytest.raises(SystemExit, match='standard python.org CPython'):
        build_windows.require_standard_windows_python()

def test_upload_archive_excludes_credentials_and_local_data(tmp_path):
    destination=package(tmp_path/'upload.zip')
    with ZipFile(destination) as archive:
        names=archive.namelist()
        assert 'server/app.py' in names
        assert 'deploy/compose.yaml' in names
        assert 'deploy/.env.example' in names
        assert 'deploy/Caddyfile' in names
        assert '.dockerignore' in names
        assert not any(name.startswith(('config/','data/','.venv/','.tools/','client/')) for name in names)
        assert not any('/secrets/' in name or '/backups/' in name or name.endswith(('.sqlite','.pyc')) for name in names)
