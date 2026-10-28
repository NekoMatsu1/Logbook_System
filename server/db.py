import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
CREATE TABLE IF NOT EXISTS students(
 student_id TEXT PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS computers(
 computer_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, run_id TEXT,
 last_seen TEXT, last_action TEXT);
CREATE TABLE IF NOT EXISTS sessions(
 session_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id),
 student_name TEXT NOT NULL, computer_id TEXT NOT NULL REFERENCES computers(computer_id),
 run_id TEXT NOT NULL, login_time TEXT NOT NULL, logout_time TEXT,
 duration REAL, end_reason TEXT, status TEXT NOT NULL CHECK(status IN ('active','completed','interrupted')));
CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_pc ON sessions(computer_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS settings(scope TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runs(computer_id TEXT NOT NULL REFERENCES computers(computer_id),
 run_id TEXT NOT NULL, PRIMARY KEY(computer_id,run_id));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, time TEXT NOT NULL,
 computer_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL);
"""

def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db

def initialize(path):
    with connect(path) as db:
        db.executescript(SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        version = db.execute('SELECT version FROM schema_version').fetchone()[0]
        if version not in (1, 2):
            raise RuntimeError('Unsupported database schema')
        if version == 1:
            migration = """
ALTER TABLE computers ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1));
CREATE TABLE oauth_states(state_hash TEXT PRIMARY KEY, browser_hash TEXT NOT NULL,
 nonce TEXT NOT NULL, verifier TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE admin_identities(email TEXT PRIMARY KEY, subject TEXT NOT NULL UNIQUE);
CREATE TABLE admin_sessions(token_hash TEXT PRIMARY KEY, subject TEXT NOT NULL,
 expires_at REAL NOT NULL);
UPDATE schema_version SET version=2;
"""
            for statement in migration.split(';'):
                if statement.strip():
                    db.execute(statement)
