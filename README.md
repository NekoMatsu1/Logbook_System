# Lab Logbook

A logbook for a computer lab. Students register their name and ID, then use their ID to sign in. The admin can see which computers are in use and view past records.

## Download

**[Download for Windows](https://github.com/NekoMatsu1/Logbook_System/releases/download/v0.1.2-test.1/Logbook-Windows-x64.zip)** | [All releases](https://github.com/NekoMatsu1/Logbook_System/releases)

The download is **Logbook-Windows-x64.zip**. It is a test version.

1. Extract the whole ZIP file.
2. Get a setup file from your lab admin. Each PC needs its own file.
3. Put that file in the `config` folder and name it `client.json`.
4. Open **Logbook.exe**.

You do not need to install Python for the Windows download. Keep the `_internal` folder beside the program. The **Code > Download ZIP** button gives you the source code, not the app.

The central server is now running on PythonAnywhere. The first Windows PC has registered and started a session through it. PCs can connect from different internet connections; they do not need to share a LAN. The dashboard is restricted to the admin network's public IP. See [how to set up another PC](DOWNLOAD.md). Each new PC must get its own private setup file from the admin.

The server needs monthly renewal in PythonAnywhere's Web tab. It can keep running when the development laptop is off. A test on a second PC and a different internet connection is still pending.

## What it does

- Keeps student and session records on one server.
- Shows the student name before sign-in.
- Shows idle warnings and supports automatic sign-out.
- Lets students click **Log out** in the portable app's session window. Closing that window minimizes it; reopen it from the taskbar.
- Gives the admin a dashboard, filters, and CSV exports.
- Runs on Windows 10/11. Linux Mint X11 setup is also available.

## Test status

This is a **test release**. New PC setup starts in simulation mode, so it does not sign out or shut down the PC.

Before using it in a real lab, test it on the actual PCs. Backup restore, access from a second network, and real power actions still need checks. The shutdown warning on the OS sign-in screen is not complete.

## Guides

- [Free internet server without a card](deploy/PYTHONANYWHERE.md)
- [Start with Oracle Cloud](deploy/ORACLE.md)
- [Download and PC setup](DOWNLOAD.md)
- [Full setup guide](SETUP.md)
- [Test with a second PC](STUDENT-PC-TEST.md)
- [Kiosk setup](KIOSK-SETUP.md)
- [Internet server deployment](deploy/README.md)
- [Server hosting](deploy/PYTHONANYWHERE.md)
- [Deployment checks](DEPLOYMENT-READINESS.md)

## Build from source

Use Python 3.11 or newer with Tkinter. The [full setup guide](SETUP.md) has the commands for Windows and Linux.

GitHub Actions tests both systems and builds the Windows download. Private PC keys, local records, and databases are kept out of Git and public downloads.
