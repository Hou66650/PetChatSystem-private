param([string]$Package='ShippingBusiness',[int]$Port=5013,[switch]$Capture,[switch]$ProviderCheck)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$health=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/native/v1/bootstrap" -TimeoutSec 3
if($health.fixture -ne $true){throw 'Refusing a non-fixture service; no credentials or mutations sent'}
if($ProviderCheck -and $health.providerFixture -ne $true){throw 'Provider test requires explicit provider-fixture service'}
$exe=Join-Path $root "Saved/Packages/$Package/PaitIsland/Binaries/Win64/PaitIsland-Win64-Shipping.exe"
$out=Join-Path $root ('Saved/Qualification/NativeBusiness-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $out | Out-Null
$testArgs=@('-unattended','-NoSound','-PaitAccountFixture',"-PaitApi=http://127.0.0.1:$Port","-PaitEvidenceDir=`"$out`"")
if($Capture){$testArgs+=@('-dx12','-windowed','-ResX=1600','-ResY=900','-PaitAccountCapture')}else{$testArgs+='-nullrhi'}
if($ProviderCheck){$audio=Join-Path $root 'Saved/Qualification/live-synthetic.wav';if(-not(Test-Path -LiteralPath $audio)){throw 'Synthetic audio fixture missing'};$testArgs+=@('-PaitProviderCheck',"-PaitLiveAudioFixture=`"$audio`"")}
$child=Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList $testArgs
if(-not $child.WaitForExit(240000)){Stop-Process -Id $child.Id;throw "Own fixture timed out: $out"}
if($child.ExitCode -ne 0){throw "Native fixture exited $($child.ExitCode): $out"}
$report=Get-Content -LiteralPath (Join-Path $out 'native-account.json') -Raw | ConvertFrom-Json
if(-not $report.passed){throw "Native business failed: $($report.error)"}
if($Capture){
    $garden=Get-Content -LiteralPath (Join-Path $out 'native-garden.json') -Raw | ConvertFrom-Json
    if($garden.mesh_components -lt 1 -or -not $garden.account_bound -or $garden.demonstration_meshes_suppressed -lt 1){throw "Garden was not bound to fixture account: $out"}
    if(-not(Test-Path -LiteralPath (Join-Path $out 'native-garden.png'))){throw "Garden screenshot missing: $out"}
}
[ordered]@{executable_sha256=(Get-FileHash -LiteralPath $exe).Hash;exit_code=$child.ExitCode;fixture_port=$Port;microphone_validated=$false;synthetic_realtime_provider_verified=[bool]$ProviderCheck;cloned_voice_provider_validated=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'launch.json') -Encoding utf8
Write-Host "Passed $out"
