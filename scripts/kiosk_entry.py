"""Absolute-path entry point for OS shell launchers with arbitrary working directories."""
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0,str(root))
from client.kiosk import main

if __name__=='__main__':
    main()
