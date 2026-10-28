import hashlib
import base64
import time
from urllib.parse import urlsplit, parse_qs
import pytest
import rsa
from jose import jwt
from jose.exceptions import JWTError
from server.app import create_app
from server.db import connect
from server.admin_auth import verify_google_token

@pytest.fixture(scope='module')
def rsa_pair():
    return rsa.newkeys(2048)

def jwks(public):
    def encode(value):
        return base64.urlsafe_b64encode(value.to_bytes((value.bit_length()+7)//8,'big')).rstrip(b'=').decode()
    return {'keys':[dict(kty='RSA',kid='test-key',alg='RS256',use='sig',n=encode(public.n),e=encode(public.e))]}

@pytest.fixture
def google_app(app,rsa_pair,monkeypatch):
    public, private = rsa_pair
    pending={}
    def claims():
        return dict(iss='https://accounts.google.com',aud='test-client',sub='owner-subject',
                    iat=int(time.time()),exp=int(time.time())+300,email='owner@gmail.com',email_verified=True,nonce=pending['nonce'])
    class Response:
        def __init__(self,data): self.data=data
        def raise_for_status(self): pass
        def json(self): return self.data
    def exchange(url,data,**kwargs):
        assert data['code_verifier']
        assert data['client_secret']=='test-client-secret'
        return Response({'id_token':jwt.encode(claims(),private.save_pkcs1(),algorithm='RS256')})
    def certificates(*args,**kwargs):
        return Response(jwks(public))
    monkeypatch.setattr('server.admin_auth.requests.get',certificates)
    configured=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,NOW=app.config['NOW'],
                               ADMIN_AUTH_MODE='google',GOOGLE_CLIENT_ID='test-client',GOOGLE_CLIENT_SECRET='test-client-secret',
                               GOOGLE_REDIRECT_URI='https://localhost/auth/callback',ADMIN_EMAIL='owner@gmail.com',
                               SESSION_COOKIE_SECURE=True,OAUTH_EXCHANGE=exchange))
    return configured,pending,claims

def begin(client,pending):
    result=client.get('/auth/login',base_url='https://localhost')
    query=parse_qs(urlsplit(result.location).query)
    pending['nonce']=query['nonce'][0]
    assert query['code_challenge_method']==['S256']
    return query['state'][0]

