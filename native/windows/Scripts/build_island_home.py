"""Compose existing fine island meshes into a separate native home. No source edits."""
import json
from pathlib import Path
import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets = unreal.EditorAssetLibrary
target = '/Game/Preview/P2_IslandHome'
if assets.does_asset_exist(target) and (Path(unreal.Paths.project_dir())/'Saved/Qualification/island-home-build.json').exists():
    raise RuntimeError('Completed home already exists; review before rebuilding')
rows = []
# Same order as the web home. Camera looks north, left/right is world X.
layout = [('Sakura', (-1450,-1300,0), .32), ('Snow',(1450,1400,100),.72),
          ('Meadow',(-1450,1400,0),.38), ('Camp',(1450,-1300,0),.72)]
for key, offset, factor in layout:
    assert levels.load_level('/Game/Preview/P1_'+key+'V2')
    for actor in actors.get_all_level_actors():
        if not isinstance(actor, unreal.StaticMeshActor): continue
        c = actor.static_mesh_component
        mesh = c.static_mesh
        if not mesh or not mesh.get_path_name().startswith('/Game/Imported/'): continue
        if actor.is_hidden_ed() or not c.get_editor_property('visible'): continue
        loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        rows.append(dict(island=key,label=actor.get_actor_label(),mesh=mesh.get_path_name(),
                         location=[loc.x*factor+offset[0],loc.y*factor+offset[1],loc.z*factor+offset[2]],
                         rotation=[rot.pitch,rot.yaw,rot.roll],scale=[scale.x*factor,scale.y*factor,scale.z*factor],
                         materials=[c.get_material(i).get_path_name() if c.get_material(i) else None for i in range(c.get_num_materials())]))
assert (levels.load_level(target) if assets.does_asset_exist(target) else levels.new_level_from_template(target, '/Game/Preview/P1_MeadowV2'))
for actor in actors.get_all_level_actors():
    if isinstance(actor,(unreal.StaticMeshActor,unreal.SkeletalMeshActor,unreal.NavMeshBoundsVolume)):
        actors.destroy_actor(actor)
    elif isinstance(actor,unreal.DirectionalLight):
        actor.set_actor_rotation(unreal.Rotator(pitch=-38,yaw=-60,roll=0),False)
        actor.light_component.set_editor_property('light_source_angle',2.5)
    elif isinstance(actor,unreal.SkyLight):
        actor.light_component.set_editor_property('intensity',1.6)
    elif isinstance(actor,unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(0,0,200),False,False)
for row in rows:
    actor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*row['location']),unreal.Rotator(*row['rotation']))
    actor.set_actor_label('Home '+row['island']+' '+row['label'])
    actor.tags=[unreal.Name('Home'+row['island'])]
    actor.set_actor_scale3d(unreal.Vector(*row['scale']))
    c=actor.static_mesh_component
    c.set_static_mesh(unreal.load_asset(row['mesh']))
    for i,path in enumerate(row['materials']):
        if path:c.set_material(i,unreal.load_asset(path))
    c.set_collision_profile_name('BlockAll')
    c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
assert levels.save_current_level()
report={'map':target,'source_maps_unchanged':True,'layout':layout,'mesh_actors':len(rows),
        'counts':{key:sum(r['island']==key for r in rows) for key,_,_ in layout},'runtime_verified':False}
(Path(unreal.Paths.project_dir())/'Saved/Qualification/island-home-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
unreal.log('PAIT_HOME_SAVED '+str(report))
