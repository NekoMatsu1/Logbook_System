"""Supervised OS shell: a server-confirmed session is required before desktop access."""
import argparse
import json
import logging
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from .api import API
from .credentials import load_config
from .gate import PREFIX
from .instance import acquire
from .platforms.desktop_gate import load_gate

class Supervisor:
    def __init__(self,api,gate):
        self.api,self.gate=api,gate
        self.run_id=None
        self.requested=None
        self.active=None
        self.warning=None
        self.gate.lock()

    def handle(self,message):
        event=message.get('event')
        if event=='hello':
            self.gate.lock()
            self.active=self.requested=None
            self.run_id=message.get('run_id')
        elif event=='grant' and message.get('run_id')==self.run_id:
            key=message.get('session_id')
            if isinstance(key,str) and key and len(key)<=128:
                self.requested=key
        elif event=='lock':
            self.gate.lock()
            self.active=self.requested=None
            self.warning=None
        elif event=='warning':
            self.warning=message if self.active else None

    def resolve(self):
        if not self.requested:
            return
        key=self.requested
        record=self.api.call('GET','/api/sessions/'+key)
        if record['status']=='active' and record['run_id']==self.run_id:
            if self.active!=key:
                self.gate.unlock()
                self.active=key
            self.requested=None
        else:
            self.requested=None
            self.gate.lock()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='config/client.json')
    args=parser.parse_args()
    config_path=str(Path(args.config).resolve())
    config=load_config(config_path)
    simulation=config.get('simulation',True)
    if type(simulation) is not bool:
        raise ValueError('simulation must be boolean')
    if not simulation and config.get('kiosk_shell_installed') is not True:
        raise RuntimeError('Live kiosk requires deliberate OS shell installation and protected code/config')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    instance_lock=acquire('supervisor')
    gate=load_gate(simulation)
    supervisor=Supervisor(API(config),gate)
    events=queue.Queue()
    child=warning=None
    last_retry=0
    def launch():
        process=subprocess.Popen([sys.executable,'-m','client','--config',config_path,'--shell-child'],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1,**gate.child_options())
        def reader():
            for line in process.stdout:
                if line.startswith(PREFIX):
                    try:
                        item=json.loads(line[len(PREFIX):])
                        if isinstance(item,dict): events.put((process.pid,item))
                    except ValueError:
                        logging.error('Malformed child protocol')
        threading.Thread(target=reader,daemon=True).start()
        return process
    try:
        child=launch()
        while True:
            if gate.session_ended():
                if supervisor.active:
                    try:
                        supervisor.api.call('POST','/api/sessions/'+supervisor.active+'/end',dict(run_id=supervisor.run_id,reason='os_signout'))
                    except Exception:
                        logging.warning('Cinnamon sign-out end was not acknowledged; central end time remains unknown')
                supervisor.handle({'event':'lock'})
                break
            if child.poll() is not None:
                supervisor.handle({'event':'lock'})
                logging.error('Student UI exited; desktop remains locked; restarting')
                time.sleep(1)
                child=launch()
            while not events.empty():
                source,message=events.get_nowait()
                if source==child.pid:
                    supervisor.handle(message)
            if time.monotonic()>=last_retry:
                last_retry=time.monotonic()+2
                try:
                    previous=supervisor.active
                    supervisor.resolve()
                    if supervisor.active and supervisor.active!=previous:
                        child.stdin.write(json.dumps(dict(event='desktop_open',session_id=supervisor.active,run_id=supervisor.run_id))+'\n')
                        child.stdin.flush()
                except Exception:
                    if supervisor.active and supervisor.active!=previous:
                        supervisor.handle({'event':'lock'})
                    logging.warning('Desktop authorization not confirmed; gate remains locked')
            gate.maintain_lock()
            display=supervisor.warning
            if display and display.get('kind')=='logout' and warning is None:
                seconds=display.get('seconds')
                if isinstance(seconds,int) and 0<=seconds<=86400:
                    command=[sys.executable,'-m','client.kiosk_warning','--seconds',str(seconds)]
                    if simulation: command.append('--simulation')
                    warning=subprocess.Popen(command,**gate.warning_options())
            elif (not display or display.get('kind') is None) and warning is not None:
                warning.terminate()
                warning.wait(timeout=5)
                warning=None
            time.sleep(.1)
    finally:
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        if warning and warning.poll() is None:
            warning.terminate()
        gate.close()

if __name__=='__main__':
    main()
