import csv
import io
from concurrent.futures import ThreadPoolExecutor
from server.db import connect

def test_admin_registration_lookup(web,auth,csrf):
    data = dict(student_id='0000000123',name='Cruz, Juan, Santos')
    assert web.post('/api/register',headers=auth,json=data).status_code == 403
    assert web.post('/admin/students',headers=csrf,json=data|{'active':True,'create':True}).status_code == 200
    assert web.post('/admin/students',headers=csrf,json=data|{'active':True,'create':True}).status_code == 409
    assert web.get('/api/students/0000000123',headers=auth).json == {
        'student_id':'0000000123','setup_required':True}
    assert web.get('/api/students/0000000124',headers=auth).status_code == 404
    assert web.post('/admin/students',headers=csrf,
                    json=dict(student_id=123,name='Name',active=True,create=True)).status_code == 400

def test_idempotent_start_end(web,auth,ready,clock):
    first = web.post('/api/sessions',headers=auth,json=ready)
    assert first.status_code == 201
    assert web.post('/api/sessions',headers=auth,json=ready).json == first.json
    assert web.post('/api/sessions',headers=auth,json=ready|{'session_id':'another'}).status_code == 401
    clock.advance(25)
    end = dict(run_id='run-1',reason='inactivity')
    result = web.post('/api/sessions/session-1/end',headers=auth,json=end).json
    clock.advance(20)
    assert web.post('/api/sessions/session-1/end',headers=auth,json=end).json == result
    assert result['duration'] == 25
    assert result['status'] == 'completed'

def test_concurrent_starts(app,auth,ready):
    def start(index):
        with app.test_client() as client:
            return client.post('/api/sessions',headers=auth,json=ready|{'session_id':f'concurrent-{index}'}).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(start,range(4)))
    assert sorted(results) == [201,401,401,401]

