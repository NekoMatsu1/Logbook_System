"""Shared, readable desktop styles for student access and session controls."""
from tkinter import ttk

BACKGROUND = '#EFF4F2'
SURFACE = '#FFFFFF'
INK = '#203D40'
MUTED = '#607778'
TEAL = '#16766F'


def install(root):
    root.configure(background=BACKGROUND)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 11), foreground=INK)
    style.configure('TFrame', background=SURFACE)
    style.configure('TLabel', background=SURFACE, foreground=INK)
    style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'))
    style.configure('Heading.TLabel', font=('Segoe UI', 16, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED, font=('Segoe UI', 10))
    style.configure('Eyebrow.TLabel', foreground=TEAL, font=('Segoe UI', 10, 'bold'))
    style.configure('Notice.TLabel', foreground='#805A1D', background='#FFF3D9', padding=10, font=('Segoe UI', 10))
    style.configure('TEntry', fieldbackground='#F7FAF9', foreground=INK,
                    bordercolor='#CCDAD6', lightcolor='#CCDAD6', darkcolor='#CCDAD6',
                    padding=10, insertcolor=INK)
    style.map('TEntry', bordercolor=[('focus', TEAL)])
    style.configure('TButton', padding=(14, 9), background='#EAF1EE', foreground=TEAL,
                    borderwidth=1, bordercolor='#D3E0DB', font=('Segoe UI', 10, 'bold'))
    style.map('TButton', background=[('active','#DCEBE5'),('disabled','#F1F4F2')],
              foreground=[('disabled','#8D9C98')])
    style.configure('Accent.TButton', background=TEAL, foreground='#FFFFFF', bordercolor=TEAL,
                    padding=(20,11), font=('Segoe UI',11,'bold'))
    style.map('Accent.TButton', background=[('disabled','#C9DAD5'),('active','#105E58')],
              foreground=[('disabled','#647A73'),('!disabled','#FFFFFF')])
    style.configure('Link.TButton', background=SURFACE, foreground=TEAL,
                    borderwidth=0, padding=(0,8))
    style.map('Link.TButton', background=[('active','#F1F7F4')])
    style.configure('TSeparator', background='#DFE8E3')