def test_real_signed_identity_and_admin_logout(google_app,clock):
    app,pending,_=google_app
    web=app.test_client()
    assert web.get('/admin/records',base_url='https://localhost').status_code==401
    state=begin(web,pending)
    result=web.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'})
    assert result.status_code==302
    assert 'Secure' in result.headers['Set-Cookie'] and 'HttpOnly' in result.headers['Set-Cookie']
    assert web.get('/admin/records',base_url='https://localhost',environ_overrides={'REMOTE_ADDR':'203.0.113.9'}).status_code==200
    assert web.get('/admin/records',base_url='https://localhost',headers={'Sec-Fetch-Site':'cross-site'}).status_code==200
    assert web.get('/admin/export.csv',base_url='https://localhost',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    with web.session_transaction() as session:
        csrf=session['csrf']
    assert web.post('/auth/logout',base_url='https://localhost',headers={'X-CSRF-Token':csrf}).status_code==302
    assert web.get('/admin/export.csv',base_url='https://localhost').status_code==403
    assert web.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'}).status_code==400

def test_state_browser_binding_and_expiry(google_app,clock):
    app,pending,_=google_app
    first,other=app.test_client(),app.test_client()
    state=begin(first,pending)
    assert other.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'}).status_code==400
    assert first.get('/auth/callback',base_url='https://localhost',query_string={'state':'wrong','code':'code'}).status_code==403
    clock.advance(601)
    assert first.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'}).status_code==403

@pytest.mark.parametrize('change',[
    {'email':'student@gmail.com'}, {'email_verified':False}, {'nonce':'wrong'}, {'sub':''},
])
def test_only_owner_identity_accepted(google_app,change):
    app,pending,claims=google_app
    web=app.test_client()
    state=begin(web,pending)
    app.config['VERIFY_GOOGLE_TOKEN']=lambda *_:claims()|change
    assert web.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'}).status_code==403
    assert web.get('/admin/export.csv',base_url='https://localhost').status_code==403

def test_admin_session_expiry_and_revocation(google_app,clock):
    app,pending,_=google_app
    web=app.test_client()
    state=begin(web,pending)
    web.get('/auth/callback',base_url='https://localhost',query_string={'state':state,'code':'code'})
    assert web.get('/admin/export.csv',base_url='https://localhost').status_code==200
    clock.advance(3601)
    assert web.get('/admin/export.csv',base_url='https://localhost').status_code==403

def test_token_verifier_rejects_bad_signature_audience_issuer_and_expiry(rsa_pair,monkeypatch):
    public,private=rsa_pair
    class Response:
        def raise_for_status(self): pass
        def json(self): return jwks(public)
    monkeypatch.setattr('server.admin_auth.requests.get',lambda *a,**kw:Response())
    claims=dict(iss='https://accounts.google.com',aud='client',sub='subject',iat=int(time.time()),exp=int(time.time())+60)
    encoded=jwt.encode(claims,private.save_pkcs1(),algorithm='RS256')
    assert verify_google_token(encoded,'client')['sub']=='subject'
    for changed in ({'aud':'other'},{'iss':'https://attacker.example'},{'exp':1}):
        token=jwt.encode(claims|changed,private.save_pkcs1(),algorithm='RS256')
        with pytest.raises(JWTError): verify_google_token(token,'client')
    token=jwt.encode(claims,'not-a-google-key',algorithm='HS256')
    with pytest.raises(JWTError): verify_google_token(token,'client')
    head,body,signature=encoded.split('.')
    signature=('A' if signature[0]!='A' else 'B')+signature[1:]
    with pytest.raises(JWTError): verify_google_token('.'.join((head,body,signature)),'client')
    for changed in ({'azp':'attacker-client'},{'iat':int(time.time())+3600}):
        token=jwt.encode(claims|changed,private.save_pkcs1(),algorithm='RS256')
        with pytest.raises(ValueError): verify_google_token(token,'client')

def test_lab_network_guard_and_computer_revocation(app,auth):
    secured=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],LAB_NETWORKS=['192.168.1.0/24'])).test_client()
    assert secured.get('/api/students/unknown',headers=auth,environ_overrides={'REMOTE_ADDR':'127.0.0.1'}).status_code==403
    assert secured.get('/api/students/unknown',base_url='https://localhost',headers=auth,environ_overrides={'REMOTE_ADDR':'192.168.1.10'}).status_code==404
    with connect(app.config['DATABASE']) as db:
        db.execute('UPDATE computers SET enabled=0 WHERE computer_id=?',('LAB-PC-01',))
    assert secured.get('/api/students/unknown',base_url='https://localhost',headers=auth,environ_overrides={'REMOTE_ADDR':'192.168.1.10'}).status_code==401

def test_remote_client_access_uses_machine_credentials_without_network_allowlist(app,auth):
    remote=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,
                           PRODUCTION=True,ADMIN_DIRECT_ONLY=True,ADMIN_ADDRESSES=['127.0.0.1'],
                           ALLOW_REMOTE_CLIENTS=True)).test_client()
    address={'REMOTE_ADDR':'198.51.100.27'}
    assert remote.get('/api/students/unknown',base_url='https://localhost',
                      headers=auth,environ_overrides=address).status_code==404
    assert remote.get('/api/students/unknown',base_url='https://localhost',
                      headers=auth|{'Authorization':'Bearer invalid'},environ_overrides=address).status_code==401
    restricted=create_app(dict(TESTING=True,DATABASE=app.config['DATABASE'],SECRET_KEY='x'*48,
                               PRODUCTION=True,ADMIN_DIRECT_ONLY=True,ADMIN_ADDRESSES=['127.0.0.1'])).test_client()
    assert restricted.get('/api/students/unknown',base_url='https://localhost',
                          headers=auth,environ_overrides=address).status_code==403
