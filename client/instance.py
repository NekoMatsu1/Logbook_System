"""One interactive agent/helper per OS machine; contains no student data."""
import os
import socket
import sys

def acquire(role='desktop'):
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel.CreateMutexW(None,False,'Global\\LabLogbook-' + role)
        if not handle or ctypes.get_last_error() == 183:
            raise RuntimeError(f'Another {role} agent is already running')
        return handle
    lock = socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    try:
        lock.bind('\0lab-logbook-' + role)
    except OSError as error:
        raise RuntimeError(f'Another {role} agent is already running') from error
    return lock
