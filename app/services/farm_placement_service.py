"""Server authority for free placement. Shared map and parity-tested browser math."""
import json, math
from pathlib import Path
MAP=json.loads((Path(__file__).resolve().parents[2]/'static/data/farm-placement.json').read_text())

def radius(species,container):
    return .28 if container=='pot' else .42 if species=='birch' else .48 if species=='pumpkin' else .30

def inside(p,d):
    return abs(p['x']-d['x'])<=d['w']/2 and abs(p['z']-d['z'])<=d['d']/2 if d.get('kind')=='rect' else ((p['x']-d['x'])/d['rx'])**2+((p['z']-d['z'])/d['rz'])**2<=1

def overlap(p,o,r):
    if o.get('kind')!='rect':return math.hypot(p['x']-o['x'],p['z']-o['z'])<=r+o['r']
    c=math.cos(o.get('angle',0));s=math.sin(o.get('angle',0));dx=p['x']-o['x'];dz=p['z']-o['z']
    return math.hypot(max(0,abs(c*dx+s*dz)-o['w']/2),max(0,abs(-s*dx+c*dz)-o['d']/2))<=r

def segment(p,line):
    a,b=line['a'],line['b'];dx=b['x']-a['x'];dz=b['z']-a['z'];t=max(0,min(1,((p['x']-a['x'])*dx+(p['z']-a['z'])*dz)/(dx*dx+dz*dz or 1)))
    return math.hypot(p['x']-a['x']-t*dx,p['z']-a['z']-t*dz)

def validate(p,others=(),ignore=None):
    if p.get('container') not in ('soil','pot') or p.get('species') not in ('cosmos','pumpkin','birch') or any(type(p.get(k)) not in (float,int) or not math.isfinite(p[k]) for k in ('x','z','yaw')):return '请选择有效落点'
    if p['container']=='pot' and p['species']!='cosmos':return '这株植物需要栽入土壤'
    r=radius(p['species'],p['container']);ring=[p]+[dict(x=p['x']+r*math.cos(i*math.pi/8),z=p['z']+r*math.sin(i*math.pi/8)) for i in range(16)]
    if not all(any(inside(q,d) for d in MAP['domains']) for q in ring):return '请放在岛屿地面内'
    if any(overlap(p,o,r+.08) for o in MAP['blocked']):return '请避开水面、建筑和已有设施'
    if any(segment(p,line)<line['r']+r for line in MAP['paths']):return '这里要留给宠物通行'
    if p['container']=='soil' and (not all(any(inside(q,d) for d in MAP['soil']) for q in ring) or any(overlap(p,o,r) for o in MAP['soilExcluded'])):return '这里是铺装地面，请选择草地土壤或使用花盆'
    if any(o['id']!=ignore and math.hypot(p['x']-o['x'],p['z']-o['z'])<r+radius(o['species'],o['container'])+.12 for o in others):return '与其他植物太近了'
    return ''
