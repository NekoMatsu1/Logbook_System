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


def focus_existing_logbook():
    """Bring the one allowed student window forward when Logbook is already running."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        for title in ('Laboratory student login', 'Laboratory session status'):
            handle = user32.FindWindowW(None, title)
            if handle:
                user32.ShowWindow(handle, 9)  # SW_RESTORE
                user32.SetForegroundWindow(handle)
                return True
    except Exception:
        pass
    return False


def startup_message(error):
    """Return an actionable startup message without exposing config/token contents."""
    detail = str(error)
    if 'Another supervisor agent is already running' in detail:
        return ('Logbook is already running. Its window was not found. Open it from the taskbar. '
                'If it is not there, end Logbook.exe in Task Manager, then open Logbook again.')
    if 'Machine credential could not be opened/protected on this PC' in detail:
        return ('This client configuration belongs to a different PC. Ask the administrator for a new '
                'configuration for this PC. Do not copy client.json from another computer.')
    if isinstance(error, FileNotFoundError):
        return 'The client configuration was not found. Put this PC\'s client.json in the config folder beside Logbook.exe.'
    if isinstance(error, PermissionError):
        return 'Windows cannot read or update this PC\'s client configuration. Move the full Logbook folder to Documents and try again.'
    if isinstance(error, json.JSONDecodeError):
        return 'This PC\'s client configuration is damaged. Ask the administrator for a new configuration file.'
    return ('Logbook could not read this PC\'s configuration. Ask the administrator for a new configuration '
            'for this PC. Do not reuse a configuration from another computer.')


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
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ['--warning']:
        from .kiosk_warning import main as warning_main
        return warning_main(arguments[1:])
    parser = argparse.ArgumentParser(description='Laboratory student logbook')
    parser.add_argument('--config', type=Path, help='Private configuration provisioned for this PC')
    parser.add_argument('--self-test', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--shell-child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--protect-config', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    if args.protect_config:
        from .credentials import protect_config
        try:
            protect_config(args.protect_config)
        except Exception:
            return 1  # Installer receives a failure code; no credential data or dialogs.
        return 0
    if args.self_test:
        self_test(args.self_test)
        return 0
    root = tk.Tk()
    root.withdraw()
    config = args.config or default_config()
    try:
        if not config.is_file() and args.config is None:
            messagebox.showinfo('Configure this PC',
                                'Select the private client JSON supplied by your laboratory administrator. '
                                'Each PC needs its own configuration. To skip this prompt next time, '
                                'place it in the config folder beside Logbook.exe as client.json.', parent=root)
            selected = filedialog.askopenfilename(parent=root, title='Select this PC\'s configuration',
                                                   filetypes=[('Client configuration', '*.json')])
            if not selected:
                return 0
            config = Path(selected)
        config_path = str(config.resolve())
        if args.shell_child:
            from .__main__ import main as desktop_main
            desktop_main(['--config', config_path, '--shell-child'], root=root)
        else:
            root.destroy()
            root = None
            from .kiosk import main as kiosk_main
            kiosk_main(['--config', config_path])
    except Exception as error:
        if 'Another supervisor agent is already running' in str(error) and focus_existing_logbook():
            return 0
        # Do not expose credentials or private config contents in a startup error.
        error_root = root or tk.Tk()
        if root is None:
            error_root.withdraw()
        try:
            messagebox.showerror('Logbook could not start',
                                 startup_message(error),
                                 parent=error_root)
        finally:
            if root is None:
                error_root.destroy()
        return 1
    finally:
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass  # The desktop's Close handler may already have destroyed it.
    return 0
