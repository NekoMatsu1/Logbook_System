"""Opt-in real Tk rendering with fake input/power adapters and a fake clock."""
import os
import time
import pytest
from client.api import APIError

pytestmark=pytest.mark.skipif(os.getenv('LOGBOOK_GUI_TEST')!='1',reason='Set LOGBOOK_GUI_TEST=1 with an interactive desktop')

@pytest.fixture(scope='module')
def desktop_root():
    import tkinter as tk
    root=tk.Tk()
    yield root
    root.destroy()

@pytest.mark.parametrize('gated',[False,True])
@pytest.mark.parametrize('manual',[False,True])
def test_tk_registration_login_and_simulated_logout(app,clock,monkeypatch,gated,manual,desktop_root):
    import tkinter as tk
    import client.__main__ as desktop
    class TestAPI:
        def __init__(self,config): pass
        def call(self,method,path,data=None):
            with app.test_client() as web:
                response=web.open(path,method=method,json=data,headers={'X-Computer-ID':'LAB-PC-01','Authorization':'Bearer test-token'})
                if response.status_code>=400:
                    raise APIError(f'{response.status_code}: {response.json["error"]}')
                return response.json
        def lookup(self,sid): return self.call('GET','/api/students/'+sid)
    class FakeAdapter:
        simulation=True
        actions=[]
        def sample(self): return {}
        def attach_signout(self,*args): return False
        def action(self,name): self.actions.append(name)
    adapter=FakeAdapter()
    class FakeLink:
        def __init__(self): self.messages=[]; self.warning_state=None; self.locked=False; self.granted=None
        def hello(self,run): self.run=run
        def grant(self,key,run): self.granted=(key,run)
        def lock(self): self.locked=True
        def warning(self,kind,seconds): self.warning_state=(kind,seconds)
        def poll(self):
            result,self.messages=self.messages,[]
            return result
    link=FakeLink() if gated else None
    monkeypatch.setattr(desktop,'API',TestAPI)
    monkeypatch.setattr(desktop,'load',lambda _:adapter)
    monkeypatch.setattr(desktop.messagebox,'askyesno',lambda *args,**kwargs:True)
    root=desktop_root
    root.deiconify()
    agent=desktop.Desktop(root,{'computer_id':'LAB-PC-01','simulation':True},gate=link)
    agent.timers.clock=clock
    agent.timers.last_activity=clock()
    agent.timers.wait_since=clock()
    def pump_until(predicate):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            root.update()
            if predicate(): return
            time.sleep(.01)
        raise AssertionError('Tk operation did not finish')
    try:
        pump_until(lambda:agent.connected and not agent.busy)
        agent.sid.set('00042')
        agent.name.set('Ana Reyes')
        agent.mode.set('register')
        agent.identify()
        pump_until(lambda:not agent.busy)
        assert 'Registered' in agent.status.get()
        agent.identify()
        pump_until(lambda:agent.session_id is not None)
        assert agent.timers.active
        if gated:
            assert root.state()!='withdrawn' # Start acknowledgement alone does not open desktop.
            assert link.granted==(agent.session_id,agent.run_id)
            link.messages.append(dict(event='desktop_open',session_id=agent.session_id,run_id=agent.run_id))
            pump_until(lambda:root.state()=='withdrawn')
        if manual:
            if not gated:
                assert agent.logout_button.cget('text') == 'Log out'
                agent.session_window.withdraw()
                agent.show_session_window()
                assert agent.session_window.state() != 'withdrawn'
                agent.logout_button.invoke()
            else:
                agent.manual_logout()
        else:
            clock.advance(300)
            pump_until(lambda:agent.timers.warning=='logout')
            if gated:
                assert link.warning_state[0]=='logout'
            else:
                assert agent.warning is not None
                assert 'Are you still working?' in agent.warning_text.get()
                assert agent.presence_button.cget('text')=="Yes, I'm still here"
            agent.timers.activity(mouse_moved=True,mouse_click=True,keyboard=True)
            assert agent.timers.warning=='logout'
            if gated:
                link.messages.append(dict(event='confirm_presence',session_id=agent.session_id,run_id=agent.run_id))
                pump_until(lambda:agent.timers.warning is None)
            else:
                agent.presence_button.invoke()
                assert agent.timers.warning is None
            # Acknowledgement starts a fresh inactivity interval, not an early session ending.
            assert agent.session_id is not None
            clock.advance(300)
            pump_until(lambda:agent.timers.warning=='logout')
            clock.advance(60)
        pump_until(lambda:agent.session_id is None and not agent.busy)
        assert adapter.actions==['logout']
        if gated: assert link.locked and root.state()!='withdrawn'
        assert not agent.timers.active
        clock.advance(600)
        pump_until(lambda:agent.timers.warning=='shutdown')
        assert "Yes, I'm still here" in agent.warning_text.get()
        agent.timers.activity(mouse_moved=True,mouse_click=True,keyboard=True)
        assert agent.timers.warning=='shutdown'
        agent.identify()
        assert 'on the warning before continuing' in agent.status.get()
        assert agent.timers.warning=='shutdown'
        agent.presence_button.invoke()
        assert agent.timers.warning is None
        assert adapter.actions==['logout']
        clock.advance(600)
        pump_until(lambda:agent.timers.warning=='shutdown')
        clock.advance(60)
        pump_until(lambda:adapter.actions==['logout','shutdown'])
        with app.test_client() as web:
            assert ('simulated_manual_logout' if manual else 'simulated_inactivity') in web.get('/admin/records').text
    finally:
        agent.pool.shutdown(wait=True,cancel_futures=True)
        for callback in root.tk.call('after','info'):
            root.after_cancel(callback)
        for widget in root.winfo_children():
            widget.destroy()
        root.withdraw()
