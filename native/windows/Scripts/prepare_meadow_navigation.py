"""Enable authored solid geometry for isolated P1 navigation; preserve source art."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
meshes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
assets = unreal.EditorAssetLibrary
if not levels.load_level('/Game/Preview/P1_MeadowV2'):
    raise RuntimeError('P1 map missing')
ground = {
    'Cloud_meadow_Meadow_walk_earth', 'Cloud_meadow_Meadow_living_turf',
    'Cloud_meadow_Weathered_limestone', 'Mistwood_Forest_floor',
    'Mistwood_Weathered_limestone', 'Farm_terrace_Garden_fine_gravel',
    'Farm_terrace_Garden_weathered_limestone',
    'Dressed_bridge_masonry_Craft_cut_warm_limestone', 'Dressed_bridge_masonry_Chalk_coping_stone', 'cat_home_linen',
    'Conservatory_craft_Chalk_coping_stone',
    *('cat_home_cedar_'+str(i) for i in range(5)),
}
solid_tokens = ('Cedar_bark', 'Patinated_iron', 'Weathered_bench',
                'Garden_oiled_larch', 'Garden_patinated_iron', 'Garden_ivory_ceramic',
                'Deep_botanical_green_iron', 'Chalk_coping_stone',
                'Four_millimetre_clear_horticultural_glass', 'Hand_thrown_terracotta',
                'V2_fired_terracotta_pores', 'cat_home_cedar_', 'cat_home_end_grain',
                'cat_home_sage_roof', 'cat_home_glazed_cream')
records = []
for actor in actors.get_all_level_actors():
    if not isinstance(actor, unreal.StaticMeshActor):
        continue
    c = actor.static_mesh_component
    mesh = c.static_mesh
    if not mesh or not mesh.get_path_name().startswith('/Game/Imported/P1MeadowV2_Conventional/'):
        continue
    name = mesh.get_name()
    if name not in ground and not any(t in name for t in solid_tokens):
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        continue
    body = mesh.get_editor_property('body_setup')
    if not body:
        raise RuntimeError('Missing body setup: '+name)
    body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    body.set_editor_property('double_sided_geometry', True)
    for i in range(mesh.get_num_sections(0)):
        meshes.enable_section_collision(mesh, True, 0, i)
    c.set_collision_profile_name('BlockAll')
    c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
    actor.tags = [unreal.Name('PaitGround' if name in ground else 'PaitSolid')]
    assets.save_loaded_asset(mesh, only_if_is_dirty=False)
    origin, extent = actor.get_actor_bounds(False)
    records.append({'mesh':name, 'role':'ground' if name in ground else 'solid',
                    'center':[origin.x,origin.y,origin.z], 'extent':[extent.x,extent.y,extent.z]})
volume = next((a for a in actors.get_all_level_actors() if a.get_actor_label()=='P1 navigation bounds'), None)
if volume is None:
    volume = actors.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(0,0,300))
    volume.set_actor_label('P1 navigation bounds')
# The editor volume factory supplies a 200 cm cube brush. Verify before scaling.
volume.set_actor_scale3d(unreal.Vector(1,1,1))
origin, extent = volume.get_actor_bounds(False)
if min(extent.x,extent.y,extent.z) < 1:
    raise RuntimeError('Navigation factory did not create volume brush')
volume.set_actor_scale3d(unreal.Vector(5000/extent.x,5000/extent.y,1200/extent.z))
nav = next((a for a in actors.get_all_level_actors() if isinstance(a,unreal.RecastNavMesh)),None)
if nav is None:
    # A headless editor can save the volume before its deferred auto-create tick.
    nav = actors.spawn_actor_from_class(unreal.RecastNavMesh,unreal.Vector())
    nav.set_actor_label('P1 dynamic navigation')
nav.set_editor_property('runtime_generation',unreal.RuntimeGenerationType.DYNAMIC)
nav.set_editor_property('agent_radius',35.0)
nav.set_editor_property('agent_height',110.0)
# The integration fixture's old (500,-400) spawn intersects the east-side pots.
# Place the isolated demo cat on the open central lawn, clear of authored props.
for a in actors.get_all_level_actors():
    if isinstance(a,unreal.SkeletalMeshActor):
        a.set_actor_location(unreal.Vector(-200,-200,35),False,False)
if not levels.save_current_level():
    raise RuntimeError('Could not save navigation map')
cat_records=[]
for a in actors.get_all_level_actors():
    if isinstance(a,unreal.SkeletalMeshActor):
        c=a.skeletal_mesh_component
        cat_records.append({'mesh':c.skeletal_mesh_asset.get_name(), 'rotation':str(a.get_actor_rotation()),
                            'scale':str(a.get_actor_scale3d()),
                            'bones':[str(c.get_bone_name(i)) for i in range(c.get_num_bones())]})
(Path(unreal.Paths.project_dir())/'Saved/Qualification/meadow-navigation-setup.json').write_text(
    json.dumps({'status':'saved_requires_runtime_navigation_check','colliders':records,'cats':cat_records},indent=2),encoding='utf-8')
