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
from .theme import install as install_theme, BACKGROUND
from common import valid_student_id, STUDENT_ID_ERROR, valid_student_password, STUDENT_PASSWORD_ERROR

class Desktop:
    def __init__(self, root, config, gate=None):
        self.root, self.config = root, config
        install_theme(root)
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
        self.stage = 'id'
        self.sid = tk.StringVar()
        self.password, self.password_confirm = tk.StringVar(), tk.StringVar()
        self.identity = tk.StringVar()
        self.id_count = tk.StringVar(value='0/10')
        self.status = tk.StringVar(value='Connecting to central server…')
        root.title('Laboratory student logbook')
        root.geometry('520x680')
        root.minsize(480,630)
        if gate and not self.adapter.simulation:
            root.overrideredirect(True)
            root.geometry(f'{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0')
        frame = ttk.Frame(root, padding=28, style='Card.TFrame')
        frame.pack(fill='both', expand=True,padx=20,pady=20)
        ttk.Label(frame,text='LAB LOGBOOK',style='Eyebrow.TLabel').pack(anchor='w')
        ttk.Label(frame,text=config['computer_id'],style='Title.TLabel').pack(anchor='w',pady=(4,14))
        ttk.Label(frame,text='Test mode: desktop access is not blocked; power actions disabled.' if self.adapter.simulation else 'Managed student access · Live OS operations',style='Notice.TLabel',wraplength=400).pack(fill='x',pady=(0,20))
        self.login_page = ttk.Frame(frame)
        self.password_page = ttk.Frame(frame)
        self.setup_page = ttk.Frame(frame)
        ttk.Label(self.login_page,text='Welcome back',style='Heading.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Label(self.login_page,text='Enter your student ID to begin a session.',style='Muted.TLabel').pack(anchor='w',pady=(0,18))
        ttk.Label(self.login_page,text='Student ID (exactly 10 digits)').pack(anchor='w')
        id_validation = (root.register(lambda value: len(value) <= 10 and (not value or value.isascii() and value.isdigit())), '%P')
        login_id = ttk.Frame(self.login_page,style='Soft.TFrame')
        login_id.pack(fill='x',pady=(8,4))
        self.login_id_entry = ttk.Entry(login_id,textvariable=self.sid,style='Id.TEntry',validate='key',validatecommand=id_validation)
        self.login_id_entry.pack(fill='x')
        self.login_count = ttk.Label(login_id,textvariable=self.id_count,style='IdCount.TLabel')
        self.login_count.place(relx=1,rely=.5,x=-14,anchor='e')
        ttk.Label(self.login_page,text='Your account is created by the administrator.',style='Muted.TLabel').pack(anchor='w',pady=(10,0))

        ttk.Label(self.password_page,text='Enter your password',style='Heading.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Label(self.password_page,textvariable=self.identity,style='Muted.TLabel').pack(anchor='w',pady=(0,18))
        ttk.Label(self.password_page,text='Password').pack(anchor='w')
        self.password_entry = ttk.Entry(self.password_page,textvariable=self.password,show='•')
        self.password_entry.pack(fill='x',pady=(8,6))
        ttk.Button(self.password_page,text='Use a different student ID',style='Link.TButton',command=self.reset_identification).pack(anchor='w',pady=(6,0))

        ttk.Label(self.setup_page,text='Create your password',style='Heading.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Label(self.setup_page,textvariable=self.identity,style='Muted.TLabel').pack(anchor='w',pady=(0,14))
        ttk.Label(self.setup_page,text='Use 10-128 characters with at least one letter and number.',style='SmallMuted.TLabel',wraplength=400).pack(anchor='w',pady=(0,12))
        ttk.Label(self.setup_page,text='New password').pack(anchor='w')
        self.setup_password_entry = ttk.Entry(self.setup_page,textvariable=self.password,show='•')
        self.setup_password_entry.pack(fill='x',pady=(8,12))
        ttk.Label(self.setup_page,text='Confirm password').pack(anchor='w')
        self.confirm_entry = ttk.Entry(self.setup_page,textvariable=self.password_confirm,show='•')
        self.confirm_entry.pack(fill='x',pady=(8,6))
        ttk.Button(self.setup_page,text='Use a different student ID',style='Link.TButton',command=self.reset_identification).pack(anchor='w',pady=(6,0))
        self.page_host = frame
        for entry in (self.login_id_entry,self.password_entry,self.setup_password_entry,self.confirm_entry):
            entry.bind('<KeyPress>',lambda event:self.begin())
        actions = ttk.Frame(frame)
        actions.pack(fill='x',pady=12)
        self.submit = ttk.Button(actions,text='Continue',style='Accent.TButton',command=self.identify)
        self.submit.pack(fill='x')
        self.page_anchor = actions
        self.sid.trace_add('write',self.update_student_id_state)
        self.password.trace_add('write',self.update_student_id_state)
        self.password_confirm.trace_add('write',self.update_student_id_state)
        self.show_identification_page('id')
        self.update_student_id_state()
        ttk.Separator(frame).pack(fill='x',pady=(8,14))
        ttk.Label(frame,textvariable=self.status,wraplength=500,style='Muted.TLabel').pack(anchor='w',pady=8)
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

    def update_student_id_state(self, *_):
        sid = self.sid.get()
        if self.stage == 'id':
            valid = valid_student_id(sid)
        elif self.stage == 'password':
            valid = bool(self.password.get())
        else:
            valid = (valid_student_password(self.password.get())
                     and self.password.get() == self.password_confirm.get())
        self.id_count.set(f'{len(sid)}/10')
        unavailable = self.busy or self.pending_start or self.session_id
        self.submit.state(('!disabled',) if valid and not unavailable else ('disabled',))
        style = 'IdCountDone.TLabel' if valid else 'IdCount.TLabel'
        self.login_count.configure(style=style)

    def show_identification_page(self, stage='id'):
        self.stage = stage
        for candidate in (self.login_page, self.password_page, self.setup_page):
            candidate.pack_forget()
        page = {'id':self.login_page, 'password':self.password_page, 'setup':self.setup_page}[stage]
        page.pack(fill='x',before=self.page_anchor)
        self.id_entry = self.login_id_entry
        self.submit.configure(text={'id':'Continue', 'password':'Sign in', 'setup':'Create password and sign in'}[stage])
        self.root.title('Laboratory student login')
        (self.login_id_entry if stage == 'id' else self.password_entry).focus_set()
        self.update_student_id_state()

    def reset_identification(self):
        if self.busy or self.pending_start:
            return
        self.sid.set('')
        self.password.set('')
        self.password_confirm.set('')
        self.identity.set('')
        self.show_identification_page('id')
        self.status.set('Enter your administrator-issued student ID.')

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
        self.reset_identification()
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
        if not valid_student_id(sid):
            self.status.set(STUDENT_ID_ERROR)
            messagebox.showerror('Invalid student ID', STUDENT_ID_ERROR, parent=self.root)
            self.id_entry.focus_set()
            return
        if self.stage == 'id':
            def found(result):
                if not self.timers.identifying:
                    self.status.set('Identification expired; continue again.')
                    return
                self.identity.set(f'Student ID · {result["student_id"]}')
                self.password.set('')
                self.password_confirm.set('')
                stage = 'setup' if result['setup_required'] else 'password'
                self.show_identification_page(stage)
                self.status.set('Create your private password.' if stage == 'setup' else 'Enter your password.')
            self.job(lambda:self.api.lookup(sid),found)
            return
        password = self.password.get()
        if self.stage == 'setup':
            if not valid_student_password(password):
                messagebox.showerror('Invalid password', STUDENT_PASSWORD_ERROR, parent=self.root)
                return
            if password != self.password_confirm.get():
                messagebox.showerror('Passwords do not match','Enter the same password in both fields.',parent=self.root)
                return
        path = '/api/student-auth/setup' if self.stage == 'setup' else '/api/student-auth/login'
        attempted_stage = self.stage
        def authenticated(result):
            self.password.set('')
            self.password_confirm.set('')
            self.pending_start = dict(student_id=sid,run_id=self.run_id,session_id=str(uuid.uuid4()),
                                      student_auth_token=result['student_auth_token'])
            self.timers.blocked = True
            self.start_request()
        def rejected(error):
            self.status.set(str(error))
            self.password.set('')
            self.password_confirm.set('')
            messagebox.showerror('Sign in failed',str(error),parent=self.root)
            (self.setup_password_entry if attempted_stage == 'setup' else self.password_entry).focus_set()
        self.job(lambda:self.api.call('POST',path,dict(student_id=sid,password=password)),authenticated,rejected)

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
                self.status.set('Server connected.')
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
            if result.get('session_revoked') and self.session_id:
                self.status.set('Your account was deactivated by the administrator. Ending this session.')
                self.end_session('admin_deactivated')
                return
            if not self.session_id:
                self.status.set('Server connected. Register or enter your student ID.' if self.monitor_ok else 'Activity monitoring unavailable; sessions disabled.')
            else:
                self.status.set('Server connected.')
        self.job(heartbeat_work,received)

    def show_session_window(self):
        if self.session_window is None:
            self.session_window = tk.Toplevel(self.root)
            self.session_window.title('Laboratory session status')
            self.session_window.configure(background=BACKGROUND)
            self.session_window.geometry('480x430')
            self.session_window.minsize(440,390)
            panel=ttk.Frame(self.session_window,padding=28,style='Card.TFrame')
            panel.pack(fill='both',expand=True,padx=20,pady=20)
            ttk.Label(panel,text='SESSION ACTIVE',style='Eyebrow.TLabel').pack(anchor='w')
            ttk.Label(panel,text="You're signed in",style='Heading.TLabel').pack(anchor='w',pady=(6,14))
            identity=ttk.Frame(panel,padding=(16,12),style='Soft.TFrame')
            identity.pack(fill='x',pady=(0,12))
            details=ttk.Frame(identity,style='Soft.TFrame')
            details.pack(side='left',fill='x',expand=True)
            ttk.Label(details,text=self.student_name or 'Student',style='IdentityName.TLabel').pack(anchor='w')
            ttk.Label(details,text=self.config['computer_id'],style='IdentityMeta.TLabel').pack(anchor='w',pady=(2,0))
            ttk.Label(identity,text='Simulation' if self.adapter.simulation else 'Live',style='Chip.TLabel').pack(side='right',padx=(12,0))
            connection=ttk.Frame(panel)
            connection.pack(fill='x',pady=(0,18))
            ttk.Label(connection,text='●',style='StatusDot.TLabel').pack(side='left',padx=(0,8))
            ttk.Label(connection,textvariable=self.status,wraplength=350,style='SmallMuted.TLabel').pack(side='left',fill='x',expand=True)
            self.logout_button = ttk.Button(panel,text='Log out',style='Accent.TButton',command=self.manual_logout)
            self.logout_button.pack(fill='x',pady=(0,16))
            ttk.Label(panel,text='•  Save your work before ending your session.\n•  Closing this window minimizes it. Reopen it from the taskbar.',
                      style='SmallMuted.TLabel',wraplength=385,justify='left').pack(anchor='w')
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
            self.reset_identification()
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
                self.warning.configure(background=BACKGROUND)
                self.warning.attributes('-topmost',True)
                self.warning.protocol('WM_DELETE_WINDOW',lambda:None)
                panel=ttk.Frame(self.warning,padding=28)
                panel.pack(fill='both',expand=True,padx=16,pady=16)
                ttk.Label(panel,text='PLEASE CONFIRM',style='Eyebrow.TLabel').pack(anchor='w',pady=(0,12))
                ttk.Label(panel,textvariable=self.warning_text,wraplength=460).pack(anchor='w')
                self.presence_button=ttk.Button(panel,text="Yes, I'm still here",style='Accent.TButton',command=self.confirm_presence)
                self.presence_button.pack(fill='x',pady=(20,0))
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
                    if self.adapter.simulation:
                        self.show_session_window()
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
            self.reset_identification()
            self.root.focus_set()
            self.status.set('Identification timed out; remaining shutdown wait resumed.')
        self.show_warning()
        if not self.busy and not (self.session_id and self.timers.blocked) and time.monotonic() >= self.next_heartbeat:
            self.next_heartbeat = time.monotonic()+10
            if self.pending_start:
                self.start_request()
            else:
                self.heartbeat()
        self.update_student_id_state()
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
    if not args.shell_child:
        from .kiosk import main as kiosk_main
        kiosk_main(['--config', args.config])
        return
    config = load_config(args.config)
    instance_lock = acquire()
    root = root if root is not None else tk.Tk()
    from .gate import ShellLink
    Desktop(root,config,gate=ShellLink())
    root.deiconify()
    root.mainloop()

if __name__ == '__main__':
    main()
