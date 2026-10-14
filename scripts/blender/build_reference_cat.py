"""Fit reference-reconstructed Tabby to the Cat companion rig and mesh fur.
Input model comes from the generated tabby reference-image reconstruction.
"""
import bpy,bmesh,math,random,json,sys,bisect
import numpy as np
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import material,studio
R=Path(__file__).resolve().parents[2];OUT=R/'art/cat-v2';DEST=R/'static/models/petchat-cat-v2';DEST.mkdir(exist_ok=True)
random.seed(915)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-motion-v1/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');rig.name='Tabby_reference_companion'
for o in list(bpy.data.objects):
 if o.type=='MESH':bpy.data.objects.remove(o,do_unlink=True)
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
for p in rig.pose.bones:p.matrix_basis.identity()
bpy.ops.import_scene.gltf(filepath=str(OUT/'rodin-detail.glb'))
body=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices));body.name='Reference_cat_skin'
bpy.context.view_layer.objects.active=body;body.select_set(True);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
# Align body longitudinal axis to the shared companion's negative-Y forward convention.
rotation=Matrix.Identity(4);floor=min(v.co.z for v in body.data.vertices);height=max(v.co.z for v in body.data.vertices)-floor;scale=1.0/height
for v in body.data.vertices:
 p=rotation@v.co;p.z-=floor;p*=scale;p.y+=.02;v.co=p
# Weld UV seams geometrically while preserving UVs per loop; remove tiny floating reconstruction scraps.
bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00003)
seen=set();remove=[]
for v in bm.verts:
 if v in seen:continue
 stack=[v];component=[];seen.add(v)
 while stack:
  a=stack.pop();component.append(a)
  for e in a.link_edges:
   b=e.other_vert(a)
   if b not in seen:seen.add(b);stack.append(b)
 if len(component)<10:remove.extend(component)
if remove:bmesh.ops.delete(bm,geom=remove,context='VERTS')
bm.to_mesh(body.data);bm.free();body.data.update()
mod=body.modifiers.new('Reconstruction cleanup','SMOOTH');mod.factor=.28;mod.iterations=2;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=body.modifiers.new('Surface refinement','SUBSURF');mod.levels=1;mod.render_levels=1;bpy.ops.object.modifier_apply(modifier=mod.name)
for p in body.data.polygons:p.use_smooth=True
body.data.normals_split_custom_set_from_vertices([v.normal for v in body.data.vertices])
mat=body.data.materials[0];bs=mat.node_tree.nodes.get('Principled BSDF')
for name in ['Metallic','Roughness','Normal']:
 for link in list(bs.inputs[name].links):mat.node_tree.links.remove(link)
bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.86
atlas=bs.inputs['Base Color'].links[0].from_node.image
# Base color connection identifies the actual albedo node without relying on import order.
texture=bs.inputs['Base Color'].links[0].from_node;texture.image=atlas
pix=np.empty(atlas.size[0]*atlas.size[1]*4,dtype=np.float32);atlas.pixels.foreach_get(pix);pix=pix.reshape(atlas.size[1],atlas.size[0],4)
def sample(uv):
 rgb=pix[int(max(0,min(atlas.size[1]-1,uv.y*(atlas.size[1]-1)))),int(max(0,min(atlas.size[0]-1,uv.x*(atlas.size[0]-1)))),:3]
 return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def fit(p):
 x,y,z=p;t=smooth(.50,.70,z)
 return Vector((x*.80+.025*t,y*.85-.20,z*1.03))
bpy.context.view_layer.objects.active=rig;bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for b in rig.data.edit_bones:b.head=fit(b.head);b.tail=fit(b.tail)
for name,head,tail in [('tail',(.02,.23,.59),(.05,.42,.78)),('tail_mid',(.05,.42,.78),(.08,.59,.96)),('tail_tip',(.08,.59,.96),(.08,.66,.95)),('jaw',(.06,-.45,.75),(.10,-.54,.74)),('tongue',(.10,-.53,.74),(.11,-.58,.73)),('SOCKET_mouth',(.104,-.55,.745),(.104,-.60,.745))]:
 b=rig.data.edit_bones[name];b.head=head;b.tail=tail
