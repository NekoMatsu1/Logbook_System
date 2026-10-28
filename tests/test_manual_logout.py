from types import SimpleNamespace

import pytest

from client.__main__ import Desktop
from client.api import APIError
from client.state import Timers


@pytest.fixture
def agent(clock):
    desktop = Desktop.__new__(Desktop)
    desktop.session_id = 'session-1'
    desktop.run_id = 'run-1'
    desktop.student_name = 'Test Student'
    desktop.busy = desktop.pending_end = False
    desktop.session_window = desktop.logout_button = desktop.gate = None
    desktop.pending_events = []
    desktop.timers = Timers(clock)
    desktop.timers.start()
    desktop.status = SimpleNamespace(set=lambda value: setattr(desktop, 'message', value))
    desktop.sid = desktop.name = SimpleNamespace(set=lambda value: None)
    desktop.root = SimpleNamespace(deiconify=lambda: None)
    desktop.actions = []
    desktop.adapter = SimpleNamespace(simulation=True, action=desktop.actions.append)
    desktop.failed = lambda error: None
    def job(work, success, failure):
        try:
            result = work()
        except Exception as error:
            failure(error)
        else:
            success(result)
    desktop.job = job
    return desktop


def test_cancel_manual_logout_keeps_active_session(agent, monkeypatch):
    def cancel(*args, **kwargs):
        assert agent.timers.blocked  # A modal dialog must not allow an automatic timer action.
        return False
    monkeypatch.setattr('client.__main__.messagebox.askyesno', cancel)
    agent.manual_logout()
    assert agent.session_id == 'session-1' and agent.timers.active
    assert not agent.actions and not agent.timers.blocked


@pytest.mark.parametrize('result', [APIError('offline'), APIError('400: Invalid end reason'), {'status':'unexpected'}])
def test_unconfirmed_manual_logout_never_signs_out_or_discards_session(agent, result):
    def call(*args):
        if isinstance(result, Exception):
            raise result
        return result
    agent.api = SimpleNamespace(call=call)
    agent.end_session('manual_logout', require_ack=True)
    assert agent.session_id == 'session-1' and agent.timers.active
    assert not agent.actions and not agent.pending_end and not agent.timers.blocked
    assert 'session continues' in agent.message


def test_manual_logout_of_interrupted_session_does_not_invent_end_time(agent, web, auth, ready):
    web.post('/api/sessions',headers=auth,json=ready)
    web.post('/api/heartbeat',headers=auth,json={'run_id':'new-run','active_session':None})
    def call(method,path,data):
        response=web.open(path,method=method,headers=auth,json=data)
        assert response.status_code==200
        return response.json
    agent.api=SimpleNamespace(call=call)
    agent.end_session('manual_logout',require_ack=True)
    assert agent.session_id is None and agent.actions==['logout']
    assert 'end time remains unknown' in agent.message
    record=web.get('/api/sessions/session-1',headers=auth).json
    assert record['status']=='interrupted'
    assert record['logout_time'] is None and record['duration'] is None


@pytest.mark.parametrize('simulation,reason', [(True,'simulated_manual_logout'), (False,'manual_logout')])
def test_manual_logout_is_saved_once_before_os_action(agent, web, auth, ready, clock, simulation, reason):
    web.post('/api/sessions', headers=auth, json=ready)
    clock.advance(25)
    agent.adapter.simulation = simulation
    def call(method, path, data):
        response = web.open(path, method=method, headers=auth, json=data)
        assert response.status_code == 200
        assert response.json['end_reason'] == reason
        assert not agent.actions
        return response.json
    agent.api = SimpleNamespace(call=call)
    agent.end_session('manual_logout', require_ack=True)
    agent.end_session('manual_logout', require_ack=True)  # Duplicate click cannot repeat power action.
    assert agent.actions == ['logout']
    assert agent.session_id is None and not agent.timers.active
    record = web.get('/api/sessions/session-1', headers=auth).json
    assert record['status'] == 'completed' and record['duration'] == 25
    assert record['end_reason'] == reason
