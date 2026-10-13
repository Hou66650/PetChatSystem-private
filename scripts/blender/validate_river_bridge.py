"""Reimport final GLB: preserve props, verify channel and navigation/deck agreement."""
import bpy, json, math, re
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
layout=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(ROOT/'static/js/den/sakura-river-layout.js').read_text()).group(1))
def read(path):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/path));result={}
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        points=[o.matrix_world@v.co for v in o.data.vertices]
        assert all(math.isfinite(x) for p in points for x in p),o.name
        result[o.name]={tuple(round(x,4) for x in p) for p in points}
    return result
old=read('static/models/petchat-courtyard-v3/sakura.glb')
new=read('static/models/petchat-river-v1/sakura.glb')
kept=[]
for name,points in old.items():
    if any(k in name for k in ['_grass.','_edge.','_rug.','_rug_edge.']):continue
    assert points==new[name],f'Changed unrelated mesh: {name}'
    kept.append(name)
water=next(p for n,p in new.items() if n.startswith('River_v1_River_jade_water'))
assert max(p[2] for p in water)<-.05,'Water must be recessed below the ground'
assert min(p[2] for p in water)>-.18,'Water stays inside island thickness'
depsgraph=bpy.context.evaluated_depsgraph_get()
def hit(x,z):
    return bpy.context.scene.ray_cast(depsgraph,Vector((x,-z,2)),Vector((0,0,-1)))
b=layout['bridges'][0]
for i in range(30):
    z=b['z']-b['d']/2+b['d']*(i+.5)/30
    h=b['base']+b['rise']*math.sin(math.pi*((z-b['z'])/b['d']+.5))**2
    ok,pos,normal,_,obj,_=hit(.11,z)
    assert ok and 'River_v1_Bridge_' in obj.name,(z,obj.name if obj else None)
    assert abs(pos.z-h)<.005,(z,pos.z,h)
    assert normal.z>.85,'Bridge surface faces up'
for x in [-2,-1.4,1.4,2]:
    ok,pos,normal,_,obj,_=hit(x,layout['water'][0]['z'])
    assert ok and pos.z<0,(x,pos.z,obj.name)
report={'preserved_meshes':kept,'deck_height_samples':30,'uncovered_water_samples':4,'water_below_ground':True,'finite_geometry':True}
(ROOT/'art/river-v1/validation.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/river-v1/river-bridge.blend'))
print('RIVER_VALIDATED',json.dumps(report))
