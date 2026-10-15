"""Render photo-taking examples from the shipped Tangyuan model (no cloud calls).
Run with Blender --background --python scripts/blender/render_cat_photo_guide.py.
Convert output PNGs to static/images/pet-photo-guide/*.webp with Pillow,
quality=88, method=6. The cat faces -Y, so its anatomical left is +X.
"""
import bpy, math
from pathlib import Path
from mathutils import Vector, Matrix
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/cat-photo-guide'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-cat-v3/cat.glb'))
for obj in bpy.context.scene.objects:
    if obj.animation_data:
        obj.animation_data.action=None
        for track in obj.animation_data.nla_tracks: track.mute=True
    if obj.type=='ARMATURE':
        for bone in obj.pose.bones: bone.matrix_basis.identity()
# Bake a neutral, forward-facing guide pose without changing the shipped rig.
bpy.context.view_layer.update()
dep=bpy.context.evaluated_depsgraph_get()
pivot=Vector((.025,-.44,.72));rotation=Matrix.Rotation(-math.atan2(.76,.65),3,'Z')
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
for obj in list(bpy.context.scene.objects):
    if obj.type!='MESH' or obj.hide_render or obj.name=='Icosphere': continue
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(dep),depsgraph=dep)
    obj.modifiers.clear();obj.data=mesh
    inverse=obj.matrix_world.inverted()
    for v in mesh.vertices:
        point=obj.matrix_world@v.co
        weight=smooth(.54,.76,point.z)*(1-smooth(-.30,-.12,point.y))
        moved=pivot+rotation@(point-pivot)
        v.co=inverse@point.lerp(moved,weight)
bpy.context.view_layer.update()
dep=bpy.context.evaluated_depsgraph_get(); points=[]
for obj in bpy.context.scene.objects:
    if obj.type!='MESH' or obj.hide_render or obj.name=='Icosphere': continue
    evaluated=obj.evaluated_get(dep); mesh=evaluated.to_mesh()
    points.extend(evaluated.matrix_world@v.co for v in mesh.vertices)
    evaluated.to_mesh_clear()
lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
center=(lo+hi)/2; size=max(hi-lo)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.resolution_x=720;scene.render.resolution_y=600;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Soft daylight');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.79,.75,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
bpy.ops.mesh.primitive_plane_add(size=size*200,location=(0,0,lo.z-.006))
floor=bpy.context.object;mat=bpy.data.materials.new('Warm neutral floor');mat.diffuse_color=(.78,.82,.75,1);floor.data.materials.append(mat)
for offset,energy in [((2,-3,4),450),((-3,1,3),300)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*size)
    lamp=bpy.context.object;lamp.data.energy=energy*size*size;lamp.data.size=size*3
    lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
for name,direction in [('stand',(-2,-3,.7)),('front',(0,-4,.15)),('left',(4,0,.15)),('right',(-4,0,.15)),('back',(0,4,.15)),('detail',(-1,-4,.4))]:
    target=center.copy();cam.data.ortho_scale=size*1.32
    if name=='detail':
        target=Vector((center.x,lo.y+(hi.y-lo.y)*.18,lo.z+(hi.z-lo.z)*.72));cam.data.ortho_scale=size*.65
    cam.location=target+Vector(direction)*size
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
print('PHOTO_GUIDE_DONE',OUT)
