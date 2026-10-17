param(
    [ValidateSet('Meadow','Sakura')][string]$Island='Meadow',
    [string]$Package='ShippingDaily',
    [int]$TimeoutSeconds=360,
    [switch]$Smoke
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$exe=Join-Path $root "Saved/Packages/$Package/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe"
if(-not (Test-Path -LiteralPath $exe)) { throw 'Package executable missing' }
$out=Join-Path $root ("Saved/Qualification/$Island-Care-"+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$mode=if($Smoke){'-PaitSmoke'}else{'-PaitCareTest'}
$testArgs=@('-dx12','-windowed','-ResX=1600','-ResY=900','-unattended','-NoSound',$mode,"-PaitIsland=$Island","-PaitEvidenceDir=`"$out`"")
if($Smoke){$testArgs+='-PaitCleanCapture'}
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList $testArgs
if(-not $child.WaitForExit($TimeoutSeconds*1000)) { Stop-Process -Id $child.Id; throw "Own test timed out: $out" }
$name=if($Smoke){'runtime-smoke.json'}else{'care.json'}
$report=Join-Path $out $name
if(-not (Test-Path -LiteralPath $report)) { throw "Missing report: $out" }
$data=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$actualMap=if($Smoke){$data.actual_map}else{$data.map}
if($actualMap -ne "P1_${Island}V2") { throw "Wrong runtime map: $actualMap; $out" }
if($Smoke -and ($data.status -ne 'rendered_capture_saved' -or -not (Test-Path (Join-Path $out 'runtime-smoke.png')))) { throw "Missing rendered smoke capture: $out" }
[ordered]@{executable_sha256=(Get-FileHash -LiteralPath $exe).Hash;exit_code=$child.ExitCode;island=$Island;performance_qualified=$false;manual_input_validated=$false} | ConvertTo-Json | Set-Content (Join-Path $out 'launch.json') -Encoding utf8
if($child.ExitCode -ne 0 -or (-not $Smoke -and -not $data.passed)) { throw "Care failed: $($data.error); $out" }
if(-not $Smoke){
 foreach($image in @('food','water','home','toy')){
  if(-not (Test-Path -LiteralPath (Join-Path $out "$image.png"))){throw "Missing action capture: $image"}
 }
}
Write-Host "Passed $out - visual review still required"
