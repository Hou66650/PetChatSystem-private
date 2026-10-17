param([Parameter(Mandatory=$true)][string]$EngineRoot)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectRoot "PaitIsland.uproject"
$editor = Join-Path $EngineRoot "Engine/Binaries/Win64/UnrealEditor.exe"
if (-not (Test-Path -LiteralPath $editor)) { throw "UnrealEditor.exe not found." }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "Content/Qualification/P0_Lighting.umap"))) {
    throw "Qualification map is absent. Compile Editor and run Build-Client.ps1 -Mode CreateMap first."
}
# This is an explicitly interactive editor, so a visible window is intentional.
Start-Process -FilePath $editor -ArgumentList @('"' + $projectFile + '"', "-dx12", "-log")
