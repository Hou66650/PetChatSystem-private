"""Import the existing Blender botanical growth assets without redesigning them."""
import gc,hashlib,json,re
from pathlib import Path
import unreal
p=Path(unreal.Paths.project_dir());root=p.parent.parent
source=root/'static/models/petchat-farm-v1'
a=unreal.EditorAssetLibrary
pipeline=unreal.InterchangeGenericAssetsPipeline()
for key,value in [('build_nanite',False),('generate_lightmap_u_vs',False),('distance_field_resolution_scale',0.),('max_lumen_mesh_cards',0),('collision',False)]:
    pipeline.mesh_pipeline.set_editor_property(key,value)
pipeline.common_meshes_properties.set_editor_property('recompute_normals',False)
pipeline.material_pipeline.texture_pipeline.set_editor_property('allow_non_power_of_two',True)
stack=unreal.InterchangePipelineStackOverride();stack.override_pipelines=[unreal.SoftObjectPath(pipeline.get_path_name())]
catalog={}
files=sorted(f for f in source.glob('*.glb') if re.fullmatch(r'[a-z-]+-\d\d\.glb',f.name))
assert len(files)>=130
files.append(source/'flowerpot.glb')
for f in files:
    dest='/Game/Imported/P2Garden/'+f.stem.replace('-','_')
    if not a.does_directory_exist(dest):
        task=unreal.AssetImportTask();task.filename=str(f);task.destination_path=dest;task.automated=True;task.save=True;task.options=stack
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths=[x for x in a.list_assets(dest,recursive=True) if str(a.find_asset_data(x).asset_class_path.asset_name)=='StaticMesh']
    assert paths,f
    catalog[f.stem]={'meshes':paths,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    unreal.log('PAIT GARDEN '+f.stem)
    unreal.SystemLibrary.collect_garbage();gc.collect()
out=p/'Content/PaitData';out.mkdir(exist_ok=True)
(out/'garden-models.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
(p/'Saved/Qualification/garden-import.json').write_text(json.dumps({'status':'imported','stages':len(catalog),'meshes':sum(len(v['meshes']) for v in catalog.values()),'source':'existing Blender farm-v1','visual_review_pending':True},indent=2),encoding='utf-8')
