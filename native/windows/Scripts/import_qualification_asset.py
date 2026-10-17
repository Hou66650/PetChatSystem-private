"""Import a hash-pinned public source into the isolated P0 fixture, inside UE Python.

This proves editor import/cooking only, not runtime UGC loading or final art quality.
"""
import hashlib
import json
import os
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir())
inventory = json.loads((project / "Qualification/meadow-source-inventory.json").read_text(encoding="utf-8"))
reference = next(r for r in inventory["references"] if r["source"].endswith("/architecture.glb"))
source = Path(os.environ.get("PAIT_SOURCE_ROOT", r"D:\PetChatSystem")) / reference["source"]
digest = hashlib.sha256(source.read_bytes()).hexdigest()
if digest != reference["sha256"]:
    raise RuntimeError("Source differs from the frozen public P0 inventory")
destination = "/Game/Imported/P0Architecture"
if unreal.EditorAssetLibrary.does_directory_exist(destination):
    raise RuntimeError("Import destination exists; inspect it instead of overwriting authored assets")
task = unreal.AssetImportTask()
task.filename = str(source)
task.destination_path = destination
task.automated = True
task.replace_existing = False
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
objects = task.get_objects()
meshes = [asset for asset in objects if isinstance(asset, unreal.StaticMesh)]
if not meshes:
    raise RuntimeError("GLB import produced no static meshes")
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level("/Game/Qualification/P0_Lighting"):
    raise RuntimeError("P0 fixture map is missing")
records = []
mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
for mesh in meshes:
    # Explicit conventional baseline. Nanite needs separate per-material qualification.
    nanite = mesh_editor.get_nanite_settings(mesh)
    nanite.set_editor_property("enabled", False)
    mesh_editor.set_nanite_settings(mesh, nanite, True)
    bounds = mesh.get_bounds()
    extent = bounds.box_extent
    if max(extent.x, extent.y, extent.z) <= 0:
        raise RuntimeError("Empty imported bounds: " + mesh.get_name())
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, 0))
    actor.set_actor_label("P0 imported " + mesh.get_name())
    actor.static_mesh_component.set_static_mesh(mesh)
    records.append({"asset": mesh.get_path_name(), "bounds_extent_cm": [extent.x, extent.y, extent.z],
                    "materials": [str(m.material_interface.get_path_name()) if m.material_interface else None
                                  for m in mesh.static_materials]})
if not levels.save_current_level():
    raise RuntimeError("Imported fixture map could not be saved")
if not unreal.EditorAssetLibrary.save_directory(destination, only_if_is_dirty=True, recursive=True):
    raise RuntimeError("Imported content could not be saved")
out = project / "Saved/Qualification/asset-import.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"source": str(source), "source_sha256": digest, "static_meshes": records,
                          "status": "editor_import_saved", "material_visual_qualified": False,
                          "runtime_ugc_qualified": False}, indent=2) + "\n", encoding="utf-8")
unreal.log("PAIT_P0_ASSET_IMPORTED " + str(len(meshes)))
