param([int]$TimeoutSeconds=180)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$exe=Join-Path $root 'Saved/Packages/Shipping/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe'
$out=Join-Path $root ('Saved/Qualification/MeadowInteraction-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList @(
    '-dx12','-windowed','-ResX=1600','-ResY=900','-unattended','-nosplash','-NoSound',
    '-PaitMeadowTest',"-PaitEvidenceDir=`"$out`""
)
if(-not $child.WaitForExit($TimeoutSeconds*1000)) { Stop-Process -Id $child.Id; throw 'Own interaction test timed out' }
$report=Join-Path $out 'interaction.json'
if(-not (Test-Path -LiteralPath $report)) { throw "Interaction report missing: $out" }
$data=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($child.ExitCode -ne 0 -or -not $data.passed -or $data.actual_map -ne 'P1_MeadowV2') { throw "Interaction failed: $($data.error); $out" }
foreach($name in @('walking.png','greeting.png')) {
    if(-not (Test-Path -LiteralPath (Join-Path $out $name))) { throw "Missing capture: $name" }
}
$paks=Join-Path $root 'Saved/Packages/Shipping/PaitIsland/Content/Paks'
$content=@(Get-ChildItem -LiteralPath $paks -File | Where-Object {$_.Extension -in @('.pak','.utoc','.ucas')} | ForEach-Object {
    [ordered]@{file=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}
})
[ordered]@{executable_sha256=(Get-FileHash -LiteralPath $exe).Hash;packaged_content=$content;exit_code=$child.ExitCode;manual_input_validated=$false;performance_qualified=$false} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'launch.json') -Encoding utf8
Write-Host "Movement and greeting test passed; inspect $out"
