import csv
import hashlib
import hmac
import io
import ipaddress
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session
from .db import connect, initialize
from .admin_auth import install_admin_auth
from common import DEFAULTS

def utcnow():
    return datetime.now(timezone.utc)

def create_app(config=None):
    app = Flask(__name__)
    secret_file = os.getenv('LOGBOOK_SECRET_FILE')
    secret = Path(secret_file).read_text(encoding='utf-8').strip() if secret_file else os.getenv('LOGBOOK_SECRET')
    app.config.update(DATABASE=os.getenv('LOGBOOK_DATABASE', 'data/logbook.sqlite'),
                      ADMIN_ADDRESSES=[address.strip() for address in os.getenv('LOGBOOK_ADMIN_ADDRESSES', '127.0.0.1,::1').split(',')],
                      SECRET_KEY=secret or secrets.token_hex(32),
                      PRODUCTION=os.getenv('LOGBOOK_PRODUCTION', '0') == '1',
                      ADMIN_DIRECT_ONLY=os.getenv('LOGBOOK_ADMIN_DIRECT_ONLY', '0') == '1',
                      ADMIN_AUTH_MODE=os.getenv('LOGBOOK_ADMIN_AUTH_MODE','local'),
                      ADMIN_EMAIL=os.getenv('LOGBOOK_ADMIN_EMAIL',''),
                      GOOGLE_CLIENT_ID=os.getenv('LOGBOOK_GOOGLE_CLIENT_ID',''),
                      GOOGLE_CLIENT_SECRET=os.getenv('LOGBOOK_GOOGLE_CLIENT_SECRET',''),
                      GOOGLE_REDIRECT_URI=os.getenv('LOGBOOK_GOOGLE_REDIRECT_URI',''),
                      ALLOW_REMOTE_CLIENTS=os.getenv('LOGBOOK_ALLOW_REMOTE_CLIENTS','0') == '1',
                      LAB_NETWORKS=[value.strip() for value in os.getenv('LOGBOOK_LAB_NETWORKS','').split(',') if value.strip()],
                      TRUSTED_HOSTS=os.getenv('LOGBOOK_TRUSTED_HOSTS', 'localhost,127.0.0.1,[::1]').split(','),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_SECURE=os.getenv('LOGBOOK_HTTPS', '0') == '1',
                      MAX_CONTENT_LENGTH=16384, NOW=utcnow)
    if config:
        app.config.update(config)
    trusted_proxy = app.config.get('TRUSTED_PROXY_ADDRESS') or os.getenv('LOGBOOK_TRUSTED_PROXY')
    if app.config['PRODUCTION']:
        if not secret and not (config or {}).get('SECRET_KEY'):
            raise RuntimeError('Production requires a persistent external session secret')
        if len(app.config['SECRET_KEY']) < 32:
            raise RuntimeError('Production session secret must contain at least 32 characters')
        if app.config['ADMIN_AUTH_MODE'] == 'local':
            if app.config['ADMIN_DIRECT_ONLY']:
                if not app.config['ADMIN_ADDRESSES'] or any(not ipaddress.ip_address(address).is_loopback for address in app.config['ADMIN_ADDRESSES']):
                    raise RuntimeError('Direct-only administrator addresses must be loopback only')
            elif (not trusted_proxy and not app.config.get('HOSTED_IP_VERIFIED')) or not app.config['ADMIN_ADDRESSES']:
                raise RuntimeError('Remote administrator access requires a trusted proxy and an explicit IP allowlist')
    lab_networks = tuple(ipaddress.ip_network(value) for value in app.config['LAB_NETWORKS'])
    if trusted_proxy:
        original = app.wsgi_app
        proxy = ProxyFix(original, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)
        def selected_proxy(environ, start_response):
            from_proxy = environ.get('REMOTE_ADDR') == trusted_proxy and bool(
                environ.get('HTTP_X_FORWARDED_FOR') or environ.get('HTTP_X_FORWARDED_PROTO'))
            environ['logbook.from_proxy'] = from_proxy
            return (proxy if from_proxy else original)(environ,start_response)
        app.wsgi_app = selected_proxy
    initialize(app.config['DATABASE'])

    @app.before_request
    def database():
        g.db = connect(app.config['DATABASE'])
        try:
            loopback = ipaddress.ip_address(request.remote_addr or '').is_loopback
        except ValueError:
            loopback = False
        if not request.is_secure and not loopback:
            abort(403, 'HTTPS required outside loopback development')

    @app.teardown_request
    def close(_error):
        if 'db' in g:
            g.db.close()

    def now():
        return app.config['NOW']().isoformat()

    @app.after_request
    def security_headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.path.startswith(('/admin', '/api', '/auth')) or request.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.get('/healthz')
    def health():
        g.db.execute('SELECT 1').fetchone()
        return jsonify(status='ok')

    def event(kind, detail, computer=None):
        g.db.execute('INSERT INTO events(time,computer_id,kind,detail) VALUES(?,?,?,?)',
                     (now(), computer, kind, detail))

    admin = install_admin_auth(app)

    def machine(fn):
        @wraps(fn)
        def guarded(*args, **kwargs):
            try:
                address = ipaddress.ip_address(request.remote_addr or '')
            except ValueError:
                abort(403)
            if not app.config['ALLOW_REMOTE_CLIENTS'] and (
                (app.config['PRODUCTION'] and not lab_networks)
                or (lab_networks and not any(address in network for network in lab_networks))
            ):
                abort(403,'Student access is permitted only from the configured laboratory network')
            computer = request.headers.get('X-Computer-ID', '')
            token = request.headers.get('Authorization', '').removeprefix('Bearer ')
            row = g.db.execute('SELECT * FROM computers WHERE computer_id=?', (computer,)).fetchone()
            if not row or not row['enabled'] or not hmac.compare_digest(row['token_hash'], hashlib.sha256(token.encode()).hexdigest()):
                abort(401)
            g.computer = computer
            return fn(*args, **kwargs)
        return guarded

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            abort(400, 'JSON object required')
        return value

    def field(value, key, maximum=128):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or any(ord(c) < 32 for c in text):
            abort(400, f'Invalid {key}')
        text = text.strip()
        if key == 'student_id' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',text):
            abort(400, 'Student ID must use letters, digits, periods, underscores or hyphens')
        return text

    def settings(computer='*'):
        result = DEFAULTS.copy()
        for scope in ('*', computer) if computer != '*' else ('*',):
            row = g.db.execute('SELECT value FROM settings WHERE scope=?', (scope,)).fetchone()
            if row:
                result.update(json.loads(row['value']))
        return result

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    def error(exc):
        return jsonify(error=exc.description), exc.code

    @app.post('/api/register')
    @machine
    def register():
        data = body()
        sid, name = field(data, 'student_id', 64), field(data, 'name')
        try:
            with g.db:
                g.db.execute('INSERT INTO students(student_id,name) VALUES(?,?)', (sid, name))
                event('registration', sid, g.computer)
        except sqlite3.IntegrityError:
            abort(409, 'Student ID already registered')
        return jsonify(student_id=sid, name=name), 201

    @app.get('/api/students/<sid>')
    @machine
    def lookup(sid):
        row = g.db.execute('SELECT student_id,name FROM students WHERE student_id=? AND active=1', (sid,)).fetchone()
        if not row:
            abort(404, 'Unknown or deactivated student ID')
        return jsonify(dict(row))

    @app.post('/api/heartbeat')
    @machine
    def heartbeat():
        data = body()
        run = field(data, 'run_id')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            current = g.db.execute('SELECT run_id FROM computers WHERE computer_id=?',(g.computer,)).fetchone()['run_id']
            seen = g.db.execute('SELECT 1 FROM agent_runs WHERE computer_id=? AND run_id=?',(g.computer,run)).fetchone()
            if seen and current != run:
                abort(409, 'Retired agent run; restart the client')
            g.db.execute('INSERT OR IGNORE INTO agent_runs VALUES(?,?)',(g.computer,run))
            # Network gaps alone never establish logout. A new process run does.
            count = g.db.execute("UPDATE sessions SET status='interrupted',end_reason='agent_restart' "
                                 "WHERE computer_id=? AND status='active' AND run_id<>?", (g.computer, run)).rowcount
            if count:
                event('interruption', 'Agent restarted; end time unknown', g.computer)
            active = data.get('active_session')
            if active is not None and not isinstance(active, str):
                abort(400, 'Invalid active session')
            if active is None:
                count = g.db.execute("UPDATE sessions SET status='interrupted',end_reason='unacknowledged_end' "
                                     "WHERE computer_id=? AND run_id=? AND status='active'", (g.computer, run)).rowcount
                if count:
                    event('interruption', 'Client has no session; end time unknown', g.computer)
            g.db.execute('UPDATE computers SET run_id=?,last_seen=? WHERE computer_id=?', (run, now(), g.computer))
        return jsonify(settings=settings(g.computer))

    @app.post('/api/sessions')
    @machine
    def start():
        data = body()
        sid, run, key = field(data, 'student_id', 64), field(data, 'run_id'), field(data, 'session_id')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            old = g.db.execute('SELECT * FROM sessions WHERE session_id=?', (key,)).fetchone()
            if old:
                if (old['computer_id'], old['student_id'], old['run_id']) != (g.computer, sid, run):
                    abort(409, 'Session request ID already used')
                return jsonify(dict(old))
            pc = g.db.execute('SELECT run_id FROM computers WHERE computer_id=?', (g.computer,)).fetchone()
            if pc['run_id'] != run:
                abort(409, 'Agent run changed; send heartbeat first')
            student = g.db.execute('SELECT * FROM students WHERE student_id=? AND active=1', (sid,)).fetchone()
            if not student:
                abort(404, 'Unknown or deactivated student ID')
            try:
                g.db.execute('INSERT INTO sessions(session_id,student_id,student_name,computer_id,run_id,login_time,status) '
                             "VALUES(?,?,?,?,?,?,'active')", (key, sid, student['name'], g.computer, run, now()))
            except sqlite3.IntegrityError:
                abort(409, 'Computer already has an active session')
            event('login', f'{sid}: {key}', g.computer)
        return jsonify(dict(g.db.execute('SELECT * FROM sessions WHERE session_id=?', (key,)).fetchone())), 201

    @app.post('/api/sessions/<key>/end')
    @machine
    def end(key):
        data = body()
        run, reason = field(data, 'run_id'), field(data, 'reason')
        if reason not in ('inactivity', 'os_signout', 'simulated_inactivity'):
            abort(400, 'Invalid end reason')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            row = g.db.execute('SELECT * FROM sessions WHERE session_id=? AND computer_id=? AND run_id=?',
                               (key, g.computer, run)).fetchone()
            if not row:
                abort(404)
            if row['status'] == 'active':
                stamp = now()
                duration = (datetime.fromisoformat(stamp) - datetime.fromisoformat(row['login_time'])).total_seconds()
                g.db.execute("UPDATE sessions SET status='completed',logout_time=?,duration=?,end_reason=? WHERE session_id=?",
                             (stamp, max(0, duration), reason, key))
                event('logout', f'{key}: {reason}', g.computer)
        return jsonify(dict(g.db.execute('SELECT * FROM sessions WHERE session_id=?', (key,)).fetchone()))

    @app.get('/api/sessions/<key>')
    @machine
    def own_session(key):
        row=g.db.execute('SELECT * FROM sessions WHERE session_id=? AND computer_id=?',(key,g.computer)).fetchone()
        if not row:
            abort(404)
        return jsonify(dict(row))

    @app.post('/api/events')
    @machine
    def client_event():
        data = body()
        with g.db:
            event(field(data, 'kind', 64), field(data, 'detail', 1000), g.computer)
        return jsonify(ok=True)

    @app.post('/api/helper/absent')
    @machine
    def helper_absent():
        # A privileged helper reports OS-level absence, not a missed network heartbeat.
        data = body()
        if data.get('confirmed_no_interactive_session') is not True:
            abort(400, 'OS absence confirmation required')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            changed = g.db.execute("UPDATE sessions SET status='interrupted',end_reason='no_interactive_os_session' "
                                   "WHERE computer_id=? AND status='active'", (g.computer,)).rowcount
            if changed:
                event('interruption', 'Helper confirms no OS session; logout time unknown', g.computer)
            g.db.execute('UPDATE computers SET last_seen=? WHERE computer_id=?', (now(),g.computer))
        return jsonify(settings=settings(g.computer))

    def records():
        query, params = 'SELECT * FROM sessions WHERE 1=1', []
        for arg, column in [('student', 'student_id'), ('computer', 'computer_id')]:
            if request.args.get(arg):
                query += f' AND {column}=?'
                params.append(request.args[arg])
        if request.args.get('date'):
            try:
                day = datetime.strptime(request.args['date'], '%Y-%m-%d').replace(tzinfo=ZoneInfo('Asia/Manila'))
            except ValueError:
                abort(400, 'Invalid date')
            from datetime import timedelta
            query += ' AND login_time>=? AND login_time<?'
            params.extend([day.astimezone(timezone.utc).isoformat(), (day + timedelta(days=1)).astimezone(timezone.utc).isoformat()])
        return [dict(r) for r in g.db.execute(query + ' ORDER BY login_time DESC', params)]

    @app.template_filter('manila')
    def manila(value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Manila')).strftime('%Y-%m-%d %H:%M:%S') if value else 'Unknown'

    @app.get('/')
    @admin
    def home():
        return redirect('/admin/overview')

    @app.get('/admin/<page>')
    @admin
    def dashboard(page):
        if page not in ('overview', 'records', 'students', 'settings', 'events'):
            abort(404)
        session.setdefault('csrf', secrets.token_hex(32))
        pcs = [dict(r) for r in g.db.execute('SELECT * FROM computers')]
        active = [dict(r) for r in g.db.execute("SELECT * FROM sessions WHERE status='active'")]
        for pc in pcs:
            online = pc['last_seen'] and (app.config['NOW']() - datetime.fromisoformat(pc['last_seen'])).total_seconds() < settings(pc['computer_id'])['heartbeat_timeout_seconds']
            pc['status'] = ('in-use' if any(r['computer_id'] == pc['computer_id'] for r in active) else 'available') if online else 'offline'
        return render_template('dashboard.html', page=page, pcs=pcs, active=active,
                               records=records() if page == 'records' else [],
                               students=g.db.execute('SELECT * FROM students ORDER BY student_id').fetchall(),
                               events=g.db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 300').fetchall(),
                               defaults=settings(), keys=DEFAULTS,
                               overrides=[dict(r) for r in g.db.execute("SELECT * FROM settings WHERE scope<>'*'")])

    @app.get('/admin/export.csv')
    @admin
    def export():
        rows = records()
        columns = ['session_id','student_id','student_name','computer_id','login_time','logout_time','duration','end_reason','status']
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            # Neutralize spreadsheet formulas, including leading whitespace/control characters.
            writer.writerow([("'" + str(row[c])) if str(row[c] or '').lstrip().startswith(('=', '+', '-', '@')) else row[c] for c in columns])
        return app.response_class(output.getvalue(), mimetype='text/csv', headers={
            'Content-Disposition': 'attachment; filename="logbook.csv"', 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff'})

    @app.post('/admin/students')
    @admin
    def edit_student():
        data = body()
        sid, name = field(data, 'student_id', 64), field(data, 'name')
        if type(data.get('active', True)) is not bool:
            abort(400, 'Active must be boolean')
        with g.db:
            if data.get('create'):
                try:
                    g.db.execute('INSERT INTO students VALUES(?,?,?)', (sid, name, int(data.get('active', True))))
                except sqlite3.IntegrityError:
                    abort(409, 'Student ID already registered')
            else:
                if not g.db.execute('UPDATE students SET name=?,active=? WHERE student_id=?', (name, int(data.get('active', True)), sid)).rowcount:
                    abort(404)
            event('admin_student_change', sid)
        return jsonify(ok=True)

    @app.post('/admin/settings')
    @admin
    def edit_settings():
        data = body()
        scope = field(data, 'scope')
        values = data.get('values')
        if not isinstance(values, dict) or set(values) - set(DEFAULTS):
            abort(400, 'Unknown settings')
        for key, value in values.items():
            if key.startswith('auto_'):
                if type(value) is not bool:
                    abort(400, 'Boolean required')
            elif type(value) is not int or not 1 <= value <= 86400:
                abort(400, 'Timer must be 1–86400 seconds')
        with g.db:
            if scope != '*' and not g.db.execute('SELECT 1 FROM computers WHERE computer_id=?', (scope,)).fetchone():
                abort(404, 'Unknown computer')
            g.db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET value=excluded.value', (scope, json.dumps(values)))
            event('admin_settings_change', scope + ': ' + json.dumps(values))
        return jsonify(ok=True)

    return app
