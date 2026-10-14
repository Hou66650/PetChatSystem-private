import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-snow-v1/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
report={'bones':{b.name:[list(b.head_local),list(b.tail_local)] for b in rig.data.bones},'meshes':[{'name':o.name,'vertices':len(o.data.vertices),'bounds':[list(v) for v in o.bound_box],'materials':[m.name for m in o.data.materials]} for o in bpy.data.objects if o.type=='MESH'],'clips':[a.name for a in bpy.data.actions]}
out=R/'art/husky-v2';out.mkdir(exist_ok=True,parents=True)
(out/'source-inspection.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
