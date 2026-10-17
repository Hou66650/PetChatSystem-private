"""Render a separate establishing still of the saved, verified Sakura level.

Uses the same TANGYUAN_SHOT_CONFIG as the matched shot. This is a layout still,
not a claimed continuation of the video camera. No existing sequence is edited.
"""
import json
import os
import uuid
from pathlib import Path
import unreal as u

cfg=json.loads(Path(os.environ['TANGYUAN_SHOT_CONFIG']).read_text(encoding='utf-8'))
out=Path(cfg['output']);frames=out/cfg.get('overview_frames_directory','overview-frames')
if frames.exists() and any(frames.glob('*.png')):raise ValueError('Overview output already exists')
report={'render_completed':False,'engine':u.SystemLibrary.get_engine_version(),'kind':'separate layout still'}
def save():
    (out/'overview-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
save()
try:
    u.SystemLibrary.execute_console_command(None,'r.Nanite 0')
    levels=u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level('/Game/Tangyuan/'+cfg['map_name']):raise RuntimeError('Matched island level unavailable')
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    name='SakuraOverview_'+uuid.uuid4().hex[:8]
    map_path='/Game/Tangyuan/'+name+'Level'
    if not u.EditorLoadingAndSavingUtils.save_map(world,map_path):raise RuntimeError('Could not create overview map')
    if not levels.load_level(map_path):raise RuntimeError('Could not load the overview copy')
    report['map']=map_path
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    camera=next(o for o in actors.get_all_level_actors() if isinstance(o,u.CineCameraActor))
    camera.set_actor_location(u.Vector(1400,1700,1200),False,False)
    rotation=u.MathLibrary.find_look_at_rotation(camera.get_actor_location(),u.Vector(300,0,-180))
    camera.set_actor_rotation(rotation,False)
    cc=camera.get_cine_camera_component();film=cc.filmback;film.sensor_width=36;film.sensor_height=20.25;cc.filmback=film;cc.current_focal_length=32
    assets=u.AssetToolsHelpers.get_asset_tools()
    seq=u.load_asset('/Game/Tangyuan/'+name) or assets.create_asset(name,'/Game/Tangyuan',u.LevelSequence,u.LevelSequenceFactoryNew())
    for binding in seq.get_bindings():binding.remove()
    for track in seq.get_tracks():seq.remove_track(track)
    seq.set_display_rate(u.FrameRate(30,1));seq.set_playback_start(0);seq.set_playback_end(1)
    cb=seq.add_possessable(camera);transform=cb.add_track(u.MovieScene3DTransformTrack).add_section();transform.set_range(-32,1)
    values=[1400,1700,1200,rotation.roll,rotation.pitch,rotation.yaw,1,1,1]
    for channel,value in zip(transform.get_all_channels(),values):
        for frame in (-32,0):channel.add_key(u.FrameNumber(frame),value)
    cut=seq.add_track(u.MovieSceneCameraCutTrack).add_section();cut.set_range(-32,1);cut.set_camera_binding_id(seq.get_binding_id(cb))
    # Save a separate map, preserving the approved matched camera in its map.
    levels.save_current_level()
    u.EditorAssetLibrary.save_loaded_asset(seq)
    subsystem=u.get_editor_subsystem(u.MoviePipelineQueueSubsystem);queue=subsystem.get_queue();queue.delete_all_jobs()
    job=queue.allocate_new_job(u.MoviePipelineExecutorJob);job.map=u.SoftObjectPath(map_path);job.sequence=u.SoftObjectPath(seq.get_path_name())
    config=job.get_configuration();s=config.find_or_add_setting_by_class(u.MoviePipelineOutputSetting)
    s.output_directory=u.DirectoryPath(str(frames));s.output_resolution=u.IntPoint(1280,720);s.file_name_format='{frame_number}';s.zero_pad_frame_numbers=4
    config.find_or_add_setting_by_class(u.MoviePipelineDeferredPassBase);config.find_or_add_setting_by_class(u.MoviePipelineImageSequenceOutput_PNG)
    cvars=config.find_or_add_setting_by_class(u.MoviePipelineConsoleVariableSetting)
    cvars.add_or_update_console_variable('r.MotionBlurQuality',0)
    cvars.add_or_update_console_variable('r.DepthOfFieldQuality',0)
    aa=config.find_or_add_setting_by_class(u.MoviePipelineAntiAliasingSetting);aa.spatial_sample_count=4;aa.temporal_sample_count=1
    aa.engine_warm_up_count=32;aa.render_warm_up_count=8;aa.render_warm_up_frames=True;aa.use_camera_cut_for_warm_up=True
    executor=u.MoviePipelinePIEExecutor()
    def finished(executor,success):
        report['render_completed']=bool(success);report['frames']=[str(p) for p in frames.glob('*.png')];save();u.SystemLibrary.quit_editor()
    def failed(executor,pipeline,fatal,error):
        report.setdefault('errors',[]).append(str(error));save()
    executor.on_executor_finished_delegate.add_callable_unique(finished)
    executor.on_executor_errored_delegate.add_callable_unique(failed)
    subsystem.render_queue_with_executor_instance(executor)
except Exception as error:
    report['error']=repr(error);save();u.log_error(str(error));u.SystemLibrary.quit_editor()
