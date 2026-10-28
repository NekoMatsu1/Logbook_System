# Reference review

Reviewed on 2026-10-23. Source files were fetched for inspection only, into ignored `.tools/references/`. No reference project was installed or executed. No source, assets, or dependency manifests were copied into this implementation. The logbook code is independently written; no third-party code attribution obligation was introduced through this review. Dependency licenses remain their respective authors' licenses.

| Project / inspected revision | Actual source inspected | License finding |
| --- | --- | --- |
| Libki Client · `cdca236eecce9891715dc1b575cbd01661abd477` | [`timerwindow.cpp`](https://github.com/Libki/libki-client/blob/cdca236eecce9891715dc1b575cbd01661abd477/timerwindow.cpp), [`loginwindow.cpp`](https://github.com/Libki/libki-client/blob/cdca236eecce9891715dc1b575cbd01661abd477/loginwindow.cpp) | [`LICENSE`](https://github.com/Libki/libki-client/blob/cdca236eecce9891715dc1b575cbd01661abd477/LICENSE): GPLv3 text; no code reused |
| Libki Server · `6acf2d1327efcae92fda3509163a9a1da54b99f2` | [`lib/Libki/Controller/API/V2/Sessions.pm`](https://github.com/Libki/libki-server/blob/6acf2d1327efcae92fda3509163a9a1da54b99f2/lib/Libki/Controller/API/V2/Sessions.pm) | [`LICENSE`](https://github.com/Libki/libki-server/blob/6acf2d1327efcae92fda3509163a9a1da54b99f2/LICENSE): AGPLv3 or later; no code reused |
| wynnnn26/lab_system · `178d2c669db7b80889fa063c9fb739248f21cd09` | [`client.py`](https://github.com/wynnnn26/lab_system/blob/178d2c669db7b80889fa063c9fb739248f21cd09/client.py), [`server.py`](https://github.com/wynnnn26/lab_system/blob/178d2c669db7b80889fa063c9fb739248f21cd09/server.py) | No license file in the inspected repository tree and no license declared in repository metadata; no permission to reuse assumed |

Source-level observations:

- Libki's `checkForInactivity` reads global Windows input through `GetLastInputInfo` and applies warning/logout settings. The non-Windows mouse-check block in that function is commented out. Its presence does not establish functioning Linux inactivity monitoring. Our Linux adapter independently uses X11/XScreenSaver and still requires real Mint testing.
- Libki's sessions controller checks server-side administrator roles before listing sessions. Our requirements instead use designated administrator addresses, CSRF tokens, and separate machine credentials; no password screen or role-login system was imported.
- `lab_system` uses a Tkinter event pump, updates central heartbeat timestamps in `_on_heartbeat`, and writes session rows in `_on_session_start`/`_on_session_end`. Its disconnect handler calls `user_logout`, and its start handler uses `INSERT OR REPLACE`. Those behaviors are unsuitable for the requested network-loss and idempotency rules. Our implementation keeps active students running across network gaps and uses transactional inserts and a partial unique index. Remote viewing, remote commands, and unrelated features were excluded.

These observations describe inspected code paths, not claims that the reference projects work on this laptop or on both platforms.
