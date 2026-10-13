import bpy, json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-v1/sakura.glb'))
result=[]
for o in bpy.context.scene.objects:
    if o.type!='MESH':continue
    coords=[o.matrix_world@v.co for v in o.data.vertices]
    result.append({'name':o.name,'verts':len(coords),'min':[min(v[i] for v in coords) for i in range(3)],'max':[max(v[i] for v in coords) for i in range(3)]})
out=ROOT/'art/sakura-v2';out.mkdir(parents=True,exist_ok=True)
(out/'original-inspection.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
