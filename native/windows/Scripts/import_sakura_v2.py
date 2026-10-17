"""Import the reviewed Sakura master into a separate native map; resumable assets.
Never writes original .blend, web resources, account data or the Meadow map.
"""
import gc, hashlib, json
from pathlib import Path
import unreal
unreal.get_default_object(unreal.load_class(None,"/Script/DataValidation.DataValidationSettings")).set_editor_property("bValidateOnSave", False)
def main():
    project=Path(unreal.Paths.project_dir())
    source=project/'Saved/Art/P1SakuraV2Chunks'
    manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_sha256']=='88eb4d3fd808cb1b1f4fdb0935cd9f211634aea12bac1b7f4c626c68b8a93e86'
    a=unreal.EditorAssetLibrary
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    map_path='/Game/Preview/P1_SakuraV2'
    if a.does_asset_exist(map_path):
        assert levels.load_level(map_path)
    else:
        assert levels.new_level_from_template(map_path,'/Game/Qualification/P0_Lighting')
    # Only this generated scene is rebuilt; imported assets can resume module by module.
    for actor in actors.get_all_level_actors():
        if isinstance(actor,(unreal.StaticMeshActor,unreal.SkeletalMeshActor,unreal.NavMeshBoundsVolume,unreal.RecastNavMesh)):
            actors.destroy_actor(actor)
        elif isinstance(actor,unreal.PlayerStart): actor.set_actor_location(unreal.Vector(0,800,150),False,False)
    pipeline=unreal.InterchangeGenericAssetsPipeline()
    for key,value in [('build_nanite',False),('generate_lightmap_u_vs',False),('distance_field_resolution_scale',0.),('max_lumen_mesh_cards',0),('collision',False)]:
        pipeline.mesh_pipeline.set_editor_property(key,value)
    for key in ['recompute_normals','recompute_tangents','use_mikk_t_space']:
        pipeline.common_meshes_properties.set_editor_property(key,False)
    pipeline.material_pipeline.texture_pipeline.set_editor_property('allow_non_power_of_two',True)
    stack=unreal.InterchangePipelineStackOverride()
    stack.override_pipelines=[unreal.SoftObjectPath(pipeline.get_path_name())]
    report={'map':map_path,'source_sha256':manifest['source_sha256'],'modules':[],'colliders':[],'status':'importing'}
    ground_tokens=('Natural_moss_and_soil','Weathered_mineral_stone','Dressed_limestone','Terrain_V2_mossy','Terrain_V2_warm','Crafted_structures_V2_warm','Crafted_structures_V2_aged','Companion_detail_V2_muted')
    solid_tokens=('timber','wood','bark','iron','granite','basalt','roof','ceramic','glaze','chestnut','brass')
    new_imports=0
    for mod in manifest['modules']:
        f=source/mod['file']; assert hashlib.sha256(f.read_bytes()).hexdigest()==mod['sha256']
        dest='/Game/Imported/P1SakuraV2/'+f.stem.replace('-','_')
        meshes=[]
        if a.does_directory_exist(dest):
            meshes=[a.load_asset(p) for p in a.list_assets(dest,recursive=True) if str(a.find_asset_data(p).asset_class_path.asset_name)=='StaticMesh']
        if not meshes:
            new_imports+=1
            task=unreal.AssetImportTask();task.filename=str(f);task.destination_path=dest
            task.automated=True;task.save=True;task.options=stack
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            meshes=[o for o in task.get_objects() if isinstance(o,unreal.StaticMesh)]
        assert meshes, f.name
        for mesh in meshes:
            name=mesh.get_name();actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector())
            actor.set_actor_label('Sakura V2 '+name);c=actor.static_mesh_component;c.set_static_mesh(mesh)
            ground=any(t in name for t in ground_tokens)
            solid=ground or any(t in name.lower() for t in solid_tokens)
            if solid:
                body=mesh.get_editor_property('body_setup')
                if body.get_editor_property('collision_trace_flag')!=unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
                    body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                    body.set_editor_property('double_sided_geometry',True)
                    for i in range(mesh.get_num_sections(0)): me.enable_section_collision(mesh,True,0,i)
                c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
                actor.tags=[unreal.Name('PaitGround' if ground else 'PaitSolid')]
                report['colliders'].append({'name':name,'ground':ground})
            else: c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            # Tiny anthers/calyxes are retained but do not cast millions of VSM shadows.
            if any(t in name for t in ('anther','pollen','calyx','grass','living_moss')): c.set_cast_shadow(False)
            # Preserve conventional transparent water. Opaque blossom geometry can
            # use Nanite without the transparent foliage fallback seen on Meadow.
            if 'Cherry_ecology' in name and any(t in name for t in ('petal','anther','calyx')):
                settings=me.get_nanite_settings(mesh);settings.enabled=True;me.set_nanite_settings(mesh,settings,False)
            a.save_loaded_asset(mesh,only_if_is_dirty=True)
        assert a.save_directory(dest,only_if_is_dirty=True,recursive=True)
        assert levels.save_current_level()
        report['modules'].append({'file':mod['file'],'meshes':[m.get_path_name() for m in meshes]})
        (project/'Saved/Qualification/sakura-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        unreal.log('SAKURA_IMPORTED '+f.name)
        meshes=[];task=None;gc.collect();unreal.SystemLibrary.collect_garbage()
        if new_imports>=6:
            report['status']='checkpoint_continue'
            (project/'Saved/Qualification/sakura-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            unreal.log('SAKURA_CHECKPOINT_SAVED')
            return
    # Same rig contract as native cat, but actual authored Shiba mesh and animations.
    pet_source=project.parents[1]/'static/models/petchat-shiba-v4/qiuqiu.glb'
    pet_dest='/Game/Imported/P1Shiba'
    if not a.does_directory_exist(pet_dest):
        task=unreal.AssetImportTask();task.filename=str(pet_source);task.destination_path=pet_dest;task.automated=True;task.save=True
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    pet_objects=[a.load_asset(p) for p in a.list_assets(pet_dest,recursive=True) if str(a.find_asset_data(p).asset_class_path.asset_name) in ('SkeletalMesh','AnimSequence')]
    pet_meshes=[o for o in pet_objects if isinstance(o,unreal.SkeletalMesh)]
    anims=[o for o in pet_objects if isinstance(o,unreal.AnimSequence)]
    idle=next(o for o in anims if o.get_name().endswith('idle_breathe'))
    fur=a.load_asset('/Game/Qualification/Materials/M_P0_CatFurVertexColor')
    for mesh in pet_meshes:
        if 'fur' in mesh.get_name().lower():
            slots=mesh.materials
            for i in range(len(slots)):
                slot=slots[i];slot.material_interface=fur;slots[i]=slot
            mesh.materials=slots;a.save_loaded_asset(mesh,only_if_is_dirty=True)
        actor=actors.spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector(0,800,20))
        actor.set_actor_label('Sakura native Shiba '+mesh.get_name());c=actor.skeletal_mesh_component
        c.set_skeletal_mesh_asset(mesh);c.override_animation_data(idle,True,True,0.,1.)
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    report['pet_meshes']=[m.get_path_name() for m in pet_meshes]
    report['animations']=[m.get_path_name() for m in anims]
    volume=actors.spawn_actor_from_class(unreal.NavMeshBoundsVolume,unreal.Vector(0,-500,300))
    volume.set_actor_label('Sakura navigation bounds');_,extent=volume.get_actor_bounds(False)
    assert min(extent.x,extent.y,extent.z)>1
    volume.set_actor_scale3d(unreal.Vector(5000/extent.x,5000/extent.y,1400/extent.z))
    nav=actors.spawn_actor_from_class(unreal.RecastNavMesh,unreal.Vector())
    nav.set_editor_property('runtime_generation',unreal.RuntimeGenerationType.DYNAMIC)
    nav.set_editor_property('agent_radius',35.);nav.set_editor_property('agent_height',110.)
    cloud=actors.spawn_actor_from_class(unreal.VolumetricCloud,unreal.Vector())
    c=cloud.get_component_by_class(unreal.VolumetricCloudComponent)
    c.set_editor_property('material',a.load_asset('/Game/Preview/Materials/MI_MeadowCloudSea'));c.set_editor_property('layer_bottom_altitude',.8);c.set_editor_property('layer_height',.9)
    assert levels.save_current_level()
    assert a.save_directory(pet_dest,only_if_is_dirty=True,recursive=True)
    report['status']='saved_requires_runtime_review';report['production_data_access']=False
    (project/'Saved/Qualification/sakura-import.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    unreal.log('SAKURA_NATIVE_COMPLETE')
main()
