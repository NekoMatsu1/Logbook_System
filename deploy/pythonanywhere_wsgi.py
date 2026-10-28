"""Import from PythonAnywhere's Web-tab WSGI file, never expose with a local HTTP server.

The provider's Force HTTPS setting is part of the trusted deployment boundary.
Client-supplied forwarding headers are deliberately removed.
"""
import json
from pathlib import Path
from server.app import create_app

def build_application(config_path):
    configuration=json.loads(Path(config_path).read_text(encoding='utf-8'))
    if configuration.pop('PLATFORM_HTTPS_ENFORCED',False) is not True:
        raise RuntimeError('Enable PythonAnywhere Force HTTPS, then explicitly confirm it in the private configuration')
    app=create_app(configuration)
    def application(environ,start_response):
        # Hosted WSGI is reached only through the provider-controlled HTTPS front end.
        # Never infer client identity from arbitrary X-Forwarded-* headers.
        for key in tuple(environ):
            if key.startswith('HTTP_X_FORWARDED_') or key=='HTTP_FORWARDED':
                del environ[key]
        environ['wsgi.url_scheme']='https'
        return app(environ,start_response)
    return application
