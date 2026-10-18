param([string]$Package='ShippingPark',[int]$Port=5013,[switch]$ThroughHome)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$health=Invoke-RestMethod "http://127.0.0.1:$Port/api/native/v1/bootstrap" -TimeoutSec 3
if($health.fixture -ne $true){throw 'Refusing a non-fixture service'}
$exe=Join-Path $root "Saved/Packages/$Package/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe"
$out=Join-Path $root ('Saved/Qualification/PublicPark-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$flags=@('/Game/Preview/P2_Park','-PaitIsland=Park','-PaitParkFixture','-unattended','-NoSound','-dx12','-windowed','-ResX=1600','-ResY=900',"-PaitApi=http://127.0.0.1:$Port","-PaitEvidenceDir=`"$out`"")
if($ThroughHome){$flags=$flags | Where-Object { $_ -ne '/Game/Preview/P2_Park' }}
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList $flags
if(-not $child.WaitForExit(320000)){Stop-Process -Id $child.Id;throw "Own park fixture timed out: $out"}
$report=Get-Content -LiteralPath (Join-Path $out 'park-gameplay.json') -Raw | ConvertFrom-Json
if($child.ExitCode -ne 0 -or -not $report.passed){throw "Park test failed: $out / $($report.status)"}
foreach($name in @('park-bridge.png','park-play.png')){if(-not(Test-Path -LiteralPath (Join-Path $out $name))){throw "Missing $name"}}
@{binary_sha256=(Get-FileHash $exe).Hash;exit_code=$child.ExitCode;fixture_port=$Port;through_home=[bool]$ThroughHome;performance_qualified=$false} | ConvertTo-Json | Set-Content (Join-Path $out 'launch.json') -Encoding utf8
Write-Host "Passed $out"
