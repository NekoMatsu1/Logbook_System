import pytest
from server.app import create_app

def test_security_headers_cover_admin_and_errors(web):
    for path in ('/admin/overview','/admin/export.csv','/does-not-exist'):
        result = web.get(path)
        assert result.headers['X-Frame-Options'] == 'DENY'
        assert result.headers['X-Content-Type-Options'] == 'nosniff'
        assert "frame-ancestors 'none'" in result.headers['Content-Security-Policy']
    assert web.get('/admin/overview').headers['Cache-Control'] == 'no-store'

def test_host_header_rebinding_is_rejected(web):
    assert web.get('/admin/overview',headers={'Host':'attacker.example'}).status_code == 400

def test_cross_site_admin_requests_rejected(web,csrf):
    assert web.get('/admin/overview',headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403
    result=web.post('/admin/settings',headers=csrf|{'Origin':'https://attacker.example'},json=dict(scope='*',values={}))
    assert result.status_code == 403
    assert web.post('/admin/settings',headers=csrf|{'Origin':'http://localhost'},json=dict(scope='*',values={})).status_code == 200
    assert web.post('/admin/settings',headers=csrf|{'Origin':'http://['},json=dict(scope='*',values={})).status_code == 403

def test_proxy_cannot_reach_private_admin_even_with_loopback_address(app):
    private=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,
                            PRODUCTION=True,ADMIN_DIRECT_ONLY=True,TRUSTED_PROXY_ADDRESS='127.0.0.1')).test_client()
    assert private.get('/admin/overview').status_code == 200
    assert private.get('/admin/export.csv',headers={'X-Forwarded-For':'127.0.0.1','X-Forwarded-Proto':'https'}).status_code == 403
    assert private.get('/admin/overview',headers={'X-Forwarded-For':'10.0.0.5','X-Forwarded-Proto':'https'}).status_code == 403

def test_remote_admin_is_limited_to_allowlisted_client_ip(app):
    remote=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,
                           PRODUCTION=True,ADMIN_DIRECT_ONLY=False,ADMIN_ADDRESSES=['198.51.100.42'],
                           TRUSTED_PROXY_ADDRESS='127.0.0.1')).test_client()
    headers={'X-Forwarded-For':'198.51.100.42','X-Forwarded-Proto':'https'}
    assert remote.get('/admin/overview',headers=headers).status_code==200
    assert remote.get('/admin/overview',headers=headers,
                      environ_overrides={'REMOTE_ADDR':'203.0.113.17'}).status_code==403

@pytest.mark.parametrize('changes',[
    {'SECRET_KEY':'short'},
    {'ADMIN_DIRECT_ONLY':False},
    {'ADMIN_ADDRESSES':['10.0.0.5']},
    {'ADMIN_ADDRESSES':[]},
])
def test_production_fails_closed(app,changes):
    config=dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,
                PRODUCTION=True,ADMIN_DIRECT_ONLY=True)
    config.update(changes)
    with pytest.raises(RuntimeError):
        create_app(config)

def test_https_hsts_and_minimal_health(web):
    result=web.get('/healthz',base_url='https://localhost')
    assert result.json=={'status':'ok'}
    assert result.headers['Strict-Transport-Security']=='max-age=31536000'

def test_stored_student_html_is_escaped(web,auth):
    web.post('/api/register',headers=auth,json={'student_id':'0003','name':'<script>alert(1)</script>'})
    result=web.get('/admin/students')
    assert '<script>alert(1)</script>' not in result.text
    assert '&lt;script&gt;' in result.text
