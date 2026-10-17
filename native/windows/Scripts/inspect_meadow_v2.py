"""Blender: inventory V2 master without modifying or saving it."""
import hashlib
import json
from pathlib import Path
import bpy

root = Path(__file__).resolve().parents[3]
source = root / 'art/cloud-meadow-cinematic-v2/cloud-meadow-refined.blend'
digest = hashlib.sha256(source.read_bytes()).hexdigest()
if digest != '531402009492e1c5600b628dacc73f81a100f915a4e934faca58d6bd9aaa5f80':
    raise RuntimeError('V2 master differs from reviewed dark botanical palette')
bpy.ops.wm.open_mainfile(filepath=str(source))
records = []
for c in bpy.data.collections:
    objects = [o for o in c.objects if o.type == 'MESH']
    if not objects:
        continue
    records.append({'collection': c.name, 'objects': [
        {'name': o.name, 'triangles': sum(len(p.vertices)-2 for p in o.data.polygons),
         'materials': [m.name if m else None for m in o.data.materials],
         'modifiers': [m.type for m in o.modifiers], 'hidden_render': o.hide_render}
        for o in objects]})
materials = []
for m in bpy.data.materials:
    p = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m.use_nodes else None
    materials.append({'name': m.name, 'diffuse': list(m.diffuse_color),
                      'nodes': [n.type for n in m.node_tree.nodes] if m.use_nodes else [],
                      'base_color': list(p.inputs['Base Color'].default_value) if p else None,
                      'color_linked': bool(p and p.inputs['Base Color'].is_linked)})
out = root / 'native/windows/Saved/Qualification/meadow-v2-inspection.json'
out.write_text(json.dumps({'source_sha256': digest, 'collections': records,
                            'materials': materials}, ensure_ascii=False, indent=2), encoding='utf-8')
print('V2_INSPECTED', len(records), 'collections', len(materials), 'materials', flush=True)
