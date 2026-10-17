"""Run inside UE's editor with TANGYUAN_SHOT_CONFIG pointing to local JSON.

Creates an isolated review level/sequence and records actual MRQ completion.
Private media and the Unreal project must stay outside the tracked repository.
Enable PythonScriptPlugin, EditorScriptingUtilities, SequencerScripting and
MovieRenderPipeline in the isolated .uproject. Launch the editor with
-ExecCmds="py /absolute/path/to/this.py" -unattended -RenderOffscreen.
Config requires fbx, motion, output and ground_texture; asset_folder and
frames_directory should be new revision names. This script replaces only its
review map/sequence. It does not certify engine-wide startup self-tests.
"""
import json
import math
import os
from pathlib import Path
import unreal as u

cfg=json.loads(Path(os.environ['TANGYUAN_SHOT_CONFIG']).read_text(encoding='utf-8'))
out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
report={'engine':u.SystemLibrary.get_engine_version(),'render_completed':False}
render_dir=out/cfg.get('frames_directory','ue-frames')
assets=u.AssetToolsHelpers.get_asset_tools()
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
levels=u.get_editor_subsystem(u.LevelEditorSubsystem)

def save_report():
    (out/'unreal-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

def constant_material(name,color,roughness=.85):
    path='/Game/Tangyuan/'+name
    m=u.load_asset(path) or assets.create_asset(name,'/Game/Tangyuan',u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(m)
    c=u.MaterialEditingLibrary.create_material_expression(m,u.MaterialExpressionConstant3Vector)
    c.set_editor_property('constant',u.LinearColor(*color,1))
    u.MaterialEditingLibrary.connect_material_property(c,'',u.MaterialProperty.MP_BASE_COLOR)
    r=u.MaterialEditingLibrary.create_material_expression(m,u.MaterialExpressionConstant)
    r.set_editor_property('r',roughness)
    u.MaterialEditingLibrary.connect_material_property(r,'',u.MaterialProperty.MP_ROUGHNESS)
    u.MaterialEditingLibrary.recompile_material(m)
    return m

def textured_material(name,texture,tiling=1):
    m=constant_material(name,(.2,.2,.2),.9)
    sample=u.MaterialEditingLibrary.create_material_expression(m,u.MaterialExpressionTextureSample)
    sample.texture=texture
    uv=u.MaterialEditingLibrary.create_material_expression(m,u.MaterialExpressionTextureCoordinate)
    uv.u_tiling=tiling;uv.v_tiling=tiling
    u.MaterialEditingLibrary.connect_material_expressions(uv,'',sample,'UVs')
    u.MaterialEditingLibrary.connect_material_property(sample,'RGB',u.MaterialProperty.MP_BASE_COLOR)
    spec=u.MaterialEditingLibrary.create_material_expression(m,u.MaterialExpressionConstant);spec.r=.18
    u.MaterialEditingLibrary.connect_material_property(spec,'',u.MaterialProperty.MP_SPECULAR)
    u.MaterialEditingLibrary.recompile_material(m)
    return m

try:
    u.SystemLibrary.execute_console_command(None,'Interchange.FeatureFlags.Import.FBX 0')
    asset_folder=cfg.get('asset_folder','/Game/Tangyuan/Character')
    task=u.AssetImportTask();task.filename=cfg['fbx'];task.destination_path=asset_folder;task.destination_name='Tangyuan'
    task.automated=True;task.replace_existing=True;task.save=True
    options=u.FbxImportUI();options.import_mesh=True;options.import_as_skeletal=True;options.import_animations=True
    options.import_materials=True;options.import_textures=True;options.automated_import_should_detect_type=False
    options.mesh_type_to_import=u.FBXImportType.FBXIT_SKELETAL_MESH
    options.anim_sequence_import_data.set_editor_property('use_default_sample_rate',False)
    options.anim_sequence_import_data.set_editor_property('custom_sample_rate',30)
    task.options=options;task.factory=u.FbxFactory()
    assets.import_asset_tasks([task])
    u.EditorAssetLibrary.save_directory(asset_folder,only_if_is_dirty=False,recursive=True)
    imported=[u.load_asset(path) for path in task.imported_object_paths]
    report['imported']=[{'path':o.get_path_name(),'class':o.get_class().get_name()} for o in imported if o]
    mesh=next((o for o in imported if isinstance(o,u.SkeletalMesh)),None)
    # Some importers omit animations from the task return list.
    all_assets=[u.load_asset(path) for path in u.EditorAssetLibrary.list_assets(asset_folder,recursive=True)]
    animation=next((o for o in all_assets if isinstance(o,u.AnimSequence)),None)
    if not mesh or not animation:raise RuntimeError('FBX did not produce a skeletal mesh and animation')
    report['animation']=animation.get_path_name();report['duration']=animation.sequence_length
    world=u.EditorLoadingAndSavingUtils.new_blank_map(False)
    if not u.EditorLoadingAndSavingUtils.save_map(world,'/Game/Tangyuan/MatchLevel'):
        raise RuntimeError('Could not create the isolated review map')
    pet=actors.spawn_actor_from_class(u.SkeletalMeshActor,u.Vector(0,0,0));pet.set_actor_label('Tangyuan matched from source video')
    comp=pet.skeletal_mesh_component;comp.set_skeletal_mesh_asset(mesh)
    comp.set_editor_property('visibility_based_anim_tick_option',u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
    comp.play_animation(animation,False);comp.set_position(0,False)
    for index,slot in enumerate(mesh.materials):
        if str(slot.material_slot_name)=='Material_001':
            texture=u.load_asset(asset_folder+'/Tangyuan-corrected-albedo')
            if not texture:raise RuntimeError('Corrected coat texture missing')
            comp.set_material(index,textured_material('TangyuanFilmCoat',texture))
    report['reference_bones']={name:[getattr(comp.get_socket_location(name),k) for k in ('x','y','z')] for name in ['head','FL_foot','FR_foot','HR_foot','tail']}
    report['materials']=[str(m.material_slot_name) for m in mesh.materials]
    save_report()
    if cfg.get('import_only'):
        levels.save_current_level();u.SystemLibrary.quit_editor()
    else:
        motion=json.loads(Path(cfg['motion']).read_text(encoding='utf-8'))
        plane=actors.spawn_actor_from_class(u.StaticMeshActor,u.Vector(0,0,-1))
        plane.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane'))
        plane.set_actor_scale3d(u.Vector(200,200,1))
        ground_task=u.AssetImportTask();ground_task.filename=cfg['ground_texture'];ground_task.destination_path='/Game/Tangyuan';ground_task.destination_name='SakuraSoil';ground_task.automated=True;ground_task.replace_existing=True;ground_task.save=True
        assets.import_asset_tasks([ground_task])
        plane.static_mesh_component.set_material(0,textured_material('ReviewGrass',u.load_asset('/Game/Tangyuan/SakuraSoil'),200))
        sun=actors.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,0,300),u.Rotator(-55,-35,0))
        sun.light_component.set_editor_property('intensity',3.5)
        sun.light_component.set_editor_property('light_source_angle',5)
        sky=actors.spawn_actor_from_class(u.SkyLight,u.Vector(0,0,250));sky.light_component.set_editor_property('intensity',.8)
        sky.light_component.set_editor_property('source_type',u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
        sky.light_component.set_cubemap(u.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap'))
        # A captured sky environment; explicit fill prevents an empty-world
        # skylight from being mistaken for imported broken black materials.
        actors.spawn_actor_from_class(u.SkyAtmosphere,u.Vector(0,0,0))
        fill=actors.spawn_actor_from_class(u.DirectionalLight,u.Vector(150,-150,230),u.Rotator(-65,140,0))
        fill.light_component.set_editor_property('intensity',1.2)
        fill.light_component.set_editor_property('cast_shadows',False)
        camera=actors.spawn_actor_from_class(u.CineCameraActor,u.Vector(0,0,0))
        first=motion['frames'][0];x,y,z=first['camera_position']
        camera.set_actor_location(u.Vector(x*100,-y*100,z*100),False,False)
        camera.set_actor_rotation(u.Rotator(-math.degrees(math.pi/2-first['camera_euler'][0]),-90,0),False)
        cc=camera.get_cine_camera_component();film=cc.filmback;film.sensor_width=20.25;film.sensor_height=36;cc.filmback=film
        cc.current_focal_length=32;cc.current_aperture=8
        focus=cc.focus_settings;focus.focus_method=u.CameraFocusMethod.DISABLE;cc.focus_settings=focus
        pp=cc.post_process_settings;pp.override_auto_exposure_method=True;pp.auto_exposure_method=u.AutoExposureMethod.AEM_MANUAL
        pp.override_auto_exposure_bias=True;pp.auto_exposure_bias=cfg.get('exposure',0)
        pp.override_auto_exposure_apply_physical_camera_exposure=True;pp.auto_exposure_apply_physical_camera_exposure=False
        pp.override_motion_blur_amount=True;pp.motion_blur_amount=0
        cc.post_process_settings=pp
        seq=u.load_asset('/Game/Tangyuan/MatchedTransition') or assets.create_asset('MatchedTransition','/Game/Tangyuan',u.LevelSequence,u.LevelSequenceFactoryNew())
        for binding in seq.get_bindings():binding.remove()
        for track in seq.get_tracks():seq.remove_track(track)
        # Exclude the inclusive FBX end key: otherwise UE wraps the animation
        # at precisely its duration, producing a one-frame teleport.
        frame_count=len(motion['frames'])-1
        seq.set_display_rate(u.FrameRate(30,1));seq.set_playback_start(0);seq.set_playback_end(frame_count)
        binding=seq.add_possessable(pet);section=binding.add_track(u.MovieSceneSkeletalAnimationTrack).add_section();section.set_range(0,frame_count)
        section.set_pre_roll_frames(32)
        params=section.params;params.animation=animation;section.params=params
        cb=seq.add_possessable(camera);transform=cb.add_track(u.MovieScene3DTransformTrack).add_section();transform.set_range(-32,len(motion['frames']))
        channels=transform.get_all_channels();cp=motion['camera']['position']
        for i,f in enumerate(motion['frames']):
            # Coordinate map is chosen from the imported reference-bone probe.
            x,y,z=f.get('camera_position',cp)
            values=[100*x,-100*y,100*z]+[0, -math.degrees(math.pi/2-f['camera_euler'][0]),-90]+[1,1,1]
            for channel,value in zip(channels,values):channel.add_key(u.FrameNumber(i),value,interpolation=u.MovieSceneKeyInterpolation.LINEAR)
            if i==0:
                for channel,value in zip(channels,values):channel.add_key(u.FrameNumber(-32),value,interpolation=u.MovieSceneKeyInterpolation.LINEAR)
        cut=seq.add_track(u.MovieSceneCameraCutTrack).add_section();cut.set_range(-32,frame_count)
        cut.set_camera_binding_id(seq.get_binding_id(cb))
        levels.save_current_level();u.EditorAssetLibrary.save_directory('/Game/Tangyuan',only_if_is_dirty=False,recursive=False)
        subsystem=u.get_editor_subsystem(u.MoviePipelineQueueSubsystem);queue=subsystem.get_queue();queue.delete_all_jobs()
        job=queue.allocate_new_job(u.MoviePipelineExecutorJob);job.job_name='Tangyuan_SourceMatch';job.map=u.SoftObjectPath('/Game/Tangyuan/MatchLevel');job.sequence=u.SoftObjectPath(seq.get_path_name())
        config=job.get_configuration();setting=config.find_or_add_setting_by_class(u.MoviePipelineOutputSetting)
        setting.output_directory=u.DirectoryPath(str(render_dir));setting.file_name_format='{frame_number}';setting.output_resolution=u.IntPoint(720,1280)
        setting.use_custom_frame_rate=True;setting.output_frame_rate=u.FrameRate(30,1)
        setting.zero_pad_frame_numbers=4
        config.find_or_add_setting_by_class(u.MoviePipelineDeferredPassBase);config.find_or_add_setting_by_class(u.MoviePipelineImageSequenceOutput_PNG)
        cvars=config.find_or_add_setting_by_class(u.MoviePipelineConsoleVariableSetting)
        cvars.add_or_update_console_variable('r.MotionBlurQuality',0)
        cvars.add_or_update_console_variable('r.DepthOfFieldQuality',0)
        aa=config.find_or_add_setting_by_class(u.MoviePipelineAntiAliasingSetting);aa.spatial_sample_count=4;aa.temporal_sample_count=1;aa.engine_warm_up_count=32;aa.render_warm_up_count=8
        aa.render_warm_up_frames=True
        aa.use_camera_cut_for_warm_up=True
        executor=u.MoviePipelinePIEExecutor()
        def finished(executor,success):
            report['render_completed']=bool(success);report['frame_count']=len(list(render_dir.glob('*.png')));report['frames_directory']=str(render_dir);save_report();u.SystemLibrary.quit_editor()
        def failed(executor,pipeline,fatal,error):
            report.setdefault('render_errors',[]).append(str(error));save_report()
        executor.on_executor_finished_delegate.add_callable_unique(finished)
        executor.on_executor_errored_delegate.add_callable_unique(failed)
        subsystem.render_queue_with_executor_instance(executor)
except Exception as error:
    report['error']=repr(error);save_report();u.log_error(str(error));u.SystemLibrary.quit_editor()