bpy.ops.object.mode_set(mode='OBJECT')
# Region-aware weights keep legs distinct across the belly and preserve the reconstructed face.
def weights(p):
 x,y,z=p;side='L' if x<0 else 'R'
 if z<.56 and (y<-.25 or y>-.03):
  leg=('F' if y<-.20 else 'H')+side
  foot=1-smooth(.08,.15,z);upper=smooth(.27,.41,z);lower=(1-foot)*(1-upper);upper*=1-foot
  region=1-smooth(-.37,-.25,y) if y<-.25 else smooth(-.03,.12,y)
  limb=(1-smooth(.43,.56,z))*region
  return {leg+'_foot':foot*limb,leg+'_lower':lower*limb,leg+'_upper':upper*limb,'spine':1-limb}
 if y<-.35 and z>.67:
  h=smooth(.67,.78,z)
  if z>.88:
   ear=smooth(.88,.94,z);return {'head':1-ear,'ear_'+side:ear}
  # A soft lower-jaw influence supports speech while keeping the skull stable.
  jaw=(1-smooth(.745,.78,z))*smooth(-.49,-.56,y) if y<-.49 and z>.71 else 0
  jaw=max(0,min(.85,jaw))
  return {'head':h*(1-jaw),'neck':(1-h)*(1-jaw),'jaw':jaw}
 neck=(1-smooth(-.37,-.22,y))*smooth(.54,.73,z)
 return {'spine':(1-neck)*.7,'spine_front' if y<0 else 'spine_rear':(1-neck)*.3,'neck':neck}
w=[{k:v for k,v in weights(v.co).items() if v>.00001} for v in body.data.vertices]
adj=[set() for _ in body.data.vertices]
for e in body.data.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
# Surface-geodesic segmentation separates the tail from nearby hind legs even where
# their bounding boxes overlap; a coordinate threshold cuts the tail into strips.
import heapq
points=[v.co.copy() for v in body.data.vertices]
def geodesic(seed_positions):
 distances=[float('inf')]*len(points);queue=[]
 for pos in seed_positions:
  target=Vector(pos);index=min(range(len(points)),key=lambda i:(points[i]-target).length_squared);distances[index]=0;heapq.heappush(queue,(0,index))
 while queue:
  distance,index=heapq.heappop(queue)
  if distance!=distances[index]:continue
  for other in adj[index]:
   candidate=distance+(points[index]-points[other]).length
   if candidate<distances[other]:distances[other]=candidate;heapq.heappush(queue,(candidate,other))
 return distances
tail_dist=geodesic([(.08,.58,.95),(.05,.43,.79)])
body_dist=geodesic([(-.14,.10,.06),(.06,.24,.06),(-.12,.15,.48),(.12,.15,.48),(0,-.10,.63),(0,-.4,.68)])
for i,(tail_d,body_d) in enumerate(zip(tail_dist,body_dist)):
 if not math.isfinite(tail_d) or not math.isfinite(body_d) or points[i].y<.12 or points[i].z<.52:continue
 t=smooth(-.04,.15,body_d-tail_d)
 if t>.001:
  mid=smooth(.64,.80,points[i].z);tip=smooth(.86,.96,points[i].z)
  w[i]={'tail':t*(1-mid),'tail_mid':t*mid*(1-tip),'tail_tip':t*mid*tip,'spine_rear':1-t}
for _ in range(8):
 updated=[]
 for i,wi in enumerate(w):
  mixed={k:v*.6 for k,v in wi.items()}
  for j in adj[i]:
   for k,v in w[j].items():mixed[k]=mixed.get(k,0)+v*.4/max(1,len(adj[i]))
  top=sorted(mixed.items(),key=lambda a:a[1],reverse=True)[:4];total=sum(v for _,v in top);updated.append({k:v/total for k,v in top})
 w=updated

def bind(obj,weights):
 obj.parent=rig;groups={}
 for i,wi in enumerate(weights):
  for name,value in wi.items():
   if name not in groups:groups[name]=obj.vertex_groups.new(name=name)
   groups[name].add([i],value,'REPLACE')
 mod=obj.modifiers.new('Companion armature','ARMATURE');mod.object=rig
