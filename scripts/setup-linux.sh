#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m server init
.venv/bin/python -m server provision
printf '%s\n' 'Simulation enabled. No OS settings changed.'
