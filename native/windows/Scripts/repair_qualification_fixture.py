"""Apply known P0 fixture fixes only; never edit other maps or asset directories."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
if not levels.load_level("/Game/Qualification/P0_Lighting"):
    raise RuntimeError("Missing P0 fixture")
changed = []
for actor in actors.get_all_level_actors():
    label = actor.get_actor_label()
    if label.startswith("P0 imported "):
        mesh = actor.static_mesh_component.static_mesh
        if not mesh.get_path_name().startswith("/Game/Imported/P0Architecture/"):
            raise RuntimeError("Unexpected mesh in isolated fixture")
        settings = mesh_editor.get_nanite_settings(mesh)
        settings.set_editor_property("enabled", False)
        mesh_editor.set_nanite_settings(mesh, settings, True)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        changed.append(mesh.get_path_name())
    elif label.startswith("P0 shadow fixture "):
        i = int(label.rsplit(" ", 1)[1])
        actor.set_actor_location(unreal.Vector(*[(-1400, 0, 100), (-1400, 300, 75), (-1400, -300, 150)][i]), False, False)
    elif label.startswith("P0 standard cat skeletal fixture "):
        actor.set_actor_location(unreal.Vector(-500, 400, 0), False, False)
if len(changed) != 7 or not levels.save_current_level():
    raise RuntimeError("Fixture fix did not update the expected seven meshes and map")
out = Path(unreal.Paths.project_dir()) / "Saved/Qualification/fixture-repair.json"
out.write_text(json.dumps({"status": "saved", "nanite_disabled_meshes": changed}, indent=2), encoding="utf-8")
