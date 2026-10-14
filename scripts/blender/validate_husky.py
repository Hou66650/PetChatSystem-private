"""Validate the exported GLB, not only the authoring scene."""
import bpy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-husky-v2/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
for o in bpy.data.objects:
    if o.animation_data:o.animation_data_clear()
meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig]
report={};spec=json.loads((ROOT/'art/husky-v2/build-report.json').read_text())
for name in spec['new_clips']:
    action=next(a for a in bpy.data.actions if a.name==name or a.name.endswith('_'+name))
    rig.animation_data_create();rig.animation_data.action=action
    rig.animation_data.action_slot=next(s for s in action.slots if s.target_id_type=='OBJECT')
    samples=[]
    for ratio in (0,.25,.5,.75,1):
        bpy.context.scene.frame_set(round(action.frame_range[0]+ratio*(action.frame_range[1]-action.frame_range[0])))
        dg=bpy.context.evaluated_depsgraph_get();pts=[]
        for o in meshes:
            ev=o.evaluated_get(dg);m=ev.to_mesh();pts.extend(ev.matrix_world@v.co for v in m.vertices);ev.to_mesh_clear()
        lo=[min(v[i] for v in pts) for i in range(3)];hi=[max(v[i] for v in pts) for i in range(3)]
        assert all(math.isfinite(n) for n in lo+hi),(name,'nonfinite')
        assert max(hi[i]-lo[i] for i in range(3))<1.8,(name,'exploding mesh')
        assert lo[2]>-.045,(name,'below floor',lo[2])
        samples.append({'phase':ratio,'bounds':[lo,hi]})
    report[name]=samples
(ROOT/'art/husky-v2/export-validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('PASS: exported mesh samples across all 12 new clips, finite bounds, no extreme stretching, floor bounds')