bind(body,w)
# Preserve glTF facial interface. Blink landmarks are refined against actual front render.
body.shape_key_add(name='Basis')
landmarks=json.loads((OUT/'face-landmarks.json').read_text())
blink_report={}
for side in ['L','R']:
 key=body.shape_key_add(name='Blink_'+side);key.value=0;eye=Vector(landmarks['eye_'+side]['point']);normal=Vector(landmarks['eye_'+side]['normal']);horizontal=Vector((-normal.y,normal.x,0)).normalized();affected=0
 for vertex,target in zip(body.data.vertices,key.data):
  d=vertex.co-eye;u=d.dot(horizontal);depth=d.dot(normal);vertical=d.z
  radius=math.hypot(u/.025,vertical/.020)
  influence=(1-smooth(1,1.65,radius))*(1-smooth(.04,.075,abs(depth)))
  if influence>.002:
   target.co.z+=(eye.z-.002-vertex.co.z)*influence;target.co+=normal*.0015*influence;affected+=1
 blink_report[side]=affected
assert min(blink_report.values())>15,blink_report
# Fur ribbons use the same UV pigment as the reconstructed surface, with a soft silhouette.
mesh=body.data;mesh.calc_loop_triangles();tris=list(mesh.loop_triangles);acc=[];total=0
for tri in tris:total+=tri.area;acc.append(total)
vs=[];faces=[];colors=[];hairweights=[];normals=[];uvs=mesh.uv_layers.active.data
for _ in range(18000):
 tri=tris[bisect.bisect_left(acc,random.random()*total)];a,b,c=[mesh.vertices[i] for i in tri.vertices]
 u=math.sqrt(random.random());v=random.random();f=(1-u,u*(1-v),u*v)
 p=sum((a.co*t for a,t in zip([a,b,c],f)),Vector());n=sum((a.normal*t for a,t in zip([a,b,c],f)),Vector()).normalized()
 if p.z<.12:continue
 # Leave the eyes, nose, tongue, inner ears and collar readable.
 if p.y<-.45 and p.z>.72:continue
 uv=sum((uvs[i].uv*t for i,t in zip(tri.loops,f)),Vector((0,0)))
 color=sample(uv)
 if color[2]>color[0]*1.8 and color[1]>color[0]*1.2:continue
 if p.z>.9 and p.y<0:continue
 neck=p.y<-.25 and p.z>.55;tail=p.y>.53
 length=random.uniform(.007,.015) if neck or tail else random.uniform(.004,.009)
 if p.z<.40:length=random.uniform(.003,.007)
 d=Vector((p.x*.3,.5,-1)) if neck or tail else Vector((p.x*.2,1,-.4))
 if p.z<.48:d=Vector((0,.2,-1))
 d=(d-n*d.dot(n)).normalized();side=n.cross(d).normalized();width=random.uniform(.00045,.00070)
 root=p+n*.0005;mid=p+d*length*.5+n*length*.15;tip=p+d*length+n*length*.09
 i=len(vs);vs.extend([root-side*width,root+side*width,mid-side*width*.5,mid+side*width*.5,tip]);faces.extend([(i+2,i+3,i+1,i),(i+4,i+3,i+2)]);normals.extend([n]*5)
 merged={}
 for vertex,t in zip([a,b,c],f):
  for k,val in w[vertex.index].items():merged[k]=merged.get(k,0)+val*t
 top=sorted(merged.items(),key=lambda a:a[1],reverse=True)[:4];totalw=sum(v for _,v in top);merged={k:v/totalw for k,v in top}
 shade=random.uniform(.88,1.12)
 for t in [.80,.80,1,1,1.10]:colors.append((*[min(.9,float(c)*shade*t) for c in color],1));hairweights.append(merged)