def test_interruption_not_network_loss(web,app,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(120)
    page = web.get('/admin/overview').text
    assert 'LAB-PC-01</td><td><span class="status status-offline">offline</span>' in page
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT status FROM sessions').fetchone()[0] == 'active'
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-1',active_session='session-1'))
    assert 'LAB-PC-01</td><td><span class="status status-in-use">in-use</span>' in web.get('/admin/overview').text
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT status FROM sessions').fetchone()[0] == 'active'
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-2',active_session=None))
    with connect(app.config['DATABASE']) as db:
        record = dict(db.execute('SELECT * FROM sessions').fetchone())
    assert record['status'] == 'interrupted'
    assert record['logout_time'] is None and record['duration'] is None


def test_long_offline_pc_is_interrupted_without_an_invented_end_time(web,app,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    # Three heartbeat windows are required before absence is recorded.  This avoids
    # treating a short network gap as an inaccurate student logout.
    clock.advance(135)
    assert web.get('/admin/overview').status_code == 200
    with connect(app.config['DATABASE']) as db:
        record=dict(db.execute('SELECT * FROM sessions WHERE session_id=?',('session-1',)).fetchone())
    assert record['status']=='interrupted'
    assert record['end_reason']=='heartbeat_timeout'
    assert record['logout_time'] is None and record['duration'] is None
    assert record['last_heartbeat_at']==record['login_time']

def test_unacknowledged_end(web,app,auth,ready):
    web.post('/api/sessions',headers=auth,json=ready)
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-1',active_session=None))
    with connect(app.config['DATABASE']) as db:
        record = db.execute('SELECT * FROM sessions').fetchone()
        assert record['end_reason'] == 'unacknowledged_end'
        assert record['logout_time'] is None

def test_admin_access_csrf_and_machine_separation(web,auth,csrf):
    assert web.get('/admin/overview',environ_overrides={'REMOTE_ADDR':'10.0.0.9'},headers={'X-Forwarded-For':'127.0.0.1'}).status_code == 403
    assert web.get('/admin/overview',headers=auth).status_code == 403
    assert web.post('/admin/settings',json=dict(scope='*',values={})).status_code == 403
    assert web.post('/admin/settings',headers=csrf,json=dict(scope='*',values={})).status_code == 200
    assert web.get('/api/students/test').status_code == 401
    assert web.get('/admin/export.csv',headers=auth).status_code == 403
    assert web.post('/admin/settings',headers=csrf|auth,json=dict(scope='*',values={})).status_code == 403

def test_override_validation(web,auth,csrf):
    assert web.post('/admin/settings',headers=csrf,json=dict(scope='*',values={'inactivity_seconds':300})).status_code == 200
    assert web.post('/admin/settings',headers=csrf,json=dict(scope='LAB-PC-01',values={'inactivity_seconds':15,'auto_shutdown':False})).status_code == 200
    result=web.post('/api/heartbeat',headers=auth,json=dict(run_id='run')).json['settings']
    assert result['inactivity_seconds']==15 and result['auto_shutdown'] is False
    result=web.post('/api/heartbeat',headers=auth|{'X-Computer-ID':'LAB-PC-02'},json=dict(run_id='run')).json['settings']
    assert result['inactivity_seconds']==300 and result['auto_shutdown'] is True
    assert web.post('/admin/settings',headers=csrf,json=dict(scope='*',values={'inactivity_seconds':True})).status_code==400

def test_csv_filters_and_formula_protection(web,auth,ready,csrf,clock,app):
    web.post('/api/sessions',headers=auth,json=ready)
    assert web.post('/admin/students',headers=csrf,json=dict(student_id='0000000123',name='=1+1',active=True)).status_code==400
    # Simulate an old unsafe name already stored before strict registration validation.
    with connect(app.config['DATABASE']) as db:
        db.execute('UPDATE students SET name=? WHERE student_id=?',('=1+1','0000000123'))
    # Historical name survives admin edit.
    exported=web.get('/admin/export.csv?student=0000000123&computer=LAB-PC-01&date=2026-10-23')
    rows=list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows)==1 and rows[0]['student_name']=='Dela Cruz, Juan, Santos'
    assert len(list(csv.DictReader(io.StringIO(web.get('/admin/export.csv?student=absent').text))))==0
    web.post('/api/sessions/session-1/end',headers=auth,json=dict(run_id='run-1',reason='inactivity'))
    assert web.get('/api/students/0000000123',headers=auth).status_code==400
    records_page=web.get('/admin/records').text
    assert 'status status-completed">ended' in records_page
    assert 'Idle auto-logout' in records_page
    with connect(app.config['DATABASE']) as db:
        db.execute("INSERT INTO sessions(session_id,student_id,student_name,computer_id,run_id,login_time,status) VALUES(?,?,?,?,?,?,?)",
            ('old-session','0000000123','=1+1','LAB-PC-01','run-1',app.config['NOW']().isoformat(),'interrupted'))
    rows=list(csv.DictReader(io.StringIO(web.get('/admin/export.csv').text)))
    assert any(r['student_name']=="'=1+1" for r in rows)
    assert web.get('/admin/export.csv?date=bad').status_code==400


def test_records_are_paginated_but_csv_export_remains_complete(web,auth,ready,app):
    with connect(app.config['DATABASE']) as db:
        for number in range(125):
            stamp=f'2026-10-23T00:{number // 60:02}:{number % 60:02}+00:00'
            db.execute("INSERT INTO sessions(session_id,student_id,student_name,computer_id,run_id,login_time,logout_time,duration,end_reason,status) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (f'page-{number:03}', '0000000123', 'Dela Cruz, Juan, Santos', 'LAB-PC-01',
                        'run-1', stamp, stamp, 1, 'inactivity', 'completed'))
    first=web.get('/admin/records').text
    second=web.get('/admin/records?record_page=2').text
    assert 'Showing 1–100 of 125 records' in first
    assert 'Showing 101–125 of 125 records' in second
    assert 'page-124' in first and 'page-000' not in first
    assert 'page-000' in second
    assert len(list(csv.DictReader(io.StringIO(web.get('/admin/export.csv').text))))==125


