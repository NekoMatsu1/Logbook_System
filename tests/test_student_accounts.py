import io

from server.db import connect


def test_admin_account_first_login_password_and_session_authorization(web, auth, csrf, app):
    account = dict(student_id='2024035580', name='Cernal, Vhenz, Abad', active=True, create=True)
    assert web.post('/admin/students', headers=csrf, json=account).status_code == 200
    assert web.post('/api/register', headers=auth, json=account).status_code == 403

    lookup = web.get('/api/students/2024035580', headers=auth)
    assert lookup.json == dict(student_id='2024035580', setup_required=True)
    web.post('/api/heartbeat', headers=auth, json={'run_id':'account-test','active_session':None})
    request = {'student_id':'2024035580','run_id':'account-test','session_id':'protected-session'}
    assert web.post('/api/sessions', headers=auth, json=request).status_code == 401
    assert web.post('/api/student-auth/setup', headers=auth,
                    json={'student_id':'2024035580','password':'short'}).status_code == 400

    setup = web.post('/api/student-auth/setup', headers=auth,
                     json={'student_id':'2024035580','password':'Privatepass1'})
    assert setup.status_code == 200 and setup.json['student_auth_token']
    assert web.post('/api/student-auth/setup', headers=auth,
                    json={'student_id':'2024035580','password':'Otherpass2'}).status_code == 409
    assert web.get('/api/students/2024035580', headers=auth).json['setup_required'] is False
    assert web.post('/api/student-auth/login', headers=auth,
                    json={'student_id':'2024035580','password':'wrong-password'}).status_code == 401

    started = web.post('/api/sessions', headers=auth,
                       json=request | {'student_auth_token':setup.json['student_auth_token']})
    assert started.status_code == 201
    assert web.post('/api/sessions', headers=auth,
                    json=request | {'session_id':'bypass','student_auth_token':setup.json['student_auth_token']}).status_code == 401
    with connect(app.config['DATABASE']) as db:
        stored = db.execute('SELECT password_hash FROM students WHERE student_id=?',('2024035580',)).fetchone()[0]
    assert stored and stored != 'Privatepass1' and 'Privatepass1' not in web.get('/admin/students').text

    assert web.post('/admin/students/password-reset', headers=csrf,
                    json={'student_id':'2024035580'}).status_code == 200
    assert web.get('/api/students/2024035580', headers=auth).json['setup_required'] is True
    assert web.post('/api/student-auth/login', headers=auth,
                    json={'student_id':'2024035580','password':'Privatepass1'}).status_code == 401


def test_csv_import_is_strict_atomic_and_audited(web, auth, csrf, app):
    content = (b'student_id,surname,first_name,middle_name\n'
               b'2024035580,Dela Cruz,Juan,Santos\n'
               b'0000000007,O\'Neil,Maria,Reyes\n')
    response = web.post('/admin/students/import', headers=csrf,
                        data={'file':(io.BytesIO(content),'students.csv')})
    assert response.status_code == 200 and response.json == {'imported':2}
    assert "O&#39;Neil, Maria, Reyes" in web.get('/admin/students').text
    with connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='admin_student_import'").fetchone()[0] == 1

    invalid = (b'student_id,surname,first_name,middle_name\n'
               b'0000000008,Santos,Ana,Reyes\n'
               b'letters,Santos,Juan,Reyes\n')
    response = web.post('/admin/students/import', headers=csrf,
                        data={'file':(io.BytesIO(invalid),'students.csv')})
    assert response.status_code == 400 and 'Row 3' in response.json['error']
    assert web.get('/api/students/0000000008', headers=auth).status_code == 404
    with connect(app.config['DATABASE']) as db:
        assert db.execute("SELECT COUNT(*) FROM events WHERE kind='admin_student_import_rejected'").fetchone()[0] == 1

    duplicate = (b'student_id,surname,first_name,middle_name\n'
                 b'2024035580,Santos,Ana,Reyes\n')
    response = web.post('/admin/students/import', headers=csrf,
                        data={'file':(io.BytesIO(duplicate),'students.csv')})
    assert response.status_code == 409 and 'nothing was imported' in response.json['error']


def test_csv_template_and_student_page_explain_admin_flow(web):
    template = web.get('/admin/students-template.csv')
    assert template.status_code == 200
    assert template.text.startswith('student_id,surname,first_name,middle_name')
    page = web.get('/admin/students').text
    assert 'Import official student accounts' in page
    assert 'Download CSV template' in page
    assert 'New student? Go to registration' not in page


def test_admin_can_delete_unused_account_but_not_account_with_logbook_records(web, auth, csrf, ready, app):
    unused = dict(student_id='2024035580', name='Cernal, Vhenz, Abad', active=True, create=True)
    assert web.post('/admin/students', headers=csrf, json=unused).status_code == 200
    assert web.post('/admin/students/delete', headers=csrf,
                    json={'student_id':'2024035580'}).status_code == 200
    assert web.get('/api/students/2024035580', headers=auth).status_code == 404

    assert web.post('/api/sessions', headers=auth, json=ready).status_code == 201
    response = web.post('/admin/students/delete', headers=csrf,
                        json={'student_id':'0000000123'})
    assert response.status_code == 409
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT 1 FROM students WHERE student_id=?', ('0000000123',)).fetchone()
        assert db.execute("SELECT 1 FROM events WHERE kind='admin_student_deleted' AND detail=?", ('2024035580',)).fetchone()


def test_password_attempt_throttle_and_short_lived_session_token(web, auth, csrf, clock):
    account = dict(student_id='2024035580', name='Cernal, Vhenz, Abad', active=True, create=True)
    assert web.post('/admin/students', headers=csrf, json=account).status_code == 200
    setup = web.post('/api/student-auth/setup', headers=auth,
                     json={'student_id':'2024035580','password':'Privatepass1'})
    for _ in range(10):
        assert web.post('/api/student-auth/login', headers=auth,
                        json={'student_id':'2024035580','password':'Wrongpass2'}).status_code == 401
    assert web.post('/api/student-auth/login', headers=auth,
                    json={'student_id':'2024035580','password':'Privatepass1'}).status_code == 429
    clock.advance(121)
    web.post('/api/heartbeat', headers=auth, json={'run_id':'expiry-test','active_session':None})
    expired = web.post('/api/sessions', headers=auth, json={
        'student_id':'2024035580', 'run_id':'expiry-test', 'session_id':'expired-token',
        'student_auth_token':setup.json['student_auth_token']})
    assert expired.status_code == 401 and 'expired' in expired.json['error']
    fresh = web.post('/api/student-auth/login', headers=auth,
                     json={'student_id':'2024035580','password':'Privatepass1'})
    assert fresh.status_code == 200
