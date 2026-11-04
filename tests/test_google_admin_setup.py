import json
import os

import pytest

from deploy.enable_google_admin import enable


@pytest.fixture
def private_config(tmp_path):
    path = tmp_path/'server.json'
    path.write_text(json.dumps(dict(DATABASE='private/records.sqlite', SECRET_KEY='s'*48,
        TRUSTED_HOSTS=['nekomatsui.pythonanywhere.com'], PLATFORM_HTTPS_ENFORCED=True,
        SESSION_COOKIE_SECURE=True, ADMIN_AUTH_MODE='local', ADMIN_ADDRESSES=['198.51.100.1'],
        ALLOW_REMOTE_CLIENTS=True)))
    return path


def test_switch_preserves_data_settings_and_removes_ip_dependency(private_config):
    before = json.loads(private_config.read_text())
    enable(private_config, 'Owner@gmail.com', '123-owner.apps.googleusercontent.com', 'private-secret')
    after = json.loads(private_config.read_text())
    assert after['DATABASE'] == before['DATABASE']
    assert after['SECRET_KEY'] == before['SECRET_KEY']
    assert after['ALLOW_REMOTE_CLIENTS'] is True
    assert after['ADMIN_AUTH_MODE'] == 'google'
    assert after['ADMIN_EMAIL'] == 'owner@gmail.com'
    assert after['ADMIN_ADDRESSES'] == []
    assert after['GOOGLE_REDIRECT_URI'] == 'https://nekomatsui.pythonanywhere.com/auth/callback'
    if os.name != 'nt':
        assert private_config.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('email,client,secret', [
    ('not-email', '123.apps.googleusercontent.com', 'secret'),
    ('owner@gmail.com', 'wrong-client', 'secret'),
    ('owner@gmail.com', '123.apps.googleusercontent.com', ''),
])
def test_invalid_setup_leaves_access_unchanged(private_config, email, client, secret):
    before = private_config.read_bytes()
    with pytest.raises(ValueError):
        enable(private_config, email, client, secret)
    assert private_config.read_bytes() == before


def test_failed_atomic_replace_keeps_old_config(private_config, monkeypatch):
    before = private_config.read_bytes()
    def fail(*args):
        raise OSError('storage error')
    monkeypatch.setattr('deploy.enable_google_admin.os.replace', fail)
    with pytest.raises(OSError):
        enable(private_config, 'owner@gmail.com', '123.apps.googleusercontent.com', 'secret')
    assert private_config.read_bytes() == before
    assert list(private_config.parent.glob('.google-admin-*')) == []


@pytest.mark.parametrize('change', [dict(PLATFORM_HTTPS_ENFORCED=False),
    dict(SESSION_COOKIE_SECURE=False), dict(TRUSTED_HOSTS=['*.pythonanywhere.com']),
    dict(SECRET_KEY='short')])
def test_setup_refuses_unsafe_hosting(private_config, change):
    config = json.loads(private_config.read_text()) | change
    private_config.write_text(json.dumps(config))
    before = private_config.read_bytes()
    with pytest.raises(ValueError):
        enable(private_config, 'owner@gmail.com', '123.apps.googleusercontent.com', 'secret')
    assert private_config.read_bytes() == before
