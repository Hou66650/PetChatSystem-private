param([ValidateSet("Shipping", "Development")][string]$Configuration = "Shipping")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$name = if ($Configuration -eq "Shipping") { "PaitIsland-Win64-Shipping.exe" } else { "PaitIsland.exe" }
$exe = Join-Path $root "Saved/Packages/$Configuration/PaitIsland/Binaries/Win64/$name"
if (-not (Test-Path -LiteralPath $exe)) { throw "Build the client package first." }
# Explicit interactive preview launcher; visible game window is intentional.
Start-Process -FilePath $exe -ArgumentList @("/Game/Preview/P1_MeadowV2", "-dx12", "-windowed", "-ResX=1600", "-ResY=900")