def test_records_use_short_session_reference_and_minute_precision(web,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(10)
    web.post('/api/heartbeat',headers=auth,json={'run_id':'run-1','active_session':'session-1'})
    page=web.get('/admin/records').text
    assert '#session-' in page
    assert '>Duration</th>' in page and '>Seconds</th>' not in page
    with connect(web.application.config['DATABASE']) as db:
        row=db.execute('SELECT login_time,last_heartbeat_at FROM sessions WHERE session_id=?',('session-1',)).fetchone()
    assert row['last_heartbeat_at'] != row['login_time']

def test_all_dashboard_pages(web,ready):
    for page in ('overview','records','students','settings','events'):
        assert web.get('/admin/'+page).status_code==200

def test_deactivation_and_duplicate_admin_registration(web,auth,ready,csrf):
    data=dict(student_id='0000000123',name='Cruz, Juan, Santos',active=False)
    assert web.post('/admin/students',headers=csrf,json=data|{'create':True}).status_code==409
    assert web.post('/admin/students',headers=csrf,json=data).status_code==200
    assert web.get('/api/students/0000000123',headers=auth).status_code==404
    # Deactivation revokes any password token already issued to this account.
    assert web.post('/api/sessions',headers=auth,json=ready).status_code==401

def test_no_cross_machine_session_access(web,auth,ready):
    web.post('/api/sessions',headers=auth,json=ready)
    other=auth|{'X-Computer-ID':'LAB-PC-02'}
    assert web.post('/api/sessions',headers=other,json=ready).status_code==409
    assert web.post('/api/sessions/session-1/end',headers=other,json=dict(run_id='run-1',reason='inactivity')).status_code==404

def test_helper_marks_unknown_time(web,app,auth,ready):
    web.post('/api/sessions',headers=auth,json=ready)
    assert web.post('/api/helper/absent',headers=auth,json={}).status_code==400
    assert web.post('/api/helper/absent',headers=auth,json={'confirmed_no_interactive_session':True}).status_code==200
    with connect(app.config['DATABASE']) as db:
        record = db.execute('SELECT * FROM sessions').fetchone()
        assert record['status']=='interrupted' and record['logout_time'] is None

def test_retired_run_cannot_interrupt_newer_session(web,auth,ready):
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-2',active_session=None))
    assert web.post('/api/sessions',headers=auth,json=ready|{'run_id':'run-2'}).status_code==201
    assert web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-1',active_session=None)).status_code==409
    assert 'active' in web.get('/admin/records').text

def test_manila_date_boundary(web,auth,ready,clock):
    clock.advance(16*3600) # UTC 16:00 is next calendar day in Manila.
    login=web.post('/api/student-auth/login',headers=auth,
                   json={'student_id':'0000000123','password':'Studentpass1'})
    web.post('/api/sessions',headers=auth,json=ready|{'student_auth_token':login.json['student_auth_token']})
    assert 'session-1' not in web.get('/admin/export.csv?date=2026-10-23').text
    assert 'session-1' in web.get('/admin/export.csv?date=2026-10-24').text

def test_forwarded_headers_only_from_designated_proxy(app):
    from server.app import create_app
    proxied=create_app({'TESTING':True,'DATABASE':app.config['DATABASE'],'TRUSTED_PROXY_ADDRESS':'10.0.0.2','ADMIN_ADDRESSES':['10.0.0.3']}).test_client()
    headers={'X-Forwarded-For':'10.0.0.3','X-Forwarded-Proto':'https'}
    assert proxied.get('/admin/overview',headers=headers,environ_overrides={'REMOTE_ADDR':'10.0.0.2'}).status_code==200
    assert proxied.get('/admin/overview',headers=headers,environ_overrides={'REMOTE_ADDR':'10.0.0.9'}).status_code==403
