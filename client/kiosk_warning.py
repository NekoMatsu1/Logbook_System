"""Warning-only UI on the work desktop; never performs power/session operations."""
import argparse
import sys
import time
import tkinter as tk
from tkinter import ttk

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=int,required=True)
    parser.add_argument('--simulation',action='store_true')
    parser.add_argument('--confirmation-token',required=True)
    args=parser.parse_args(argv)
    from .gate import _attach_windows_pipes
    _attach_windows_pipes(('stdout',))
    root=tk.Tk()
    from .theme import install
    install(root)
    root.title('Laboratory inactivity warning')
    root.attributes('-topmost',True)
    root.protocol('WM_DELETE_WINDOW',lambda:None)
    text=tk.StringVar()
    panel=ttk.Frame(root,padding=28)
    panel.pack(fill='both',expand=True,padx=16,pady=16)
    ttk.Label(panel,text='SESSION CHECK',style='Eyebrow.TLabel').pack(anchor='w')
    ttk.Label(panel,text='Are you still working?',style='Heading.TLabel').pack(anchor='w',pady=(8,14))
    ttk.Label(panel,textvariable=text,wraplength=460).pack(anchor='w')
    deadline=time.monotonic()+args.seconds
    def confirm():
        if time.monotonic() >= deadline:
            return
        print(args.confirmation_token,file=sys.stdout,flush=True)
        button.configure(state='disabled')
    button=ttk.Button(panel,text="Yes, I'm still here",style='Accent.TButton',command=confirm)
    button.pack(fill='x',pady=(20,0))
    def tick():
        import math
        seconds=max(0,math.ceil(deadline-time.monotonic()))
        if seconds == 0:
            button.configure(state='disabled')
        text.set(('Test mode\n' if args.simulation else '')+f'Automatic sign-out in {seconds} seconds may close applications and lose unsaved work.\n\nClick "Yes, I\'m still here" to keep your session.')
        root.after(200,tick)
    tick()
    root.mainloop()

if __name__=='__main__':
    main()