# Whiskers are tapered geometry, following the head rather than a painted line.
mouth=Vector(landmarks['mouth']['point']);horizontal=Vector((.65,.76,0));normal=Vector((.76,-.65,0))
for side_sign in [-1,1]:
 for j in range(7):
  root=mouth+horizontal*side_sign*.025+normal*.012+Vector((0,0,.015+(j-3)*.003))
  direction=horizontal*side_sign*random.uniform(.10,.16)+normal*random.uniform(.015,.04)+Vector((0,0,(j-3)*.009))
  start=len(vs);axis=direction.normalized();u=axis.cross(Vector((0,0,1))).normalized();v=axis.cross(u)
  for k in range(7):
   t=k/6;p=root+direction*t+normal*(.018*t*t);radius=.00065*(1-t)+.00008
   for q in range(3):
    n=u*math.cos(q*math.tau/3)+v*math.sin(q*math.tau/3);vs.append(p+n*radius);normals.append(n);colors.append((.65,.65,.61,1));hairweights.append({'head':1})
  for k in range(6):
   for q in range(3):a=start+k*3+q;c=start+k*3+(q+1)%3;faces.append((a,c,c+3,a+3))
hmesh=bpy.data.meshes.new('Reference_fur');hmesh.from_pydata(vs,[],faces);hmesh.update();fur=bpy.data.objects.new('Reference_fur',hmesh);bpy.context.collection.objects.link(fur)
fm=material('Directional_coat_fibres',(.2,.1,.04),.93);vc=fm.node_tree.nodes.new('ShaderNodeVertexColor');vc.layer_name='Coat';fm.node_tree.links.new(vc.outputs['Color'],fm.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);hmesh.materials.append(fm)
for p in hmesh.polygons:p.use_smooth=True
hmesh.normals_split_custom_set_from_vertices(normals);attr=hmesh.color_attributes.new(name='Coat',type='FLOAT_COLOR',domain='POINT')
for c,col in zip(attr.data,colors):c.color=col
bind(fur,hairweights)
# Keep each source action's local translation amplitude proportional to the new limbs.
for track in rig.animation_data.nla_tracks:
 for layer in track.strips[0].action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     if fc.data_path.endswith('.location'):
      for k in fc.keyframe_points:k.co.y*=1.0;k.handle_left.y*=1.0;k.handle_right.y*=1.0
# Replant the new anatomy's paws during sitting transitions, then bake local transforms.
scene=bpy.context.scene
for obj in [body,fur]:obj.modifiers[-1].show_viewport=False
bones=list(rig.pose.bones);constraints=[];targets={}
for leg in ['FL','FR','HL','HR']:
 target=bpy.data.objects.new('Ground_'+leg,None);bpy.context.collection.objects.link(target);targets[leg]=target
 c=rig.pose.bones[leg+'_lower'].constraints.new('IK');c.target=target;c.chain_count=2;c.use_stretch=False;c.mute=True;constraints.append(c)
for track in rig.animation_data.nla_tracks:
 if track.name not in ['sit_idle','sit_down','stand_up']:continue
 action=track.strips[0].action;rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0];snapshots=[]
 start=math.floor(action.frame_range[0]);end=math.ceil(action.frame_range[1])
 for frame in range(start,end+1):
  for c in constraints:c.mute=True
  scene.frame_set(frame);bpy.context.view_layer.update()
  phase=(frame-start)/max(1,end-start);influence=1 if track.name=='sit_idle' else smooth(0,1,phase if track.name=='sit_down' else 1-phase)
  for leg,target in targets.items():
   foot=rig.pose.bones[leg+'_foot'];target.location=foot.head;target.location.z+=(foot.bone.head_local.z-target.location.z)*influence
  for c in constraints:c.mute=False
  bpy.context.view_layer.update()
  for leg in targets:
   foot=rig.pose.bones[leg+'_foot'];matrix=foot.bone.matrix_local.copy();matrix.translation=foot.head;foot.matrix=matrix
  bpy.context.view_layer.update();snapshots.append({p.name:p.matrix.copy() for p in bones})
 for c in constraints:c.mute=True
 # Imported clips have fractional-frame keys. Replace them, rather than interleaving
 # integer bake keys with the old values (which corrupts the exported NLA sampling).
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:fc.keyframe_points.clear()
 for frame,mats in zip(range(start,end+1),snapshots):
  scene.frame_set(frame)
  for bone in bones:
   if bone.parent:bone.matrix_basis=bone.bone.convert_local_to_pose(mats[bone.name],bone.bone.matrix_local,parent_matrix=mats[bone.parent.name],parent_matrix_local=bone.parent.bone.matrix_local,invert=True)
   else:bone.matrix_basis=bone.bone.convert_local_to_pose(mats[bone.name],bone.bone.matrix_local,invert=True)
  for bone in bones:
   for prop in ['location','rotation_quaternion','scale']:bone.keyframe_insert(data_path=prop,frame=frame,group=bone.name)
 track.strips[0].action_frame_start=start;track.strips[0].action_frame_end=end
 track.strips[0].frame_start=1;track.strips[0].frame_end=1+end-start
