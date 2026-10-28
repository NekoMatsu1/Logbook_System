# Back up the records

Use the central server, not a student's PC. Keep backup files private: they contain student and session records.

After updating the server code, run this in the PythonAnywhere Bash console:

```bash
cd ~/lab-logbook
~/.virtualenvs/lab-logbook/bin/python -m server backup \
  --database ~/.local/share/lab-logbook/logbook.sqlite \
  --output ~/private-backups/logbook-$(date -u +%Y%m%dT%H%M%SZ).sqlite
```

The command uses SQLite's online backup API, checks the output's integrity, and refuses to replace an existing file. It does not change registrations or session records. Do not copy the raw live database file: committed records may still be in its WAL file.

Download backups through your signed-in Files tab and keep a protected copy outside the hosting account. Back up regularly and before server updates. Account loss, host failure, or deleting the database can lose records if there is no independent copy. This command does not create a backup schedule or an off-site storage account.

Keep the private server configuration separately too; the database backup does not include `~/.config/lab-logbook/server.json`.

## Restore checks

Restore a backup to a separate location first. Check its SQLite integrity, schema version, student IDs including leading zeros, historical names, session counts, timestamps, durations, and interrupted records. The automated tests restore a consistent snapshot and compare the full session record with the original.

For a live restore, stop web requests and the client rollout first, protect the existing database and its WAL/SHM files, then restore the verified backup deliberately. Do not overwrite a running SQLite database. Verify the restored site before reconnecting clients. Ask the system maintainer to perform this operation; it is not a student action.
