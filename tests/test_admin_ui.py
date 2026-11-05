from pathlib import Path

from server.app import create_app
from werkzeug.security import generate_password_hash


ROOT = Path(__file__).parents[1]


def test_dashboard_uses_complete_local_admin_interface(web):
    for page in ('overview', 'records', 'students', 'settings', 'events'):
        response = web.get('/admin/' + page)
        text = response.text
        assert response.status_code == 200
        assert '<header class="app-header">' in text
        assert 'class="tabs"' in text
        assert f'Lab Logbook · {page.capitalize()}' in text
        assert 'https://fonts.googleapis.com' not in text
        assert 'design-preview' not in text
        assert 'Â' not in text and 'â€' not in text


def test_overview_keeps_live_refresh_targets(web):
    text = web.get('/admin/overview').text
    assert 'class="cards stats"' in text
    assert 'data-overview-table' in text
    script = (ROOT / 'server/static/dashboard.js').read_text(encoding='utf-8')
    assert "querySelector('.cards')" in script
    assert "querySelector('[data-overview-table]')" in script


def test_password_login_design_preserves_real_authentication(app):
    secured = create_app(dict(app.config) | dict(
        ADMIN_AUTH_MODE='password', ADMIN_USERNAME='owner',
        ADMIN_PASSWORD_HASH=generate_password_hash('test-only passphrase!', method='scrypt:32768:8:1'),
        SESSION_COOKIE_SECURE=True))
    response = secured.test_client().get('/auth/login', base_url='https://localhost')
    text = response.text
    assert response.status_code == 200
    assert 'name="csrf"' in text and 'design-preview' not in text
    assert 'method="post" action="/auth/login"' in text
    assert 'name="username"' in text and 'name="password"' in text
    assert '/static/login.js' in text
    assert 'https://fonts.googleapis.com' not in text


def test_admin_assets_are_self_contained_and_clean():
    for name in ('style.css', 'dashboard.js', 'login.js'):
        text = (ROOT / 'server/static' / name).read_text(encoding='utf-8')
        assert 'fonts.googleapis.com' not in text
        assert 'Â' not in text and 'â€' not in text
