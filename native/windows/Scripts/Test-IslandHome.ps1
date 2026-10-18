param([string]$Package='ShippingHome',[switch]$OverviewOnly)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$exe=Join-Path $root "Saved/Packages/$Package/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe"
$out=Join-Path $root ('Saved/Qualification/IslandHome-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$flags=@('-PaitIsland=Home','-unattended','-NoSound','-dx12','-windowed','-ResX=1600','-ResY=900',"-PaitEvidenceDir=`"$out`"")
if($OverviewOnly){$flags+='-PaitSmoke'}else{$flags+='-PaitHomeFlow'}
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList $flags
if(-not $child.WaitForExit(360000)){Stop-Process -Id $child.Id;throw "Own home test timed out: $out"}
if($child.ExitCode -ne 0){throw "Home process failed: $($child.ExitCode) $out"}
$report=Join-Path $out $(if($OverviewOnly){'runtime-smoke.json'}else{'home-flow.json'})
if(-not(Test-Path -LiteralPath $report)){throw "Home evidence missing: $out"}
$result=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if(-not $OverviewOnly -and -not $result.passed){throw 'Home route failed'}
$images=if($OverviewOnly){@('runtime-smoke.png')}else{@('home-0.png','home-1.png','home-2.png','home-3.png','island-0.png','island-1.png','island-2.png','island-3.png')}
foreach($name in $images){if(-not(Test-Path -LiteralPath (Join-Path $out $name))){throw "Capture missing: $name"}}
[ordered]@{executable_sha256=(Get-FileHash -LiteralPath $exe).Hash;exit_code=$child.ExitCode;manual_mouse_checked=$false;performance_qualified=$false;production_mutations=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'launch.json') -Encoding utf8
Write-Host "Passed $out"
