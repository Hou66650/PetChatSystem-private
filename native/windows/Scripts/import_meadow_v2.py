"""UE Editor: assemble the complete V2 first-look map in an isolated namespace."""
import gc
import hashlib
import json
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir())
source = project / 'Saved/Art/P1MeadowV2'
manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
if manifest['source_sha256'] != '531402009492e1c5600b628dacc73f81a100f915a4e934faca58d6bd9aaa5f80':
    raise RuntimeError('Unexpected V2 source')
assets = unreal.EditorAssetLibrary
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
map_path = '/Game/Preview/P1_MeadowV2'
report_path = project / 'Saved/Qualification/meadow-v2-import.json'
if report_path.exists():
    prior = json.loads(report_path.read_text(encoding='utf-8'))
    if prior['source_sha256'] != manifest['source_sha256'] or prior['status'] != 'importing':
        raise RuntimeError('Completed or different P1 scene exists; preserve it')
if assets.does_asset_exist(map_path):
    if not levels.load_level(map_path):
        raise RuntimeError('Could not resume isolated P1 map')
elif not levels.new_level_from_template(map_path, '/Game/Qualification/P0_Lighting'):
    raise RuntimeError('Could not create separate P1 scene')
for actor in actors.get_all_level_actors():
    if isinstance(actor, unreal.StaticMeshActor):
        if not actor.get_actor_label().startswith(('P0 ', 'P1 ')):
            raise RuntimeError('Unexpected authored actor; do not rebuild this map')
        actors.destroy_actor(actor)
    elif isinstance(actor, unreal.SkeletalMeshActor):
        actor.set_actor_location(unreal.Vector(500, -400, 35), False, False)
        if not actor.get_actor_label().startswith('P1 '):
            actor.set_actor_label('P1 standard cat ' + actor.get_actor_label())
    elif isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location(unreal.Vector(200, 200, 150), False, False)
report = {'status': 'importing', 'map': map_path, 'source_sha256': manifest['source_sha256'],
          'modules': [], 'visual_review_pending': True, 'production_data_access': False}
glass = unreal.load_asset('/Game/Qualification/Materials/M_P0_ThinGlass')
if not glass:
    raise RuntimeError('P0 thin glass missing; run RepairLighting first')
pipeline = unreal.InterchangeGenericAssetsPipeline()
pipeline.mesh_pipeline.set_editor_property('build_nanite', False)
pipeline.mesh_pipeline.set_editor_property('generate_lightmap_u_vs', False)
pipeline.mesh_pipeline.set_editor_property('distance_field_resolution_scale', 0.0)
pipeline.mesh_pipeline.set_editor_property('max_lumen_mesh_cards', 0)
pipeline.mesh_pipeline.set_editor_property('collision', False)
pipeline.common_meshes_properties.set_editor_property('recompute_normals', False)
pipeline.common_meshes_properties.set_editor_property('recompute_tangents', False)
pipeline.common_meshes_properties.set_editor_property('use_mikk_t_space', False)
pipeline.material_pipeline.texture_pipeline.set_editor_property('allow_non_power_of_two', True)
stack = unreal.InterchangePipelineStackOverride()
stack.set_editor_property('override_pipelines', [unreal.SoftObjectPath(pipeline.get_path_name())])
for module in manifest['modules']:
    file = source / module['file']
    if hashlib.sha256(file.read_bytes()).hexdigest() != module['sha256']:
        raise RuntimeError('Module changed: ' + file.name)
    # New namespace avoids loading the original default-Nanite attempt (retained
    # locally). Apply the lightweight import pipeline before any mesh is built.
    destination = '/Game/Imported/P1MeadowV2_Conventional/' + file.stem.replace('-', '_')
    task = None
    if assets.does_directory_exist(destination):
        # Resume assets saved by this isolated import, without overwriting them.
        meshes = [assets.load_asset(p) for p in assets.list_assets(destination, recursive=True)
                  if str(assets.find_asset_data(p).asset_class_path.asset_name) == 'StaticMesh']
        if not all(isinstance(m, unreal.StaticMesh) for m in meshes):
            raise RuntimeError('Unexpected partial import assets')
    else:
        task = unreal.AssetImportTask()
        task.filename = str(file)
        task.destination_path = destination
        task.automated = True
        task.replace_existing = False
        task.save = True
        task.options = stack
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        meshes = [asset for asset in task.get_objects() if isinstance(asset, unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError('No meshes imported: ' + file.name)
    paths = []
    for mesh in meshes:
        # Conventional first-look baseline avoids transparent foliage/glass Nanite
        # fallback. Tune per module after seeing the complete scene.
        nanite = mesh_editor.get_nanite_settings(mesh)
        nanite.set_editor_property('enabled', False)
        mesh_editor.set_nanite_settings(mesh, nanite, False)
        settings = mesh_editor.get_lod_build_settings(mesh, 0)
        settings.set_editor_property('distance_field_resolution_scale', 0.0)
        mesh_editor.set_lod_build_settings(mesh, 0, settings)
        actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
        actor.set_actor_label('P1 ' + mesh.get_name())
        actor.static_mesh_component.set_static_mesh(mesh)
        for index, slot in enumerate(mesh.static_materials):
            if slot.material_interface and 'Four_millimetre_clear' in slot.material_interface.get_name():
                actor.static_mesh_component.set_material(index, glass)
        paths.append(mesh.get_path_name())
    if not assets.save_directory(destination, only_if_is_dirty=True, recursive=True):
        raise RuntimeError('Module save failed')
    if not levels.save_current_level():
        raise RuntimeError('Map checkpoint save failed')
    report['modules'].append({'file': file.name, 'sha256': module['sha256'], 'meshes': paths})
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    unreal.log('PAIT_P1_MODULE_IMPORTED ' + file.name + ' ' + str(len(meshes)))
    del task, meshes
    gc.collect()
    unreal.SystemLibrary.collect_garbage()
report['status'] = 'editor_scene_saved_requires_runtime_review'
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
unreal.log('PAIT_P1_COMPLETE_ISLAND_SAVED')
