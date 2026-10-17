"""Read-only inspection of P0 material bindings, including actor overrides."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if not levels.load_level("/Game/Qualification/P0_Lighting"):
    raise RuntimeError("P0 map missing")
records = []
for actor in actors.get_all_level_actors():
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if component is None:
        continue
    mesh = component.get_editor_property("skeletal_mesh_asset")
    if not mesh or not mesh.get_path_name().startswith("/Game/Imported/P0Cat/"):
        continue
    slots = mesh.get_editor_property("materials")
    records.append({
        "mesh": mesh.get_path_name(),
        "asset_materials": [s.get_editor_property("material_interface").get_path_name() for s in slots],
        "component_materials": [component.get_material(i).get_path_name() for i in range(component.get_num_materials())],
        "override_materials": [m.get_path_name() if m else None for m in component.get_editor_property("override_materials")],
    })
if len(records) != 3:
    raise RuntimeError("Expected three P0 cat layers")
out = Path(unreal.Paths.project_dir()) / "Saved/Qualification/material-bindings.json"
out.write_text(json.dumps({"cat_layers": records}, indent=2), encoding="utf-8")
