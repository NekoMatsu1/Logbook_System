import json

import pytest
from werkzeug.security import generate_password_hash, check_password_hash

from deploy.enable_password_admin import enable
from server.app import create_app


@pytest.fixture(scope='module')
def password_hash():
    return generate_password_hash('test-only passphrase!', method='scrypt:32768:8:1')


@pytest.fixture
def secured(app, password_hash):
    return create_app(dict(app.config) | dict(ADMIN_AUTH_MODE='password',
        ADMIN_USERNAME='owner', ADMIN_PASSWORD_HASH=password_hash, SESSION_COOKIE_SECURE=True))


def sign_in(web, password='test-only passphrase!', username='owner', address='203.0.113.9'):
    web.get('/auth/login', base_url='https://localhost')
    with web.session_transaction() as session:
        csrf = session['login_csrf']
    return web.post('/auth/login', base_url='https://localhost',
        data=dict(username=username, password=password, csrf=csrf),
        environ_overrides={'REMOTE_ADDR':address})


def test_password_login_survives_ip_change_and_worker_reload(secured):
    web = secured.test_client()
    assert sign_in(web).status_code == 302
    cookie = web.get_cookie('session')
    worker = create_app(dict(secured.config)).test_client()
    worker.set_cookie('session', cookie.value)
    result = worker.get('/admin/overview', base_url='https://localhost',
        environ_overrides={'REMOTE_ADDR':'198.51.100.25'}, headers={'Sec-Fetch-Site':'cross-site'})
    assert result.status_code == 200
    assert 'Sign out administrator' in result.text
    assert result.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('path', ['/admin/overview', '/admin/records', '/admin/students',
    '/admin/settings', '/admin/events', '/admin/export.csv'])
def test_private_records_not_accessible_without_login(secured, path):
    web = secured.test_client()
    assert web.get(path, base_url='https://localhost').status_code in (401,403)
    assert web.get(path, base_url='https://localhost', headers={
        'Authorization':'Bearer test-token', 'X-Computer-ID':'LAB-PC-01'}).status_code == 403


def test_password_rejection_and_shared_throttle(secured, clock):
    web = secured.test_client()
    for _ in range(10):
        assert sign_in(web, password='wrong').status_code == 401
    worker = create_app(dict(secured.config)).test_client()
    assert sign_in(worker).status_code == 429
    clock.advance(61)
    assert sign_in(worker).status_code == 302


def test_csrf_expiry_logout_and_credential_rotation(secured, clock):
    web = secured.test_client()
    assert web.post('/auth/login', base_url='https://localhost', data={}).status_code == 403
    assert sign_in(web).status_code == 302
    assert web.post('/auth/logout', base_url='https://localhost').status_code == 403
    with web.session_transaction() as session:
        csrf = session['csrf']
    assert web.post('/auth/logout', base_url='https://localhost', data={'csrf':csrf}).status_code == 302
    assert web.get('/admin/export.csv', base_url='https://localhost').status_code == 403
    assert sign_in(web).status_code == 302
    clock.advance(3601)
    assert web.get('/admin/export.csv', base_url='https://localhost').status_code == 403
    assert sign_in(web).status_code == 302
    secured.config['ADMIN_PASSWORD_HASH'] = generate_password_hash('new test passphrase!', method='scrypt:32768:8:1')
    assert web.get('/admin/export.csv', base_url='https://localhost').status_code == 403


def test_cross_site_login_and_writes_are_blocked(secured):
    web = secured.test_client()
    web.get('/auth/login', base_url='https://localhost')
    with web.session_transaction() as session:
        csrf = session['login_csrf']
    assert web.post('/auth/login', base_url='https://localhost',
        data=dict(username='owner', password='test-only passphrase!', csrf=csrf),
        headers={'Origin':'https://attacker.example'}).status_code == 403
    assert sign_in(web).status_code == 302
    assert web.post('/admin/settings', base_url='https://localhost',
        headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
    assert web.get('/admin/export.csv', base_url='https://localhost',
        headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403


def test_private_setup_preserves_records_without_storing_password(tmp_path):
    path = tmp_path/'server.json'
    before = dict(DATABASE='private.sqlite', SECRET_KEY='s'*48, SESSION_COOKIE_SECURE=True,
        PLATFORM_HTTPS_ENFORCED=True, ADMIN_AUTH_MODE='local', ALLOW_REMOTE_CLIENTS=True)
    path.write_text(json.dumps(before))
    enable(path, 'owner', 'private test passphrase!')
    result = json.loads(path.read_text())
    assert result['DATABASE'] == before['DATABASE']
    assert result['ALLOW_REMOTE_CLIENTS'] is True
    assert result['SECRET_KEY'] != before['SECRET_KEY']
    assert result['ADMIN_AUTH_MODE'] == 'password'
    assert check_password_hash(result['ADMIN_PASSWORD_HASH'], 'private test passphrase!')
    assert 'private test passphrase!' not in path.read_text()
    snapshot = path.read_bytes()
    with pytest.raises(ValueError):
        enable(path, 'owner', 'short')
    assert path.read_bytes() == snapshot


def test_password_mode_requires_https_and_configured_credentials(app, password_hash):
    for change in ({'SESSION_COOKIE_SECURE':False}, {'ADMIN_PASSWORD_HASH':''}):
        with pytest.raises(RuntimeError):
            create_app(dict(app.config) | dict(ADMIN_AUTH_MODE='password', ADMIN_USERNAME='owner',
                ADMIN_PASSWORD_HASH=password_hash, SESSION_COOKIE_SECURE=True) | change)
