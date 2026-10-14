"""Refine the shipped cat's facial materials and fine vibrissae without retargeting its rig.
The v2 source stays immutable. Output is shared by the native cat and coat builder.
"""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2]
dest=R/'static/models/petchat-cat-v3';dest.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-cat-v2/cat.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
rig.animation_data.action=None
for t in rig.animation_data.nla_tracks:t.mute=True
for b in rig.pose.bones:b.matrix_basis.identity()
body=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.polygons))
# Identify the textured skin rather than the fibre mesh by material texture input.
body=next(o for o in bpy.data.objects if o.type=='MESH' and any(m and m.use_nodes and any(n.type=='TEX_IMAGE' for n in m.node_tree.nodes) for m in o.data.materials))
landmarks=json.loads((R/'art/cat-v2/face-landmarks.json').read_text())
base=body.data.materials[0]
for name,rough in [('Cat_cornea',.19),('Cat_nose',.38),('Cat_inner_ear',.72)]:
 mat=base.copy();mat.name=name;mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=rough;body.data.materials.append(mat)
eyes=[Vector(landmarks['eye_'+side]['point']) for side in ['L','R']];nose=Vector(landmarks['mouth']['point'])+Vector((0,-.004,.026))
counts=[0,0,0,0]
for face in body.data.polygons:
 p=sum((body.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
 if min((p-e).length for e in eyes)<.021:face.material_index=1
 elif (p-nose).length<.014:face.material_index=2
 elif p.z>.91 and p.y<-.35:face.material_index=3
 counts[face.material_index]+=1
# Fine curved supraorbital whiskers, with tapered tips, skinned to the head.
# Low triangle cost; these are actual geometry, not a painted highlight.
verts=[];faces=[]
horizontal=Vector((.65,.76,0));normal=Vector((.76,-.65,0))
for eye,sign in zip(eyes,[-1,1]):
 for j in range(4):
  root=eye+Vector((0,0,.027+j*.003))+normal*.003
  direction=horizontal*sign*(.035+j*.008)+Vector((0,0,.055+j*.008))
  axis=direction.normalized();u=axis.cross(normal).normalized();v=axis.cross(u);start=len(verts)
  for k in range(7):
   t=k/6;p=root+direction*t+normal*(.012*t*t);radius=.00035*(1-t)+.000035
   for q in range(3):verts.append(p+(u*math.cos(q*math.tau/3)+v*math.sin(q*math.tau/3))*radius)
  for k in range(6):
   for q in range(3):a=start+k*3+q;b=start+k*3+(q+1)%3;faces.append((a,b,b+3,a+3))
mesh=bpy.data.meshes.new('Brow_vibrissae');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('Brow_vibrissae',mesh);bpy.context.collection.objects.link(obj);obj.parent=rig
group=obj.vertex_groups.new(name='head');group.add(list(range(len(verts))),1,'REPLACE');mod=obj.modifiers.new('Head attachment','ARMATURE');mod.object=rig
mat=bpy.data.materials.new('Whisker_satin');mat.diffuse_color=(.47,.45,.39,1);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.47,.45,.39,1);bs.inputs['Roughness'].default_value=.56;mesh.materials.append(mat)
for f in mesh.polygons:f.use_smooth=True
rig['polish']='Anatomical eye/nose roughness regions and eight tapered brow vibrissae; original facial morphs and 35 clips retained.'
bpy.context.view_layer.update();bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(dest/'cat.glb'),export_format='GLB',use_selection=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_def_bones=True,export_extras=True,export_morph_normal=False)
print('CAT_POLISH',counts,'brow triangles',len(faces)*2,'bytes',(dest/'cat.glb').stat().st_size)
