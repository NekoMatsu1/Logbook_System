"""Upload-ready source for the free hosted WSGI deployment; no credentials or local records."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent.parent

def package(destination):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=[ROOT/'common.py',ROOT/'requirements-server.txt',ROOT/'KIOSK-SETUP.md',ROOT/'BACKUPS.md']
    files += [path for path in (ROOT/'server').rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc']
    files += [ROOT/'deploy'/name for name in ('pythonanywhere_wsgi.py','configure_pythonanywhere.py','PYTHONANYWHERE.md')]
    with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
        for path in sorted(files): archive.write(path,path.relative_to(ROOT).as_posix())
    return destination

if __name__=='__main__':
    print(package(ROOT/'dist'/'pythonanywhere-server.zip'))
