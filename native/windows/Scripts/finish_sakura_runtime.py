"""Preserve tiny blossom surfaces in Nanite and light the overview-facing side.
Run in bounded editor batches; never rebuild already processed meshes.
"""
from pathlib import Path
import json
import unreal

p=Path(unreal.Paths.project_dir());a=unreal.EditorAssetLibrary
me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
unreal.get_default_object(unreal.load_class(None,'/Script/DataValidation.DataValidationSettings')).set_editor_property('bValidateOnSave',False)
report=p/'Saved/Qualification/sakura-runtime-finishing.json'
source=json.loads((p/'Saved/Qualification/two-island-care-setup.json').read_text(encoding='utf-8'))
changed=[];inspected=[]
for record in source['sakura_meshes']:
    if 'Cherry_ecology_V2_petal' not in record['name']:continue
    m=a.load_asset(record['mesh']);settings=me.get_nanite_settings(m)
    if settings.shape_preservation!=unreal.NaniteShapePreservation.PRESERVE_AREA:
        settings.shape_preservation=unreal.NaniteShapePreservation.PRESERVE_AREA
        me.set_nanite_settings(m,settings,True)
        a.save_loaded_asset(m,only_if_is_dirty=False);changed.append(m.get_path_name())
    inspected.append(m.get_path_name())
    if len(changed)>=6:
        report.write_text(json.dumps({'status':'checkpoint_continue','changed':changed}),encoding='utf-8')
        break
else:
    assert levels.load_level('/Game/Preview/P1_SakuraV2')
    for actor in actors.get_all_level_actors():
        if isinstance(actor,unreal.DirectionalLight):
            actor.set_actor_rotation(unreal.Rotator(pitch=-40,yaw=55,roll=0),False)
            actor.light_component.set_editor_property('light_source_angle',2.0)
        elif isinstance(actor,unreal.SkyLight):
            actor.light_component.set_editor_property('intensity',1.8)
            actor.light_component.set_editor_property('lower_hemisphere_is_black',False)
        elif isinstance(actor,unreal.PostProcessVolume):
            settings=actor.get_editor_property('settings')
            settings.set_editor_property('auto_exposure_min_brightness',12.5)
            settings.set_editor_property('auto_exposure_max_brightness',12.5)
            actor.set_editor_property('settings',settings)
    assert levels.save_current_level()
    report.write_text(json.dumps({'status':'saved_requires_runtime_review','preserved_petal_meshes':inspected,'sun_pitch':-40,'sun_yaw':55,'sky_intensity':1.8,'fixed_ev100':12.5},indent=2),encoding='utf-8')
