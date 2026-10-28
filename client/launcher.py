"""Portable desktop entry point; configuration always lives outside the bundle."""
import argparse
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox


def default_config():
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    return base / 'config' / 'client.json'


def self_test(output):
    """Exercise the bundled Tk, TLS certificates and Windows adapter without power/network actions."""
    import certifi
    import requests
    from .platforms import load
    root = tk.Tk()
    root.withdraw()
    try:
        root.update()
        adapter = load(True)
        adapter.sample()
        assert adapter.simulation is True
        assert Path(certifi.where()).is_file()
        assert requests.Session().verify is True
        Path(output).write_text(json.dumps({'ok': True, 'tk': root.tk.call('info', 'patchlevel'),
                                           'simulation': True}), encoding='utf-8')
    finally:
        root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Laboratory student logbook')
    parser.add_argument('--config', type=Path, help='Private configuration provisioned for this PC')
    parser.add_argument('--self-test', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.self_test:
        self_test(args.self_test)
        return 0
    config = args.config or default_config()
    if not config.is_file() and args.config is None:
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo('Configure this PC',
                                'Select the private client JSON supplied by your laboratory administrator. '
                                'Each PC needs its own configuration. To skip this prompt next time, '
                                'place it in the config folder beside Logbook.exe as client.json.', parent=root)
            selected = filedialog.askopenfilename(parent=root, title='Select this PC\'s configuration',
                                                   filetypes=[('Client configuration', '*.json')])
        finally:
            root.destroy()
        if not selected:
            return 0
        config = Path(selected)
    try:
        from .__main__ import main as desktop_main
        desktop_main(['--config', str(config.resolve())])
    except Exception:
        # Do not expose credentials or private config contents in a startup error.
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showerror('Logbook could not start',
                                 'Check that no other Logbook is running and that this PC has a valid, '
                                 'writable configuration. Windows-protected configurations work only on '
                                 'the PC where they were first opened. Ask your administrator for help.', parent=root)
        finally:
            root.destroy()
        return 1
    return 0
