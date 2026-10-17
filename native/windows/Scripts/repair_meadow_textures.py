"""UE: reimport only materials/textures rejected by the first V2 import."""
import hashlib
import json
import re
from pathlib import Path
import unreal

project = Path(unreal.Paths.project_dir())
source = project / 'Saved/Art/P1MeadowV2'
manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
log = (project / 'Saved/Qualification/meadow-v2-import-r4.log').read_text(encoding='utf-8', errors='replace')
failed = sorted(set(re.findall(r'(meadow-\d\d-\d\d\.glb).*?不能导入尺寸非2', log)))
if not failed:
    raise RuntimeError('No matching texture failures; inspect the import log')
pipeline = unreal.InterchangeGenericAssetsPipeline()
pipeline.mesh_pipeline.set_editor_property('import_static_meshes', False)
pipeline.mesh_pipeline.set_editor_property('import_skeletal_meshes', False)
pipeline.material_pipeline.texture_pipeline.set_editor_property('allow_non_power_of_two', True)
stack = unreal.InterchangePipelineStackOverride()
stack.set_editor_property('override_pipelines', [unreal.SoftObjectPath(pipeline.get_path_name())])
records = []
for name in failed:
    module = next(m for m in manifest['modules'] if m['file'] == name)
    file = source / name
    if hashlib.sha256(file.read_bytes()).hexdigest() != module['sha256']:
        raise RuntimeError('Changed source')
    destination = '/Game/Imported/P1MeadowV2_Conventional/' + file.stem.replace('-', '_')
    task = unreal.AssetImportTask()
    task.filename = str(file)
    task.destination_path = destination
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = stack
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objects = task.get_objects()
    if any(isinstance(o, (unreal.StaticMesh, unreal.SkeletalMesh)) for o in objects):
        raise RuntimeError('Texture-only repair unexpectedly imported geometry')
    textures = [o for o in objects if isinstance(o, unreal.Texture2D)]
    if not textures:
        raise RuntimeError('No repaired textures: ' + name)
    unreal.EditorAssetLibrary.save_directory(destination, only_if_is_dirty=True, recursive=True)
    records.append({'module': name, 'textures': [o.get_path_name() for o in textures]})
(project / 'Saved/Qualification/meadow-v2-texture-repair.json').write_text(
    json.dumps({'status': 'textures_saved_requires_visual_review', 'modules': records}, indent=2), encoding='utf-8')
