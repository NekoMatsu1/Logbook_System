import json
import sys
import pytest
from client.kiosk import Supervisor
from client.api import APIError
from client.credentials import load_config, protect_config

def test_explorer_launch_failure_relocks_desktop(monkeypatch):
    from client.platforms.desktop_gate import WindowsGate
    from types import SimpleNamespace
    gate=WindowsGate.__new__(WindowsGate)
    gate.simulation=False
    gate.unlocked=False
    gate.default='work'
    gate.login='login'
    switches=[]
    gate.user=SimpleNamespace(SwitchDesktop=lambda desktop: switches.append(desktop) or True)
    def fail(*args,**kwargs): raise OSError('Explorer unavailable')
    monkeypatch.setattr('client.platforms.desktop_gate.subprocess.Popen',fail)
    with pytest.raises(OSError): gate.unlock()
    assert switches==['work','login']
    assert gate.unlocked is False

class Gate:
    def __init__(self): self.is_open=False; self.opens=0
    def lock(self): self.is_open=False
    def unlock(self): self.is_open=True; self.opens+=1

class API:
    def __init__(self): self.record={'status':'active','run_id':'run'}; self.fail=False
    def call(self,*args):
        if self.fail: raise APIError('offline')
        return self.record

def test_desktop_never_opens_without_central_confirmation():
    gate,api=Gate(),API()
    supervisor=Supervisor(api,gate)
    supervisor.handle({'event':'grant','run_id':'run','session_id':'session'})
    supervisor.resolve()
    assert not gate.is_open
    supervisor.handle({'event':'hello','run_id':'run'})
    supervisor.handle({'event':'grant','run_id':'run','session_id':'session'})
    api.fail=True
    with pytest.raises(APIError): supervisor.resolve()
    assert not gate.is_open
    api.fail=False
    supervisor.resolve()
    assert gate.is_open and gate.opens==1
    # A missed heartbeat must not close an already authorized student's desktop.
    api.fail=True
    supervisor.resolve()
    assert gate.is_open
    supervisor.handle({'event':'lock'})
    assert not gate.is_open

@pytest.mark.parametrize('record',[{'status':'completed','run_id':'run'},{'status':'active','run_id':'different'}])
def test_stale_or_wrong_run_never_opens_desktop(record):
    gate,api=Gate(),API()
    api.record=record
    supervisor=Supervisor(api,gate)
    supervisor.handle({'event':'hello','run_id':'run'})
    supervisor.handle({'event':'grant','run_id':'run','session_id':'session'})
    supervisor.resolve()
    assert not gate.is_open

def test_agent_restart_relocks_desktop():
    gate,api=Gate(),API()
    supervisor=Supervisor(api,gate)
    supervisor.handle({'event':'hello','run_id':'run'})
    supervisor.handle({'event':'grant','run_id':'run','session_id':'session'})
    supervisor.resolve()
    supervisor.handle({'event':'hello','run_id':'new-run'})
    assert not gate.is_open and supervisor.active is None


def test_presence_confirmation_is_bound_to_current_session_and_run():
    gate,api=Gate(),API()
    supervisor=Supervisor(api,gate)
    supervisor.handle({'event':'hello','run_id':'run'})
    supervisor.handle({'event':'grant','run_id':'run','session_id':'session'})
    supervisor.resolve()
    valid={'event':'presence_confirmed','session_id':'session','run_id':'run'}
    assert supervisor.presence_confirmation(valid) is None
    supervisor.handle({'event':'warning','kind':'logout','seconds':30})
    assert supervisor.presence_confirmation(valid)==dict(event='confirm_presence',session_id='session',run_id='run')
    assert supervisor.presence_confirmation(valid|{'session_id':'old'}) is None
    assert supervisor.presence_confirmation(valid|{'run_id':'old'}) is None
    supervisor.handle({'event':'lock'})
    assert supervisor.presence_confirmation(valid) is None

@pytest.mark.skipif(sys.platform!='win32',reason='Windows DPAPI test')
def test_windows_machine_credential_is_encrypted_and_readable_on_same_pc(tmp_path):
    path=tmp_path/'client.json'
    path.write_text(json.dumps({'machine_token':'not-a-real-token','computer_id':'test'}))
    protect_config(path)
    stored=json.loads(path.read_text())
    assert 'machine_token' not in stored
    assert 'not-a-real-token' not in path.read_text()
    assert load_config(path)['machine_token']=='not-a-real-token'
    protect_config(path) # Idempotent; no double encryption.
    assert load_config(path)['machine_token']=='not-a-real-token'
