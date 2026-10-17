param([int]$TimeoutSeconds=210,[string]$Package='ShippingDaily')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$exe=Join-Path $root "Saved/Packages/$Package/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw 'Build Shipping first.' }
$out=Join-Path $root ('Saved/Qualification/MeadowAgent-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList @(
    '-dx12','-windowed','-ResX=1600','-ResY=900','-unattended','-nosplash','-NoSound',
    '-PaitAgentTest',"-PaitEvidenceDir=`"$out`""
)
if(-not $child.WaitForExit($TimeoutSeconds*1000)) { Stop-Process -Id $child.Id; throw 'Own Agent test timed out' }
$report=Join-Path $out 'agent.json'
if(-not (Test-Path -LiteralPath $report)) { throw "Agent report missing: $out" }
$data=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($child.ExitCode -ne 0 -or -not $data.passed -or $data.actual_map -ne 'P1_MeadowV2') { throw "Agent failed: $($data.error); $out" }
foreach($name in @('agent-exploring.png','agent-resting.png','preview-memory.json')) {
    if(-not (Test-Path -LiteralPath (Join-Path $out $name))) { throw "Missing evidence: $name" }
}
$paks=Join-Path $root "Saved/Packages/$Package/PaitIsland/Content/Paks"
$content=@(Get-ChildItem -LiteralPath $paks -File | Where-Object {$_.Extension -in @('.pak','.utoc','.ucas')} | ForEach-Object {
    [ordered]@{file=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}
})
[ordered]@{executable_sha256=(Get-FileHash -LiteralPath $exe).Hash;packaged_content=$content;exit_code=$child.ExitCode;manual_input_validated=$false;performance_qualified=$false} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'launch.json') -Encoding utf8
Write-Host "Native Agent sequence passed; inspect $out"
