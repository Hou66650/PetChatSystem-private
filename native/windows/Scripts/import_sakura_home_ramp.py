"""Install Blender-made accessible shelter ramp into the isolated Sakura map."""
from pathlib import Path
import json
import unreal

p=Path(unreal.Paths.project_dir());a=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
unreal.get_default_object(unreal.load_class(None,'/Script/DataValidation.DataValidationSettings')).set_editor_property('bValidateOnSave',False)
dest='/Game/Imported/P1SakuraHomeRamp'
if not a.does_directory_exist(dest):
    task=unreal.AssetImportTask();task.filename=str(p/'Saved/Art/P1SakuraHomeRamp/sakura-home-ramp.glb')
    task.destination_path=dest;task.automated=True;task.save=True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
meshes=[a.load_asset(x) for x in a.list_assets(dest,recursive=True) if str(a.find_asset_data(x).asset_class_path.asset_name)=='StaticMesh']
assert len(meshes)==1
m=meshes[0];body=m.get_editor_property('body_setup')
body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
body.set_editor_property('double_sided_geometry',True)
for i in range(m.get_num_sections(0)):me.enable_section_collision(m,True,0,i)
a.save_loaded_asset(m,only_if_is_dirty=False)
assert levels.load_level('/Game/Preview/P1_SakuraV2')
for old in actors.get_all_level_actors():
    if old.get_actor_label()=='Sakura shelter accessible ramp':actors.destroy_actor(old)
actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(160,-550,0))
actor.set_actor_label('Sakura shelter accessible ramp');c=actor.static_mesh_component;c.set_static_mesh(m)
c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
actor.tags=[unreal.Name('PaitGround')]
assert levels.save_current_level()
(p/'Saved/Qualification/sakura-home-ramp.json').write_text(json.dumps({'status':'saved_requires_runtime_check','mesh':m.get_path_name(),'rise_cm':23,'length_cm':113}),encoding='utf-8')
