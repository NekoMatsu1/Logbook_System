"""Import from PythonAnywhere's Web-tab WSGI file, never expose with a local HTTP server.

The provider's Force HTTPS setting is part of the trusted deployment boundary.
Client-supplied forwarding headers are deliberately removed.
"""
import json
import ipaddress
from pathlib import Path
from server.app import create_app

def build_application(config_path):
    configuration=json.loads(Path(config_path).read_text(encoding='utf-8'))
    if configuration.pop('PLATFORM_HTTPS_ENFORCED',False) is not True:
        raise RuntimeError('Enable PythonAnywhere Force HTTPS, then explicitly confirm it in the private configuration')
    configuration['HOSTED_IP_VERIFIED']=True
    app=create_app(configuration)
    def application(environ,start_response):
        # Hosted WSGI is reached only through the provider-controlled HTTPS front end.
        # Only PythonAnywhere's managed gateway may serve this adapter. Its final
        # X-Real-IP item is the peer it saw; earlier items can be caller-supplied.
        try:
            address=ipaddress.ip_address(environ.get('HTTP_X_REAL_IP','').split(',')[-1].strip())
        except ValueError:
            start_response('403 Forbidden',[('Content-Type','text/plain')])
            return [b'Provider client address missing or invalid']
        for key in tuple(environ):
            if key.startswith('HTTP_X_FORWARDED_') or key=='HTTP_FORWARDED':
                del environ[key]
        environ.pop('HTTP_X_REAL_IP',None)
        environ['REMOTE_ADDR']=str(address)
        environ['wsgi.url_scheme']='https'
        return app(environ,start_response)
    return application
