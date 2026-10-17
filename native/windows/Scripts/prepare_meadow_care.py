"""Finish Meadow care props in a separate editor process to bound peak memory."""
import json
from pathlib import Path
import unreal
p=Path(unreal.Paths.project_dir());a=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
unreal.get_default_object(unreal.load_class(None,"/Script/DataValidation.DataValidationSettings")).set_editor_property("bValidateOnSave",False)
ball=json.loads((p/'Saved/Qualification/two-island-care-setup.json').read_text(encoding='utf-8'))['toy_asset']
assert levels.load_level('/Game/Preview/P1_MeadowV2')
for actor in actors.get_all_level_actors():
    if isinstance(actor,unreal.RecastNavMesh): actor.set_editor_property('agent_height',110.)
existing=next((actor for actor in actors.get_all_level_actors() if actor.get_actor_label()=='P1 care toy'),None)
if existing is None:
    existing=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
    existing.set_actor_label('P1 care toy');existing.static_mesh_component.set_static_mesh(a.load_asset(ball))
    center,extent=existing.get_actor_bounds(False)
    existing.set_actor_location(unreal.Vector(50-center.x,-200-center.y,extent.z+3-center.z),False,False)
    existing.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
assert levels.save_current_level()
(p/'Saved/Qualification/meadow-care-setup.json').write_text(json.dumps({'status':'saved','toy':ball}),encoding='utf-8')
