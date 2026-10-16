"""Preserve geometry and PBR, reduce embedded textures for browser delivery."""
import sys
import json
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pet_mesh_checks import rear_branches

source, output = sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(Path(source).resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes or sum(len(o.data.vertices) for o in meshes)>250000:
    raise ValueError('Model empty or exceeds vertex budget')
branches = rear_branches(meshes)
Path(output).with_suffix('.quality.json').write_text(json.dumps({
    'status':'unknown', 'rearBranchCountsAssumingMinusY':branches,
    'reason':'疑似重复尾巴或尾部结构粘连，需核对朝向并检查身体结构' if sum(n>1 for n in branches)>=2 else '身体结构待审核；基础检查不能判定肢体与尾巴是否正确'
}, ensure_ascii=False), encoding='utf-8')
for im in bpy.data.images:
    if max(im.size)>2048:
        scale=2048/max(im.size)
        im.scale(round(im.size[0]*scale),round(im.size[1]*scale))
bpy.ops.export_scene.gltf(filepath=str(Path(output).resolve()),export_format='GLB')
