param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [ValidateSet("Development", "Shipping")][string]$Configuration = "Development",
    [ValidateRange(90,600)][int]$DurationSeconds = 300
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$exe = (Resolve-Path -LiteralPath $Executable).Path
$run = Join-Path $projectRoot ("Saved/Qualification/SixViews-$Configuration-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $run | Out-Null
$process = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList @(
    "-dx12", "-windowed", "-ResX=1600", "-ResY=900", "-PaitQualification", "-unattended",
    "-PaitQualificationSeconds=$DurationSeconds", "-nosplash", "-NoSound",
    "-abslog=`"$(Join-Path $run 'runtime.log')`"", "-PaitEvidenceDir=`"$run`""
)
Write-Host "Qualification running: $run"
if (-not $process.WaitForExit(($DurationSeconds + 150) * 1000)) {
    $process.Kill()
    throw "Only this test child was stopped after timeout; inspect $run"
}
if ($process.ExitCode -ne 0) { throw "Qualification exited $($process.ExitCode); inspect $run" }
$result = Get-Content -LiteralPath (Join-Path $run 'qualification.json') -Raw | ConvertFrom-Json
if ($result.status -ne 'runtime_checks_passed_requires_visual_review') { throw "Runtime checks failed: $run" }
if ($result.elapsed_seconds -lt $DurationSeconds -or $result.captures.Count -ne 9) { throw "Incomplete runtime evidence" }
$poses = @($result.pose_samples | Group-Object shot | ForEach-Object {
    $moving = @($_.Group | Where-Object max_bone_translation_delta_cm -GT 0.01).Count
    if ($moving -lt 2) { throw "No sustained bone movement in $($_.Name)" }
    foreach ($sample in $_.Group) {
        if ($sample.layers.Count -ne 3 -or @($sample.layers | Where-Object bones -LT 10).Count) {
            throw "Incomplete skeletal layers in $($_.Name)"
        }
    }
    [ordered]@{shot=$_.Name; samples=$_.Count; moving_samples=$moving
        maximum_bone_delta_cm=($_.Group.max_bone_translation_delta_cm | Measure-Object -Maximum).Maximum}
})
if ($poses.Count -ne 6) { throw 'Not all camera stages produced pose evidence' }
$captures = @($result.captures | ForEach-Object {
    $file = Join-Path $run $_
    [ordered]@{ file = $_; sha256 = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
})
foreach ($shot in @('01-cat-portrait','02-cat-walk','03-cat-trot')) {
    $pair = @($captures | Where-Object file -Like "$shot-*")
    if ($pair.Count -ne 2 -or $pair[0].sha256 -eq $pair[1].sha256) { throw "Missing or identical animation pair: $shot" }
}
$packagedProject = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $exe))
$content = @(Get-ChildItem -LiteralPath (Join-Path $packagedProject 'Content/Paks') -File | Where-Object {
    $_.Extension -in @('.pak','.utoc','.ucas')
} | ForEach-Object { [ordered]@{file=$_.Name; sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash} })
if ($content.Count -eq 0) { throw 'Missing packaged content' }
[ordered]@{
    configuration=$Configuration; executable_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    adapter=$result.adapter; elapsed_seconds=$result.elapsed_seconds; captures=$captures; packaged_content=$content
    pose_summary=$poses; resolution='1600x900'; requested_window_state='Hidden'; animation_clips=@('idle_breathe','walk','trot')
    five_minute_runtime_completed=($result.elapsed_seconds -ge 300)
    visual_qualified=$false; performance_qualified=$false; utc=(Get-Date).ToUniversalTime().ToString('o')
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'launch.json') -Encoding utf8
Write-Host "Runtime checks complete; inspect all images and pose evidence: $run"
