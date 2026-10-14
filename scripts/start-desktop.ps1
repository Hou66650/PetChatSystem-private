$ErrorActionPreference = 'Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$clientRoot=Join-Path $projectRoot 'desktop'
$electronPath=Join-Path $clientRoot 'node_modules/electron/dist/electron.exe'
if(!(Test-Path -LiteralPath $electronPath)){throw '请先在 desktop 目录运行 npm ci 安装桌面依赖。'}
Start-Process -FilePath $electronPath -ArgumentList ('"'+$clientRoot+'"') -WorkingDirectory $clientRoot
