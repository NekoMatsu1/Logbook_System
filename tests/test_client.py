import pytest
from client.api import API, APIError
from client.helper import Helper
from client.platforms.base import Adapter

def test_monitor_failure_preserves_settings_and_can_recover(clock):
    from client.__main__ import Desktop
    from client.state import Timers
    from types import SimpleNamespace
    agent=Desktop.__new__(Desktop)
    agent.timers=Timers(clock)
    agent.session_id=None
    agent.status=SimpleNamespace(set=lambda value: None)
    def fail(): raise RuntimeError('input desktop unavailable')
    agent.adapter=SimpleNamespace(sample=fail)
    configured=agent.timers.settings.copy()
    assert agent.sample_activity() is False
    assert agent.timers.settings==configured
    agent.adapter.sample=lambda: {}
    assert agent.sample_activity() is True
    assert agent.timers.settings==configured

@pytest.mark.parametrize('url',['http://10.0.0.2:5000','ftp://127.0.0.1','https://user:secret@example.com','https://example.com/path'])
def test_reject_insecure_urls(url):
    with pytest.raises(ValueError):
        API(dict(server_url=url,machine_token='test',computer_id='PC',allow_loopback_http=True))

def test_requires_explicit_loopback_http():
    with pytest.raises(ValueError):
        API(dict(server_url='http://127.0.0.1:5000',machine_token='test',computer_id='PC'))

def test_simulation_never_real_action():
    class Fake(Adapter):
        def real_action(self,name):
            raise AssertionError('Real power operation called')
    fake=Fake()
    fake.action('logout')
    fake.action('shutdown')

def test_helper_only_without_os_session(clock):
    class FakeAdapter:
        simulation=True
        present=True
        actions=[]
        def interactive_present(self): return self.present
        def action(self,name): self.actions.append(name)
    class FakeAPI:
        def call(self,*args):
            return {'settings':{'shutdown_wait_seconds':5,'shutdown_warning_seconds':2}}
    adapter=FakeAdapter()
    helper=Helper(FakeAPI(),adapter,clock)
    helper.step()
    clock.advance(100)
    helper.step()
    assert not adapter.actions
    adapter.present=False
    helper.step()
    clock.advance(5)
    helper.step()
    clock.advance(2)
    helper.step()
    assert adapter.actions==['shutdown']
    adapter.present=True
    clock.advance(1000)
    helper.step()
    assert adapter.actions==['shutdown']

def test_heartbeat_failure_does_not_end_student_session(clock):
    from client.__main__ import Desktop
    from client.state import Timers
    class Status:
        def set(self,value): self.value=value
    agent=Desktop.__new__(Desktop)
    agent.session_id='active-session'
    agent.student_name='Ana'
    agent.status=Status()
    agent.failure_count=0
    agent.connected=True
    agent.timers=Timers(clock)
    agent.timers.start()
    cached=agent.timers.settings.copy()
    agent.failed(APIError('Server connection failed'))
    assert agent.session_id=='active-session'
    assert agent.timers.active and agent.timers.settings==cached
    assert not agent.connected and 'Session continues' in agent.status.value

def test_helper_connection_loss_retains_loaded_timers(clock):
    class FakeAdapter:
        simulation=True
        actions=[]
        def interactive_present(self): return False
        def action(self,name): self.actions.append(name)
    class FakeAPI:
        calls=0
        def call(self,*args):
            self.calls+=1
            if self.calls>1: raise APIError('Connection failed')
            return {'settings':{'shutdown_wait_seconds':10,'shutdown_warning_seconds':5}}
    adapter=FakeAdapter()
    helper=Helper(FakeAPI(),adapter,clock)
    helper.step()
    clock.advance(10)
    helper.step()
    assert helper.timers.warning=='shutdown'
    clock.advance(5)
    helper.step()
    assert adapter.actions==['shutdown']

def test_live_helper_cannot_shutdown_without_visible_cancellable_warning(clock):
    from types import SimpleNamespace
    actions=[]
    adapter=SimpleNamespace(simulation=False,interactive_present=lambda: False,action=actions.append)
    api=SimpleNamespace(call=lambda *args: {'settings':{'shutdown_wait_seconds':1,'shutdown_warning_seconds':1}})
    helper=Helper(api,adapter,clock)
    helper.step()
    clock.advance(1)
    helper.step()
    clock.advance(1)
    helper.step()
    assert actions==[]
