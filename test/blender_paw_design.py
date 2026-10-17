"""Run in the detailed Blender scene through paw_mcp_client.py."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[1]
deps=bpy.context.evaluated_depsgraph_get()

def hits(objects,origin,direction,distance):
    found=[]
    for obj in objects:
        tree=BVHTree.FromObject(obj,deps)
        p,n,face,d=tree.ray_cast(Vector(origin),Vector(direction),distance)
        if p is not None:found.append((obj.name,tuple(p),d))
    return found

meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.get('preview_only')]
assert all(math.isfinite(v) for o in meshes for p in o.data.vertices for v in p.co)
for prefix,x,y,scale in [('05 Ear tunnel',-10,.8,1),('D04 Second',-7.4,4,.82)]:
    objects=[o for c in bpy.data.collections if c.name.startswith(prefix) for o in c.objects]
    assert objects,prefix
    # A central, above-floor ray traverses both open portals and the complete bore.
    assert not hits(objects,(x,y-1.8*scale,.40*scale),(0,1,0),3.6*scale),prefix+' bore blocked'
objects=[o for c in bpy.data.collections if c.name.startswith('D07') for o in c.objects]
landing=hits(objects,(-6.5+.8*1.18,7.4+.1*1.18,3.3),(0,0,-1),1)
assert any(2.75<p[1][2]<2.90 for p in landing),'front door has no landing'
report={'status':'pass','checks':['finite master vertices','large tunnel through passage','small tunnel through passage','front doorway has landing below it'],'notCertified':['animal facility safety','runtime collision','multiplayer navigation']}
(root/'art/paw-commons-v2/review/structure-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PAW_STRUCTURE_PASS '+json.dumps(report),flush=True)
