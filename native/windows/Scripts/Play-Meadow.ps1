param(
    [ValidateSet('Shipping','Development')][string]$Configuration='Shipping',
    [ValidateSet('Meadow','Sakura')][string]$Island='Meadow'
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$name=if($Configuration -eq 'Shipping'){'PaitIsland-Win64-Shipping.exe'}else{'PaitIsland.exe'}
$package=if($Configuration -eq 'Shipping'){'ShippingDaily'}else{$Configuration}
$exe=Join-Path $root "Saved/Packages/$package/PaitIsland/Binaries/Win64/$name"
if(-not (Test-Path -LiteralPath $exe)){throw 'Build the current client package first.'}
# Explicit user-facing launcher. Keep previously running previews untouched.
Start-Process -FilePath $exe -ArgumentList @("-PaitIsland=$Island",'-dx12','-windowed','-ResX=1600','-ResY=900')
