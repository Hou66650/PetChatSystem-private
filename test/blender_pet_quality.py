"""Run in Blender: synthetic duplicate tails and real mesh tear rejection."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts/blender'))
from pet_mesh_checks import rear_branches, mesh_snapshot, deformation_ratio

bpy.ops.wm.read_factory_settings(use_empty=True)
def sphere(location, scale):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=location)
    mesh=bpy.context.object;mesh.scale=scale
    bpy.context.view_layer.update()
    return mesh
body=sphere((0,0,.5),(.25,.5,.3))
tail=sphere((-.15,.75,.4),(.08,.35,.08))
assert rear_branches([body,tail]) == [1,1,1]
extra=sphere((.15,.75,.4),(.08,.35,.08))
assert rear_branches([body,tail,extra]) == [2,2,2]
rest=mesh_snapshot([body]);assert deformation_ratio(rest,rest,[body]) == 1
posed=[[p.copy() for p in part] for part in rest]
posed[0][0] += Vector((10,0,0))
try:
    deformation_ratio(rest,posed,[body])
except ValueError:
    pass
else:
    raise AssertionError('A torn vertex must be rejected')
print('PASS single tail, duplicate tail, unchanged mesh, torn mesh')
