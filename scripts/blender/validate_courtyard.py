"""Read back the exported GLB and verify preservation of unrelated assets."""
import bpy,math,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def read(file):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(R/file));result={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        points=[o.matrix_world@v.co for v in o.data.vertices]
        assert all(math.isfinite(x) for p in points for x in p),o.name
        result[o.name]={tuple(round(x,4) for x in p) for p in points}
    return result
old=read('static/models/petchat-sakura-v2/sakura.glb');new=read('static/models/petchat-courtyard-v3/sakura.glb');kept=[]
for name,points in old.items():
    if any(s in name for s in ['_wood.','_wood_light.','_lamp.']):continue
    if '_stone' in name:points={p for p in points if not (p[0]>1.93 and p[1]>.9)}
    assert points==new[name],name
    kept.append(name)
newpoints=set().union(*(p for n,p in new.items() if n.startswith('Garden_v3')))
assert min(p[2] for p in newpoints)>-.005
assert max(p[2] for p in newpoints)<1.5
assert sum(n.startswith('Garden_v3') for n in new)==11
report={'preserved_meshes':kept,'finite_geometry':True,'no_below_ground_geometry':True,'new_batches':11}
(R/'art/courtyard-v3/validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(R/'art/courtyard-v3/courtyard-v3.blend'))
print('VALIDATED',json.dumps(report))
