"""Bind the inspected Tangyuan reconstruction and verify a short walk study.

Blender --background --python this.py -- --input refined.blend --output DIR
This writes a review asset only, never equips it in a user's pet account.
"""
import argparse,json,math,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix
sys.path.insert(0,str(Path(__file__).parent))
from pet_mesh_checks import binding_support,mesh_snapshot,deformation_ratio

p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--render-all',action='store_true')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
if (out/'Tangyuan-walk-study.blend').exists():raise FileExistsError('Use a new output directory')
bpy.ops.wm.open_mainfile(filepath=str(Path(args.input).resolve()))
body=bpy.data.objects['Tangyuan | reconstructed surface, original UV retained'];scene=bpy.context.scene
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
# Locate four actual paw clusters from the reconstructed low geometry.
a=np.asarray([v.co[:] for v in body.data.vertices]);low=a[a[:,2]<.12,:2]
centers=np.array([[np.percentile(low[:,0],q),np.percentile(low[:,1],r)] for q,r in [(20,20),(80,20),(20,80),(80,80)]])
for _ in range(40):
 labels=np.argmin(((low[:,None,:]-centers[None,:,:])**2).sum(axis=2),axis=1)
 updated=np.array([low[labels==i].mean(axis=0) for i in range(4)])
 if not np.isfinite(updated).all():raise ValueError('Four distinct paw clusters were not found')
 if np.max(np.abs(updated-centers))<1e-7:break
 centers=updated
front=sorted(sorted(centers.tolist(),key=lambda v:v[1])[:2]);rear=sorted(sorted(centers.tolist(),key=lambda v:v[1])[2:])
feet=dict(zip(['FL','FR','HL','HR'],front+rear))
if min(np.linalg.norm(np.array(x)-np.array(y)) for i,x in enumerate(feet.values()) for j,y in enumerate(feet.values()) if i<j)<.12:raise ValueError('Paw clusters overlap')
print('PAW_LANDMARKS',json.dumps(feet),flush=True)
bpy.ops.object.select_all(action='DESELECT');bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='Tangyuan | walk-study skeleton';rig.show_in_front=True
bpy.ops.object.mode_set(mode='EDIT');rig.data.edit_bones.remove(rig.data.edit_bones[0])
def bone(name,head,tail,parent=None,deform=True):
 b=rig.data.edit_bones.new(name);b.head=head;b.tail=tail;b.use_deform=deform
 if parent:b.parent=rig.data.edit_bones[parent]
 return b
bone('root',(0,0,0),(0,0,.1),deform=False)
bone('spine',(0,.25,.55),(0,-.14,.63),'root')
bone('neck',(0,-.14,.63),(.03,-.32,.78),'spine')
bone('head',(.03,-.32,.78),(.1,-.58,.76),'neck')
bone('tail',(0,.41,.72),(-.02,.46,.89),'spine')
for name,(x,y) in feet.items():
 front_leg=name.startswith('F');hip=(x*.72,y+(.08 if front_leg else -.08),.63)
 knee=(x*.95,y+(.15 if front_leg else -.17),.345);ankle=(x,y,.12)
 bone(name+'_upper',hip,knee,'spine');bone(name+'_lower',knee,ankle,name+'_upper')
 bone(name+'_foot',ankle,(x,y-.07,.045),name+'_lower')
 bone(name+'_goal',ankle,(x,y,.22),'root',False)
bpy.ops.object.mode_set(mode='POSE')
for name in feet:
 con=rig.pose.bones[name+'_lower'].constraints.new('IK');con.target=rig;con.subtarget=name+'_goal';con.chain_count=2;con.use_stretch=False
bpy.ops.object.mode_set(mode='OBJECT')

