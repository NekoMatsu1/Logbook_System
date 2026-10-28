import csv
import io
from concurrent.futures import ThreadPoolExecutor
from server.db import connect

def test_registration_lookup(web,auth):
    data = dict(student_id='00123',name='Juan')
    assert web.post('/api/register',headers=auth,json=data).status_code == 201
    assert web.post('/api/register',headers=auth,json=data).status_code == 409
    assert web.get('/api/students/00123',headers=auth).json == data
    assert web.get('/api/students/123',headers=auth).status_code == 404
    assert web.post('/api/register',headers=auth,json=dict(student_id=123,name='Name')).status_code == 400

def test_idempotent_start_end(web,auth,ready,clock):
    first = web.post('/api/sessions',headers=auth,json=ready)
    assert first.status_code == 201
    assert web.post('/api/sessions',headers=auth,json=ready).json == first.json
    assert web.post('/api/sessions',headers=auth,json=ready|{'session_id':'another'}).status_code == 409
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
    assert sorted(results) == [201,409,409,409]

def test_interruption_not_network_loss(web,app,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(120)
    page = web.get('/admin/overview').text
    assert 'LAB-PC-01</td><td>offline' in page
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT status FROM sessions').fetchone()[0] == 'active'
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-1',active_session='session-1'))
    assert 'LAB-PC-01</td><td>in-use' in web.get('/admin/overview').text
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT status FROM sessions').fetchone()[0] == 'active'
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-2',active_session=None))
    with connect(app.config['DATABASE']) as db:
        record = dict(db.execute('SELECT * FROM sessions').fetchone())
    assert record['status'] == 'interrupted'
    assert record['logout_time'] is None and record['duration'] is None

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

def test_csv_filters_and_formula_protection(web,auth,ready,csrf,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    assert web.post('/admin/students',headers=csrf,json=dict(student_id='00123',name='=1+1',active=True)).status_code==200
    # Historical name survives admin edit.
    exported=web.get('/admin/export.csv?student=00123&computer=LAB-PC-01&date=2026-10-23')
    rows=list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows)==1 and rows[0]['student_name']=='Juan dela Cruz'
    assert len(list(csv.DictReader(io.StringIO(web.get('/admin/export.csv?student=absent').text))))==0
    web.post('/api/sessions/session-1/end',headers=auth,json=dict(run_id='run-1',reason='inactivity'))
    web.post('/api/sessions',headers=auth,json=ready|{'session_id':'session-2'})
    rows=list(csv.DictReader(io.StringIO(web.get('/admin/export.csv').text)))
    assert any(r['student_name']=="'=1+1" for r in rows)
    assert web.get('/admin/export.csv?date=bad').status_code==400

def test_all_dashboard_pages(web,ready):
    for page in ('overview','records','students','settings','events'):
        assert web.get('/admin/'+page).status_code==200

def test_deactivation_and_duplicate_admin_registration(web,auth,ready,csrf):
    data=dict(student_id='00123',name='Juan',active=False)
    assert web.post('/admin/students',headers=csrf,json=data|{'create':True}).status_code==409
    assert web.post('/admin/students',headers=csrf,json=data).status_code==200
    assert web.get('/api/students/00123',headers=auth).status_code==404
    assert web.post('/api/sessions',headers=auth,json=ready).status_code==404

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
    web.post('/api/sessions',headers=auth,json=ready)
    assert 'session-1' not in web.get('/admin/export.csv?date=2026-10-23').text
    assert 'session-1' in web.get('/admin/export.csv?date=2026-10-24').text

def test_forwarded_headers_only_from_designated_proxy(app):
    from server.app import create_app
    proxied=create_app({'TESTING':True,'DATABASE':app.config['DATABASE'],'TRUSTED_PROXY_ADDRESS':'10.0.0.2','ADMIN_ADDRESSES':['10.0.0.3']}).test_client()
    headers={'X-Forwarded-For':'10.0.0.3','X-Forwarded-Proto':'https'}
    assert proxied.get('/admin/overview',headers=headers,environ_overrides={'REMOTE_ADDR':'10.0.0.2'}).status_code==200
    assert proxied.get('/admin/overview',headers=headers,environ_overrides={'REMOTE_ADDR':'10.0.0.9'}).status_code==403
