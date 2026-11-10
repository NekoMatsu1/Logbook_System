from pathlib import Path

from server.app import create_app
from server.db import connect
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


def test_students_page_uses_quiet_account_actions_and_a_delete_warning(web):
    text = web.get('/admin/students').text
    template = (ROOT / 'server/templates/dashboard.html').read_text(encoding='utf-8')
    script = (ROOT / 'server/static/dashboard.js').read_text(encoding='utf-8')
    assert 'class="student-actions"' in template
    assert '<summary>More actions</summary>' not in template
    assert 'data-student-active=' in template
    assert 'Deactivate' in template and 'Activate' in template
    assert 'id="notice-dialog"' in text
    assert 'showNotice' in script
    assert "data-student-active" in script
    assert "save('/admin/students/delete', {student_id: studentId}, false)" in script


def test_events_are_presented_in_plain_admin_language(web, app):
    with connect(app.config['DATABASE']) as db:
        db.execute("INSERT INTO events(time,computer_id,kind,detail) VALUES(?,?,?,?)",
                   ('2026-11-07T05:58:00+00:00', 'LAB-PC-02', 'logout', 'secret-session: simulated_inactivity'))
        db.execute("INSERT INTO events(time,kind,detail) VALUES(?,?,?)",
                   ('2026-11-07T05:57:00+00:00', 'admin_settings_change', '*: {\"inactivity_seconds\": 10, \"auto_logout\": true}'))
    text = web.get('/admin/events').text
    assert 'Student session ended' in text and 'Idle auto-logout' in text
    assert 'Settings updated' in text and 'Idle limit: 10 seconds' in text
    assert 'secret-session' not in text and '"inactivity_seconds"' not in text


def test_admin_pages_explain_csv_import_and_use_human_durations(web, app):
    with connect(app.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name) VALUES(?,?)',
                   ('2024035580', 'Dela Cruz, Juan, Santos'))
        db.execute("INSERT INTO sessions(session_id,student_id,student_name,computer_id,run_id,login_time,logout_time,last_heartbeat_at,duration,end_reason,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   ('session-1', '2024035580', 'Dela Cruz, Juan, Santos', 'LAB-PC-01', 'run-1',
                    '2026-11-07T05:00:00+00:00', '2026-11-07T06:30:00+00:00', '2026-11-07T06:30:00+00:00',
                    5400, 'manual_logout', 'completed'))
    students = web.get('/admin/students').text
    records = web.get('/admin/records').text
    assert '>1</span><div><h3>Download the CSV template' in students
    assert '>3</span><div><h3>Upload the completed file' in students
    assert 'Time used' in records and '1 hr 30 min' in records


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
