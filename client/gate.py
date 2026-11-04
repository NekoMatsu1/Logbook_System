"""Private child-to-supervisor protocol; no student names or input contents."""
import json
import os
import sys
import queue
import threading

PREFIX='LOGBOOK_GATE '

def _attach_windows_pipes(streams=('stdin','stdout')):
    if sys.platform != 'win32' or all(getattr(sys, name) is not None for name in streams):
        return
    import ctypes
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    for name, handle_id, mode, flags in (
        ('stdin', -10, 'r', os.O_RDONLY),
        ('stdout', -11, 'w', os.O_WRONLY),
    ):
        if name not in streams or getattr(sys, name) is not None:
            continue
        handle = kernel.GetStdHandle(handle_id)
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise OSError(f'Windows {name} pipe is unavailable')
        descriptor = msvcrt.open_osfhandle(handle, flags)
        setattr(sys, name, os.fdopen(descriptor, mode, encoding='utf-8', buffering=1))

class ShellLink:
    def __init__(self):
        _attach_windows_pipes()
        self.last_warning=None
        self.incoming=queue.Queue()
        def read():
            for line in sys.stdin:
                try:
                    item=json.loads(line)
                    if isinstance(item,dict): self.incoming.put(item)
                except ValueError:
                    pass
        threading.Thread(target=read,daemon=True).start()
    def poll(self):
        values=[]
        while not self.incoming.empty(): values.append(self.incoming.get_nowait())
        return values
    def emit(self,event,**values):
        print(PREFIX+json.dumps(dict(event=event,**values)),file=sys.stdout,flush=True)
    def hello(self,run_id): self.emit('hello',run_id=run_id)
    def grant(self,session_id,run_id): self.emit('grant',session_id=session_id,run_id=run_id)
    def lock(self): self.emit('lock')
    def warning(self,kind,seconds):
        state=(kind,seconds)
        if state!=self.last_warning:
            self.last_warning=state
            self.emit('warning',kind=kind,seconds=seconds)
