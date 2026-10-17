"""Blender: stage complete V2 geometry for the first interactive UE island.

The source .blend is never saved. Procedural micro-surfaces still need UE shaders
or baking; this first integration keeps geometry, images and the dark base palette.
"""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Matrix

root = Path(__file__).resolve().parents[3]
source = root / 'art/sakura-cinematic-v2/sakura-archipelago.blend'
expected = '88eb4d3fd808cb1b1f4fdb0935cd9f211634aea12bac1b7f4c626c68b8a93e86'
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise RuntimeError('Reviewed V2 source changed')
out = root / 'native/windows/Saved/Art/P1SakuraV2'
out.mkdir(parents=True, exist_ok=True)
if (out / 'manifest.json').exists():
    raise RuntimeError('Export already complete; inspect it instead of overwriting')
bpy.ops.wm.open_mainfile(filepath=str(source))
scene = bpy.context.scene
# Keep authored dark colors where procedural color networks cannot travel in glTF.
for material in bpy.data.materials:
    if not material.use_nodes: continue
    for node in material.node_tree.nodes:
        if node.type != 'BSDF_PRINCIPLED': continue
        base = node.inputs.get('Base Color')
        if base and base.is_linked and base.links[0].from_node.type != 'TEX_IMAGE':
            for link in list(base.links): material.node_tree.links.remove(link)

groups = []
for collection in sorted(bpy.data.collections, key=lambda c: c.name):
    if not collection.name.startswith(('01 ', '02 ', '03 ', '04 ', 'V2 01', 'V2 02', 'V2 03', 'V2 04', 'V2 05')):
        continue
    objects = sorted((o for o in collection.objects if o.type == 'MESH' and not o.hide_render), key=lambda o: o.name)
    batch, count, index = [], 0, 0
    for obj in objects:
        triangles = sum(len(p.vertices)-2 for p in obj.data.polygons)
        if batch and count + triangles > 900000:
            groups.append((f'sakura-{collection.name[:5].replace(" ","_")}-{index:02d}', batch, count))
            batch, count, index = [], 0, index + 1
        batch.append(obj)
        count += triangles
    if batch:
        groups.append((f'sakura-{collection.name[:5].replace(" ","_")}-{index:02d}', batch, count))

# Exported mesh vertices share island origin, so UE mesh actors can all spawn at
# (0,0,0). Work on the Blender session only; do not save over the source mother.
used = {o for _, objects, _ in groups for o in objects}
for obj in used:
    transform = obj.matrix_world.copy()
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    obj.data.transform(transform)
    obj.parent = None
    obj.matrix_world = Matrix.Identity(4)
    obj.hide_set(False)

manifest = {'source_sha256': expected, 'source_unchanged': True,
            'phase': 'P1 first playable integration', 'units': 'metres',
            'vertex_origin': 'shared island origin; glTF Y-up', 'modules': [],
            'limitations': ['Procedural color/bump/roughness require engine recreation or baking.',
                           'No collision, navigation, LOD or performance acceptance yet.',
                           'Offline atmosphere and presentation lighting excluded.']}
for name, objects, triangles in groups:
    path = out / (name + '.glb')
    if path.exists():
        raise RuntimeError('Partial export exists; review before replacing: ' + str(path))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB',
                             use_selection=True, export_apply=True,
                             export_cameras=False, export_lights=False)
    manifest['modules'].append({'file': path.name, 'base_triangles': triangles,
                                'objects': [o.name for o in objects],
                                'bytes': path.stat().st_size,
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    print('P1_MODULE_EXPORTED', name, triangles, flush=True)
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise RuntimeError('Source unexpectedly changed')
(out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('P1_V2_EXPORT_COMPLETE', len(groups), flush=True)
