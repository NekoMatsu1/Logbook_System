"""Native shell gating. Never activate live mode on the development laptop."""
import logging
import os
import signal
import subprocess
import sys
import uuid

class WindowsGate:
    def __init__(self,simulation=True):
        self.simulation=simulation
        self.unlocked=False
        self.name='LogbookLogin-'+uuid.uuid4().hex
        self.login=self.default=None
        if simulation:
            return
        import ctypes
        from ctypes import wintypes
        self.ctypes=ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            raise RuntimeError('Live student shell must run under a standard account, never an administrator')
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.CreateDesktopW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
        self.user.CreateDesktopW.restype=wintypes.HANDLE
        self.user.OpenDesktopW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.user.OpenDesktopW.restype=wintypes.HANDLE
        self.user.SwitchDesktop.argtypes=[wintypes.HANDLE]
        self.user.CloseDesktop.argtypes=[wintypes.HANDLE]
        self.default=self.user.OpenDesktopW('Default',0,False,0x0103)
        self.login=self.user.CreateDesktopW(self.name,None,None,0,0x000F01FF,None)
        if not self.default or not self.login:
            raise ctypes.WinError(ctypes.get_last_error())
        self.lock()

    def child_options(self):
        if self.simulation:
            return {}
        startup=subprocess.STARTUPINFO()
        startup.lpDesktop='WinSta0\\'+self.name
        return {'startupinfo':startup}

    def lock(self):
        if not self.simulation and not self.user.SwitchDesktop(self.login):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        self.unlocked=False
        logging.warning('%s desktop gate locked','SIMULATED' if self.simulation else 'NATIVE')

    def maintain_lock(self):
        if not self.simulation and not self.unlocked:
            # Secure Winlogon desktop can refuse switches; do not bypass it.
            self.user.SwitchDesktop(self.login)

    def unlock(self):
        if not self.simulation:
            if not self.user.SwitchDesktop(self.default):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
            try:
                subprocess.Popen([os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'explorer.exe')])
            except Exception:
                self.lock()
                raise
        else:
            logging.warning('SIMULATION: would switch to the normal desktop and launch Explorer')
        self.unlocked=True

    def warning_options(self):
        if self.simulation:
            return {}
        startup=subprocess.STARTUPINFO()
        startup.lpDesktop='WinSta0\\Default'
        return {'startupinfo':startup}

    def session_ended(self): return False # WM_ENDSESSION is handled by the interactive agent.

    def close(self):
        # Never unlock the work desktop as a side effect of an agent crash.
        if not self.simulation:
            if not self.unlocked:
                self.maintain_lock()
            for handle in (self.default,self.login):
                if handle:
                    self.user.CloseDesktop(handle)

class LinuxGate:
    def __init__(self,simulation=True):
        if not simulation and os.environ.get('XDG_SESSION_TYPE')=='wayland':
            raise RuntimeError('Managed logbook session requires X11')
        self.simulation=simulation
        self.unlocked=False
        self.shell=None
    def child_options(self): return {}
    def warning_options(self): return {}
    def maintain_lock(self): pass # Before authorization the managed Xsession has no desktop shell.
    def session_ended(self): return self.shell is not None and self.shell.poll() is not None
    def unlock(self):
        if not self.simulation:
            self.shell=subprocess.Popen(['cinnamon-session','--session','cinnamon'],start_new_session=True)
        else:
            logging.warning('SIMULATION: would start the Cinnamon desktop')
        self.unlocked=True
    def lock(self):
        was_unlocked=self.unlocked
        self.unlocked=False
        if not self.simulation and was_unlocked:
            if self.shell and self.shell.poll() is None:
                os.killpg(self.shell.pid,signal.SIGTERM)
            # Ending the custom Xsession returns control to the display manager.
            raise SystemExit(0)
    def close(self): pass

def load_gate(simulation):
    return WindowsGate(simulation) if sys.platform=='win32' else LinuxGate(simulation)
