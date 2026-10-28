"""Passwordless admin identity: Google authorization-code flow + server-side sessions."""
import base64
import hashlib
import hmac
import secrets
import time
import threading
from collections import OrderedDict
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import abort, g, jsonify, redirect, render_template, request, session

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def verify_google_token(token, audience, access_token=None):
    from jose import jwt
    response = requests.get('https://www.googleapis.com/oauth2/v3/certs',timeout=(3,5),allow_redirects=False)
    response.raise_for_status()
    claims = jwt.decode(token,response.json(),algorithms=['RS256'],audience=audience,
                      issuer=['accounts.google.com','https://accounts.google.com'],access_token=access_token,
                      options={'require_exp':True,'require_iat':True,'require_sub':True,'require_aud':True,
                               'require_iss':True,'leeway':30})
    if int(claims['iat']) > time.time()+30 or claims.get('azp',audience) != audience:
        raise ValueError('Unexpected token issue time or authorized party')
    return claims

def install_admin_auth(app):
    mode = app.config['ADMIN_AUTH_MODE']
    attempts=OrderedDict()
    attempts_lock=threading.Lock()
    if mode not in ('local', 'google'):
        raise RuntimeError('ADMIN_AUTH_MODE must be local or google')
    if mode == 'google':
        required = ('GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REDIRECT_URI','ADMIN_EMAIL')
        if any(not app.config.get(key) for key in required):
            raise RuntimeError('Google admin access requires client credentials, HTTPS redirect URI, and your exact admin email')
        if not app.config['GOOGLE_REDIRECT_URI'].startswith('https://'):
            raise RuntimeError('Google administrator callback must use HTTPS')
        if not app.config['SESSION_COOKIE_SECURE']:
            raise RuntimeError('Google administrator access requires Secure cookies')
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # OIDC returns through a cross-site top-level GET.

    def now():
        return app.config['NOW']().timestamp()

    def audit(kind, detail):
        g.db.execute('INSERT INTO events(time,kind,detail) VALUES(?,?,?)',
                     (app.config['NOW']().isoformat(),kind,detail))

    def authorized():
        token = session.get('admin_session')
        if not isinstance(token, str):
            return False
        row = g.db.execute('SELECT s.subject FROM admin_sessions s JOIN admin_identities i ON i.subject=s.subject '
                           'WHERE s.token_hash=? AND s.expires_at>? AND i.email=?',
                           (digest(token),now(),app.config['ADMIN_EMAIL'].lower())).fetchone()
        return row is not None

    def network_allowed():
        return not (app.config['ADMIN_DIRECT_ONLY'] and request.environ.get('logbook.from_proxy')) and request.remote_addr in app.config['ADMIN_ADDRESSES']

    @app.get('/auth/login')
    def login():
        if request.headers.get('Authorization') or request.headers.get('X-Computer-ID'):
            abort(403)
        if mode != 'google':
            abort(404)
        if not request.is_secure:
            abort(403)
        with attempts_lock:
            stamp=time.monotonic()
            address=request.remote_addr
            recent=[value for value in attempts.pop(address,[]) if stamp-value<60]
            if len(recent)>=10:
                attempts[address]=recent
                abort(429,'Too many sign-in attempts; wait one minute')
            attempts[address]=recent+[stamp]
            while len(attempts)>2048:
                attempts.popitem(last=False)
        state, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(3))
        browser = session.setdefault('oidc_browser',secrets.token_urlsafe(48))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        with g.db:
            g.db.execute('DELETE FROM oauth_states WHERE expires_at<=?',(now(),))
            g.db.execute('DELETE FROM oauth_states WHERE browser_hash=?',(digest(browser),))
            g.db.execute('INSERT INTO oauth_states VALUES(?,?,?,?,?)',(digest(state),digest(browser),nonce,verifier,now()+600))
        parameters = dict(client_id=app.config['GOOGLE_CLIENT_ID'],redirect_uri=app.config['GOOGLE_REDIRECT_URI'],
                          response_type='code',scope='openid email',state=state,nonce=nonce,
                          code_challenge=challenge,code_challenge_method='S256',prompt='select_account')
        return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(parameters))

    @app.get('/auth/callback')
    def callback():
        if mode != 'google' or not request.is_secure:
            abort(403)
        if request.headers.get('Authorization') or request.headers.get('X-Computer-ID'):
            abort(403)
        state, browser = request.args.get('state',''), session.get('oidc_browser','')
        code = request.args.get('code','')
        if not state or not browser or not code or len(code)>4096 or len(state)>256:
            abort(400,'Invalid authorization response; start sign-in again')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            row = g.db.execute('SELECT * FROM oauth_states WHERE state_hash=? AND browser_hash=? AND expires_at>?',
                               (digest(state),digest(browser),now())).fetchone()
            if not row:
                abort(403,'Sign-in expired or state mismatch')
            g.db.execute('DELETE FROM oauth_states WHERE state_hash=?',(digest(state),))
        try:
            response = app.config.get('OAUTH_EXCHANGE',requests.post)(
                'https://oauth2.googleapis.com/token',
                data=dict(code=code,client_id=app.config['GOOGLE_CLIENT_ID'],client_secret=app.config['GOOGLE_CLIENT_SECRET'],
                          redirect_uri=app.config['GOOGLE_REDIRECT_URI'],grant_type='authorization_code',code_verifier=row['verifier']),
                timeout=(3,5),allow_redirects=False)
            response.raise_for_status()
            tokens = response.json()
            claims = app.config.get('VERIFY_GOOGLE_TOKEN',verify_google_token)(tokens['id_token'],app.config['GOOGLE_CLIENT_ID'],tokens.get('access_token'))
        except Exception:
            app.logger.warning('Google sign-in exchange/verification failed; no credentials logged')
            abort(403,'Identity could not be verified; start sign-in again')
        email = claims.get('email','').lower()
        subject = claims.get('sub')
        if not isinstance(subject,str) or not subject or email != app.config['ADMIN_EMAIL'].lower() or claims.get('email_verified') is not True:
            abort(403,'This Google account is not the configured administrator')
        if not hmac.compare_digest(str(claims.get('nonce','')),row['nonce']):
            abort(403,'Identity nonce mismatch')
        # Google is authoritative for Gmail and Workspace domains. Pin subject on first verified login.
        if not email.endswith('@gmail.com') and not claims.get('hd'):
            abort(403,'Use a Gmail or managed Google Workspace administrator identity')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            identity = g.db.execute('SELECT subject FROM admin_identities WHERE email=?',(email,)).fetchone()
            if identity and identity['subject'] != subject:
                abort(403,'Administrator identity changed; server-side recovery is required')
            g.db.execute('INSERT OR IGNORE INTO admin_identities VALUES(?,?)',(email,subject))
            token = secrets.token_urlsafe(48)
            g.db.execute('DELETE FROM admin_sessions WHERE expires_at<=?',(now(),))
            g.db.execute('INSERT INTO admin_sessions VALUES(?,?,?)',(digest(token),subject,now()+3600))
            audit('admin_signin',email)
        session.clear()
        session.update(admin_session=token,csrf=secrets.token_hex(32))
        return redirect('/admin/overview')

    @app.get('/auth/status')
    def status():
        # No identity/email/session information exposed.
        return jsonify(authenticated=authorized() if mode == 'google' else network_allowed())

    def admin(fn):
        @wraps(fn)
        def guarded(*args,**kwargs):
            if request.headers.get('Authorization') or request.headers.get('X-Computer-ID'):
                abort(403,'Machine credentials cannot access administrator routes')
            if mode == 'google':
                if not request.is_secure:
                    abort(403)
                if not authorized():
                    if request.method == 'GET' and request.path != '/admin/export.csv':
                        return render_template('admin_login.html'),401
                    abort(403,'Administrator sign-in required')
            elif not network_allowed():
                abort(403,'Administrator access requires the designated private connection')
            # An authenticated Google callback may redirect through a cross-site GET chain.
            # Read-only HTML navigation remains same-origin readable only; writes/exports stay blocked.
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' and (
                mode != 'google' or request.method != 'GET' or request.path == '/admin/export.csv'
            ):
                abort(403,'Cross-site administrator requests are forbidden')
            if request.method != 'GET':
                from urllib.parse import urlsplit
                origin = request.headers.get('Origin')
                if origin:
                    try:
                        parsed = urlsplit(origin)
                    except ValueError:
                        abort(403)
                    if (parsed.scheme,parsed.netloc) != (request.scheme,request.host):
                        abort(403,'Administrator origin mismatch')
                expected, supplied = session.get('csrf',''), request.headers.get('X-CSRF-Token') or request.form.get('csrf','')
                if not expected or not hmac.compare_digest(expected,supplied):
                    abort(403,'Invalid CSRF token; reload dashboard')
            return fn(*args,**kwargs)
        return guarded

    @app.post('/auth/logout')
    @admin
    def logout():
        token = session.get('admin_session','')
        with g.db:
            g.db.execute('DELETE FROM admin_sessions WHERE token_hash=?',(digest(token),))
            audit('admin_signout','Administrator browser session revoked')
        session.clear()
        return redirect('/admin/overview')

    return admin
