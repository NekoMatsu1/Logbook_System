param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
& $Python -3 -m venv .venv
if ($LASTEXITCODE) { throw 'Python 3.11+ with Tkinter is required. Install from python.org.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe -m server init
& .\.venv\Scripts\python.exe -m server provision
if ($LASTEXITCODE) { throw 'Provisioning failed; an existing config is never overwritten' }
Write-Output 'Simulation is enabled. No OS settings changed.'
