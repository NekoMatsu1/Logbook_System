import argparse
import json
import logging
import queue
import time
import tkinter as tk
import uuid
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, messagebox

from .api import API, APIError
from .platforms import load
from .state import Timers
from .instance import acquire
from .credentials import load_config

class Desktop:
    def __init__(self, root, config, gate=None):
        self.root, self.config = root, config
        self.gate = gate
        self.api = API(config)
        self.adapter = load(config.get('simulation', True))
        if type(config.get('simulation', True)) is not bool:
            raise ValueError('simulation must be a JSON boolean')
        self.timers = Timers(time.monotonic)
        self.run_id = str(uuid.uuid4())
        self.session_id = None
        self.pending_start = None
        self.pending_end = False
        self.busy = False
        self.connected = False
        self.failure_count = 0
        self.pending_events = []
        self.session_window = None
        self.logout_button = None
        self.student_name = None
        self.next_heartbeat = 0
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.results = queue.Queue()
        self.mode = tk.StringVar(value='login')
        self.sid, self.name = tk.StringVar(), tk.StringVar()
        self.status = tk.StringVar(value='Connecting to central server…')
        root.title('Laboratory student logbook')
        root.geometry('560x450')
        if gate and not self.adapter.simulation:
            root.overrideredirect(True)
            root.geometry(f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0')
        frame = ttk.Frame(root, padding=25)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame,text=config['computer_id'],font=('',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text='SIMULATION — power actions disabled' if self.adapter.simulation else 'LIVE OS OPERATIONS ENABLED',foreground='#a3291c').pack(anchor='w',pady=10)
        ttk.Label(frame,text='Register once, then sign in using your student ID.').pack(anchor='w')
        modes = ttk.Frame(frame)
        modes.pack(anchor='w',pady=8)
        for mode in ('login','register'):
            ttk.Radiobutton(modes,text=mode.capitalize(),variable=self.mode,value=mode,command=self.begin).pack(side='left')
        ttk.Label(frame,text='Student ID (leading zeros preserved)').pack(anchor='w')
        self.id_entry = ttk.Entry(frame,textvariable=self.sid)
        self.id_entry.pack(fill='x',pady=5)
        ttk.Label(frame,text='Full name (registration only)').pack(anchor='w')
        self.name_entry = ttk.Entry(frame,textvariable=self.name)
        self.name_entry.pack(fill='x',pady=5)
        for entry in (self.id_entry,self.name_entry):
            entry.bind('<FocusIn>',lambda event:self.begin())
            entry.bind('<KeyPress>',lambda event:self.begin())
        actions = ttk.Frame(frame)
        actions.pack(anchor='w',pady=12)
        self.submit = ttk.Button(actions,text='Continue',command=self.identify)
        self.submit.pack(side='left')
        ttk.Button(actions,text='Cancel identification',command=self.cancel).pack(side='left',padx=8)
        ttk.Label(frame,textvariable=self.status,wraplength=500).pack(anchor='w',pady=8)
        ttk.Label(frame,text='A shared desktop account requires separate OS policies for access control.',wraplength=500).pack(anchor='w')
        self.warning = None
        self.presence_button = None
        self.warning_text = tk.StringVar()
        root.protocol('WM_DELETE_WINDOW',self.close)
        try:
            supported = self.adapter.attach_signout(root,self.os_signout)
            logging.info('Confirmed external OS sign-out callback: %s', supported)
            self.adapter.sample()
            self.monitor_ok = True
        except Exception as exc:
            self.monitor_ok = False
            self.status.set(f'Global input monitoring unavailable: {exc}. Sessions disabled.')
            logging.error('%s',exc)
        root.after(100,self.tick)
        if self.gate:
            self.gate.hello(self.run_id)

    def job(self, work, success, failure=None):
        if self.busy:
            return False
        self.busy = True
        def run():
            try:
                self.results.put((success,work()))
            except Exception as exc:
                self.results.put((failure or self.failed,exc))
        self.pool.submit(run)
        return True

    def failed(self, error):
        self.connected = False
        self.failure_count += 1
        self.status.set((f'Session continues for {self.student_name}. Cached timers remain active.\n' if self.session_id else '') + str(error))
        logging.warning('Communication/operation failure: %s',error)

    def begin(self):
        if not self.pending_start and not self.session_id:
            self.timers.identify()

    def cancel(self):
        if self.busy or self.pending_start:
            self.status.set('Wait for the current server operation to resolve.')
            return
        self.timers.cancel_identify()
        self.sid.set('')
        self.name.set('')
        self.status.set('Identification cancelled; remaining shutdown wait resumed.')

    def identify(self):
        if self.busy or self.pending_start or self.session_id:
            return
        if self.timers.warning:
            self.status.set('Click "Yes, I\'m still here" on the warning before continuing.')
            return
        if not self.monitor_ok:
            self.status.set('Global desktop activity monitoring is unavailable; cannot start a session.')
            return
        self.begin()
        sid = self.sid.get().strip()
        if not sid or len(sid)>64:
            self.status.set('Enter a student ID of 1–64 characters.')
            return
        if self.mode.get() == 'register':
            name = self.name.get().strip()
            if not name:
                self.status.set('Full name is required for registration.')
                return
            def registered(result):
                self.status.set(f'Registered {result["name"]}. Select Login to start.')
                self.mode.set('login')
            self.job(lambda:self.api.call('POST','/api/register',dict(student_id=sid,name=name)),registered)
        else:
            def found(result):
                if not self.timers.identifying:
                    self.status.set('Identification expired; continue again.')
                    return
                confirmed = messagebox.askyesno('Confirm student',f'{result["name"]}\nStudent ID: {result["student_id"]}\nStart session?',parent=self.root)
                if confirmed and self.timers.identifying:
                    self.pending_start = dict(student_id=sid,run_id=self.run_id,session_id=str(uuid.uuid4()))
                    self.timers.blocked = True
                    self.start_request()
                else:
                    self.cancel()
            self.job(lambda:self.api.lookup(sid),found)

    def start_request(self):
        def started(result):
            self.pending_start = None
            self.timers.blocked = False
            if result['status'] != 'active':
                self.status.set('This request already ended; begin identification again.')
                self.timers.reset()
                return
            self.session_id = result['session_id']
            self.student_name = result['student_name']
            self.timers.start()
            self.connected = True
            logging.info('Session started for %s',result['student_id'])
            if self.gate:
                self.gate.grant(self.session_id,self.run_id)
                self.status.set('Student session saved. Waiting for supervisor authorization before opening the desktop.')
            else:
                self.root.withdraw()
                self.show_session_window()
                self.status.set(f'{self.student_name} · {self.config["computer_id"]}\nServer connected. ' + ('SIMULATION' if self.adapter.simulation else 'LIVE OS OPERATIONS'))
        def failure(error):
            self.failed(error)
            if str(error).startswith(('400:','401:','403:','404:','409:')):
                self.pending_start = None
                self.timers.blocked = False
                self.timers.reset()
            else:
                self.status.set('Start result unknown; retrying the SAME request. Keep this program open.')
                self.next_heartbeat = time.monotonic()+5
        self.job(lambda:self.api.call('POST','/api/sessions',self.pending_start),started,failure)

    def heartbeat(self):
        def heartbeat_work():
            result = self.api.call('POST','/api/heartbeat',dict(run_id=self.run_id,active_session=self.session_id))
            if self.failure_count:
                self.api.call('POST','/api/events',dict(kind='communication_recovered',detail=f'{self.failure_count} failed operations since last report; no local session log retained'))
            for item in list(self.pending_events):
                self.api.call('POST','/api/events',item)
                self.pending_events.remove(item)
            return result
        def received(result):
            self.connected = True
            self.failure_count = 0
            self.timers.configure(result['settings'])
            if not self.session_id:
                self.status.set('Server connected. Register or enter your student ID.' if self.monitor_ok else 'Activity monitoring unavailable; sessions disabled.')
            else:
                self.status.set(f'{self.student_name} · {self.config["computer_id"]}\nServer connected. ' + ('SIMULATION' if self.adapter.simulation else 'LIVE OS OPERATIONS'))
        self.job(heartbeat_work,received)

    def show_session_window(self):
        if self.session_window is None:
            self.session_window = tk.Toplevel(self.root)
            self.session_window.title('Laboratory session status')
            ttk.Label(self.session_window,textvariable=self.status,padding=18,wraplength=400).pack()
            self.logout_button = ttk.Button(self.session_window,text='Log out',command=self.manual_logout)
            self.logout_button.pack(pady=(0,12))
            ttk.Label(self.session_window,text='Closing this window minimizes it. Reopen it from the taskbar.',
                      padding=10,wraplength=400).pack()
            self.session_window.protocol('WM_DELETE_WINDOW',self.session_window.iconify)
        self.session_window.deiconify()
        self.session_window.lift()

    def manual_logout(self):
        if not self.session_id or self.busy or self.pending_end:
            return
        # The modal dialog runs Tk events: pause automatic timer actions while asking.
        self.timers.blocked = True
        try:
            confirmed = messagebox.askyesno('Log out',
                'End your logbook session?' + ('\nSimulation: Windows will stay signed in.'
                if self.adapter.simulation else '\nSave your work first. Windows sign-out will close your applications.'),
                parent=self.session_window or self.root)
        finally:
            self.timers.blocked = False
        if confirmed:
            self.end_session('manual_logout',require_ack=True)

    def end_for_inactivity(self):
        self.end_session('inactivity')

    def end_session(self, reason, require_ack=False):
        if not self.session_id or self.busy or self.pending_end:
            return
        self.pending_end = True
        self.timers.blocked = True
        key = self.session_id
        reason = 'simulated_' + reason if self.adapter.simulation else reason
        def ended(result):
            status = result.get('status')
            finish(status == 'completed', interrupted=status == 'interrupted')
        def failed(error):
            self.failed(error)
            finish(False, error=error)
        def finish(saved, interrupted=False, error=None):
            if require_ack and not (saved or interrupted):
                self.pending_end = False
                self.timers.blocked = False
                detail = str(error)[:250] if error else 'Unexpected session status returned by the server.'
                if detail.startswith('400:') and 'Invalid end reason' in detail:
                    detail = 'The server version is too old for manual logout. Update and reload the hosted server.'
                self.status.set('Log out was not saved. Your session continues. ' + detail + ' Try again.')
                return
            if self.gate:
                self.gate.lock()
            self.session_id = None
            self.student_name = None
            if self.session_window is not None:
                self.session_window.destroy()
                self.session_window = None
                self.logout_button = None
            self.pending_end = False
            self.timers.blocked = False
            self.timers.reset()
            self.root.deiconify()
            self.sid.set('')
            self.name.set('')
            record_status = ('Session ending saved. ' if saved else
                             'Session was already interrupted; its exact end time remains unknown. ' if interrupted else
                             'End NOT saved; central record requires review. ')
            self.status.set(record_status + ('SIMULATED OS sign-out.' if self.adapter.simulation else 'Requesting OS sign-out.'))
            try:
                self.adapter.action('logout')
            except Exception as error:
                self.status.set(f'OS sign-out failed: {error}. Contact administrator.')
                logging.error('OS sign-out failed: %s',error)
                self.pending_events.append(dict(kind='os_operation_failure',detail=f'Logout request failed: {error}'[:1000]))
        self.job(lambda:self.api.call('POST',f'/api/sessions/{key}/end',dict(run_id=self.run_id,reason=reason)),ended,failed)

    def os_signout(self):
        # Only called by confirmed WM_ENDSESSION, never by window close.
        if self.session_id:
            try:
                api = API(self.config)
                api.http.request('POST',api.url+f'/api/sessions/{self.session_id}/end',
                    json=dict(run_id=self.run_id,reason='os_signout'),timeout=(.5,1),allow_redirects=False).raise_for_status()
                logging.info('Confirmed OS sign-out saved')
            except Exception:
                logging.warning('OS sign-out not acknowledged; next run will mark interruption')

    def confirm_presence(self):
        if self.timers.confirm_presence():
            self.show_warning()
            return True
        return False

    def show_warning(self):
        if self.gate:
            self.gate.warning(self.timers.warning if self.timers.active else None,self.timers.countdown())
            if self.timers.active:
                return # Work-desktop warning is owned by the supervisor.
        if self.timers.warning:
            if self.warning is None:
                self.warning = tk.Toplevel(self.root)
                self.warning.title('Laboratory warning')
                self.warning.attributes('-topmost',True)
                self.warning.protocol('WM_DELETE_WINDOW',lambda:None)
                ttk.Label(self.warning,textvariable=self.warning_text,padding=30,wraplength=460,font=('',14)).pack()
                self.presence_button=ttk.Button(self.warning,text="Yes, I'm still here",command=self.confirm_presence)
                self.presence_button.pack(pady=(0,20))
            prefix = 'SIMULATION\n' if self.adapter.simulation else ''
            seconds = self.timers.countdown()
            self.presence_button.configure(state='normal' if seconds>0 else 'disabled')
            text = (f'Are you still working?\nAutomatic sign-out in {seconds} seconds may close applications and lose unsaved work.\nClick "Yes, I\'m still here" to keep your session.' if self.timers.warning=='logout' else
                    f'Shutdown in {seconds} seconds.\nClick "Yes, I\'m still here" to cancel shutdown.')
            self.warning_text.set(prefix+text)
        elif self.warning is not None:
            self.warning.destroy()
            self.warning = None
            self.presence_button = None

    def sample_activity(self):
        """Pause automatic actions on sample failure without changing server settings."""
        try:
            self.timers.activity(**self.adapter.sample())
            self.monitor_ok = True
        except Exception as error:
            self.monitor_ok = False
            self.status.set(f'Global input monitoring failed; automatic actions paused: {error}')
            if self.session_id:
                self.root.deiconify()
        return self.monitor_ok

    def tick(self):
        if self.gate:
            for message in self.gate.poll():
                if (message.get('event')=='confirm_presence' and message.get('session_id')==self.session_id
                        and message.get('run_id')==self.run_id):
                    self.confirm_presence()
                if message.get('event')=='desktop_open' and message.get('session_id')==self.session_id and message.get('run_id')==self.run_id:
                    self.root.withdraw()
        try:
            while True:
                callback,result = self.results.get_nowait()
                self.busy = False
                callback(result)
        except queue.Empty:
            pass
        self.sample_activity()
        # Avoid firing a timer while a network mutation is in progress.
        action = self.timers.tick() if self.monitor_ok and not self.busy else None
        if action == 'logout' and self.session_id:
            self.end_for_inactivity()
        elif action == 'shutdown' and not self.session_id and not self.pending_start:
            self.status.set('SIMULATED shutdown requested.' if self.adapter.simulation else 'OS shutdown requested.')
            logging.warning('%s shutdown', 'SIMULATED' if self.adapter.simulation else 'LIVE')
            self.job(lambda:self.api.call('POST','/api/events',dict(kind='shutdown',detail='simulation' if self.adapter.simulation else 'requested')),lambda _:None)
            try:
                self.adapter.action('shutdown')
            except Exception as error:
                self.status.set(f'Shutdown request failed: {error}')
                self.pending_events.append(dict(kind='os_operation_failure',detail=f'Shutdown request failed: {error}'[:1000]))
        elif action == 'identification_expired':
            self.sid.set('')
            self.name.set('')
            self.root.focus_set()
            self.status.set('Identification timed out; remaining shutdown wait resumed.')
        self.show_warning()
        if not self.busy and not (self.session_id and self.timers.blocked) and time.monotonic() >= self.next_heartbeat:
            self.next_heartbeat = time.monotonic()+10
            if self.pending_start:
                self.start_request()
            else:
                self.heartbeat()
        self.submit.configure(state='disabled' if self.busy or self.pending_start or self.session_id else 'normal')
        if self.logout_button is not None:
            self.logout_button.configure(state='disabled' if self.busy or self.pending_end else 'normal')
        self.root.after(200,self.tick)

    def close(self):
        if self.gate:
            self.status.set('Student identification is required before desktop access.')
            return
        if self.session_id or self.pending_start or self.busy:
            messagebox.showwarning('Agent running','The agent is tracking a session or resolving a server operation. Closing it is not OS sign-out.',parent=self.root)
            return
        self.pool.shutdown(wait=False,cancel_futures=True)
        self.root.destroy()

def main(argv=None, root=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/client.json')
    parser.add_argument('--shell-child',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    config = load_config(args.config)
    instance_lock = acquire()
    root = root if root is not None else tk.Tk()
    if args.shell_child:
        from .gate import ShellLink
        Desktop(root,config,gate=ShellLink())
    else:
        Desktop(root,config)
    root.deiconify()
    root.mainloop()

if __name__ == '__main__':
    main()
