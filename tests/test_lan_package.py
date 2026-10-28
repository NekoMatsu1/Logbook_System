import json
from zipfile import ZipFile
import pytest
from client.api import API
from scripts.prepare_lan_test import build_package, gateway_config

def test_student_package_has_no_server_database_or_private_keys(tmp_path):
    ca=tmp_path/'ca.pem'
    ca.write_text('public-test-ca')
    config=dict(server_url='https://192.168.1.128:5443',computer_id='LAB-PC-02',machine_token='test-only',
                simulation=True,allow_loopback_http=False,ca_bundle='config/lan-ca.pem')
    output=build_package(tmp_path/'client.zip',config,ca)
    with ZipFile(output) as archive:
        names=archive.namelist()
        assert 'start-student.cmd' in names and 'client/__main__.py' in names
        assert 'config/lan-ca.pem' in names
        assert json.loads(archive.read('config/client.json'))==config
        assert not any(name.startswith(('server/','data/','deploy/')) for name in names)
        assert not any(name.endswith(('.key','.sqlite','.sqlite3')) for name in names)
        assert 'client/helper.py' not in names
        assert b'flask' not in archive.read('requirements-client.txt').lower()

def test_custom_ca_keeps_verification_enabled(tmp_path):
    ca=tmp_path/'ca.pem'
    ca.write_text('test')
    api=API(dict(server_url='https://192.168.1.128:5443',computer_id='PC',machine_token='test',ca_bundle=str(ca)))
    assert api.http.verify==str(ca.resolve())
    assert api.http.verify is not False

@pytest.mark.parametrize('ca',[False,True,'',None])
def test_ca_cannot_disable_certificate_verification(ca):
    config=dict(server_url='https://192.168.1.128:5443',computer_id='PC',machine_token='test')
    if ca is not None:
        config['ca_bundle']=ca
        with pytest.raises(ValueError): API(config)
    else:
        assert API(config).http.verify is True

def test_gateway_exposes_only_api_routes(tmp_path):
    text=gateway_config('192.168.1.128',tmp_path/'server.pem',tmp_path/'server.key')
    assert 'handle /api/*' in text
    assert 'respond "Administrator dashboard is private" 403' in text
    assert 'bind 192.168.1.128' in text
    assert 'admin off' in text
    assert 'header_up X-Forwarded-For {remote_host}' in text
