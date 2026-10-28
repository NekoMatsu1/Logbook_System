"""Warning-only UI on the work desktop; never performs power/session operations."""
import argparse
import time
import tkinter as tk
from tkinter import ttk

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=int,required=True)
    parser.add_argument('--simulation',action='store_true')
    args=parser.parse_args()
    root=tk.Tk()
    root.title('Laboratory inactivity warning')
    root.attributes('-topmost',True)
    root.protocol('WM_DELETE_WINDOW',lambda:None)
    text=tk.StringVar()
    ttk.Label(root,textvariable=text,padding=30,wraplength=480,font=('',14)).pack()
    deadline=time.monotonic()+args.seconds
    def tick():
        import math
        seconds=max(0,math.ceil(deadline-time.monotonic()))
        text.set(('SIMULATION\n' if args.simulation else '')+f'Are you still working?\nAutomatic sign-out in {seconds} seconds may close applications and lose unsaved work.\nUse the keyboard or mouse to cancel.')
        root.after(200,tick)
    tick()
    root.mainloop()

if __name__=='__main__':
    main()
