"""Calm teal desktop styles shared by student access and session controls."""
from tkinter import ttk

BACKGROUND = '#F7F8F6'
SURFACE = '#FFFFFF'
SOFT = '#EEF2F0'
INK = '#14231F'
MUTED = '#5D6B66'
LINE = '#E0E6E3'
TEAL = '#0F6B5C'
TEAL_DARK = '#0B584C'
WARNING = '#8A5A00'
WARNING_BG = '#FFF3D6'
OK_BG = '#DFF1EC'


def install(root):
    root.configure(background=BACKGROUND)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), foreground=INK)
    style.configure('TFrame', background=SURFACE)
    style.configure('Card.TFrame', background=SURFACE, borderwidth=1, relief='solid',
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
    style.configure('Soft.TFrame', background=SOFT, borderwidth=1, relief='solid',
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
    style.configure('TLabel', background=SURFACE, foreground=INK)
    style.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'))
    style.configure('Heading.TLabel', font=('Segoe UI', 16, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED, font=('Segoe UI', 10))
    style.configure('SmallMuted.TLabel', foreground=MUTED, font=('Segoe UI', 9))
    style.configure('Eyebrow.TLabel', foreground=TEAL, font=('Segoe UI', 9, 'bold'))
    style.configure('Notice.TLabel', foreground=WARNING, background=WARNING_BG,
                    padding=(12,10), font=('Segoe UI', 9))
    style.configure('IdCount.TLabel', foreground=MUTED, background=SOFT,
                    font=('Segoe UI', 9, 'bold'))
    style.configure('IdCountDone.TLabel', foreground=TEAL, background=SOFT,
                    font=('Segoe UI', 9, 'bold'))
    style.configure('IdentityName.TLabel', background=SOFT, foreground=INK,
                    font=('Segoe UI', 11, 'bold'))
    style.configure('IdentityMeta.TLabel', background=SOFT, foreground=MUTED,
                    font=('Segoe UI', 9))
    style.configure('Chip.TLabel', background=OK_BG, foreground=TEAL,
                    font=('Segoe UI', 9, 'bold'), padding=(10,4))
    style.configure('StatusDot.TLabel', background=SURFACE, foreground=TEAL,
                    font=('Segoe UI', 8), padding=(0,0))
    style.configure('TEntry', fieldbackground=SOFT, foreground=INK,
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                    padding=(14,11), insertcolor=INK, font=('Segoe UI', 12, 'bold'))
    style.configure('Id.TEntry', padding=(14,11,64,11))
    style.map('TEntry', bordercolor=[('focus', TEAL)], lightcolor=[('focus', TEAL)],
              darkcolor=[('focus', TEAL)])
    style.configure('TButton', padding=(16,10), background=SOFT, foreground=TEAL,
                    borderwidth=1, bordercolor=LINE, font=('Segoe UI', 10, 'bold'))
    style.map('TButton', background=[('active','#E4ECE9'),('disabled','#F1F4F2')],
              foreground=[('disabled','#899793')])
    style.configure('Accent.TButton', background=TEAL, foreground='#FFFFFF',
                    bordercolor=TEAL, padding=(20,12), font=('Segoe UI',10,'bold'))
    style.map('Accent.TButton', background=[('disabled','#A8CAC3'),('active',TEAL_DARK)],
              foreground=[('disabled','#FFFFFF'),('!disabled','#FFFFFF')])
    style.configure('Link.TButton', background=SURFACE, foreground=TEAL,
                    borderwidth=0, padding=(0,8), font=('Segoe UI',9,'bold'))
    style.map('Link.TButton', background=[('active',SURFACE)], foreground=[('active',TEAL_DARK)])
    style.configure('TSeparator', background=LINE)