def weights(v):
 x,y,z=v
 # Continuous spatial masks avoid the seam tearing caused by hard head/leg cuts.
 tail=smooth(.7,.81,z)*smooth(.35,.43,y)
 head=(1-smooth(-.39,-.22,y))*smooth(.59,.77,z)*(1-tail)
 neck=(1-smooth(-.28,-.1,y))*smooth(.5,.73,z)*(1-head-tail)
 remaining=max(0,1-tail-head-neck)
 leg_region=(1-smooth(.4,.64,z))*max(1-smooth(-.25,-.1,y),smooth(.15,.31,y))*remaining
 result={'tail':tail,'head':head,'neck':neck,'spine':remaining-leg_region}
 front_weight=1-smooth(-.06,.12,y)
 foot=1-smooth(.09,.17,z);upper=smooth(.27,.44,z);lower=(1-foot)*(1-upper);upper*=1-foot
 for prefix,region in [('F',front_weight),('H',1-front_weight)]:
  middle=(feet[prefix+'L'][0]+feet[prefix+'R'][0])*.5;right=smooth(middle-.035,middle+.035,x)
  for side,amount in [('L',1-right),('R',right)]:
   name=prefix+side;amount*=region*leg_region
   result[name+'_foot']=foot*amount;result[name+'_lower']=lower*amount;result[name+'_upper']=upper*amount
 return result
def bind(obj):
 obj.parent=rig;groups={}
 for v in obj.data.vertices:
  values={k:w for k,w in weights(v.co).items() if w>.0001};total=sum(values.values())
  for name,w in values.items():
   if name not in groups:groups[name]=obj.vertex_groups.new(name=name)
   groups[name].add([v.index],w/total,'REPLACE')
 mod=obj.modifiers.new('Tangyuan skin binding','ARMATURE');mod.object=rig
bind(body)

