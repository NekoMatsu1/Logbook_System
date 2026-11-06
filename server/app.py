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
from werkzeug.security import check_password_hash, generate_password_hash

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session
from .db import connect, initialize
from .admin_auth import install_admin_auth
from common import (DEFAULTS, valid_student_id, STUDENT_ID_ERROR, valid_student_name,
                    STUDENT_NAME_ERROR, valid_student_password, STUDENT_PASSWORD_ERROR)

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
                      ADMIN_USERNAME=os.getenv('LOGBOOK_ADMIN_USERNAME',''),
                      ADMIN_PASSWORD_HASH=os.getenv('LOGBOOK_ADMIN_PASSWORD_HASH',''),
                      ADMIN_EMAIL=os.getenv('LOGBOOK_ADMIN_EMAIL',''),
                      GOOGLE_CLIENT_ID=os.getenv('LOGBOOK_GOOGLE_CLIENT_ID',''),
                      GOOGLE_CLIENT_SECRET=os.getenv('LOGBOOK_GOOGLE_CLIENT_SECRET',''),
                      GOOGLE_REDIRECT_URI=os.getenv('LOGBOOK_GOOGLE_REDIRECT_URI',''),
                      ALLOW_REMOTE_CLIENTS=os.getenv('LOGBOOK_ALLOW_REMOTE_CLIENTS','0') == '1',
                      LAB_NETWORKS=[value.strip() for value in os.getenv('LOGBOOK_LAB_NETWORKS','').split(',') if value.strip()],
                      TRUSTED_HOSTS=os.getenv('LOGBOOK_TRUSTED_HOSTS', 'localhost,127.0.0.1,[::1]').split(','),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_SECURE=os.getenv('LOGBOOK_HTTPS', '0') == '1',
                      MAX_CONTENT_LENGTH=1048576, NOW=utcnow)
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

    def field(value, key, maximum=128, allow_legacy_id=False):
        text = value.get(key)
        if key == 'student_id' and not allow_legacy_id:
            if not isinstance(text, str) or len(text)>maximum or not valid_student_id(text.strip()):
                abort(400, STUDENT_ID_ERROR)
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or any(ord(c) < 32 for c in text):
            abort(400, f'Invalid {key}')
        text = text.strip()
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
    @app.errorhandler(413)
    @app.errorhandler(429)
    def error(exc):
        return jsonify(error=exc.description), exc.code

    def issue_student_access(student_id):
        token = secrets.token_urlsafe(32)
        stamp = app.config['NOW']().timestamp()
        g.db.execute('DELETE FROM student_access_tokens WHERE expires_at<=? OR (student_id=? AND computer_id=?)',
                     (stamp, student_id, g.computer))
        g.db.execute('INSERT INTO student_access_tokens VALUES(?,?,?,?)',
                     (hashlib.sha256(token.encode()).hexdigest(), student_id, g.computer, stamp + 120))
        return token

    def student_auth_throttle(student_id):
        stamp = app.config['NOW']().timestamp()
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            g.db.execute('DELETE FROM student_login_attempts WHERE time<=?', (stamp - 60,))
            count = g.db.execute('SELECT COUNT(*) FROM student_login_attempts WHERE computer_id=? AND student_id=?',
                                 (g.computer, student_id)).fetchone()[0]
            if count >= 10:
                abort(429, 'Too many password attempts; wait one minute')
            g.db.execute('INSERT INTO student_login_attempts VALUES(?,?,?)', (g.computer, student_id, stamp))

    @app.post('/api/register')
    @machine
    def register():
        abort(403, 'Student self-registration is disabled. Ask the administrator to import the official account.')

    @app.get('/api/students/<sid>')
    @machine
    def lookup(sid):
        if not valid_student_id(sid):
            abort(400, STUDENT_ID_ERROR)
        row = g.db.execute('SELECT student_id,name,password_hash FROM students WHERE student_id=? AND active=1', (sid,)).fetchone()
        if not row:
            abort(404, 'Unknown or deactivated student ID')
        if not valid_student_name(row['name']):
            abort(400, 'Registered name needs administrator correction. ' + STUDENT_NAME_ERROR)
        return jsonify(student_id=row['student_id'], setup_required=row['password_hash'] is None)

    @app.post('/api/student-auth/setup')
    @machine
    def setup_student_password():
        data = body()
        sid, password = field(data, 'student_id', 64), data.get('password')
        if not valid_student_password(password):
            abort(400, STUDENT_PASSWORD_ERROR)
        password_hash = generate_password_hash(password, method='scrypt:32768:8:1')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            row = g.db.execute('SELECT name,password_hash FROM students WHERE student_id=? AND active=1',
                               (sid,)).fetchone()
            if not row:
                abort(404, 'Unknown or deactivated student ID')
            if not valid_student_name(row['name']):
                abort(400, 'Registered name needs administrator correction. ' + STUDENT_NAME_ERROR)
            if row['password_hash'] is not None:
                abort(409, 'Password is already configured. Return to sign in.')
            g.db.execute('UPDATE students SET password_hash=? WHERE student_id=?', (password_hash, sid))
            token = issue_student_access(sid)
            event('student_password_created', sid, g.computer)
        return jsonify(student_id=sid, name=row['name'], student_auth_token=token)

    @app.post('/api/student-auth/login')
    @machine
    def student_password_login():
        data = body()
        sid, password = field(data, 'student_id', 64), data.get('password')
        if not isinstance(password, str) or len(password) > 128:
            abort(401, 'Student ID or password is incorrect')
        student_auth_throttle(sid)
        row = g.db.execute('SELECT name,password_hash FROM students WHERE student_id=? AND active=1',
                           (sid,)).fetchone()
        if row and not valid_student_name(row['name']):
            abort(400, 'Registered name needs administrator correction. ' + STUDENT_NAME_ERROR)
        valid = bool(row and row['password_hash'])
        if valid:
            try:
                valid = check_password_hash(row['password_hash'], password)
            except ValueError:
                valid = False
        if not valid:
            with g.db:
                event('student_password_rejected', sid, g.computer)
            abort(401, 'Student ID or password is incorrect')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            g.db.execute('DELETE FROM student_login_attempts WHERE computer_id=? AND student_id=?',
                         (g.computer, sid))
            token = issue_student_access(sid)
            event('student_password_login', sid, g.computer)
        return jsonify(student_id=sid, name=row['name'], student_auth_token=token)

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
            access = data.get('student_auth_token')
            if not isinstance(access, str) or not access:
                abort(401, 'Student password verification required')
            token_hash = hashlib.sha256(access.encode()).hexdigest()
            authorized = g.db.execute(
                'SELECT 1 FROM student_access_tokens WHERE token_hash=? AND student_id=? AND computer_id=? AND expires_at>?',
                (token_hash, sid, g.computer, app.config['NOW']().timestamp())).fetchone()
            if not authorized:
                abort(401, 'Student password verification expired; sign in again')
            g.db.execute('DELETE FROM student_access_tokens WHERE token_hash=?', (token_hash,))
            pc = g.db.execute('SELECT run_id FROM computers WHERE computer_id=?', (g.computer,)).fetchone()
            if pc['run_id'] != run:
                abort(409, 'Agent run changed; send heartbeat first')
            student = g.db.execute('SELECT * FROM students WHERE student_id=? AND active=1', (sid,)).fetchone()
            if not student:
                abort(404, 'Unknown or deactivated student ID')
            if not valid_student_name(student['name']):
                abort(400, 'Registered name needs administrator correction. ' + STUDENT_NAME_ERROR)
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
        if reason not in ('inactivity', 'os_signout', 'simulated_inactivity', 'manual_logout', 'simulated_manual_logout'):
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
                if duration < 0:
                    abort(409, 'Server clock precedes session start; logout was not recorded')
                g.db.execute("UPDATE sessions SET status='completed',logout_time=?,duration=?,end_reason=? WHERE session_id=?",
                             (stamp, duration, reason, key))
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

    @app.get('/admin/students-template.csv')
    @admin
    def student_template():
        return app.response_class(
            'student_id,surname,first_name,middle_name\n2024035580,Dela Cruz,Juan,Santos\n',
            mimetype='text/csv', headers={
                'Content-Disposition':'attachment; filename="student-import-template.csv"',
                'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})

    @app.post('/admin/students/import')
    @admin
    def import_students():
        def reject(status, detail, public):
            with g.db:
                event('admin_student_import_rejected', detail)
            abort(status, public)
        upload = request.files.get('file')
        if not upload or not upload.filename.lower().endswith('.csv'):
            reject(400, 'missing_csv', 'Select a CSV file')
        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            reject(400, 'invalid_encoding', 'CSV must use UTF-8 encoding')
        reader = csv.DictReader(io.StringIO(text, newline=''))
        normalize = lambda value: re.sub(r'[^a-z0-9]+', '_', (value or '').strip().lower()).strip('_')
        headers = [normalize(value) for value in (reader.fieldnames or [])]
        required = ['student_id', 'surname', 'first_name', 'middle_name']
        if headers != required:
            reject(400, 'invalid_headers', 'CSV columns must be: student_id, surname, first_name, middle_name')
        rows, seen = [], set()
        for number, raw in enumerate(reader, start=2):
            if None in raw:
                reject(400, f'extra_columns_row_{number}', f'Row {number}: too many columns')
            values = {normalize(key): (value or '').strip() for key, value in raw.items()}
            if not any(values.values()):
                continue
            sid = values['student_id']
            name = f"{values['surname']}, {values['first_name']}, {values['middle_name']}"
            if not valid_student_id(sid):
                reject(400, f'invalid_id_row_{number}', f'Row {number}: {STUDENT_ID_ERROR}')
            if not valid_student_name(name):
                reject(400, f'invalid_name_row_{number}', f'Row {number}: {STUDENT_NAME_ERROR}')
            if sid in seen:
                reject(409, f'duplicate_csv_id_row_{number}', f'Row {number}: duplicate student ID in CSV')
            seen.add(sid)
            rows.append((sid, name))
            if len(rows) > 5000:
                reject(400, 'too_many_rows', 'CSV cannot contain more than 5,000 students')
        if not rows:
            reject(400, 'empty_csv', 'CSV contains no student records')
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            existing_ids = {row['student_id'] for row in g.db.execute('SELECT student_id FROM students')}
            duplicate = next((sid for sid, _ in rows if sid in existing_ids), None)
            if duplicate:
                g.db.rollback()
                reject(409, 'existing_student_id', f'Student ID {duplicate} already exists; nothing was imported')
            g.db.executemany('INSERT INTO students(student_id,name,active,password_hash) VALUES(?,?,1,NULL)', rows)
            event('admin_student_import', f'{len(rows)} accounts created')
        return jsonify(imported=len(rows))

    @app.post('/admin/students')
    @admin
    def edit_student():
        data = body()
        # Preserve old test records and let an admin deactivate them, never reactivate invalid IDs.
        sid = field(data, 'student_id', 64,
                    allow_legacy_id=not data.get('create') and data.get('active') is False)
        name = field(data, 'name')
        if (data.get('create') or data.get('active', True) is not False) and not valid_student_name(name):
            abort(400, STUDENT_NAME_ERROR)
        if type(data.get('active', True)) is not bool:
            abort(400, 'Active must be boolean')
        with g.db:
            if data.get('create'):
                try:
                    g.db.execute('INSERT INTO students(student_id,name,active,password_hash) VALUES(?,?,?,NULL)',
                                 (sid, name, int(data.get('active', True))))
                except sqlite3.IntegrityError:
                    abort(409, 'Student ID already registered')
            else:
                if not g.db.execute('UPDATE students SET name=?,active=? WHERE student_id=?', (name, int(data.get('active', True)), sid)).rowcount:
                    abort(404)
            event('admin_student_change', sid)
        return jsonify(ok=True)

    @app.post('/admin/students/password-reset')
    @admin
    def reset_student_password():
        data = body()
        sid = field(data, 'student_id', 64)
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            if not g.db.execute('UPDATE students SET password_hash=NULL WHERE student_id=?', (sid,)).rowcount:
                abort(404, 'Unknown student ID')
            g.db.execute('DELETE FROM student_access_tokens WHERE student_id=?', (sid,))
            event('admin_student_password_reset', sid)
        return jsonify(ok=True)

    @app.post('/admin/students/delete')
    @admin
    def delete_student():
        # Historical logbook records are evidence and must never be removed with an account.
        data = body()
        sid = field(data, 'student_id', 64, allow_legacy_id=True)
        with g.db:
            g.db.execute('BEGIN IMMEDIATE')
            if not g.db.execute('SELECT 1 FROM students WHERE student_id=?', (sid,)).fetchone():
                abort(404, 'Unknown student ID')
            if g.db.execute('SELECT 1 FROM sessions WHERE student_id=? LIMIT 1', (sid,)).fetchone():
                abort(409, 'This account has logbook records and cannot be deleted. Deactivate it instead to preserve the records.')
            g.db.execute('DELETE FROM student_access_tokens WHERE student_id=?', (sid,))
            g.db.execute('DELETE FROM student_login_attempts WHERE student_id=?', (sid,))
            g.db.execute('DELETE FROM students WHERE student_id=?', (sid,))
            event('admin_student_deleted', sid)
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
