"""Private child-to-supervisor protocol; no student names or input contents."""
import json
import sys
import queue
import threading

PREFIX='LOGBOOK_GATE '

class ShellLink:
    def __init__(self):
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