# Keep editable film curves, using a restrained card groom for animated review.
hair_vertices=[];hair_faces=[];hair_material_indices=[];materials=[]
for obj in list(bpy.data.objects):
 if not obj.name.startswith('Fine groom ') or obj.type!='CURVE':continue
 material_index=len(materials);materials.append(obj.data.materials[0]);obj.hide_render=True;obj.hide_set(True)
 for i,spline in enumerate(obj.data.splines):
  if i%4:continue
  points=[Vector(point.co[:3]) for point in spline.points];root=points[0];mid=points[len(points)//2];tip=points[-1];d=(tip-root).normalized();side=d.cross(Vector((.3,.6,.7)))
  if side.length<.01:side=d.cross(Vector((1,0,0)))
  side.normalize();width=.00032;start=len(hair_vertices)
  hair_vertices.extend([root-side*width,root+side*width,mid-side*width*.5,mid+side*width*.5,tip]);hair_faces.extend([(start,start+1,start+3,start+2),(start+2,start+3,start+4)]);hair_material_indices.extend([material_index]*2)
mesh=bpy.data.meshes.new('Animated fine groom');mesh.from_pydata(hair_vertices,[],hair_faces);mesh.update();hair=bpy.data.objects.new('Tangyuan | animated review fibres',mesh);scene.collection.objects.link(hair)
for mat in materials:mesh.materials.append(mat)
for poly,index in zip(mesh.polygons,hair_material_indices):poly.material_index=index;poly.use_smooth=True
bind(hair)

support=binding_support([body],rig)
scene.frame_start=1;scene.frame_end=96;scene.render.fps=24
period=1.1;stance=.68;step=.14;speed=step/(period*stance)
phases={'FL':0,'FR':.5,'HL':.75,'HR':.25}
for frame in range(1,97):
 scene.frame_set(frame)
 t=(frame-1)/24;rig.location.y=.25-speed*t;rig.keyframe_insert('location',frame=frame)
 for name in feet:
  phase=(t/period+phases[name])%1
  if phase<stance:dy=-step*.5+step*phase/stance;lift=0
  else:
   s=(phase-stance)/(1-stance);tangent=step*(1-stance)/stance
   dy=(2*s**3-3*s*s+1)*step*.5+(s**3-2*s*s+s)*tangent+(-2*s**3+3*s*s)*(-step*.5)+(s**3-s*s)*tangent
   lift=.055*math.sin(math.pi*s)**2
  goal=rig.pose.bones[name+'_goal'];goal.location=goal.bone.matrix_local.to_3x3().inverted()@Vector((0,dy,lift));goal.keyframe_insert('location',frame=frame)
 head=rig.pose.bones['head'];head.rotation_mode='XYZ';head.rotation_euler=(.012*math.sin(t*math.tau/period),0,.025*math.sin(t*1.4));head.keyframe_insert('rotation_euler',frame=frame)
 tail=rig.pose.bones['tail'];tail.rotation_mode='XYZ';tail.rotation_euler=(0,.09*math.sin(t*3),0);tail.keyframe_insert('rotation_euler',frame=frame)
 spine=rig.pose.bones['spine'];spine.location=spine.bone.matrix_local.to_3x3().inverted()@Vector((0,0,.003*math.cos(t*math.tau/period*2)));spine.keyframe_insert('location',frame=frame)
 bpy.context.view_layer.update()
 for name in feet:
  foot=rig.pose.bones[name+'_foot'];ankle=rig.pose.bones[name+'_lower'].tail
  foot.rotation_mode='QUATERNION';foot.matrix=Matrix.Translation(ankle)@foot.bone.matrix_local.to_3x3().to_4x4();foot.keyframe_insert('rotation_quaternion',frame=frame)
# Validate posed edge deformation before claiming the rig works.
for pose in rig.pose.bones:pose.matrix_basis.identity()
rig.location.y=0;bpy.context.view_layer.update();rest=mesh_snapshot([body])
ratios={};contact_error={name:[] for name in feet}
sole_indices={}
for name in feet:
 group=body.vertex_groups[name+'_foot']
 candidates=[v.index for v in body.data.vertices if v.co.z<.06 and any(g.group==group.index and g.weight>.9 for g in v.groups)]
 if len(candidates)<5:raise ValueError(name+' has insufficient sole vertices')
 sole_indices[name]=candidates
plant_previous={};plant_slip={name:[] for name in feet};ground_heights={name:[] for name in feet}
for frame in [1,8,15,22,29,36,43,50,57,64,71,78,85,92,96]:
 scene.frame_set(frame);bpy.context.view_layer.update();snapshot=mesh_snapshot([body]);ratios[str(frame)]=deformation_ratio(rest,snapshot,[body])
 for name in feet:
  target=rig.matrix_world@rig.pose.bones[name+'_goal'].head;actual=rig.matrix_world@rig.pose.bones[name+'_lower'].tail
  contact_error[name].append((target-actual).length)
  phase=((frame-1)/24/period+phases[name])%1
  points=[snapshot[0][i] for i in sole_indices[name]];center=sum(points,Vector())/len(points)
  if phase<stance:
   ground_heights[name].append(min(v.z for v in points))
   prior=plant_previous.get(name)
   if prior and 0<phase-prior[0]<.4:plant_slip[name].append((center-prior[1]).length)
   plant_previous[name]=(phase,center)
  else:plant_previous.pop(name,None)
report={'paw_landmarks':feet,'binding_support':support,'maximum_edge_stretch_ratio':max(ratios.values()),'sampled_frames':len(ratios),'ik_target_error_max':{k:max(v) for k,v in contact_error.items()},'plant_slip_max':{k:max(v,default=0) for k,v in plant_slip.items()},'planted_sole_height_range':{k:[min(v),max(v)] for k,v in ground_heights.items()},'owner_approved':False,'status':'walk study; review motion and likeness before use','frames':96,'fps':24,'groom_cards':len(hair_faces)//2}
if max(report['ik_target_error_max'].values())>.06:raise ValueError('IK chain cannot reach its paw targets: '+str(report['ik_target_error_max']))
if max(report['plant_slip_max'].values())>.025:raise ValueError('Planted paws slide too far: '+str(report['plant_slip_max']))
(out/'walk-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
scene.frame_set(1);camera=scene.camera;camera.location=(2.5,-3,1.6);camera.rotation_euler=(Vector((0,-.15,.48))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=1.85
scene.render.resolution_x=960;scene.render.resolution_y=800;scene.cycles.samples=24;scene.render.use_persistent_data=True
try:
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for dev in prefs.devices:dev.use=dev.type!='CPU'
 scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Tangyuan-walk-study.blend'))
frames=out/'frames';frames.mkdir(exist_ok=True)
for frame in range(1,97) if args.render_all else [1,13,25]:
 scene.frame_set(frame);scene.render.filepath=str(frames/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
print('WALK_STUDY',json.dumps(report),flush=True)
