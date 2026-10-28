from zipfile import ZipFile
from deploy.package import package

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
