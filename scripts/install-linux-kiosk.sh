#!/bin/sh
set -eu

usage() {
    printf '%s\n' 'Usage:'
    printf '%s\n' '  sudo sh scripts/install-linux-kiosk.sh --install labstudent'
    printf '%s\n' '  sudo sh scripts/install-linux-kiosk.sh --uninstall labstudent'
}

action=${1:-}
lab_user=${2:-}
case "$action" in --install|--uninstall) ;; *) usage; exit 1;; esac
[ -n "$lab_user" ] || { usage; exit 1; }
case "$lab_user" in ''|*[!a-zA-Z0-9_-]*) echo 'Invalid lab username' >&2; exit 1;; esac
[ "$(id -u)" -eq 0 ] || { echo 'Administrator privileges required' >&2; exit 1; }
[ "$lab_user" != root ] && [ "$lab_user" != "${SUDO_USER:-root}" ] || { echo 'Use a separate standard lab account' >&2; exit 1; }
id "$lab_user" >/dev/null
root=/opt/lab-logbook
backup=/etc/lab-logbook/kiosk-backup
conf=/etc/lightdm/lightdm.conf.d/60-lab-logbook.conf

if [ "$action" = '--uninstall' ]; then
    [ -d "$backup" ] || { echo 'No Logbook kiosk backup exists; refusing to change LightDM.' >&2; exit 1; }
    if [ -f "$backup/lightdm.conf" ]; then
        mkdir -p /etc/lightdm/lightdm.conf.d
        cp -p "$backup/lightdm.conf" "$conf"
    else
        rm -f "$conf"
    fi
    config=/etc/lab-logbook/client.json
    if [ -f "$config" ]; then
        python3 - "$config" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
config = json.loads(path.read_text())
config.pop('kiosk_shell_installed', None)
path.write_text(json.dumps(config, indent=2) + '\n')
PY
    fi
    archive="${backup}.removed-$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$backup" "$archive"
    printf '%s\n' 'Logbook strict kiosk mode is disabled for the next lab-account logon.'
    printf '%s\n' "Previous LightDM settings were restored. Backup retained at $archive"
    printf '%s\n' 'Do not restart LightDM while students have unsaved work.'
    exit 0
fi

[ -x "$root/.venv/bin/python" ] && [ -f "$root/scripts/kiosk_entry.py" ] || { echo 'Protected /opt/lab-logbook installation required' >&2; exit 1; }
[ -f /etc/lab-logbook/client.json ] || { echo '/etc/lab-logbook/client.json required' >&2; exit 1; }
if find "$root" -perm /022 -print -quit | read -r unused; then echo 'Installation must not be group/world writable' >&2; exit 1; fi
if find "$root" ! -user root -print -quit | read -r unused; then echo 'Installation must be root-owned' >&2; exit 1; fi
[ ! -e "$backup" ] || { echo 'Existing installation/rollback backup found; review before reinstalling' >&2; exit 1; }
mkdir -m 700 "$backup"
if [ -e "$conf" ]; then cp -p "$conf" "$backup/lightdm.conf"; fi
"$root/.venv/bin/python" - /etc/lab-logbook/client.json <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); config=json.loads(p.read_text())
if config.get('simulation') is not False:
    raise SystemExit('Explicitly set simulation=false on this dedicated lab PC before installing the live session')
config['kiosk_shell_installed']=True
p.write_text(json.dumps(config,indent=2))
PY
chown root:"$(id -gn "$lab_user")" /etc/lab-logbook/client.json
chmod 640 /etc/lab-logbook/client.json
wrapper="$root/scripts/lightdm-logbook-wrapper"
cat > "$wrapper" <<EOF
#!/bin/sh
if [ "\$(/usr/bin/id -un)" = '$lab_user' ]; then
    export XDG_SESSION_TYPE=x11
    cd '$root'
    exec '$root/.venv/bin/python' '$root/scripts/kiosk_entry.py' --config /etc/lab-logbook/client.json
fi
exec /etc/X11/Xsession "\$@"
EOF
chmod 755 "$wrapper"
mkdir -p /etc/lightdm/lightdm.conf.d
printf '[Seat:*]\nsession-wrapper=%s\n' "$wrapper" > "$conf"
printf '%s\n' 'Installed for next LightDM logon. No display-manager restart, sign-out or power operation was performed.'
printf '%s\n' "Disable later: sudo sh $root/scripts/install-linux-kiosk.sh --uninstall $lab_user"
