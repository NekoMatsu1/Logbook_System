"""Pure monotonic-clock state machine. Activity contains no keys or application data."""
from common import DEFAULTS

class Timers:
    def __init__(self, clock, settings=None):
        self.clock = clock
        self.settings = DEFAULTS.copy() | (settings or {})
        self.active = False
        self.warning = None
        self.warning_at = None
        self.last_activity = clock()
        self.wait_since = clock()
        self.remaining = self.settings['shutdown_wait_seconds']
        self.identifying = False
        self.identification_started = None
        self.blocked = False

    def configure(self, settings):
        old = self.settings['shutdown_wait_seconds']
        self.settings.update(settings)
        if not self.identifying and not self.active and old != self.settings['shutdown_wait_seconds']:
            self.remaining = self.settings['shutdown_wait_seconds']
            self.wait_since = self.clock()

    def identify(self):
        if self.active or self.identifying or self.blocked or self.warning:
            return
        # Freeze remaining time; focus events cannot refresh this deadline.
        self.remaining = max(0, self.remaining - (self.clock() - self.wait_since))
        self.identifying = True
        self.identification_started = self.clock()
        self.warning = None

    def cancel_identify(self):
        if self.identifying:
            self.identifying = False
            self.wait_since = self.clock()

    def start(self):
        self.active = True
        self.identifying = False
        self.warning = None
        self.last_activity = self.clock()

    def reset(self):
        self.active = False
        self.identifying = False
        self.warning = None
        self.remaining = self.settings['shutdown_wait_seconds']
        self.wait_since = self.clock()

    def activity(self, keyboard=False, mouse_moved=False, mouse_click=False):
        if self.active and self.warning is None and (keyboard or mouse_moved or mouse_click):
            self.last_activity = self.clock()

    def confirm_presence(self):
        if self.warning not in ('logout','shutdown') or self.blocked:
            return False
        limit=self.settings['logout_warning_seconds' if self.warning=='logout' else 'shutdown_warning_seconds']
        if self.clock()-self.warning_at >= limit:
            return False
        if self.warning=='shutdown':
            self.reset()
        else:
            self.last_activity=self.clock()
            self.warning=None
        return True

    def tick(self):
        now = self.clock()
        if self.blocked:
            return None
        if self.active:
            if not self.settings['auto_logout']:
                self.warning = None
                return None
            if self.warning == 'logout':
                if now - self.warning_at >= self.settings['logout_warning_seconds']:
                    self.warning = None
                    return 'logout'
            elif now - self.last_activity >= self.settings['inactivity_seconds']:
                self.warning, self.warning_at = 'logout', now
        else:
            if self.identifying:
                if now - self.identification_started >= self.settings['identification_timeout_seconds']:
                    self.cancel_identify()
                    return 'identification_expired'
                return None
            if not self.settings['auto_shutdown']:
                self.warning = None
                return None
            if self.warning == 'shutdown':
                if now - self.warning_at >= self.settings['shutdown_warning_seconds']:
                    self.reset()
                    return 'shutdown'
            elif now - self.wait_since >= self.remaining:
                self.warning, self.warning_at = 'shutdown', now
        return None

    def countdown(self):
        if not self.warning:
            return None
        import math
        seconds = self.settings['logout_warning_seconds' if self.warning == 'logout' else 'shutdown_warning_seconds']
        return max(0, math.ceil(seconds - (self.clock() - self.warning_at)))
