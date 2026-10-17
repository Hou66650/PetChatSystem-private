"""Prepare a neutral Tangyuan rig and apply a separately reviewed video match.

Private images/annotations belong outside the repository. First run prepares the
neutral asset and landmark definition; --motion applies a fitted, non-looping
shot. Coordinates are metres in Blender, seconds in the source video.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, Euler

p = argparse.ArgumentParser()
p.add_argument('--input', required=True)
p.add_argument('--output', required=True)
p.add_argument('--motion')
p.add_argument('--render', action='store_true')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()))
scene = bpy.context.scene
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = bpy.data.objects['Tangyuan | reconstructed surface, original UV retained']
hair = bpy.data.objects['Tangyuan | animated review fibres']
rig.animation_data_clear(); rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
for b in rig.pose.bones:
    b.matrix_basis.identity()

def smooth(lo, hi, x):
    t = min(1, max(0, (x - lo) / (hi - lo)))
    return t*t*(3-2*t)

def straighten(v):
    # The reconstructed muzzle faces +X while the torso faces -Y. Correct the
    # rest geometry, including fibres, with a continuous neck transition.
    weight = smooth(.38, .50, v.z) * (1-smooth(-.23, -.08, v.y)) * max(smooth(.59,.70,v.z), smooth(-.10,.02,v.x))
    pivot = Vector((.08, -.43, .78))
    rotated = Matrix.Rotation(-math.pi/2, 3, 'Z') @ (v-pivot) + pivot + Vector((-.15, 0, 0))
    return v.lerp(rotated, weight)

if not a.motion:
    for obj in (body, hair):
        for v in obj.data.vertices:
            v.co = straighten(v.co)
        obj.data.update()
    # Curves are retained in the source study, but are not a second visible
    # groom in this animated deliverable.
    for obj in list(bpy.data.objects):
        if obj.name.startswith('Fine groom '):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    rig.data.edit_bones['head'].head = (-.07, -.35, .73)
    rig.data.edit_bones['head'].tail = (-.07, -.60, .73)
    rig.data.edit_bones['neck'].tail = (-.07, -.35, .73)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Full head rigid influence, smooth throat/neck weights. Keep limb weights.
    for obj in (body, hair):
        h = obj.vertex_groups['head']; n = obj.vertex_groups['neck']; s = obj.vertex_groups['spine']
        for v in obj.data.vertices:
            old = {g.group:g.weight for g in v.groups}
            available = sum(old.get(g.index, 0) for g in (h,n,s))
            head = smooth(.40,.53,v.co.z)*(1-smooth(-.27,-.12,v.co.y))*max(smooth(.62,.74,v.co.z),1-smooth(-.48,-.34,v.co.y))
            neck = (1-head)*(1-smooth(-.25,-.08,v.co.y))*smooth(.52,.7,v.co.z)
            for g, w in ((h,head),(n,neck),(s,1-head-neck)):
                g.add([v.index], available*w, 'REPLACE')
    nose = body.data.vertices[8345].co.copy()
    crown = body.data.vertices[2849].co.copy()
    landmarks = {'nose':list(nose), 'crown':list(crown), 'tail':[-.02,.46,.94]}
    for name in ('FL','FR','HL','HR'):
        landmarks[name] = list(rig.data.bones[name+'_foot'].head_local - Vector((0,.025,.075)))
    (out/'landmarks-3d.json').write_text(json.dumps({'points':landmarks,'head_pivot':list(rig.data.bones['head'].head_local)},indent=2))
    scene.frame_set(1)
    camera = scene.camera; camera.location = (0,-3,1.3)
    camera.rotation_euler = (Vector((0,-.1,.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=1.65
    scene.render.resolution_x=800; scene.render.resolution_y=800
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Tangyuan-neutral.blend'))
else:
    motion=json.loads(Path(a.motion).read_text(encoding='utf-8'))
    sys.path.insert(0,str(Path(__file__).parent))
    from pet_mesh_checks import mesh_snapshot,deformation_ratio
    bpy.context.view_layer.update();rest=mesh_snapshot([body])
    camera=scene.camera; camera.data.type='PERSP'; camera.data.sensor_fit='HORIZONTAL'
    camera.data.sensor_width=20.25; camera.data.lens=motion['camera']['lens']
    camera.location=motion['camera']['position']
    camera.rotation_euler=motion['camera']['rotation_euler']
    scene.render.resolution_x=720;scene.render.resolution_y=1280
    scene.render.fps=30;scene.frame_start=1;scene.frame_end=len(motion['frames'])
    for i, f in enumerate(motion['frames'],1):
        scene.frame_set(i);rig.location=f['root'];rig.rotation_euler=(0,0,f['yaw'])
        camera.rotation_euler=f['camera_euler'];camera.keyframe_insert('rotation_euler',frame=i)
        camera.location=f['camera_position'];camera.keyframe_insert('location',frame=i)
        rig.keyframe_insert('location',frame=i);rig.keyframe_insert('rotation_euler',frame=i)
        head=rig.pose.bones['head']; pivot=head.bone.head_local
        transform=Matrix.Translation(pivot) @ Euler(f['head_euler'],'XYZ').to_matrix().to_4x4() @ Matrix.Translation(-pivot)
        head.matrix=transform @ head.bone.matrix_local
        head.rotation_mode='QUATERNION';head.keyframe_insert('rotation_quaternion',frame=i);head.keyframe_insert('location',frame=i)
        if 'jaw' in rig.pose.bones:
            jaw=rig.pose.bones['jaw'];jaw.rotation_mode='XYZ'
            jaw.rotation_euler=(float(f.get('jaw_open',0)),0,0)
            jaw.keyframe_insert('rotation_euler',frame=i)
        if 'tongue' in rig.pose.bones:
            tongue=rig.pose.bones['tongue'];tongue.scale=(1,float(f.get('tongue_extension',.7)),1)
            tongue.keyframe_insert('scale',frame=i)
        for name, xyz in f['feet'].items():
            goal=rig.pose.bones[name+'_goal']
            goal.location=goal.bone.matrix_local.to_3x3().inverted() @ (Vector(xyz)-goal.bone.head_local)
            goal.keyframe_insert('location',frame=i)
        bpy.context.view_layer.update()
        for name in f['feet']:
            foot=rig.pose.bones[name+'_foot'];ankle=rig.pose.bones[name+'_lower'].tail
            foot.rotation_mode='QUATERNION';foot.matrix=Matrix.Translation(ankle) @ foot.bone.matrix_local.to_3x3().to_4x4()
            foot.keyframe_insert('rotation_quaternion',frame=i)
    validation={'frames':[],'source':'manual monocular fit, not motion capture','owner_approved':False}
    for i,f in enumerate(motion['frames'],1):
        scene.frame_set(i);bpy.context.view_layer.update()
        posed=mesh_snapshot([body]);ratio=deformation_ratio(rest,posed,[body])
        ik=max((rig.pose.bones[n+'_goal'].head-rig.pose.bones[n+'_lower'].tail).length for n in f['feet'])
        validation['frames'].append({'source_frame':f['source_frame'],'edge_stretch':ratio,'ik_error':ik,'lowest_surface_z':min(v.z for v in posed[0])})
    validation['max_ik_error']=max(f['ik_error'] for f in validation['frames'])
    validation['max_edge_stretch']=max(f['edge_stretch'] for f in validation['frames'])
    validation['min_surface_z']=min(f['lowest_surface_z'] for f in validation['frames'])
    (out/'pose-validation.json').write_text(json.dumps(validation,indent=2))
    if validation['max_ik_error']>.035:raise ValueError('Fitted paw targets exceed IK reach')
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Tangyuan-matched.blend'))
    # Export baked FK evaluation, not Blender-only IK controls. UE import has
    # its own verification; successful FBX export alone is not an UE pass.
    bpy.ops.object.select_all(action='DESELECT')
    skinned=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
    for obj in [*skinned,rig]:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.fbx(filepath=str(out/'Tangyuan-matched.fbx'),use_selection=True,
        object_types={'ARMATURE','MESH'},axis_forward='-Y',axis_up='Z',
        add_leaf_bones=False,use_armature_deform_only=False,bake_anim=True,
        bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_simplify_factor=0,path_mode='COPY',embed_textures=True,mesh_smooth_type='FACE')

if a.render:
    scene.cycles.samples=16;scene.render.use_persistent_data=True
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for dev in prefs.devices:dev.use=dev.type!='CPU'
    scene.cycles.device='GPU'
    scene.render.filepath=str(out/('matched-preview.png' if a.motion else 'neutral-corrected.png'))
    bpy.ops.render.render(write_still=True)
