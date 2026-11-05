from types import SimpleNamespace

import pytest

from common import valid_student_id, STUDENT_ID_ERROR, valid_student_name, STUDENT_NAME_ERROR
from client.__main__ import Desktop
from server.db import connect


@pytest.mark.parametrize('student_id', ['dsad', 'Neko', '123abc', '123-456', '123_456',
    '12.34', '12 34', '１２３４', '١٢٣٤', '1'*65, '123456789', '12345678901'])
def test_server_rejects_non_numeric_ids_without_creating_records(web, auth, app, student_id):
    before = None
    with connect(app.config['DATABASE']) as db:
        before = db.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    registration = web.post('/api/register', headers=auth,
        json=dict(student_id=student_id, name='Test, Student, Example'))
    assert registration.status_code == 400
    assert 'exactly 10 digits' in registration.json['error']
    assert web.get('/api/students/'+student_id,headers=auth).status_code == 400
    assert web.post('/api/sessions',headers=auth,json=dict(student_id=student_id,
        run_id='test-run',session_id='invalid-session')).status_code == 400
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM students').fetchone()[0] == before
        assert db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0


def test_legacy_word_id_cannot_log_in_and_records_are_not_deleted(web, auth, app, csrf):
    with connect(app.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name) VALUES(?,?)',('dsad','Test Legacy'))
    assert web.get('/api/students/dsad',headers=auth).status_code == 400
    assert web.post('/api/sessions',headers=auth,json=dict(student_id='dsad',
        run_id='test-run',session_id='invalid-session')).status_code == 400
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT name FROM students WHERE student_id=?',('dsad',)).fetchone()[0]=='Test Legacy'
    assert web.post('/admin/students',headers=csrf,
        json=dict(student_id='dsad',name='Test Legacy',active=False)).status_code==200
    assert web.post('/admin/students',headers=csrf,
        json=dict(student_id='dsad',name='Test Legacy',active=True)).status_code==400


def test_numeric_id_preserves_leading_zeros(web,auth):
    data=dict(student_id='0001234567',name='Test, Student, Example')
    assert web.post('/api/register',headers=auth,json=data).status_code == 201
    assert web.get('/api/students/0001234567',headers=auth).json == data


@pytest.mark.parametrize('name',['Neko','Juan Santos','Santos, Juan','Santos,Juan,Reyes',
    'Santos, Juan, ', 'Santos, Juan, Reyes, Extra', 'Santos, Juan123, Reyes',
    'Santos, Juan, R.', '<script>, Juan, Reyes', 'Santos, -Juan, Reyes'])
def test_registration_rejects_invalid_name_format(web,auth,app,name):
    assert not valid_student_name(name)
    response=web.post('/api/register',headers=auth,json=dict(student_id='2024035580',name=name))
    assert response.status_code==400
    assert 'Surname, FirstName, Middle Name' in response.json['error']
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM students').fetchone()[0]==0


@pytest.mark.parametrize('name',["Dela Cruz, Juan, Santos", "O'Neil, Mary Jane, Pérez", 'Santos-Reyes, Ana, Dela Cruz'])
def test_real_name_characters_and_multiword_parts_are_supported(web,auth,name):
    assert valid_student_name(name)
    assert web.post('/api/register',headers=auth,json=dict(student_id='2024035580',name=name)).status_code==201


def test_invalid_legacy_name_needs_correction_before_new_login(web,auth,app,csrf):
    with connect(app.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name) VALUES(?,?)',('2024035580','Neko'))
    assert web.get('/api/students/2024035580',headers=auth).status_code==400
    web.post('/api/heartbeat',headers=auth,json=dict(run_id='test-run',active_session=None))
    assert web.post('/api/sessions',headers=auth,json=dict(student_id='2024035580',
        run_id='test-run',session_id='test-session')).status_code==400
    assert web.post('/admin/students',headers=csrf,json=dict(student_id='2024035580',
        name='Santos, Juan, Reyes',active=True)).status_code==200
    assert web.get('/api/students/2024035580',headers=auth).status_code==200


@pytest.mark.parametrize('mode',['login','register'])
def test_student_ui_shows_error_before_any_network_call(mode, monkeypatch):
    messages=[]
    focused=[]
    dialogs=[]
    monkeypatch.setattr('client.__main__.messagebox.showerror',lambda *args,**kwargs:dialogs.append(args))
    class Text:
        def __init__(self,value): self.value=value
        def get(self): return self.value
        def set(self,value): messages.append(value)
    def forbidden(*args):pytest.fail('Invalid ID must not reach network or confirmation')
    agent=SimpleNamespace(busy=False,pending_start=None,session_id=None,
        timers=SimpleNamespace(warning=None),monitor_ok=True,begin=lambda:None,root=object(),
        sid=Text('dsad'),mode=Text(mode),status=Text(''),
        id_entry=SimpleNamespace(focus_set=lambda:focused.append(True)),job=forbidden)
    Desktop.identify(agent)
    assert messages==[STUDENT_ID_ERROR] and focused==[True]
    assert dialogs==[('Invalid student ID', STUDENT_ID_ERROR)]


@pytest.mark.parametrize('value',[None,123,'',' ','1\n','0.1','abc'])
def test_shared_id_rule_rejects_invalid_values(value):
    assert not valid_student_id(value)


def test_student_ui_rejects_name_before_registration_request(monkeypatch):
    messages=[]
    dialogs=[]
    monkeypatch.setattr('client.__main__.messagebox.showerror',lambda *args,**kwargs:dialogs.append(args))
    class Text:
        def __init__(self,value):self.value=value
        def get(self):return self.value
        def set(self,value):messages.append(value)
    def forbidden(*args):pytest.fail('Invalid name must not reach registration request')
    agent=SimpleNamespace(busy=False,pending_start=None,session_id=None,root=object(),
        timers=SimpleNamespace(warning=None),monitor_ok=True,begin=lambda:None,
        sid=Text('2024035580'),mode=Text('register'),name=Text('Neko'),status=Text(''),
        name_entry=SimpleNamespace(focus_set=lambda:None),job=forbidden)
    Desktop.identify(agent)
    assert messages==[STUDENT_NAME_ERROR]
    assert dialogs==[('Invalid student name', STUDENT_NAME_ERROR)]
