"""Machine-bound Windows credential protection; stores no students or session records."""
import argparse
import base64
import json
import os
from pathlib import Path
import sys

def dpapi(value, decrypt=False):
    if sys.platform != 'win32':
        raise RuntimeError('Windows-protected credentials can be opened only on their provisioned Windows PC')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    result=Blob()
    crypto=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        success=crypto.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result))
    else:
        success=crypto.CryptProtectData(ctypes.byref(source),None,None,None,None,5,ctypes.byref(result)) # UI forbidden + local machine.
    if not success:
        raise RuntimeError('Machine credential could not be opened/protected on this PC')
    try:
        return ctypes.string_at(result.data,result.size)
    finally:
        kernel.LocalFree(result.data)

def protect_config(path):
    path=Path(path)
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    if 'machine_token_dpapi' in config:
        dpapi(base64.b64decode(config['machine_token_dpapi'],validate=True),decrypt=True)
        return
    token=config.get('machine_token')
    if not isinstance(token,str) or not token:
        raise ValueError('Missing machine token')
    config['machine_token_dpapi']=base64.b64encode(dpapi(token.encode())).decode()
    del config['machine_token']
    temporary=path.with_name(path.name+'.protected.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as output:
            json.dump(config,output,indent=2)
        os.replace(temporary,path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

def load_config(path):
    path=Path(path)
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    if sys.platform == 'win32' and config.get('protect_machine_token',True) and 'machine_token' in config:
        protect_config(path)
        config=json.loads(path.read_text(encoding='utf-8-sig'))
    if 'machine_token_dpapi' in config:
        config['machine_token']=dpapi(base64.b64decode(config['machine_token_dpapi'],validate=True),decrypt=True).decode()
    if config.get('ca_bundle'):
        # Existing packages specify config/lan-ca.pem relative to the package root.
        ca=Path(config['ca_bundle'])
        if not ca.is_absolute():
            config['ca_bundle']=str((path.resolve().parent.parent/ca).resolve())
    return config

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--protect',required=True)
    args=parser.parse_args()
    protect_config(args.protect)
    print('Machine credential protected. No token printed.')

if __name__=='__main__':
    main()
