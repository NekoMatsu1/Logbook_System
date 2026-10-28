"""Consistent online SQLite backups; never copy a live WAL database as a raw file."""
import os
from pathlib import Path
import sqlite3


def backup_database(database, output):
    source_path=Path(database).resolve(strict=True)
    destination=Path(output).absolute()
    if source_path == destination.resolve():
        raise ValueError('Backup destination must differ from the live database')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Reserve a fresh filename and protect it before writing student data.
    descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(descriptor)
    try:
        source=sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True,timeout=10)
        try:
            target=sqlite3.connect(destination)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise RuntimeError('Backup integrity check failed')
            finally:
                target.close()
        finally:
            source.close()
    except BaseException:
        # Only the newly reserved output is removed; the source is never modified.
        destination.unlink(missing_ok=True)
        raise
    return destination
