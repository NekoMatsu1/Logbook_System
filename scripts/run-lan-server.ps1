param([Parameter(Mandatory=$true)][string]$ServerIP)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = '.\.venv\bin\python.exe' }
$env:LOGBOOK_ADMIN_ADDRESSES = '127.0.0.1,::1'
$env:LOGBOOK_ADMIN_DIRECT_ONLY = '1'
$env:LOGBOOK_TRUSTED_PROXY = '127.0.0.1'
$env:LOGBOOK_TRUSTED_HOSTS = "localhost,127.0.0.1,[::1],$ServerIP"
$prefix = (Get-NetIPAddress -IPAddress $ServerIP -AddressFamily IPv4 -ErrorAction Stop | Select-Object -First 1).PrefixLength
$env:LOGBOOK_LAB_NETWORKS = & $python -c 'import ipaddress,sys; print(ipaddress.ip_network(chr(47).join(sys.argv[1:]),strict=False))' $ServerIP $prefix
if ($LASTEXITCODE) { throw 'Could not determine the lab network' }
Write-Output 'Admin dashboard: http://127.0.0.1:5001/admin/overview (this laptop only)'
& $python -m server serve --port 5001
exit $LASTEXITCODE
