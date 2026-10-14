"""Render exported GLB poses, validating the shipped skin rather than a concept image."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2];OUT=R/'art/cat-v2'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-cat-v2/cat.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');scene=bpy.context.scene
actions={t.name:t.strips[0].action for t in rig.animation_data.nla_tracks}
for t in rig.animation_data.nla_tracks:t.mute=True
bpy.ops.object.camera_add(location=(1.7,-2.6,1.25));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.55))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.95;scene.camera=cam
for p,power in [((2,-4,5),700),((-3,-2,3),500)]:
    bpy.ops.object.light_add(type='AREA',location=p);o=bpy.context.object;o.data.energy=power;o.data.size=4;o.rotation_euler=(Vector((0,0,.5))-o.location).to_track_quat('-Z','Y').to_euler()
scene.world=bpy.data.worlds.new('Validation');scene.world.color=(.32,.36,.40);scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True;scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100
report={}
for name,frame in [('run',5),('sit_idle',15),('play_bow',24)]:
    a=actions[name];rig.animation_data.action=a;rig.animation_data.action_slot=a.slots[0];scene.frame_set(frame);bpy.context.view_layer.update()
    dep=bpy.context.evaluated_depsgraph_get();vertices=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not any(m.type=='ARMATURE' for m in obj.modifiers):continue
        evaluated=obj.evaluated_get(dep);mesh=evaluated.to_mesh();vertices.extend([evaluated.matrix_world@v.co for v in mesh.vertices]);evaluated.to_mesh_clear()
    assert all(math.isfinite(v) for p in vertices for v in p)
    bounds=[[min(p[i] for p in vertices),max(p[i] for p in vertices)] for i in range(3)];assert max(hi-lo for lo,hi in bounds)<3,bounds
    assert bounds[2][0]>-.015, (name,'exported pose penetrates floor',bounds[2])
    report[name]={'bounds':bounds,'vertices':len(vertices)};scene.render.filepath=str(OUT/(name+'-validation.png'));bpy.ops.render.render(write_still=True)
(OUT/'pose-report.json').write_text(json.dumps(report,indent=2));print('POSES_VALID',report)

rig.animation_data.action=None
for p in rig.pose.bones:p.matrix_basis.identity()
scene.camera.location=(1.15,-2.5,1.16);scene.camera.rotation_euler=(Vector((.06,-.48,.82))-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=.38
for state in ['open','closed']:
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                if key.name.startswith('Blink_'):key.value=1 if state=='closed' else 0
    scene.render.filepath=str(OUT/('eyes-'+state+'.png'));bpy.ops.render.render(write_still=True)
