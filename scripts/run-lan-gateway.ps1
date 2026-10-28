$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.tools\lan\caddy.exe')) { throw 'Caddy executable missing from .tools\lan.' }
# Restrict Caddy runtime data to this ignored workspace directory; no OS trust changes.
$env:APPDATA = (Join-Path (Get-Location).Path '.tools\lan\runtime')
$env:XDG_DATA_HOME = $env:APPDATA
$env:XDG_CONFIG_HOME = $env:APPDATA
& .\.tools\lan\caddy.exe run --config .tools/lan/Caddyfile --adapter caddyfile
exit $LASTEXITCODE
