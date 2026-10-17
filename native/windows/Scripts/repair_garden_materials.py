"""Give runtime ISM plants cooked shader permutations without editing Engine assets."""
import hashlib,json
from pathlib import Path
import unreal
a=unreal.EditorAssetLibrary;lib=unreal.MaterialEditingLibrary
p=Path(unreal.Paths.project_dir());cache={};instances=0;materials=0
def clone_parent(source):
    key=source.get_path_name()
    if key in cache:return cache[key]
    path='/Game/Imported/P2GardenMaterials/'+source.get_name()+'_'+hashlib.sha256(key.encode()).hexdigest()[:10]
    target=a.load_asset(path) if a.does_asset_exist(path) else a.duplicate_asset(key,path)
    assert target,key
    if isinstance(target,unreal.Material):
        lib.set_material_usage(target,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        lib.recompile_material(target)
    elif isinstance(target,unreal.MaterialInstanceConstant):
        lib.set_material_instance_parent(target,clone_parent(source.get_editor_property('parent')))
    else:raise RuntimeError('Unknown material interface '+key)
    a.save_loaded_asset(target);cache[key]=target;return target
for path in a.list_assets('/Game/Imported/P2Garden',recursive=True):
    kind=str(a.find_asset_data(path).asset_class_path.asset_name)
    if kind=='Material':
        material=a.load_asset(path)
        lib.set_material_usage(material,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        lib.recompile_material(material);a.save_loaded_asset(material);materials+=1
        continue
    if kind!='MaterialInstanceConstant':continue
    material=a.load_asset(path);parent=material.get_editor_property('parent')
    if not parent.get_path_name().startswith('/Game/Imported/P2GardenMaterials/'):
        lib.set_material_instance_parent(material,clone_parent(parent));a.save_loaded_asset(material)
    instances+=1
assert materials+instances>0,'No botanical materials found'
(p/'Saved/Qualification/garden-materials.json').write_text(json.dumps({'materials':materials,'instances':instances,'project_parent_materials':list(cache),'engine_assets_modified':False,'status':'saved_requires_runtime_review'},indent=2),encoding='utf-8')