for leg in targets:
 for constraint in list(rig.pose.bones[leg+'_lower'].constraints):rig.pose.bones[leg+'_lower'].constraints.remove(constraint)
 bpy.data.objects.remove(targets[leg],do_unlink=True)
# Retargeted paws and muzzle have different extents. Bake a minimal upward root
# correction from the actual weighted surface, including fractional source times.
skin_points=np.array([[*v.co,1] for v in body.data.vertices]);groups={}
for i,wi in enumerate(w):
 for name,value in wi.items():groups.setdefault(name,[]).append((i,value))
groups={name:(np.array([i for i,_ in items]),np.array([v for _,v in items])) for name,items in groups.items()}
inverses={name:rig.data.bones[name].matrix_local.inverted() for name in groups}
root=rig.pose.bones['root']
for track in rig.animation_data.nla_tracks:
 action=track.strips[0].action;rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
 frames=range(math.floor(action.frame_range[0]),math.ceil(action.frame_range[1])+1);values=[]
 for frame in frames:
  scene.frame_set(frame);bpy.context.view_layer.update();heights=np.zeros(len(skin_points))
  for name,(indices,strength) in groups.items():
   matrix=np.array(rig.pose.bones[name].matrix@inverses[name]);heights[indices]+=(skin_points[indices]@matrix[2])*strength
  lift=max(0,.003-float(heights.min()));matrix=root.matrix.copy();matrix.translation.z+=lift
  basis=root.bone.convert_local_to_pose(matrix,root.bone.matrix_local,invert=True);values.append(basis.to_translation())
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in bag.fcurves:
     if fc.data_path=='pose.bones["root"].location':fc.keyframe_points.clear()
 for frame,value in zip(frames,values):root.location=value;root.keyframe_insert(data_path='location',frame=frame,group='root')
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
for obj in [body,fur]:obj.modifiers[-1].show_viewport=True
for p in rig.pose.bones:p.matrix_basis.identity()
rig['reference']='art/cat-v2/reconstruction-reference.png';rig['source']='Reference-image reconstruction, then Blender cleanup and companion rig'
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
for o in [rig,body,fur]:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(DEST/'cat.glb'),export_format='GLB',use_selection=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_def_bones=True,export_extras=True,export_morph_normal=False)
rig.animation_data.action=None
for t in rig.animation_data.nla_tracks:t.mute=True
for p in rig.pose.bones:p.matrix_basis.identity()
for k in body.data.shape_keys.key_blocks:k.value=0
bpy.context.view_layer.update()
report={'source':'rodin-detail.glb','blink_vertices':blink_report,'bones':len(rig.data.bones),'triangles':sum(len(p.vertices)-2 for o in [body,fur] for p in o.data.polygons),'fur_strands':(len(vs)-14*7*3)//5,'whiskers':14,'bytes':(DEST/'cat.glb').stat().st_size}
(OUT/'cat-report.json').write_text(json.dumps(report,indent=2));print('REFERENCE_MODEL',report)
studio(OUT,(0,0,.50),(1.65,-2.8,1.05),1.60,'cat-studio',(1200,1200))
scene=bpy.context.scene
for name,pos in [('front',(0,-4,.6)),('side',(4,0,.6))]:
 scene.camera.location=pos;scene.camera.rotation_euler=(Vector((0,0,.6))-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
