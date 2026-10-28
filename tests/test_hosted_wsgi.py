import json
from io import BytesIO
from deploy.pythonanywhere_wsgi import build_application
from deploy.package_pythonanywhere import package
from zipfile import ZipFile
import pytest

def test_hosted_wrapper_requires_https_contract(tmp_path):
    config=tmp_path/'server.json'
    config.write_text('{}')
    with pytest.raises(RuntimeError): build_application(config)

def test_hosted_wrapper_ignores_forged_forwarding_and_locks_student_network(tmp_path):
    config=tmp_path/'server.json'
    config.write_text(json.dumps(dict(PLATFORM_HTTPS_ENFORCED=True,DATABASE=str(tmp_path/'data.sqlite'),
                                      TESTING=True,LAB_NETWORKS=['192.168.1.0/24'])))
    application=build_application(config)
    from werkzeug.test import Client
    web=Client(application)
    result=web.get('/api/students/test',headers={'X-Forwarded-For':'192.168.1.10','X-Forwarded-Proto':'https'})
    assert result.status_code==403

def test_free_host_package_contains_only_source(tmp_path):
    archive=package(tmp_path/'server.zip')
    with ZipFile(archive) as zipped:
        names=zipped.namelist()
        assert 'server/admin_auth.py' in names
        assert 'deploy/pythonanywhere_wsgi.py' in names
        assert not any(name.startswith(('config/','data/','client/','.tools/')) for name in names)
        assert not any(name.endswith(('.sqlite','.key','.json')) for name in names)
