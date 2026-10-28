import ctypes
import ctypes.util
import os
import subprocess
from .base import Adapter

class XScreenSaverInfo(ctypes.Structure):
    _fields_ = [('window',ctypes.c_ulong),('state',ctypes.c_int),('kind',ctypes.c_int),
                ('til_or_since',ctypes.c_ulong),('idle',ctypes.c_ulong),('eventMask',ctypes.c_ulong)]

class Linux(Adapter):
    def __init__(self, simulation=True):
        super().__init__(simulation)
        self.previous = None
        self.display = None

    def open_display(self):
        if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            raise RuntimeError('Wayland global input monitoring is not implemented; use an X11 session')
        self.x = ctypes.CDLL(ctypes.util.find_library('X11'))
        self.ss = ctypes.CDLL(ctypes.util.find_library('Xss'))
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('X11 display unavailable')
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.root = self.x.XDefaultRootWindow(self.display)
        self.ss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(XScreenSaverInfo)]
        self.x.XQueryPointer.argtypes = [ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),
                                       ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]

    def sample(self):
        if not self.display:
            self.open_display()
        info = XScreenSaverInfo()
        if not self.ss.XScreenSaverQueryInfo(self.display, self.root, ctypes.byref(info)):
            raise RuntimeError('XScreenSaver idle query failed')
        root, child = ctypes.c_ulong(), ctypes.c_ulong()
        x,y,wx,wy = (ctypes.c_int() for _ in range(4))
        mask = ctypes.c_uint()
        if not self.x.XQueryPointer(self.display,self.root,ctypes.byref(root),ctypes.byref(child),ctypes.byref(x),ctypes.byref(y),ctypes.byref(wx),ctypes.byref(wy),ctypes.byref(mask)):
            raise RuntimeError('X11 pointer query failed')
        import time
        stamp = time.monotonic() - info.idle / 1000
        sample = (stamp, x.value, y.value)
        previous, self.previous = self.previous, sample
        return dict(keyboard=previous is not None and stamp - previous[0] > .05,
                    mouse_moved=previous is not None and sample[1:] != previous[1:])

    def real_action(self, name):
        command = ['cinnamon-session-quit', '--logout', '--no-prompt'] if name == 'logout' else ['systemctl', 'poweroff']
        subprocess.run(command, check=True, timeout=10)

    def interactive_present(self):
        output = subprocess.run(['loginctl','list-sessions','--no-legend','--no-pager'], capture_output=True,text=True,check=True,timeout=5).stdout
        for line in output.splitlines():
            session_id = line.split()[0]
            properties = subprocess.run(['loginctl','show-session',session_id,'-p','Class','-p','Type'],capture_output=True,text=True,check=True,timeout=5).stdout
            if 'Class=user' in properties and any('Type=' + kind in properties for kind in ('x11','wayland','tty')):
                return True
        return False
