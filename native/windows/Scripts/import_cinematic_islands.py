"""UE import of the already approved Snow/Camp exports. No art regeneration.
Pass -PaitCamp for Camp. Run on /Engine/Maps/Entry with ExecutePythonScript.
"""
import gc
import hashlib
import json
from pathlib import Path
import unreal

p=Path(unreal.Paths.project_dir())
camp='-PaitCamp' in unreal.SystemLibrary.get_command_line()
theme='camp' if camp else 'snow'
name='Camp' if camp else 'Snow'
source=p/'Saved/Art/CinematicIslands'/theme
manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
map_path='/Game/Preview/P1_'+name+'V2'
namespace='/Game/Imported/P1'+name+'V2'
a=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
unreal.get_default_object(unreal.load_class(None,'/Script/DataValidation.DataValidationSettings')).set_editor_property('bValidateOnSave',False)
report_file=p/'Saved/Qualification'/('cinematic-'+theme+'-import.json')
if a.does_asset_exist(map_path):
    assert levels.load_level(map_path)
else:
    assert levels.new_level_from_template(map_path,'/Game/Qualification/P0_Lighting')
for actor in actors.get_all_level_actors():
    if isinstance(actor,(unreal.StaticMeshActor,unreal.SkeletalMeshActor,unreal.NavMeshBoundsVolume,unreal.RecastNavMesh,unreal.VolumetricCloud)):
        actors.destroy_actor(actor)
    elif isinstance(actor,unreal.DirectionalLight):
        actor.set_actor_rotation(unreal.Rotator(pitch=-38,yaw=-45,roll=0),False)
        actor.light_component.set_editor_property('light_source_angle',2.)
    elif isinstance(actor,unreal.SkyLight):
        actor.light_component.set_editor_property('intensity',1.5)
        actor.light_component.set_editor_property('lower_hemisphere_is_black',False)
    elif isinstance(actor,unreal.PostProcessVolume):
        settings=actor.get_editor_property('settings')
        settings.set_editor_property('auto_exposure_min_brightness',12.5)
        settings.set_editor_property('auto_exposure_max_brightness',12.5)
        actor.set_editor_property('settings',settings)
pipeline=unreal.InterchangeGenericAssetsPipeline()
for key,value in [('build_nanite',False),('generate_lightmap_u_vs',False),('distance_field_resolution_scale',0.),('max_lumen_mesh_cards',0),('collision',False)]:
    pipeline.mesh_pipeline.set_editor_property(key,value)
for key in ('recompute_normals','recompute_tangents','use_mikk_t_space'):
    pipeline.common_meshes_properties.set_editor_property(key,False)
pipeline.material_pipeline.texture_pipeline.set_editor_property('allow_non_power_of_two',True)
stack=unreal.InterchangePipelineStackOverride();stack.override_pipelines=[unreal.SoftObjectPath(pipeline.get_path_name())]
report={'map':map_path,'source_master_sha256':manifest['masterSha256'],'modules':[],'status':'importing','redesigned':False}
for entry in manifest['modules']:
    file=source/Path(entry['file']).name
    assert hashlib.sha256(file.read_bytes()).hexdigest()==entry['sha256']
    dest=namespace+'/'+file.stem.replace('-','_')
    meshes=[]
    if a.does_directory_exist(dest):
        meshes=[a.load_asset(x) for x in a.list_assets(dest,recursive=True) if str(a.find_asset_data(x).asset_class_path.asset_name)=='StaticMesh']
    if not meshes:
        task=unreal.AssetImportTask();task.filename=str(file);task.destination_path=dest;task.automated=True;task.save=True;task.options=stack
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        meshes=[m for m in task.get_objects() if isinstance(m,unreal.StaticMesh)]
    assert meshes,file
    for mesh in meshes:
        label=mesh.get_name();lower=label.lower()
        actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
        actor.set_actor_label(name+' refined '+label)
        c=actor.static_mesh_component;c.set_static_mesh(mesh)
        ground=any(t in lower for t in ('natural_moss_and_soil','snow_grains','weathered_mineral_stone','aged_oiled_timber')) and file.stem=='landscape'
        solid=ground or any(t in lower for t in ('timber','wood','bark','iron','slate'))
        if solid:
            body=mesh.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            body.set_editor_property('double_sided_geometry',True)
            for i in range(mesh.get_num_sections(0)):me.enable_section_collision(mesh,True,0,i)
            c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
            actor.tags=[unreal.Name('PaitGround' if ground else 'PaitSolid')]
        else:c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        if file.stem=='vegetation':c.set_cast_shadow(False)
        # Keep original geometry. Transparent snow/ice/water stay conventional.
        a.save_loaded_asset(mesh,only_if_is_dirty=True)
    assert a.save_directory(dest,only_if_is_dirty=True,recursive=True)
    report['modules'].append({'file':file.name,'sha256':entry['sha256'],'meshes':[m.get_path_name() for m in meshes]})
    assert levels.save_current_level()
    report_file.write_text(json.dumps(report,indent=2),encoding='utf-8')
    gc.collect();unreal.SystemLibrary.collect_garbage()
