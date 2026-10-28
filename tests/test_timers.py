from client.state import Timers

def test_inactivity_cancel(clock):
    timers=Timers(clock)
    timers.start()
    clock.advance(300)
    assert timers.tick() is None and timers.warning=='logout'
    clock.advance(30)
    timers.activity(keyboard=True)
    assert timers.warning is None
    clock.advance(300)
    timers.tick()
    clock.advance(60)
    assert timers.tick()=='logout'

def test_shutdown_mouse_only(clock):
    timers=Timers(clock)
    clock.advance(600)
    timers.tick()
    assert timers.warning=='shutdown'
    timers.activity(keyboard=True,mouse_click=True)
    assert timers.warning=='shutdown'
    timers.activity(mouse_moved=True)
    assert timers.warning is None
    clock.advance(600)
    timers.tick()
    clock.advance(60)
    assert timers.tick()=='shutdown'

def test_identification_pause_and_abandon(clock):
    timers=Timers(clock)
    clock.advance(500)
    timers.identify()
    clock.advance(50)
    timers.identify()
    clock.advance(10)
    assert timers.tick()=='identification_expired'
    assert timers.remaining==100
    clock.advance(99)
    timers.tick()
    assert timers.warning is None
    clock.advance(1)
    timers.tick()
    assert timers.warning=='shutdown'

def test_cancel_identification_resume(clock):
    timers=Timers(clock)
    clock.advance(590)
    timers.identify()
    clock.advance(20)
    timers.cancel_identify()
    clock.advance(10)
    timers.tick()
    assert timers.warning=='shutdown'

def test_active_never_shutdown(clock):
    timers=Timers(clock,{'auto_logout':False})
    clock.advance(600)
    timers.tick()
    timers.start()
    clock.advance(100000)
    assert timers.tick() is None and timers.warning is None

def test_loaded_settings_change_and_disable(clock):
    timers=Timers(clock)
    timers.configure({'shutdown_wait_seconds':5})
    clock.advance(5)
    timers.tick()
    assert timers.warning=='shutdown'
    timers.configure({'auto_shutdown':False})
    clock.advance(60)
    assert timers.tick() is None and timers.warning is None
