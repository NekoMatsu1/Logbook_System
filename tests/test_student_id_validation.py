from types import SimpleNamespace

import pytest

from common import (valid_student_id, STUDENT_ID_ERROR, valid_student_name,
                    STUDENT_NAME_ERROR, valid_student_password, STUDENT_PASSWORD_ERROR)
from client.__main__ import Desktop
from server.db import connect


@pytest.mark.parametrize('student_id', ['dsad', 'Neko', '123abc', '123-456', '123_456',
    '12.34', '12 34', '１２３４', '١٢٣٤', '1'*65, '123456789', '12345678901'])
def test_server_rejects_invalid_ids_without_creating_records(web, auth, app, csrf, student_id):
    with connect(app.config['DATABASE']) as db:
        before = db.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    registration = web.post('/admin/students', headers=csrf,
        json=dict(student_id=student_id, name='Test, Student, Example', active=True, create=True))
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
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT name FROM students WHERE student_id=?',('dsad',)).fetchone()[0]=='Test Legacy'
    assert web.post('/admin/students',headers=csrf,
        json=dict(student_id='dsad',name='Test Legacy',active=False)).status_code==200
    assert web.post('/admin/students',headers=csrf,
        json=dict(student_id='dsad',name='Test Legacy',active=True)).status_code==400


def test_numeric_id_preserves_leading_zeros(web,auth,csrf):
    data=dict(student_id='0001234567',name='Test, Student, Example')
    assert web.post('/admin/students',headers=csrf,json=data|{'active':True,'create':True}).status_code == 200
    assert web.get('/api/students/0001234567',headers=auth).json == {
        'student_id':'0001234567','setup_required':True}


@pytest.mark.parametrize('name',['Neko','Juan Santos','Santos, Juan','Santos,Juan,Reyes',
    'Santos, Juan, ', 'Santos, Juan, Reyes, Extra', 'Santos, Juan123, Reyes',
    'Santos, Juan, R.', '<script>, Juan, Reyes', 'Santos, -Juan, Reyes'])
def test_admin_rejects_invalid_name_format(web,app,csrf,name):
    assert not valid_student_name(name)
    response=web.post('/admin/students',headers=csrf,
        json=dict(student_id='2024035580',name=name,active=True,create=True))
    assert response.status_code==400
    assert 'Surname, FirstName, Middle Name' in response.json['error']
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM students').fetchone()[0]==0


@pytest.mark.parametrize('name',["Dela Cruz, Juan, Santos", "O'Neil, Mary Jane, Pérez", 'Santos-Reyes, Ana, Dela Cruz'])
def test_real_name_characters_and_multiword_parts_are_supported(web,csrf,name):
    assert valid_student_name(name)
    assert web.post('/admin/students',headers=csrf,
        json=dict(student_id='2024035580',name=name,active=True,create=True)).status_code==200


def test_invalid_legacy_name_needs_admin_correction_before_password_setup(web,auth,app,csrf):
    with connect(app.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name) VALUES(?,?)',('2024035580','Neko'))
    assert web.get('/api/students/2024035580',headers=auth).status_code==400
    assert web.post('/api/student-auth/setup',headers=auth,
        json={'student_id':'2024035580','password':'Privatepass1'}).status_code==400
    assert web.post('/admin/students',headers=csrf,json=dict(student_id='2024035580',
        name='Santos, Juan, Reyes',active=True)).status_code==200
    assert web.get('/api/students/2024035580',headers=auth).status_code==200


def test_student_ui_shows_id_error_before_network(monkeypatch):
    messages, focused, dialogs = [], [], []
    monkeypatch.setattr('client.__main__.messagebox.showerror',lambda *args,**kwargs:dialogs.append(args))
    class Text:
        def __init__(self,value): self.value=value
        def get(self): return self.value
        def set(self,value): messages.append(value)
    def forbidden(*args): pytest.fail('Invalid ID must not reach the network')
    agent=SimpleNamespace(busy=False,pending_start=None,session_id=None,stage='id',
        timers=SimpleNamespace(warning=None),monitor_ok=True,begin=lambda:None,root=object(),
        sid=Text('dsad'),status=Text(''),id_entry=SimpleNamespace(focus_set=lambda:focused.append(True)),job=forbidden)
    Desktop.identify(agent)
    assert messages==[STUDENT_ID_ERROR] and focused==[True]
    assert dialogs==[('Invalid student ID', STUDENT_ID_ERROR)]


@pytest.mark.parametrize('value',[None,123,'',' ','1\n','0.1','abc'])
def test_shared_id_rule_rejects_invalid_values(value):
    assert not valid_student_id(value)


@pytest.mark.parametrize('value',[None,'short','onlylettersxx','1234567890','bad\npassword1'])
def test_shared_password_rule_rejects_weak_values(value):
    assert not valid_student_password(value)
    assert '10-128' in STUDENT_PASSWORD_ERROR


def test_student_ui_rejects_weak_first_password_before_network(monkeypatch):
    dialogs=[]
    monkeypatch.setattr('client.__main__.messagebox.showerror',lambda *args,**kwargs:dialogs.append(args))
    class Text:
        def __init__(self,value): self.value=value
        def get(self): return self.value
    agent=SimpleNamespace(busy=False,pending_start=None,session_id=None,stage='setup',
        timers=SimpleNamespace(warning=None),monitor_ok=True,begin=lambda:None,root=object(),
        sid=Text('2024035580'),password=Text('short'),password_confirm=Text('short'),
        status=SimpleNamespace(set=lambda value:None),job=lambda *args:pytest.fail('Weak password reached network'))
    Desktop.identify(agent)
    assert dialogs==[('Invalid password', STUDENT_PASSWORD_ERROR)]
