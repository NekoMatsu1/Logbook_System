import ctypes
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from .base import Adapter

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]

class Windows(Adapter):
    def __init__(self, simulation=True):
        super().__init__(simulation)
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.previous = None
        self.input_worker = ThreadPoolExecutor(max_workers=1)

    def sample(self):
        return self.input_worker.submit(self._sample_input).result(timeout=2)

    def _sample_input(self):
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not self.user.GetLastInputInfo(ctypes.byref(info)):
            raise OSError('GetLastInputInfo failed')
        point = wintypes.POINT()
        self.user.GetThreadDesktop.argtypes=[wintypes.DWORD]
        self.user.GetThreadDesktop.restype=wintypes.HANDLE
        self.user.OpenInputDesktop.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        self.user.OpenInputDesktop.restype=wintypes.HANDLE
        self.user.SetThreadDesktop.argtypes=[wintypes.HANDLE]
        self.user.CloseDesktop.argtypes=[wintypes.HANDLE]
        previous_desktop=self.user.GetThreadDesktop(self.kernel.GetCurrentThreadId())
        input_desktop=self.user.OpenInputDesktop(0,False,0x0103)
        if not input_desktop:
            raise OSError('Input desktop unavailable; automatic actions paused')
        try:
            if not self.user.SetThreadDesktop(input_desktop) or not self.user.GetCursorPos(ctypes.byref(point)):
                raise OSError('Global cursor query failed')
        finally:
            self.user.SetThreadDesktop(previous_desktop)
            self.user.CloseDesktop(input_desktop)
        sample = (info.dwTime, point.x, point.y)
        previous, self.previous = self.previous, sample
        changed = previous is not None and sample[0] != previous[0]
        moved = previous is not None and sample[1:] != previous[1:]
        return dict(keyboard=changed, mouse_moved=moved)

    def real_action(self, name):
        if name == 'logout':
            if not self.user.ExitWindowsEx(0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            import subprocess
            subprocess.run(['shutdown.exe', '/s', '/t', '0'], check=True, timeout=10)

    def attach_signout(self, root, callback):
        # WM_QUERYENDSESSION is a request, WM_ENDSESSION(wParam=TRUE) is confirmation.
        root.update_idletasks()
        self.user.GetParent.restype = wintypes.HWND
        hwnd = self.user.GetParent(wintypes.HWND(root.winfo_id()))
        pointer = ctypes.c_ssize_t
        prototype = ctypes.WINFUNCTYPE(pointer, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        setter = self.user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.user.SetWindowLongW
        setter.argtypes = [wintypes.HWND, ctypes.c_int, pointer]
        setter.restype = pointer
        self.user.CallWindowProcW.argtypes = [ctypes.c_void_p,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.user.CallWindowProcW.restype = pointer
        def procedure(window, message, wparam, lparam):
            if message == 0x11:
                return 1
            if message == 0x16 and wparam:
                callback()
            return self.user.CallWindowProcW(self.old_proc, window, message, wparam, lparam)
        self.proc = prototype(procedure)
        self.old_proc = setter(hwnd, -4, ctypes.cast(self.proc, ctypes.c_void_p).value)
        if not self.old_proc:
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def interactive_present(self):
        import subprocess
        # Locale-independent WTS API, rather than parsing localized `quser` output.
        class WTS_SESSION_INFO(ctypes.Structure):
            _fields_ = [('SessionId', wintypes.DWORD), ('pWinStationName', wintypes.LPWSTR), ('State', ctypes.c_int)]
        wts = ctypes.WinDLL('wtsapi32')
        entries = ctypes.POINTER(WTS_SESSION_INFO)()
        count = wintypes.DWORD()
        if not wts.WTSEnumerateSessionsW(None, 0, 1, ctypes.byref(entries), ctypes.byref(count)):
            raise OSError('Cannot enumerate Windows sessions')
        try:
            for item in entries[:count.value]:
                buffer = wintypes.LPWSTR()
                size = wintypes.DWORD()
                if wts.WTSQuerySessionInformationW(None, item.SessionId, 5, ctypes.byref(buffer), ctypes.byref(size)):
                    try:
                        if buffer.value:
                            return True
                    finally:
                        wts.WTSFreeMemory(buffer)
            return False
        finally:
            wts.WTSFreeMemory(entries)
