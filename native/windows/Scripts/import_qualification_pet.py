"""UE editor-only standard cat import; no private models or production APIs.

Run after P0 map creation. Saved animation is a fixture, not the pet Agent.
"""
import hashlib
import json
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir())
source = project.parents[1] / "static/models/petchat-cat-v3/cat.glb"
expected = "dca73dc58ffd5e3aa4b52a86eeefeebd6621d30a3e695fe540d5892250e901db"
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise RuntimeError("Standard cat changed; qualify a new source explicitly")
destination = "/Game/Imported/P0Cat"
assets = unreal.EditorAssetLibrary
if assets.does_directory_exist(destination):
    raise RuntimeError("Cat destination exists; inspect rather than overwrite it")
task = unreal.AssetImportTask()
task.filename = str(source)
task.destination_path = destination
task.automated = True
task.replace_existing = False
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
objects = task.get_objects()
meshes = [obj for obj in objects if isinstance(obj, unreal.SkeletalMesh)]
animations = [obj for obj in objects if isinstance(obj, unreal.AnimSequence)]
if not meshes or not animations:
    raise RuntimeError("Import lacks skeletal mesh or animation sequences")
idle = next((obj for obj in animations if "idle_breathe" in obj.get_name().lower()), None)
if idle is None:
    raise RuntimeError("Expected idle_breathe animation was not imported")
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level("/Game/Qualification/P0_Lighting"):
    raise RuntimeError("P0 fixture missing")
records = []
for index, mesh in enumerate(meshes):
    actor = actors.spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(-500, 400, 0))
    actor.set_actor_label("P0 standard cat skeletal fixture " + str(index))
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    component.set_skeletal_mesh_asset(mesh)
    # PlayAnimation is transient. OverrideAnimationData persists playback in Cook.
    component.override_animation_data(idle, True, True, 0.0, 1.0)
    records.append(mesh.get_path_name())
if not levels.save_current_level():
    raise RuntimeError("Could not save cat fixture map")
if not assets.save_directory(destination, only_if_is_dirty=True, recursive=True):
    raise RuntimeError("Could not save imported cat assets")
report = {"source": "static/models/petchat-cat-v3/cat.glb", "source_sha256": expected,
          "skeletal_meshes": records, "animations": [obj.get_path_name() for obj in animations],
          "fixture_animation": idle.get_path_name(), "status": "editor_import_saved",
          "runtime_animation_qualified": False, "pet_agent_implemented": False}
out = project / "Saved/Qualification/pet-import.json"
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
unreal.log("PAIT_P0_PET_IMPORTED " + str(len(animations)))
