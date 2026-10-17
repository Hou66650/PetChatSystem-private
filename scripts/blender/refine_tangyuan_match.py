"""Local, reversible refinement of the already straightened Tangyuan asset.

The small oral insert is an artistic reconstruction of visible video features,
not a recovered scan of the dog's mouth. Never run the 90-degree rest correction
again on this input. Private source assets stay outside the repository.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

p = argparse.ArgumentParser()
p.add_argument('--input', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=a.input)
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = bpy.data.objects['Tangyuan | reconstructed surface, original UV retained']
hair = bpy.data.objects['Tangyuan | animated review fibres']
if 'jaw' in rig.data.bones:
    raise ValueError('Use the neutral source, not an already refined revision')

def smooth(lo, hi, x):
    t = min(1., max(0., (x-lo)/(hi-lo)))
    return t*t*(3-2*t)

# A continuous displacement shared by the surface and fibres keeps the coat
# attached. Taper only the broad upper forelegs/shoulders; leave paws and face.
maximum = 0.
for obj in (body, hair):
    for v in obj.data.vertices:
        before = v.co.copy()
        w = smooth(.40,.53,v.co.z)*(1-smooth(.68,.80,v.co.z))
        w *= smooth(-.47,-.31,v.co.y)*(1-smooth(-.12,.04,v.co.y))
        v.co.x = -.07 + (v.co.x+.07)*(1-.13*w)
        maximum = max(maximum, (v.co-before).length)
    obj.data.update()

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
jaw = rig.data.edit_bones.new('jaw')
jaw.head = (-.078,-.46,.65); jaw.tail = (-.078,-.62,.62)
jaw.parent = rig.data.edit_bones['head']; jaw.use_deform = True
t = rig.data.edit_bones.new('tongue')
t.head = (-.078,-.59,.62); t.tail = (-.078,-.66,.62)
t.parent = jaw; t.use_deform = True
bpy.ops.object.mode_set(mode='OBJECT')
for obj in (body,hair):
    j = obj.vertex_groups.new(name='jaw'); h = obj.vertex_groups['head']
    for v in obj.data.vertices:
        old = next((g.weight for g in v.groups if g.group == h.index),0)
        w = (1-smooth(.605,.654,v.co.z))*(1-smooth(-.57,-.47,v.co.y))
        if old*w > 1e-6:
            j.add([v.index],old*w,'REPLACE'); h.add([v.index],old*(1-w),'REPLACE')

def material(name, color, roughness):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color,1)
    bsdf.inputs['Roughness'].default_value = roughness
    return m

def insert(name, center, scale, mat, bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=center)
    obj = bpy.context.object; obj.name = name; obj.scale = scale
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons: poly.use_smooth = True
    obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1.,'REPLACE')
    obj.modifiers.new('Follow facial skeleton','ARMATURE').object = rig
    obj.parent = rig
    return obj

insert('Tangyuan | lip opening',(-.078,-.598,.628),(.044,.012,.008),
       material('Tangyuan_Mouth',(.018,.009,.012),.65),'head')
tongue = insert('Tangyuan | small tongue tip',(-.078,-.626,.618),(.026,.036,.010),
                material('Tangyuan_Tongue',(.37,.075,.10),.52),'tongue')
# A shallow centre groove and softly rounded tip, with no invented teeth.
for v in tongue.data.vertices:
    v.co.z -= .0015*math.exp(-((v.co.x+.078)/.006)**2)

# Hair cards use constant materials, but FBX still requires a UV channel.
if not hair.data.uv_layers:
    uv = hair.data.uv_layers.new(name='FibreUV')
    for poly in hair.data.polygons:
        for i, loop in enumerate(poly.loop_indices):
            uv.data[loop].uv = ((i%2), i/max(1,len(poly.loop_indices)-1))
scene = bpy.context.scene; scene.frame_set(1)
rig.pose.bones['jaw'].rotation_mode = 'XYZ'
rig.pose.bones['jaw'].rotation_euler.x = .06
rig.pose.bones['tongue'].scale.y = .7
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Tangyuan-refined-neutral.blend'))
(out/'refinement.json').write_text(json.dumps({
    'input':a.input,'max_shoulder_displacement':maximum,
    'jaw':'small lower-beard deformation with skinned oral inserts',
    'identity_approved_by_owner':False,
    'limitations':['mouth interior is inferred','individual coat and shoulder anatomy still require visual review']
},indent=2),encoding='utf-8')
