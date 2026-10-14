import bpy,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-snow-v1/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
obj=next(o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig)
def bounds(vertices):
    return [[round(f(v.co[i] for v in vertices),4) for i in range(3)] for f in (min,max)]
groups=[]
for g in obj.vertex_groups:
    vs=[v for v in obj.data.vertices if any(a.group==g.index and a.weight>.3 for a in v.groups)]
    groups.append({'name':g.name,'n':len(vs),'box':bounds(vs) if vs else None})
parent=list(range(len(obj.data.vertices)))
def find(a):
    while parent[a]!=a: parent[a]=parent[parent[a]];a=parent[a]
    return a
for e in obj.data.edges: parent[find(e.vertices[0])]=find(e.vertices[1])
parts={}
for v in obj.data.vertices: parts.setdefault(find(v.index),[]).append(v)
components=sorted([{'n':len(v),'box':bounds(v),'groups':list(set(obj.vertex_groups[g.group].name for p in v for g in p.groups if g.weight>.5))} for v in parts.values()],key=lambda a:-a['n'])
report={'groups':groups,'components':components,'bones':[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'matrix':[list(r) for r in b.matrix_local]} for b in rig.data.bones]}
(R/'art/husky-v2/rig-analysis.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps({'groups':groups,'components':components[:55]}))
