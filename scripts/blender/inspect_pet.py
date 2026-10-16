"""Private multi-view geometry evidence. Does not alter or certify the input.

blender -b --factory-startup --disable-autoexec --python inspect_pet.py -- INPUT OUTPUT
OUTPUT must be new. Review photos separately; branch counts are only hints for
a standing cat facing Blender -Y, not a universal tail detector.
"""
import json
import math
from pathlib import Path
import sys
import hashlib
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pet_mesh_checks import rear_branches

source, output = (Path(s).resolve() for s in sys.argv[sys.argv.index('--')+1:])
output.mkdir(parents=True, exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
points = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
if not points or not all(math.isfinite(x) for p in points for x in p):
    raise ValueError('Empty or non-finite model')
lo=Vector([min(v[i] for v in points) for i in range(3)])
hi=Vector([max(v[i] for v in points) for i in range(3)])
center=(lo+hi)/2; size=max(hi-lo)
if size <= 0: raise ValueError('Invalid model dimensions')
report={'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'semanticStatus':'unknown', 'vertices':len(points), 'meshes':len(meshes),
        'rearBranchCountsAssumingMinusY':rear_branches(meshes),
        'rigs':len([o for o in bpy.context.scene.objects if o.type=='ARMATURE']),
        'warning':'Branch counts require confirmed orientation; inspect all views and references. Do not auto-delete branches.'}
scene=bpy.context.scene;scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=size*1.3
for name,direction in [('front',(0,-2,.4)),('rear',(0,2,.4)),('left',(-2,0,.4)),('right',(2,0,.4)),
                       ('rear-left',(-1,2,1)),('rear-right',(1,2,1)),('top',(0,.01,3)),('bottom',(0,.01,-3))]:
    camera.location=center+Vector(direction).normalized()*size*3
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(output/(name+'.png'));bpy.ops.render.render(write_still=True)
(output/'geometry-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report))
