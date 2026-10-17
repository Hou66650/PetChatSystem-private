param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [ValidateSet("Development", "Shipping")][string]$Configuration = "Development",
    [int]$TimeoutSeconds = 240
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
$process = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru -ArgumentList @(
    "-dx12", "-windowed", "-ResX=1600", "-ResY=900", "-PaitSmoke", "-unattended",
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
$capture = Join-Path $evidence "runtime-smoke.png"
if (-not (Test-Path -LiteralPath $capture)) { throw "Recorded screenshot does not exist: $capture" }
[ordered]@{
    configuration = $Configuration
    executable = $exe
    executable_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    exit_code = $process.ExitCode
    screenshot_sha256 = (Get-FileHash -LiteralPath $capture -Algorithm SHA256).Hash
    status = "rendered_capture_saved_requires_visual_review"
    performance_qualified = $false
    adapter = $report.adapter
    utc = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence "launch.json") -Encoding utf8
Write-Host "Runtime capture saved at $evidence; visually inspect before qualifying."
