import json
from pathlib import Path
import unreal

levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels.load_level('/Game/Preview/P1_MeadowV2')
records=[]
for a in actors.get_all_level_actors():
    if isinstance(a,unreal.NavMeshBoundsVolume):
        records.append({'class':'bounds','label':a.get_actor_label(),'bounds':str(a.get_actor_bounds(False))})
    elif isinstance(a,unreal.RecastNavMesh):
        records.append({'class':'recast','runtime':str(a.get_editor_property('runtime_generation')),
                        'radius':a.get_editor_property('agent_radius'),'height':a.get_editor_property('agent_height')})
    elif isinstance(a,unreal.StaticMeshActor) and a.actor_has_tag('PaitGround'):
        m=a.static_mesh_component.static_mesh
        records.append({'class':'ground','name':m.get_name(),
                        'navigation_data':m.get_editor_property('has_navigation_data'),
                        'collision':str(m.get_editor_property('body_setup').get_editor_property('collision_trace_flag'))})
(Path(unreal.Paths.project_dir())/'Saved/Qualification/meadow-navigation-inspection.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
