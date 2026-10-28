from server.db import SCHEMA,connect,initialize

def test_v1_upgrade_preserves_students_computers_and_sessions(tmp_path):
    path=tmp_path/'old.sqlite'
    with connect(path) as db:
        db.executescript(SCHEMA)
        db.execute('INSERT INTO students VALUES(?,?,?)',('0001','Existing Student',1))
        db.execute('INSERT INTO computers(computer_id,token_hash) VALUES(?,?)',('PC','not-a-real-hash'))
        db.execute("INSERT INTO sessions(session_id,student_id,student_name,computer_id,run_id,login_time,status) VALUES(?,?,?,?,?,?,?)",
                   ('session','0001','Original Name','PC','old-run','2026-10-23T00:00:00+00:00','active'))
    initialize(path)
    initialize(path)
    with connect(path) as db:
        assert db.execute('SELECT version FROM schema_version').fetchone()[0]==2
        assert db.execute('SELECT student_id FROM students').fetchone()[0]=='0001'
        row=db.execute('SELECT * FROM sessions').fetchone()
        assert row['student_name']=='Original Name' and row['logout_time'] is None
        assert db.execute('SELECT enabled FROM computers').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM admin_sessions').fetchone()[0]==0
