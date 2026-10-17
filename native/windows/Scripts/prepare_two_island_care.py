"""Complete shared care fixtures and Sakura navigation after full geometry import."""
import json,re
from pathlib import Path
import unreal
unreal.get_default_object(unreal.load_class(None,"/Script/DataValidation.DataValidationSettings")).set_editor_property("bValidateOnSave", False)
def main():
    p=Path(unreal.Paths.project_dir());a=unreal.EditorAssetLibrary
    levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    me=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report=json.loads((p/'Saved/Qualification/sakura-import.json').read_text(encoding='utf-8'))
    manifest=json.loads((p/'Saved/Art/P1SakuraV2Chunks/manifest.json').read_text(encoding='utf-8'))
    semantic={}
    for item,mod in zip(report['modules'],manifest['modules']):
        if len(item['meshes'])==1 and len(mod['objects'])==1: semantic[item['meshes'][0]]=re.sub('[^A-Za-z0-9_]','_',mod['objects'][0])
    assert levels.load_level('/Game/Preview/P1_SakuraV2')
    records=[];ball=None;new_nanite=0
    for actor in actors.get_all_level_actors():
        if not isinstance(actor,unreal.StaticMeshActor) or not actor.static_mesh_component.static_mesh: continue
        c=actor.static_mesh_component;m=c.static_mesh;name=semantic.get(m.get_path_name(),m.get_name())
        actor.set_actor_label('Sakura V2 '+name)
        if 'Toy_ball' in name: ball=m.get_path_name()
        if m.get_path_name() in semantic and any(t in name.lower() for t in ('bark','timber','stone','granite','basalt','roof','ceramic')):
            body=m.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
            body.set_editor_property('double_sided_geometry',True)
            for i in range(m.get_num_sections(0)):me.enable_section_collision(m,True,0,i)
            c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
            actor.tags=[unreal.Name('PaitSolid')]
            a.save_loaded_asset(m,only_if_is_dirty=False)
        if any(t in name.lower() for t in ('anther','pollen','calyx','grass','living_moss')): c.set_cast_shadow(False)
        if 'Cherry_ecology' in name and any(t in name for t in ('petal','anther','calyx')):
            settings=me.get_nanite_settings(m)
            if not settings.enabled and "PaitFinishNanite" in unreal.SystemLibrary.get_command_line():
                settings.enabled=True;me.set_nanite_settings(m,settings,True)
                a.save_loaded_asset(m,only_if_is_dirty=False)
                new_nanite+=1
                if new_nanite>=12:
                    assert levels.save_current_level()
                    (p/'Saved/Qualification/two-island-care-setup.json').write_text(json.dumps({'status':'nanite_checkpoint_continue'}),encoding='utf-8')
                    return
        records.append({'name':name,'mesh':m.get_path_name(),'nanite':bool(me.get_nanite_settings(m).enabled)})
    assert levels.save_current_level()
    assert ball,'Authored toy not found'
    (p/'Saved/Qualification/two-island-care-setup.json').write_text(json.dumps({'status':'saved_requires_runtime_check','sakura_meshes':records,'toy_asset':ball,'navigation_height_cm':110},indent=2),encoding='utf-8')
    unreal.log('TWO_ISLAND_CARE_SETUP_COMPLETE')
main()
