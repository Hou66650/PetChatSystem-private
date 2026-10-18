param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [ValidateSet("Development", "Shipping")][string]$Configuration = "Development",
    [int]$TimeoutSeconds = 240,
    [ValidateSet("/Game/Qualification/P0_Lighting", "/Game/Preview/P1_MeadowV2", "/Game/Preview/P1_SakuraV2", "/Game/Preview/P1_SnowV2", "/Game/Preview/P1_CampV2", "/Game/Preview/P2_Park")][string]$Map = "/Game/Preview/P1_MeadowV2"
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$exe = (Resolve-Path -LiteralPath $Executable).Path
$evidence = Join-Path $projectRoot ("Saved/Qualification/Launch-$Configuration-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$log = Join-Path $evidence "runtime.log"
if (Test-Path -LiteralPath $log) {
    Move-Item -LiteralPath $log -Destination ($log + "." + (Get-Date -Format "yyyyMMdd-HHmmss"))
}
# This is a bounded automated render smoke, not a performance measurement.
$destination = if($Map -like '*/P0_*'){'Qualification'}else{($Map.Split('/')[-1] -replace '^P[12]_|V2$','')}
$process = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList @(
    $Map, "-PaitIsland=$destination", "-dx12", "-windowed", "-ResX=1600", "-ResY=900", "-PaitSmoke", "-unattended",
    "-nosplash", "-NoSound", "-abslog=`"$log`"", "-PaitEvidenceDir=`"$evidence`""
)
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    # Stop only this child, never unrelated game/editor processes.
    $process.Kill()
    throw "Client launch timed out. Inspect $log"
}
if ($process.ExitCode -ne 0) { throw "Client exited with $($process.ExitCode). Inspect $log" }
$reportPath = Join-Path $evidence "runtime-smoke.json"
if (-not (Test-Path -LiteralPath $reportPath)) { throw "Runtime evidence absent; launch is unverified." }
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.status -ne "rendered_capture_saved") { throw "Rendered capture was not confirmed." }
if ($report.actual_map -ne ($Map.Split('/')[-1])) { throw "Opened the wrong scene: $($report.actual_map). Shipping uses the configured default map." }
$capture = Join-Path $evidence "runtime-smoke.png"
if (-not (Test-Path -LiteralPath $capture)) { throw "Recorded screenshot does not exist: $capture" }
$packagedProject = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $exe))
$contentHashes = @(Get-ChildItem -LiteralPath (Join-Path $packagedProject "Content/Paks") -File | Where-Object {
    $_.Extension -in @(".pak", ".utoc", ".ucas")
} | ForEach-Object {
    [ordered]@{ file = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
})
if ($contentHashes.Count -eq 0) { throw "Packaged content evidence is missing." }
[ordered]@{
    configuration = $Configuration
    map = $Map
    actual_map = $report.actual_map
    executable = $exe
    executable_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    packaged_content = $contentHashes
    exit_code = $process.ExitCode
    screenshot_sha256 = (Get-FileHash -LiteralPath $capture -Algorithm SHA256).Hash
    status = "rendered_capture_saved_requires_visual_review"
    performance_qualified = $false
    adapter = $report.adapter
    utc = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence "launch.json") -Encoding utf8
Write-Host "Runtime capture saved at $evidence; visually inspect before qualifying."
