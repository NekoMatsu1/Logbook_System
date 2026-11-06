import threading
import pytest
from waitress import create_server
from client.api import API, APIError
from server.db import connect

def test_real_http_workflow(app,clock):
    with connect(app.config['DATABASE']) as db:
        db.execute('INSERT INTO students(student_id,name) VALUES(?,?)',
                   ('0000000007','Santos, Maria, Reyes'))
    server=create_server(app,host='127.0.0.1',port=0)
    thread=threading.Thread(target=server.run,daemon=True)
    thread.start()
    api=API(dict(server_url=f'http://127.0.0.1:{server.effective_port}',computer_id='LAB-PC-01',
                 machine_token='test-token',allow_loopback_http=True))
    try:
        api.call('POST','/api/heartbeat',dict(run_id='transport',active_session=None))
        assert api.lookup('0000000007')=={'student_id':'0000000007','setup_required':True}
        login=api.call('POST','/api/student-auth/setup',dict(student_id='0000000007',password='Transportpass1'))
        result=api.call('POST','/api/sessions',dict(student_id='0000000007',run_id='transport',
            session_id='http-session',student_auth_token=login['student_auth_token']))
        assert result['status']=='active'
        clock.advance(50)
        result=api.call('POST','/api/sessions/http-session/end',dict(run_id='transport',reason='simulated_inactivity'))
        assert result['status']=='completed' and result['duration']==50
        with pytest.raises(APIError,match='404'):
            api.lookup('9999999999')
        # Provisioned credentials do not give this client dashboard access.
        with pytest.raises(APIError,match='403'):
            api.call('GET','/admin/overview')
    finally:
        api.http.close()
        server.close()
        thread.join(timeout=2)
