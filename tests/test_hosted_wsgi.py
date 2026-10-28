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


def test_hosted_remote_pcs_and_admin_use_provider_peer_not_forged_headers(tmp_path):
    from werkzeug.test import Client
    config=tmp_path/'server.json'
    config.write_text(json.dumps(dict(PLATFORM_HTTPS_ENFORCED=True,DATABASE=str(tmp_path/'data.sqlite'),
        TESTING=True,PRODUCTION=True,SECRET_KEY='x'*48,ADMIN_DIRECT_ONLY=False,
        ADMIN_ADDRESSES=['198.51.100.42'],ALLOW_REMOTE_CLIENTS=True)))
    web=Client(build_application(config))
    assert web.get('/admin/overview',headers={'X-Real-IP':'198.51.100.42'}).status_code==200
    assert web.get('/admin/overview',headers={'X-Real-IP':'198.51.100.42, 203.0.113.7',
        'X-Forwarded-For':'198.51.100.42','Forwarded':'for=198.51.100.42'}).status_code==403
    assert web.get('/admin/overview').status_code==403
    assert web.get('/admin/overview',headers={'X-Real-IP':'invalid'}).status_code==403
    assert web.get('/api/students/unknown',headers={'X-Real-IP':'203.0.113.7'}).status_code==401
