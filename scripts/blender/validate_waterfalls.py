"""Read-back validation of the extended GLB, without changing old island geometry."""
import bpy, math, json
from pathlib import Path
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[2]
def read(path):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/path));result={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        points=[o.matrix_world@v.co for v in o.data.vertices]
        assert all(math.isfinite(x) for p in points for x in p),o.name
        result[o.name]={tuple(x for x in p) for p in points}
    return result
old=read('static/models/petchat-river-v1/sakura.glb')
new=read('static/models/petchat-waterfalls-v1/sakura.glb')
max_error=0
for name,points in old.items():
    # A GLB round trip may split vertices or round a last float bit. Check both
    # point clouds with a 10-micrometre tolerance instead of decimal equality.
    for a,b in [(points,new[name]),(new[name],points)]:
        tree=KDTree(len(b))
        for i,p in enumerate(b):tree.insert(p,i)
        tree.balance()
        error=max(tree.find(p)[2] for p in a)
        assert error<.00001,(name,error)
        max_error=max(max_error,error)
curtains=[o for o in bpy.context.scene.objects if o.get('waterfall_role')=='curtain']
assert len(curtains)==14
for side in [-1,1]:
    objs=[o for o in curtains if o.name.startswith(f'Waterfall_{side}_tongue')]
    assert len(objs)==7
    for o in objs:
        assert o.data.uv_layers and len(o.data.uv_layers.active.data)>0
        points=new[o.name]
        assert all(p[0]*side>2.70 for p in points),'Curtain stays outside play area'
        assert min(p[2] for p in points)<-.90
        assert abs(max(p[2] for p in points)+.055)<.0001,'Lip connects at river height'
        top=[p for p in points if abs(p[2]+.055)<.0001]
        assert all(abs(math.hypot(p[0],p[1])-3.2)<.04 for p in top),'No gap at island lip'
report={'preserved_meshes':len(old),'max_roundtrip_error_m':max_error,'curtains':len(curtains),'finite_geometry':True,'connected_lips':True,'outside_play_area':True}
(ROOT/'art/waterfalls-v1/validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/waterfalls-v1/waterfalls.blend'))
print('WATERFALL_VALIDATED',json.dumps(report))
