param(
    [Parameter(Mandatory=$true)][string]$EngineRoot,
    [ValidateSet("Generate", "Editor", "CreateMap", "Package")][string]$Mode = "Editor",
    [ValidateSet("Development", "Shipping")][string]$Configuration = "Development",
    [string]$PythonExe = "python"
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectRoot "PaitIsland.uproject"
$enginePath = (Resolve-Path -LiteralPath $EngineRoot).Path
$report = Join-Path $projectRoot "Saved/Qualification/toolchain-local.json"
& $PythonExe (Join-Path $projectRoot "Tools/toolchain.py") --engine-root $enginePath --output $report
if ($LASTEXITCODE -ne 0) { throw "Toolchain preflight blocked. See $report" }
$build = Join-Path $enginePath "Engine/Build/BatchFiles/Build.bat"
$editor = Join-Path $enginePath "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
$uat = Join-Path $enginePath "Engine/Build/BatchFiles/RunUAT.bat"
$mapFile = Join-Path $projectRoot "Content/Qualification/P0_Lighting.umap"
switch ($Mode) {
    "Generate" {
        & $build -projectfiles "-project=$projectFile" -game -engine
    }
    "Editor" {
        & $build PaitIslandEditor Win64 Development "-Project=$projectFile" -WaitMutex -NoHotReloadFromIDE
    }
    "CreateMap" {
        if (Test-Path -LiteralPath $mapFile) { throw "Map exists; do not overwrite authored work." }
        $script = Join-Path $projectRoot "Scripts/create_qualification_map.py"
        & $editor $projectFile "-ExecutePythonScript=$script" -unattended -nosplash -nullrhi -log
        if ($LASTEXITCODE -eq 0 -and -not (Test-Path -LiteralPath $mapFile)) {
            throw "Editor exited without creating the map. Inspect Saved/Logs."
        }
    }
    "Package" {
        if (-not (Test-Path -LiteralPath $mapFile)) { throw "Build editor and CreateMap first." }
        $archive = Join-Path $projectRoot "Saved/Packages/$Configuration"
        & $uat BuildCookRun "-project=$projectFile" -noP4 -platform=Win64 "-clientconfig=$Configuration" -build -cook -stage -pak -iostore -archive "-archivedirectory=$archive" -utf8output
    }
}
if ($LASTEXITCODE -ne 0) { throw "$Mode failed with exit code $LASTEXITCODE; qualification remains unpassed." }
Write-Host "$Mode finished. This does not mark visual/performance qualification as passed."
