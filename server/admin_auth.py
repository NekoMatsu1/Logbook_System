"""Admin identity with server-side sessions; machine credentials never grant access."""
import base64
import hashlib
import hmac
import secrets
import time
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import abort, g, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash

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
    if mode not in ('local', 'google', 'password'):
        raise RuntimeError('ADMIN_AUTH_MODE must be local, google or password')
    if mode == 'password':
        if not app.config.get('ADMIN_USERNAME') or not app.config.get('ADMIN_PASSWORD_HASH', '').startswith('scrypt:32768:8:1$'):
            raise RuntimeError('Password admin access requires an owner username and a configured scrypt password hash')
        if not app.config['SESSION_COOKIE_SECURE']:
            raise RuntimeError('Password administrator access requires Secure cookies')
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
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
        if mode == 'password':
            return g.db.execute('SELECT 1 FROM admin_sessions WHERE token_hash=? AND subject=? AND expires_at>?',
                                (digest(token), password_subject(), now())).fetchone() is not None
        row = g.db.execute('SELECT s.subject FROM admin_sessions s JOIN admin_identities i ON i.subject=s.subject '
                           'WHERE s.token_hash=? AND s.expires_at>? AND i.email=?',
                           (digest(token),now(),app.config['ADMIN_EMAIL'].lower())).fetchone()
        return row is not None

    def network_allowed():
        return not (app.config['ADMIN_DIRECT_ONLY'] and request.environ.get('logbook.from_proxy')) and request.remote_addr in app.config['ADMIN_ADDRESSES']

    def password_subject():
        # Rotating either credential invalidates every previous password session.
        return 'password:' + digest(app.config['ADMIN_USERNAME']+'\0'+app.config['ADMIN_PASSWORD_HASH'])

    def login_page(error=None):
        session.setdefault('login_csrf', secrets.token_hex(32))
        return render_template('admin_login.html', error=error)

    def throttle():
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            stamp = now()
            address = digest(request.remote_addr or '')
            g.db.execute('DELETE FROM admin_login_attempts WHERE time<=?', (stamp-60,))
            count = g.db.execute('SELECT COUNT(*) FROM admin_login_attempts WHERE address_hash=?',
                                 (address,)).fetchone()[0]
            if count >= 10:
                abort(429,'Too many sign-in attempts; wait one minute')
            g.db.execute('INSERT INTO admin_login_attempts VALUES(?,?)', (address, stamp))

    @app.route('/auth/login', methods=['GET', 'POST'])
    def login():
        if request.headers.get('Authorization') or request.headers.get('X-Computer-ID'):
            abort(403)
        if mode not in ('google', 'password'):
            abort(404)
        if not request.is_secure:
            abort(403)
        if mode == 'password':
            if request.method == 'GET':
                return login_page()
            from urllib.parse import urlsplit
            origin = request.headers.get('Origin')
            if origin:
                try:
                    parsed = urlsplit(origin)
                except ValueError:
                    abort(403)
                if (parsed.scheme, parsed.netloc) != (request.scheme, request.host):
                    abort(403)
            expected, supplied = session.get('login_csrf', ''), request.form.get('csrf', '')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                abort(403,'Sign-in form expired; reload it')
            throttle()
            username, password = request.form.get('username',''), request.form.get('password','')
            if len(username)>128 or len(password)>1024:
                return login_page('Username or password is incorrect.'), 401
            valid = check_password_hash(app.config['ADMIN_PASSWORD_HASH'], password)
            if not (hmac.compare_digest(username.encode(), app.config['ADMIN_USERNAME'].encode()) and valid):
                return login_page('Username or password is incorrect.'), 401
            token = secrets.token_urlsafe(48)
            with g.db:
                g.db.execute('DELETE FROM admin_sessions WHERE expires_at<=?', (now(),))
                g.db.execute('INSERT INTO admin_sessions VALUES(?,?,?)', (digest(token), password_subject(), now()+3600))
                audit('admin_signin','Password administrator signed in')
            session.clear()
            session.update(admin_session=token,csrf=secrets.token_hex(32))
            return redirect('/admin/overview')
        if request.method != 'GET':
            abort(405)
        throttle()
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
        return jsonify(authenticated=authorized() if mode in ('google','password') else network_allowed())

    def admin(fn):
        @wraps(fn)
        def guarded(*args,**kwargs):
            if request.headers.get('Authorization') or request.headers.get('X-Computer-ID'):
                abort(403,'Machine credentials cannot access administrator routes')
            if mode in ('google','password'):
                if not request.is_secure:
                    abort(403)
                if not authorized():
                    if request.method == 'GET' and request.path != '/admin/export.csv':
                        return login_page(),401
                    abort(403,'Administrator sign-in required')
            elif not network_allowed():
                abort(403,'Administrator access requires the designated private connection')
            # An authenticated Google callback may redirect through a cross-site GET chain.
            # Read-only HTML navigation remains same-origin readable only; writes/exports stay blocked.
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' and (
                mode not in ('google','password') or request.method != 'GET' or request.path == '/admin/export.csv'
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
