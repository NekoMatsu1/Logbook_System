import csv
from concurrent.futures import ThreadPoolExecutor
import io
import sqlite3

import pytest

from server.backup import backup_database
from server.db import connect, initialize


@pytest.mark.parametrize('reason',['manual_logout','simulated_manual_logout','inactivity','simulated_inactivity'])
def test_student_can_end_without_admin_permission(app,web,auth,ready,clock,reason):
    app.config.update(ALLOW_REMOTE_CLIENTS=True,ADMIN_ADDRESSES=['198.51.100.42'])
    outside={'REMOTE_ADDR':'203.0.113.7'}
    assert web.get('/admin/overview',base_url='https://localhost',environ_overrides=outside).status_code==403
    assert web.post('/api/sessions',base_url='https://localhost',environ_overrides=outside,
                    headers=auth,json=ready).status_code==201
    clock.advance(12.125)
    response=web.post('/api/sessions/session-1/end',base_url='https://localhost',environ_overrides=outside,
                      headers=auth,json={'run_id':'run-1','reason':reason})
    assert response.status_code==200
    assert response.json['duration']==12.125
    assert response.json['status']=='completed' and response.json['end_reason']==reason


def test_backward_server_clock_does_not_write_false_duration(web,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(-1)
    response=web.post('/api/sessions/session-1/end',headers=auth,json={'run_id':'run-1','reason':'manual_logout'})
    assert response.status_code==409
    record=web.get('/api/sessions/session-1',headers=auth).json
    assert record['status']=='active' and record['logout_time'] is None and record['duration'] is None
    clock.advance(6)
    assert web.post('/api/sessions/session-1/end',headers=auth,
                    json={'run_id':'run-1','reason':'manual_logout'}).json['duration']==5


def test_concurrent_end_retries_save_one_record_and_one_logout_event(app,web,auth,ready,clock):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(25.5)
    def end(_):
        with app.test_client() as client:
            response=client.post('/api/sessions/session-1/end',headers=auth,
                                 json={'run_id':'run-1','reason':'manual_logout'})
            assert response.status_code==200
            return response.json
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(end,range(4)))
    assert all(record==results[0] for record in results)
    assert results[0]['duration']==25.5
    with connect(app.config['DATABASE']) as database:
        assert database.execute("SELECT COUNT(*) FROM events WHERE kind='logout'").fetchone()[0]==1


@pytest.mark.parametrize('data,headers',[
    ({'run_id':'wrong-run','reason':'manual_logout'},None),
    ({'run_id':'run-1','reason':'manual_logout'},'other-computer'),
])
def test_wrong_run_or_pc_cannot_end_someone_elses_session(web,auth,ready,data,headers):
    web.post('/api/sessions',headers=auth,json=ready)
    supplied=auth if headers is None else auth|{'X-Computer-ID':'LAB-PC-02'}
    assert web.post('/api/sessions/session-1/end',headers=supplied,json=data).status_code==404
    assert web.get('/api/sessions/session-1',headers=auth).json['status']=='active'


def test_verified_backup_restores_records_without_overwriting(app,web,auth,ready,clock,tmp_path):
    web.post('/api/sessions',headers=auth,json=ready)
    clock.advance(37.125)
    completed=web.post('/api/sessions/session-1/end',headers=auth,
                       json={'run_id':'run-1','reason':'manual_logout'}).json
    # Keep a WAL writer open while the consistent snapshot is taken.
    with connect(app.config['DATABASE']) as source:
        source.execute("INSERT INTO events(time,kind,detail) VALUES(?,?,?)",(clock.utc().isoformat(),'test','committed'))
        source.commit()
        output=backup_database(app.config['DATABASE'],tmp_path/'backups/restored.sqlite')
    initialize(output)
    with connect(output) as restored:
        assert dict(restored.execute('SELECT * FROM sessions WHERE session_id=?',('session-1',)).fetchone())==completed
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute("SELECT COUNT(*) FROM events WHERE kind='test'").fetchone()[0]==1
    with pytest.raises(FileExistsError):
        backup_database(app.config['DATABASE'],output)
    with pytest.raises(ValueError):
        backup_database(app.config['DATABASE'],app.config['DATABASE'])
    # CSV keeps leading-zero IDs, exact duration and the original UTC timestamps.
    row=next(csv.DictReader(io.StringIO(web.get('/admin/export.csv').text)))
    assert row['student_id']=='00123' and row['duration']=='37.125'
    assert row['login_time']==completed['login_time'] and row['logout_time']==completed['logout_time']


def test_failed_backup_leaves_no_misleading_partial_file(tmp_path):
    source=tmp_path/'invalid.sqlite'
    source.write_bytes(b'not a database')
    output=tmp_path/'backup.sqlite'
    with pytest.raises(sqlite3.DatabaseError):
        backup_database(source,output)
    assert source.read_bytes()==b'not a database'
    assert not output.exists()


def test_backup_command_does_not_upgrade_or_rewrite_older_source(tmp_path,monkeypatch):
    import server.__main__ as cli
    from server.db import SCHEMA
    source=tmp_path/'older.sqlite'
    output=tmp_path/'snapshot.sqlite'
    with sqlite3.connect(source) as db:
        db.executescript(SCHEMA)
    monkeypatch.setattr('sys.argv',['server','backup','--database',str(source),'--output',str(output)])
    cli.main()
    for path in (source,output):
        with sqlite3.connect(path) as db:
            assert db.execute('SELECT version FROM schema_version').fetchone()[0]==1
