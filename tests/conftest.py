import hashlib
from datetime import datetime, timezone, timedelta
import pytest
from werkzeug.security import generate_password_hash
from server.app import create_app
from server.db import connect

class Clock:
    def __init__(self):
        self.value = 0
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds
    def utc(self):
        return datetime(2026,10,23,tzinfo=timezone.utc) + timedelta(seconds=self.value)

@pytest.fixture
def clock():
    return Clock()

@pytest.fixture
def app(tmp_path,clock):
    app = create_app(dict(TESTING=True,DATABASE=str(tmp_path/'test.sqlite'),SECRET_KEY='test-only',NOW=clock.utc))
    with connect(app.config['DATABASE']) as db:
        for name in ('LAB-PC-01','LAB-PC-02'):
            db.execute('INSERT INTO computers(computer_id,token_hash) VALUES(?,?)',(name,hashlib.sha256(b'test-token').hexdigest()))
    return app

@pytest.fixture
def web(app):
    return app.test_client()

@pytest.fixture
def auth():
    return {'X-Computer-ID':'LAB-PC-01','Authorization':'Bearer test-token'}

@pytest.fixture
def ready(web,auth):
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='run-1',active_session=None))
    with connect(web.application.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name,password_hash) VALUES(?,?,?)',
                   ('0000000123','Dela Cruz, Juan, Santos',
                    generate_password_hash('Studentpass1',method='scrypt:32768:8:1')))
    login = web.post('/api/student-auth/login',headers=auth,
                     json=dict(student_id='0000000123',password='Studentpass1'))
    return dict(student_id='0000000123',run_id='run-1',session_id='session-1',
                student_auth_token=login.json['student_auth_token'])

@pytest.fixture
def csrf(web):
    web.get('/admin/overview')
    with web.session_transaction() as session:
        return {'X-CSRF-Token':session['csrf']}
