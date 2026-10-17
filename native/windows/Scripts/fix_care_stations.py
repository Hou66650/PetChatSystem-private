"""Fix physical walkable surfaces and apply Blender-authored shelter clearance."""
import json
from pathlib import Path
import unreal
p=Path(unreal.Paths.project_dir());a=unreal.EditorAssetLibrary
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mes=unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
unreal.get_default_object(unreal.load_class(None,'/Script/DataValidation.DataValidationSettings')).set_editor_property('bValidateOnSave',False)
sakura='PaitSakuraCare' in unreal.SystemLibrary.get_command_line()
assert levels.load_level('/Game/Preview/P1_SakuraV2' if sakura else '/Game/Preview/P1_MeadowV2')
changed=[]
if sakura:
 dest='/Game/Imported/P1SakuraCareLawn'
 if not a.does_directory_exist(dest):
  pipeline=unreal.InterchangeGenericAssetsPipeline();pipeline.mesh_pipeline.set_editor_property('build_nanite',False)
  pipeline.mesh_pipeline.set_editor_property('generate_lightmap_u_vs',False)
  pipeline.mesh_pipeline.set_editor_property('distance_field_resolution_scale',0.)
  pipeline.mesh_pipeline.set_editor_property('max_lumen_mesh_cards',0)
  stack=unreal.InterchangePipelineStackOverride();stack.override_pipelines=[unreal.SoftObjectPath(pipeline.get_path_name())]
  task=unreal.AssetImportTask();task.filename=str(p/'Saved/Art/P1SakuraV2Care/sakura-care.glb');task.destination_path=dest;task.automated=True;task.save=True;task.options=stack
  unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
 replacements={a.load_asset(path).get_name():a.load_asset(path) for path in a.list_assets(dest,recursive=True) if str(a.find_asset_data(path).asset_class_path.asset_name)=='StaticMesh'}
 for actor in actors.get_all_level_actors():
  if not isinstance(actor,unreal.StaticMeshActor) or not actor.static_mesh_component.static_mesh:continue
  c=actor.static_mesh_component;name=c.static_mesh.get_name()
  if name not in replacements:continue
  m=replacements[name];c.set_static_mesh(m)
  body=m.get_editor_property('body_setup');body.set_editor_property('collision_trace_flag',unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE);body.set_editor_property('double_sided_geometry',True)
  for i in range(m.get_num_sections(0)):mes.enable_section_collision(m,True,0,i)
  c.set_collision_profile_name('BlockAll');c.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
  actor.tags=[unreal.Name('PaitGround' if 'aged_chestnut' in name or 'cushions' in name else 'PaitSolid')]
  a.save_loaded_asset(m,only_if_is_dirty=False);changed.append(name)
else:
 for actor in actors.get_all_level_actors():
  if isinstance(actor,unreal.StaticMeshActor) and actor.static_mesh_component.static_mesh and actor.static_mesh_component.static_mesh.get_name()=='Dressed_bridge_masonry_Chalk_coping_stone':
   actor.tags=[unreal.Name('PaitGround')];changed.append(actor.get_actor_label())
assert changed
assert levels.save_current_level()
(p/('Saved/Qualification/'+('sakura' if sakura else 'meadow')+'-care-surface-fix.json')).write_text(json.dumps({'status':'saved','changes':changed}),encoding='utf-8')
