param([int]$Port=5012,[string]$SourceRoot='D:/PetChatSystem',[switch]$Fixture)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$health="http://127.0.0.1:$Port/api/native/v1/bootstrap"
try {
    $running=Invoke-RestMethod -Uri $health -TimeoutSec 3
    if($running.apiVersion -eq 1 -and [bool]$running.fixture -eq [bool]$Fixture){Write-Host "Native service already ready on $Port";exit 0}
} catch {}
if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){throw "Port $Port belongs to another service; it was left untouched."}
$python='C:/Users/17958/.conda/envs/qijin666/python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Python environment missing'}
$log=Join-Path $root 'Saved/NativeService'
New-Item -ItemType Directory -Path $log -Force | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$arguments=@('-X','utf8',('"'+(Join-Path $PSScriptRoot 'serve_native.py')+'"'),'--port',$Port,'--source-root',('"'+$SourceRoot+'"'))
if($Fixture){$arguments+='--fixture'}
$child=Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $log "$stamp.out.log") -RedirectStandardError (Join-Path $log "$stamp.error.log")
for($attempt=0;$attempt -lt 40;$attempt++){
    if($child.HasExited){throw "Native service exited; inspect $log"}
    try{$ready=Invoke-RestMethod -Uri $health -TimeoutSec 2;if($ready.apiVersion -eq 1){Write-Host "Native service ready: $Port / PID $($child.Id)";exit 0}}catch{}
    Start-Sleep -Milliseconds 400
}
throw "Native service not ready yet; inspect $log"
