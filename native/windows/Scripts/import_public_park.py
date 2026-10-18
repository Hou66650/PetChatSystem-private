"""Import the shared Web/Harmony park verbatim; never rebuild the original islands."""
import hashlib
import json
from pathlib import Path
import unreal

p=Path(unreal.Paths.project_dir())
a=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
pipeline=unreal.InterchangeGenericAssetsPipeline()
for key,value in [('build_nanite',False),('generate_lightmap_u_vs',False),('collision',False)]:
    pipeline.mesh_pipeline.set_editor_property(key,value)
for key in ('recompute_normals','recompute_tangents','use_mikk_t_space'):
    pipeline.common_meshes_properties.set_editor_property(key,False)
stack=unreal.InterchangePipelineStackOverride();stack.override_pipelines=[unreal.SoftObjectPath(pipeline.get_path_name())]
unreal.get_default_object(unreal.load_class(None,'/Script/DataValidation.DataValidationSettings')).set_editor_property('bValidateOnSave',False)
report={'source_revision':'c077b62','source':'Web/Harmony paw-commons-v2','redesigned':False,'assets':{}}
imports={}
for tier in ('play','preview'):
    source=p/'Saved/Art/PawCommons'/f'{tier}.glb'
    dest='/Game/Imported/P2Park/'+tier
    if not a.does_directory_exist(dest):
        task=unreal.AssetImportTask();task.filename=str(source);task.destination_path=dest;task.automated=True;task.save=True;task.options=stack
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    meshes=[a.load_asset(x) for x in a.list_assets(dest,recursive=True) if str(a.find_asset_data(x).asset_class_path.asset_name)=='StaticMesh']
    assert meshes
    for mesh in meshes:
        body=mesh.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        body.set_editor_property('double_sided_geometry',True)
        for i in range(mesh.get_num_sections(0)):me.enable_section_collision(mesh,True,0,i)
    a.save_directory(dest,only_if_is_dirty=True,recursive=True)
    imports[tier]=meshes
    report['assets'][tier]={'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'meshes':[m.get_path_name() for m in meshes]}

target='/Game/Preview/P2_Park'
assert levels.load_level(target) if a.does_asset_exist(target) else levels.new_level_from_template(target,'/Game/Preview/P2_IslandHome')
for actor in actors.get_all_level_actors():
    if isinstance(actor,(unreal.StaticMeshActor,unreal.SkeletalMeshActor,unreal.NavMeshBoundsVolume,unreal.RecastNavMesh)):
        actors.destroy_actor(actor)
for mesh in imports['play']:
    actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
    actor.set_actor_label('Paw Commons '+mesh.get_name());actor.tags=[unreal.Name('ParkGround')]
    c=actor.static_mesh_component;c.set_static_mesh(mesh);c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
assert levels.save_current_level()

# Reposition the four existing previews without modifying their meshes or life maps.
assert levels.load_level('/Game/Preview/P2_IslandHome')
old={'Sakura':(-1450,-1300,-100),'Snow':(1450,1400,0),'Meadow':(-1450,1400,-100),'Camp':(1450,-1300,-100)}
new={'Sakura':(-2700,-350,-100),'Snow':(-1300,-2300,0),'Meadow':(1300,-2300,-100),'Camp':(2700,-350,-100)}
already=any('HomePark' in [str(t) for t in act.tags] for act in actors.get_all_level_actors())
if not already:
    for actor in actors.get_all_level_actors():
        for key in old:
            if 'Home'+key in [str(t) for t in actor.tags]:
                delta=unreal.Vector(*(new[key][i]-old[key][i] for i in range(3)))
                actor.set_actor_location(actor.get_actor_location()+delta,False,False)
    for mesh in imports['preview']:
        actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,1900,0))
        actor.set_actor_label('Home Park '+mesh.get_name());actor.tags=[unreal.Name('HomePark')]
        actor.set_actor_scale3d(unreal.Vector(.85,.85,.85))
        c=actor.static_mesh_component;c.set_static_mesh(mesh);c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
assert levels.save_current_level()
report['map']=target
(p/'Saved/Qualification/public-park-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('PAIT_PARK_IMPORTED')
