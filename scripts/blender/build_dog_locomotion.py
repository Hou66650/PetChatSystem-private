"""Add weighted secondary joints and baked, grounded walk/trot/run cycles to both dogs."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path(__file__).resolve().parents[2];OUT=R/'art/dog-locomotion-v1';ASSET=R/'static/models/petchat-motion-v1'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
reports={}
for pet,source in [('qiuqiu','petchat-v3/qiuqiu.glb'),('xueqiu','petchat-husky-v2/xueqiu.glb')]:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(R/'static/models'/source))
 rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
 scene=bpy.context.scene;scene.render.fps=30
 # Imported NLA tracks (including eyelid tracks) preserve every existing clip.
 for obj in [rig]+[m.data.shape_keys for m in meshes if m.data.shape_keys]:
  if obj.animation_data:
   obj.animation_data.action=None
   for track in obj.animation_data.nla_tracks:track.mute=True
 for p in rig.pose.bones:p.matrix_basis.identity()
 before=len(rig.data.bones);bpy.context.view_layer.objects.active=rig;rig.select_set(True)
 specs=[('spine_front','spine'),('spine_rear','spine'),('neck_flex','neck'),('tail_mid','tail')]
 specs += [(('shoulder_' if leg[0]=='F' else 'hip_')+leg[1],leg+'_upper') for leg in ['FL','FR','HL','HR']]
 specs += [('toe_'+leg,leg+'_foot') for leg in ['FL','FR','HL','HR']]
 bpy.ops.object.mode_set(mode='EDIT')
 for name,parent in specs:
  src=rig.data.edit_bones[parent];b=rig.data.edit_bones.new(name);b.matrix=src.matrix.copy();b.length=src.length*.45;b.parent=src;b.use_deform=True
 bpy.ops.object.mode_set(mode='OBJECT')
 weighted={name:0 for name,_ in specs}
 for obj in meshes:
  for name,parent in specs:
   src=obj.vertex_groups.get(parent)
   if not src:continue
   group=obj.vertex_groups.new(name=name)
   for v in obj.data.vertices:
    weight=next((g.weight for g in v.groups if g.group==src.index),0)
    if weight<.001:continue
    x,y,z=v.co
    fraction=.3
    if name=='spine_front':fraction=.45*max(0,min(1,(.12-y)/.35))
    elif name=='spine_rear':fraction=.45*max(0,min(1,(y+.04)/.35))
    elif name.startswith('toe_'):fraction=.55
    elif name.startswith(('shoulder_','hip_')):fraction=.35*max(0,min(1,(z-.25)/.2))
    if weight*fraction<.001:continue
    src.add([v.index],weight*(1-fraction),'REPLACE');group.add([v.index],weight*fraction,'REPLACE');weighted[name]+=1
 assert all(weighted.values()),weighted
 bones=list(rig.pose.bones)
 def reset():
  for p in bones:p.matrix_basis.identity();p.rotation_mode='QUATERNION'
 def rotate(name,axis,value):
  p=rig.pose.bones[name];p.rotation_quaternion=Quaternion(p.bone.matrix_local.to_quaternion().inverted()@Vector(axis),value)
 targets={};constraints=[]
 for leg in ['FL','FR','HL','HR']:
  p=rig.pose.bones[leg+'_lower'];o=bpy.data.objects.new('Contact_'+leg,None);bpy.context.collection.objects.link(o);o.location=p.bone.tail_local;targets[leg]=o
  c=p.constraints.new('IK');c.target=o;c.chain_count=2;c.use_stretch=False;constraints.append((p,c))
 rests={leg:o.location.copy() for leg,o in targets.items()};errors={};created=[]
 cycles={'motion_walk':(1.1,.26,.68,.055),'motion_trot':(.8,.30,.55,.075),'run':(.666667,.30,.45,.1)}
 for name,(duration,stride,duty,lift) in cycles.items():
  frames=round(duration*30);samples=[];error=0
  phases={'FL':0,'FR':.5,'HL':.75,'HR':.25} if name=='motion_walk' else {'FL':0,'FR':.5,'HL':.5,'HR':0} if name=='motion_trot' else {'FL':0,'FR':.12,'HL':.52,'HR':.64}
  for frame in range(frames+1):
   reset();u=frame/frames;wave=math.sin(u*math.tau);spine=rig.pose.bones['spine'];spine.location=spine.bone.matrix_local.to_quaternion().inverted()@Vector((0,0,-.055+(.008 if name!='run' else .015)*math.cos(u*math.tau*2)))
   for control in ['spine_front','spine_rear','neck_flex','tail_mid']:
    rotate(control,(1,0,0),(.025 if name!='run' else .055)*math.sin(u*math.tau+(0 if control=='spine_front' else .8)))
   for leg,o in targets.items():
    phase=(u+phases[leg])%1
    if phase<duty:y=stride*(phase/duty-.5);height=0
    else:
     swing=(phase-duty)/(1-duty);y=stride*(.5-swing);height=lift*math.sin(math.pi*swing)**2
    o.location=rests[leg]+Vector((0,y,height))
    rotate(('shoulder_' if leg[0]=='F' else 'hip_')+leg[1],(1,0,0),.045*math.sin(math.tau*phase))
    rotate('toe_'+leg,(1,0,0),-.12*math.sin(math.pi*max(0,(phase-duty)/(1-duty))))
   rotate('head',(1,0,0),-.035*wave);rotate('tail',(0,0,1),.07*wave)
   for side in ['L','R']:rotate('ear_'+side,(1,0,0),.06*math.sin(u*math.tau+.7))
   bpy.context.view_layer.update()
   for leg in targets:
    p=rig.pose.bones[leg+'_foot'];m=p.bone.matrix_local.copy();m.translation=p.head;p.matrix=m
   bpy.context.view_layer.update();samples.append({p.name:p.matrix.copy() for p in bones})
   error=max(error,max((rig.pose.bones[leg+'_lower'].tail-o.location).length for leg,o in targets.items()))
  samples[-1]={key:value.copy() for key,value in samples[0].items()}
  errors[name]=round(error,6)
  for _,c in constraints:c.mute=True
  action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=action
  for frame,mats in enumerate(samples,1):
   scene.frame_set(frame);reset()
   for p in bones:
    if p.parent:p.matrix_basis=p.bone.convert_local_to_pose(mats[p.name],p.bone.matrix_local,parent_matrix=mats[p.parent.name],parent_matrix_local=p.parent.bone.matrix_local,invert=True)
    else:p.matrix_basis=p.bone.convert_local_to_pose(mats[p.name],p.bone.matrix_local,invert=True)
   for p in bones:
    for prop in ['location','rotation_quaternion','scale']:p.keyframe_insert(data_path=prop,frame=frame,group=p.name)
  created.append(action);rig.animation_data.action=None
  for _,c in constraints:c.mute=False
 for p,c in constraints:p.constraints.remove(c)
 for o in targets.values():bpy.data.objects.remove(o,do_unlink=True)
 for action in created:
  track=rig.animation_data.nla_tracks.new();track.name=action.name;strip=track.strips.new(action.name,1,action);strip.action_slot=action.slots[0];track.mute=True
 reset();scene.frame_set(1)
 bpy.ops.export_scene.gltf(filepath=str(ASSET/(pet+'.glb')),export_format='GLB',export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_def_bones=True,export_extras=True)
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(pet+'.blend')))
 reports[pet]={'bones_before':before,'bones_after':len(bones),'weighted_vertices':weighted,'contact_error_m':errors,'gaits':cycles,'bytes':(ASSET/(pet+'.glb')).stat().st_size}
 # Inspect a real run pose, with no generated image substitution.
 rig.animation_data.action=created[-1];rig.animation_data.action_slot=created[-1].slots[0];scene.frame_set(5)
 bpy.ops.object.camera_add(location=(2,-3,1.3));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,.5))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.65;scene.camera=cam
 for loc,power in [((2,-3,4),450),((-2,-1,2),200)]:
  bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=3;o.rotation_euler=(Vector((0,0,.4))-o.location).to_track_quat('-Z','Y').to_euler()
 scene.world=bpy.data.worlds.new('Studio');scene.world.color=(.5,.5,.5);scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/(pet+'-run.png'));bpy.ops.render.render(write_still=True)
(OUT/'build-report.json').write_text(json.dumps(reports,indent=2));print('MOTION_COMPLETE',json.dumps(reports))
