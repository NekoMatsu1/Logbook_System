import ipaddress
from pathlib import Path
from urllib.parse import urlparse, quote
import requests

class APIError(Exception):
    pass

class API:
    def __init__(self, config):
        self.url = config['server_url'].rstrip('/')
        parsed = urlparse(self.url)
        try:
            loopback = ipaddress.ip_address(parsed.hostname or '').is_loopback
        except ValueError:
            loopback = parsed.hostname == 'localhost'
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError('Server URL must be an origin without credentials or path')
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback and config.get('allow_loopback_http') is True):
            raise ValueError('HTTPS required except explicitly enabled loopback development')
        self.http = requests.Session()
        self.http.trust_env = False
        ca_bundle = config.get('ca_bundle')
        if ca_bundle is not None:
            if not isinstance(ca_bundle, str) or not ca_bundle or not Path(ca_bundle).is_file():
                raise ValueError('ca_bundle must name an existing CA certificate file; verification cannot be disabled')
            self.http.verify = str(Path(ca_bundle).resolve())
        self.http.headers.update({'Authorization':'Bearer ' + config['machine_token'], 'X-Computer-ID':config['computer_id']})

    def call(self, method, path, data=None):
        try:
            response = self.http.request(method, self.url + path, json=data, timeout=(2, 4), allow_redirects=False)
            if not 200 <= response.status_code < 300:
                try:
                    detail = response.json().get('error', 'Request rejected')
                except ValueError:
                    detail = 'Request rejected'
                raise APIError(f'{response.status_code}: {detail}')
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise APIError('Server connection failed; operation not confirmed') from exc

    def lookup(self, sid):
        return self.call('GET', '/api/students/' + quote(sid, safe=''))
