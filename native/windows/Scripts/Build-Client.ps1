param(
    [Parameter(Mandatory=$true)][string]$EngineRoot,
    [ValidateSet("Generate", "Editor", "CreateMap", "ImportAsset", "ImportPet", "RepairFur", "RepairLighting", "Package")][string]$Mode = "Editor",
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
    "ImportAsset" {
        if (-not (Test-Path -LiteralPath $mapFile)) { throw "CreateMap first." }
        $importReport = Join-Path $projectRoot "Saved/Qualification/asset-import.json"
        if (Test-Path -LiteralPath $importReport) { throw "Import already recorded; inspect it rather than overwriting." }
        $script = Join-Path $projectRoot "Scripts/import_qualification_asset.py"
        & $editor $projectFile "-ExecutePythonScript=$script" -unattended -nosplash -nullrhi -log
        if ($LASTEXITCODE -eq 0) {
            if (-not (Test-Path -LiteralPath $importReport)) { throw "Import evidence is missing. Inspect Saved/Logs." }
            $result = Get-Content -LiteralPath $importReport -Raw | ConvertFrom-Json
            if ($result.status -ne "editor_import_saved" -or $result.static_meshes.Count -lt 1) {
                throw "Import did not produce verified static meshes."
            }
        }
    }
    "ImportPet" {
        if (-not (Test-Path -LiteralPath $mapFile)) { throw "CreateMap first." }
        $petReport = Join-Path $projectRoot "Saved/Qualification/pet-import.json"
        if (Test-Path -LiteralPath $petReport) { throw "Pet import already recorded; inspect it rather than overwriting." }
        $script = Join-Path $projectRoot "Scripts/import_qualification_pet.py"
        & $editor $projectFile "-ExecutePythonScript=$script" -unattended -nosplash -nullrhi -log
        if ($LASTEXITCODE -eq 0) {
            if (-not (Test-Path -LiteralPath $petReport)) { throw "Pet import evidence missing. Inspect Saved/Logs." }
            $result = Get-Content -LiteralPath $petReport -Raw | ConvertFrom-Json
            if ($result.status -ne "editor_import_saved" -or $result.skeletal_meshes.Count -lt 1 -or $result.animations.Count -lt 1) {
                throw "Import did not produce skeletal meshes and animations."
            }
        }
    }
    "RepairFur" {
        $furReport = Join-Path $projectRoot "Saved/Qualification/fur-material-repair.json"
        if (Test-Path -LiteralPath $furReport) { throw "Fur repair already recorded; inspect existing evidence." }
        $script = Join-Path $projectRoot "Scripts/repair_qualification_fur.py"
        & $editor $projectFile "-ExecutePythonScript=$script" -unattended -nosplash -nullrhi -stdout
        if ($LASTEXITCODE -eq 0) {
            if (-not (Test-Path -LiteralPath $furReport)) { throw "Fur repair evidence missing. Inspect Saved/Logs." }
            $result = Get-Content -LiteralPath $furReport -Raw | ConvertFrom-Json
            if ($result.status -ne "saved_requires_cook_and_visual_review") { throw "Fur repair did not save." }
        }
    }
    "RepairLighting" {
        if (-not (Test-Path -LiteralPath $mapFile)) { throw "CreateMap and ImportAsset first." }
        foreach ($step in @(
            @{Script="repair_qualification_lighting.py"; Report="lighting-repair.json"; Status="candidate_saved_requires_runtime_review"},
            @{Script="repair_qualification_glass.py"; Report="thin-glass-repair.json"; Status="saved_requires_cook_and_visual_review"}
        )) {
            $started = [DateTime]::UtcNow
            $script = Join-Path $projectRoot "Scripts/$($step.Script)"
            $evidence = Join-Path $projectRoot "Saved/Qualification/$($step.Report)"
            & $editor $projectFile "-ExecutePythonScript=$script" -unattended -nosplash -nullrhi -stdout
            if ($LASTEXITCODE -ne 0) { throw "Lighting editor step failed: $($step.Script)" }
            # UE can exit zero after a Python exception: require fresh success evidence.
            if (-not (Test-Path -LiteralPath $evidence) -or (Get-Item -LiteralPath $evidence).LastWriteTimeUtc -lt $started) {
                throw "Fresh lighting evidence missing: $($step.Script)"
            }
            $result = Get-Content -LiteralPath $evidence -Raw | ConvertFrom-Json
            if ($result.status -ne $step.Status) { throw "Lighting fixture did not save." }
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