pet='shepherd' if camp else 'xueqiu'
pet_source=p.parents[1]/('static/models/petchat-shepherd-v2/shepherd.glb' if camp else 'static/models/petchat-husky-v3/xueqiu.glb')
pet_dest='/Game/Imported/'+('P1Shepherd' if camp else 'P1Husky')
if not a.does_directory_exist(pet_dest):
    task=unreal.AssetImportTask();task.filename=str(pet_source);task.destination_path=pet_dest;task.automated=True;task.save=True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
objects=[a.load_asset(x) for x in a.list_assets(pet_dest,recursive=True) if str(a.find_asset_data(x).asset_class_path.asset_name) in ('SkeletalMesh','AnimSequence')]
skins=[o for o in objects if isinstance(o,unreal.SkeletalMesh)]
anims=[o for o in objects if isinstance(o,unreal.AnimSequence)]
idle=next((o for o in anims if o.get_name().endswith('idle_breathe')),anims[0] if anims else None)
assert skins and idle
fur=a.load_asset('/Game/Qualification/Materials/M_P0_CatFurVertexColor')
for mesh in skins:
    if 'fur' in mesh.get_name().lower():
        slots=mesh.materials
        for i in range(len(slots)):slot=slots[i];slot.material_interface=fur;slots[i]=slot
        mesh.materials=slots;a.save_loaded_asset(mesh,only_if_is_dirty=True)
    actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,-250,30))
    actor.set_actor_label(name+' native '+pet);c=actor.skeletal_mesh_component;c.set_skeletal_mesh_asset(mesh)
    c.override_animation_data(idle,True,True,0.,1.);c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
volume=actors.spawn_actor_from_class(unreal.NavMeshBoundsVolume,unreal.Vector(0,0,200))
_,extent=volume.get_actor_bounds(False);assert min(extent.x,extent.y,extent.z)>1
volume.set_actor_scale3d(unreal.Vector(1600/extent.x,1600/extent.y,700/extent.z))
nav=actors.spawn_actor_from_class(unreal.RecastNavMesh,unreal.Vector())
nav.set_editor_property('runtime_generation',unreal.RuntimeGenerationType.DYNAMIC)
nav.set_editor_property('agent_radius',35.);nav.set_editor_property('agent_height',110.)
cloud=actors.spawn_actor_from_class(unreal.VolumetricCloud,unreal.Vector())
component=cloud.get_component_by_class(unreal.VolumetricCloudComponent)
component.set_editor_property('material',a.load_asset('/Game/Preview/Materials/MI_MeadowCloudSea'))
component.set_editor_property('layer_bottom_altitude',.8);component.set_editor_property('layer_height',.9)
assert a.save_directory(pet_dest,only_if_is_dirty=True,recursive=True)
assert levels.save_current_level()
report.update(status='saved_requires_runtime_review',pet_meshes=[o.get_path_name() for o in skins],animations=[o.get_path_name() for o in anims])
report_file.write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('CINEMATIC_ISLAND_IMPORTED '+theme)
