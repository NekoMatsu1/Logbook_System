# Lab Logbook

A logbook for a computer lab. Students register their name and ID, then use their ID to sign in. The admin can see which computers are in use and view past records.

## Download

**[Download for Windows](https://github.com/NekoMatsu1/Logbook_System/releases)**

Open the newest test release. Under **Assets**, choose **Logbook-Windows-x64.zip**.

1. Extract the whole ZIP file.
2. Get a setup file from your lab admin. Each PC needs its own file.
3. Put that file in the `config` folder and name it `client.json`.
4. Open **Logbook.exe**.

You do not need to install Python for the Windows download. Keep the `_internal` folder beside the program. The **Code > Download ZIP** button gives you the source code, not the app.

The app needs a running server. It cannot sign students in without a connection. See [how to set up another PC](DOWNLOAD.md).

## What it does

- Keeps student and session records on one server.
- Shows the student name before sign-in.
- Shows idle warnings and supports automatic sign-out.
- Gives the admin a dashboard, filters, and CSV exports.
- Runs on Windows 10/11. Linux Mint X11 setup is also available.

## Test status

This is a **test release**. New PC setup starts in simulation mode, so it does not sign out or shut down the PC.

Before using it in a real lab, test it on the actual PCs. Server hosting, backups, access rules, and real power actions need to be checked. The shutdown warning on the OS sign-in screen is not complete.

## Guides

- [Download and PC setup](DOWNLOAD.md)
- [Full setup guide](SETUP.md)
- [Test with a second PC](STUDENT-PC-TEST.md)
- [Kiosk setup](KIOSK-SETUP.md)
- [Server hosting](deploy/PYTHONANYWHERE.md)
- [Deployment checks](DEPLOYMENT-READINESS.md)

## Build from source

Use Python 3.11 or newer with Tkinter. The [full setup guide](SETUP.md) has the commands for Windows and Linux.

GitHub Actions tests both systems and builds the Windows download. Private PC keys, local records, and databases are kept out of Git and public downloads.
