"""Verify the exported stage's finite geometry and retained prop positions."""
import bpy,json,math
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def read(path):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(R/path))
    result={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        points=[o.matrix_world@v.co for v in o.data.vertices]
        assert all(math.isfinite(x) for p in points for x in p)
        result[o.name]={tuple(round(x,4) for x in p) for p in points}
    return result
old=read('static/models/petchat-v1/sakura.glb')
new=read('static/models/petchat-sakura-v2/sakura.glb')
kept=[]
for name,points in old.items():
    if '_pink' in name:continue
    if '_wood.' in name:points={p for p in points if p[1]>=2.4}
    # Import/export may change split normals and vertex ordering; compare positions.
    assert points==new[name],name
    kept.append(name)
tree=[n for n in new if n.startswith('Sakura_v2')]
report={'retained_prop_world_geometry_identical':kept,'finite_geometry':True,'tree_batches':len(tree)}
(R/'art/sakura-v2/validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(R/'art/sakura-v2/sakura-v2.blend'))
print('VALIDATED',json.dumps(report))
