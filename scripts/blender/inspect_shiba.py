import bpy, json, math
from pathlib import Path
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art/shiba-v3'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-v2/qiuqiu.glb'))
report = []
for obj in bpy.data.objects:
    row = {'name':obj.name,'type':obj.type,'location':list(obj.location),'dimensions':list(obj.dimensions),'parent':obj.parent.name if obj.parent else None}
    if obj.type=='ARMATURE': row['bones']=[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None} for b in obj.data.bones]
    if obj.type=='MESH': row.update(vertices=len(obj.data.vertices),materials=[m.name for m in obj.data.materials],groups=[g.name for g in obj.vertex_groups])
    report.append(row)
(OUT/'source-inspection.json').write_text(json.dumps(report,indent=2),encoding='utf8')
for obj in bpy.data.objects:
    if obj.animation_data: obj.animation_data_clear()
    if obj.type=='ARMATURE':
        for bone in obj.pose.bones: bone.matrix_basis.identity()
bpy.context.view_layer.update()
meshes=[o for o in bpy.data.objects if o.type=='MESH']
pts=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
low=Vector(tuple(min(p[i] for p in pts) for i in range(3)))
high=Vector(tuple(max(p[i] for p in pts) for i in range(3)))
center=(low+high)/2
print('BOUNDS',list(low),list(high))
bpy.ops.object.camera_add(location=center+Vector((3,-5,2.3)))
camera=bpy.context.object
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=max(high-low)*1.35
bpy.context.scene.camera=camera
for loc,power,size in [((3,-4,6),800,5),((-4,-2,3),500,4),((1,4,5),900,3)]:
    bpy.ops.object.light_add(type='AREA',location=loc);bpy.context.object.data.energy=power;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=size
    bpy.context.object.rotation_euler=(center-bpy.context.object.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.7,.8,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100
scene.render.filepath=str(OUT/'source-preview.png');scene.render.image_settings.file_format='PNG'
bpy.ops.render.render(write_still=True)
