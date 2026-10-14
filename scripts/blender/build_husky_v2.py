"""Xueqiu expression rig: preserve the husky mesh/materials and all 20 original clips.
The acting/IK recipes follow Qiuqiu, with controls fitted to Xueqiu's anatomy.
Run with Blender --background --python scripts/blender/build_husky_v2.py.
"""
import bpy,math,json,bmesh
from pathlib import Path
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/husky-v2';ASSET=ROOT/'static/models/petchat-husky-v2'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-snow-v1/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
body=next(o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig)
for o in list(bpy.data.objects):
 if o not in (rig,body):bpy.data.objects.remove(o,do_unlink=True)
rig.name='Xueqiu_V2_Rig';body.name='Xueqiu_V2_Body'
original_actions=list(bpy.data.actions);rig.animation_data_clear()
for p in rig.pose.bones:p.matrix_basis.identity()
bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bm.to_mesh(body.data);bm.free();body.data.update()
neighbors=[set() for _ in body.data.vertices]
for edge in body.data.edges:
    a,b=edge.vertices;neighbors[a].add(b);neighbors[b].add(a)
weights=[{g.group:g.weight for g in v.groups} for v in body.data.vertices]
for iteration in range(5):
    updated=[]
    for i,w in enumerate(weights):
        near=neighbors[i];avg={k:v*.6 for k,v in w.items()}
        if not near:updated.append(w);continue
        for j in near:
            for k,v in weights[j].items():avg[k]=avg.get(k,0)+v*.4/len(near)
        updated.append(avg)
    weights=updated
for i,w in enumerate(weights):
    for g in body.vertex_groups:
        if g.index in w:g.add([i],w[g.index],'REPLACE')
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for side,s in [('L',-1),('R',1)]:
 for name,head,tail in [('ear_'+side,(s*.15,-.405,.875),(s*.16,-.405,1.048)),('brow_'+side,(s*.09,-.577,.85),(s*.09,-.577,.90)),('cheek_'+side,(s*.145,-.59,.70),(s*.185,-.59,.74))]:
  b=rig.data.edit_bones.new(name);b.head=head;b.tail=tail;b.parent=rig.data.edit_bones['head']
for name,head,tail,parent in [('tongue',(0,-.655,.553),(0,-.723,.553),'jaw'),('tail_tip',(.075,.64,.80),(.06,.5,.85),'tail')]:
 b=rig.data.edit_bones.new(name);b.head=head;b.tail=tail;b.parent=rig.data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for n in ['ear_L','ear_R','brow_L','brow_R','cheek_L','cheek_R','tongue','tail_tip']:body.vertex_groups.new(name=n)
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def transfer(v,source,dest,f):
 g=body.vertex_groups[source];w=next((a.weight for a in v.groups if a.group==g.index),0)
 if w*f>.0001:g.add([v.index],w*(1-f),'REPLACE');body.vertex_groups[dest].add([v.index],w*f,'REPLACE')
for v in body.data.vertices:
 x,y,z=v.co;side='L' if x<0 else 'R'
 if abs(x)>.08 and -.48<y<-.32 and z>.88:transfer(v,'head','ear_'+side,smooth(.88,.95,z))
 if -.62<y<-.53 and .84<z<.91:transfer(v,'head','brow_'+side,.72*math.exp(-((abs(x)-.09)/.045)**2-((z-.858)/.027)**2))
 if -.68<y<-.51 and .64<z<.75:transfer(v,'head','cheek_'+side,.5*math.exp(-((abs(x)-.14)/.04)**2-((z-.69)/.04)**2))
 if abs(x)<.043 and y<-.67 and z<.56:transfer(v,'jaw','tongue',.9)
 if z>.79:transfer(v,'tail','tail_tip',smooth(.79,.9,z)*.65)
def mat(name,color,rough=.65):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;return m
tan=mat('Husky_eyelid_fur',(.79,.83,.86),.85)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=(0,-.692,.552))
detail=bpy.context.object;detail.name='Xueqiu_Tongue';detail.scale=(.026,.047,.007)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
detail.data.materials.append(mat('Husky_tongue',(.55,.16,.19),.5));detail.parent=rig
g=detail.vertex_groups.new(name='tongue');g.add(list(range(len(detail.data.vertices))),1,'REPLACE');mod=detail.modifiers.new('Skin','ARMATURE');mod.object=rig
for p in detail.data.polygons:p.use_smooth=True

# Anatomical eyelid shells: open lids tuck around the rim; closing lids cover
# the unchanged eyeballs. Two morph channels allow asymmetric blinks/squints.
lidverts=[];lidfaces=[];lidmats=[];lidmeta=[]
def lidpoint(side,upper,col,row,close):
    xn=-1+2*col/20;cap=math.sqrt(max(0,1-xn*xn))
    edge=(.94*(1-close)-.025*close) if upper else (-.94*(1-close)+.025*close)
    zn=(edge+(1-edge)*row/8) if upper else (edge+(-1-edge)*row/8)
    z=zn*cap;depth=math.sqrt(max(0,1-xn*xn-z*z))
    return (side*.091465+xn*.036,-.583957-depth*.022-.001+close*.025,.795139+z*.051)
for side in (-1,1):
    for upper in (True,False):
        offset=len(lidverts)
        for row in range(9):
            for col in range(21):lidverts.append(lidpoint(side,upper,col,row,0));lidmeta.append((side,upper,col,row))
        for row in range(8):
            for col in range(20):
                a=offset+row*21+col;lidfaces.append((a,a+1,a+22,a+21));lidmats.append(0 if upper else 1)
mesh=bpy.data.meshes.new('Anatomical_eyelids');mesh.from_pydata(lidverts,[],lidfaces);mesh.update()
lids=bpy.data.objects.new('Xueqiu_V2_Eyelids',mesh);bpy.context.collection.objects.link(lids);lids.parent=rig
lids.data.materials.append(tan);lids.data.materials.append(tan)
for p,mi in zip(mesh.polygons,lidmats):p.material_index=mi;p.use_smooth=True
g=lids.vertex_groups.new(name='head');g.add(list(range(len(lidverts))),1,'REPLACE');mod=lids.modifiers.new('Skin','ARMATURE');mod.object=rig
lids.shape_key_add(name='Basis')
for name,sign in [('Blink_L',-1),('Blink_R',1)]:
    key=lids.shape_key_add(name=name)
    for i,(side,upper,col,row) in enumerate(lidmeta):
        if side==sign:key.data[i].co=lidpoint(side,upper,col,row,1)
rig['design_reference']='art/shiba-v3/expression-design.png'
rig['motion_reference']='art/shiba-v3/motion-blueprint.png'
rig['expression_controls']='ear_L/R, brow_L/R, cheek_L/R, tongue, tail_tip; eye/lid controls retained'
body['surface_finished']=True;body['asset_version']='2.0'

scene=bpy.context.scene;scene.render.fps=30
new_bones=['ear_L','ear_R','brow_L','brow_R','cheek_L','cheek_R','tongue','tail_tip']
allbones=list(rig.pose.bones)
def reset():
    for p in allbones:p.matrix_basis.identity();p.rotation_mode='QUATERNION'
    for name in ('lid_L','lid_R'):rig.pose.bones[name].scale=(.001,.001,.001)
def rotate(name,axis,angle):
    p=rig.pose.bones[name];local=p.bone.matrix_local.to_quaternion().inverted()@Vector(axis)
    p.rotation_quaternion=p.rotation_quaternion@Quaternion(local,angle)
def move(name,vec):
    p=rig.pose.bones[name];p.location+=p.bone.matrix_local.to_quaternion().inverted()@Vector(vec)
lid_values=[0,0]
def face(joy=0,shy=0,alert=0,sleep=0,curious=0,mouth=0,t=0):
    global lid_values
    lid_values=[max(0,min(1,.48*joy+.98*sleep))]*2
    for side,s in [('L',-1),('R',1)]:
        rotate('ear_'+side,(0,1,0),s*(joy*.16+shy*.32+sleep*.22-alert*.08))
        rotate('ear_'+side,(1,0,0),shy*.16+sleep*.1-alert*.12+math.sin(t*3+s)*.015)
        move('brow_'+side,(0,-.003*joy,.012*alert+.007*curious-.009*sleep))
        rotate('brow_'+side,(0,1,0),s*(shy*.18-joy*.08))
        move('cheek_'+side,(s*.006*joy,-.002*joy,.010*joy))
        # Cartoon eye compression follows the existing v2 blink convention.
        rig.pose.bones['eye_'+side].scale=(1,1,1)
        move('eye_'+side,(0,.042*lid_values[0],0))
        rig.pose.bones['lid_'+side].scale=(1,1,1) if lid_values[0]>.62 else (.001,.001,.001)
    rotate('jaw',(1,0,0),mouth)
    rotate('tongue',(1,0,0),-.18*mouth)
    rotate('tail',(0,0,1),math.sin(t*8)*(.04+.14*joy))
    rotate('tail_tip',(1,0,0),.05*joy*math.sin(t*8-1))

# IK is only an authoring aid. Every result is baked back into deform bones.
targets={};constraints=[]
for leg in ['FL','FR','HL','HR']:
    p=rig.pose.bones[leg+'_lower'];o=bpy.data.objects.new('IK_'+leg,None);bpy.context.collection.objects.link(o)
    o.location=p.bone.tail_local;targets[leg]=o
    c=p.constraints.new('IK');c.name='Authoring_contact';c.target=o;c.chain_count=2;c.use_stretch=False;constraints.append((p,c))
rest_targets={k:o.location.copy() for k,o in targets.items()}
def contact_targets(kind,e,t):
    for k,o in targets.items():o.location=rest_targets[k]
    if kind=='paw_greeting':targets['FL'].location+=Vector((-.025,-.10,.17))*e
    if kind=='play_bow':
        for k in ('FL','FR'):targets[k].location.y-=.055*e

clips={
 'curious_listen':2.4,'ear_perk':1.6,'shy_look':2.8,'alert_scan':3.0,
 'sleepy_yawn':3.2,'affection':2.6,'surprised':1.6,'play_bow':2.8,
 'paw_greeting':2.4,'nose_lick':1.8,'shake_off':2.0,'tail_greeting':2.4,
}
created=[];face_actions=[];contact_error={}
for kind,duration in clips.items():
    print('AUTHOR',kind,flush=True);rig.animation_data_clear();reset();samples=[];end=round(duration*30)+1;maxerr=0
    for frame in range(1,end+1):
        scene.frame_set(frame);reset();u=(frame-1)/(end-1);t=u*duration
        e=smooth(0,.23,u)*(1-smooth(.73,1,u));contact_targets(kind,e,t)
        move('spine',(0,0,.003*math.sin(t*2*math.pi/duration)))
        if kind=='curious_listen':
            rotate('head',(0,1,0),math.radians(18)*e*(1-.28*math.sin(u*math.pi*2)))
            rotate('head',(0,0,1),.06*e);rotate('ear_L',(1,0,0),-.2*e);face(curious=e,t=t)
        elif kind=='ear_perk':face(alert=e*.8,t=t);rotate('ear_R',(1,0,0),-.16*e)
        elif kind=='shy_look':rotate('head',(1,0,0),.14*e);rotate('head',(0,1,0),-.13*e);face(shy=e,joy=e*.2,t=t)
        elif kind=='alert_scan':rotate('head',(0,0,1),.23*math.sin(u*math.pi*2)*e);face(alert=e,t=t)
        elif kind=='sleepy_yawn':
            gape=math.sin(math.pi*u)**4;rotate('head',(1,0,0),-.17*gape)
            face(sleep=e,mouth=.30*gape,t=t);move('tongue',(0,-.012*gape,.010*gape))
        elif kind=='affection':rotate('head',(0,1,0),.12*e);rotate('head',(1,0,0),-.06*e);face(joy=e*.95,mouth=.07*e,t=t)
        elif kind=='surprised':rotate('head',(1,0,0),-.10*e);face(alert=e,mouth=.17*e,t=t)
        elif kind=='play_bow':
            rotate('spine',(1,0,0),.28*e);move('spine',(0,-.015*e,-.058*e))
            rotate('neck',(1,0,0),.1*e);rotate('head',(1,0,0),-.28*e);face(joy=e*.6,mouth=.08*e,t=t)
        elif kind=='paw_greeting':
            move('spine',(.017*e,0,-.006*e));rotate('head',(0,1,0),-.09*e)
            face(joy=e*.65,mouth=.04*e,t=t)
        elif kind=='nose_lick':
            face(joy=e*.3,mouth=.09*e,t=t);rotate('tongue',(1,0,0),-.85*e);move('tongue',(0,-.022*e,.045*e));rotate('head',(0,1,0),.055*e)
        elif kind=='shake_off':
            a=math.sin(t*15)*e;rotate('spine',(0,1,0),.055*a);rotate('head',(0,0,1),.18*a)
            face(t=t);rotate('ear_L',(0,1,0),.18*math.sin(t*15-.6)*e);rotate('ear_R',(0,1,0),.18*math.sin(t*15+.6)*e)
        elif kind=='tail_greeting':
            rotate('head',(0,1,0),.09*math.sin(t*3)*e);face(joy=e*.8,mouth=.06*e,t=t);rotate('tail',(0,0,1),.13*math.sin(t*11)*e)
        bpy.context.view_layer.update()
        # Preserve ankle world orientation while legs bend, and curl the raised paw.
        for leg in targets:
            p=rig.pose.bones[leg+'_foot'];m=p.matrix.copy();m=p.bone.matrix_local.copy();m.translation=p.head
            if kind=='paw_greeting' and leg=='FL':
                q=Quaternion((1,0,0),-.5*e)@Quaternion((0,1,0),.18*math.sin(t*9)*e);m=q.to_matrix().to_4x4()@m;m.translation=p.head
            p.matrix=m
        bpy.context.view_layer.update()
        sample={p.name:p.matrix.copy() for p in allbones};samples.append((sample,list(lid_values)))
        for leg,o in targets.items():maxerr=max(maxerr,(rig.pose.bones[leg+'_lower'].tail-o.location).length)
    contact_error[kind]=round(maxerr,6)
    for _,c in constraints:c.mute=True
    action=bpy.data.actions.new(kind);action.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=action
    for frame,(mats,eyes) in enumerate(samples,1):
        scene.frame_set(frame);reset()
        for p in allbones:p.matrix=mats[p.name]
        for p in allbones:
            for prop in ('location','rotation_quaternion','scale'):p.keyframe_insert(data_path=prop,frame=frame,group=p.name)
    created.append(action)
    rig.animation_data.action=None
    keys=lids.data.shape_keys;keys.animation_data_create()
    fa=bpy.data.actions.new(kind+'_eyelids');fa.use_fake_user=True;keys.animation_data.action=fa
    for frame,(_,eyes) in enumerate(samples,1):
        for name,value in zip(('Blink_L','Blink_R'),eyes):keys.key_blocks[name].value=value;keys.key_blocks[name].keyframe_insert(data_path='value',frame=frame)
    face_actions.append((kind,fa));keys.animation_data.action=None
    for _,c in constraints:c.mute=False
for p,c in constraints:p.constraints.remove(c)
for o in targets.values():bpy.data.objects.remove(o,do_unlink=True)
rig.animation_data_clear();reset()
# Export every named clip through NLA tracks, avoiding accidental merged actions.
rig.animation_data_create()
for action in original_actions+created:
    action.use_fake_user=True
    track=rig.animation_data.nla_tracks.new();track.name=action.name
    strip=track.strips.new(action.name,1,action);strip.action_slot=action.slots[0];track.mute=True
keys=lids.data.shape_keys
for name,action in face_actions:
    track=keys.animation_data.nla_tracks.new();track.name=name;strip=track.strips.new(name,1,action);strip.action_slot=action.slots[0];track.mute=True
for key in list(keys.key_blocks)[1:]:key.value=0
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
for o in (rig,body,detail,lids):o.select_set(True)
bpy.context.view_layer.objects.active=rig
ASSET_FILE=ASSET/'xueqiu.glb'
bpy.ops.export_scene.gltf(filepath=str(ASSET_FILE),export_format='GLB',use_selection=True,
    export_animations=True,export_animation_mode='NLA_TRACKS',export_nla_strips_merged_animation_name='Animation',
    export_force_sampling=True,export_frame_range=False,export_def_bones=True,export_skins=True,export_extras=True)

# Editable studio source and honest Blender renders, separate from concept art.
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;reset();scene.frame_set(1)
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(1.65,-2.8,1.5));camera=bpy.context.object;camera.name='Portrait_camera';look(camera,(0,-.06,.54));camera.data.type='ORTHO';camera.data.ortho_scale=1.55;scene.camera=camera
for name,loc,power,size in [('Key',(2,-3,4),400,3),('Fill',(-2,-1,2),180,3),('Rim',(0,3,3),500,2)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;look(o,(0,0,.5))
floor_mat=mat('Studio_warm_ivory',(.72,.68,.58),.95)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.001));floor=bpy.context.object;floor.name='Studio_floor';floor.data.materials.append(floor_mat)
if scene.world is None:scene.world=bpy.data.worlds.new('Studio_world')
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.7,.78,.9,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.frame_start=1;scene.frame_end=97
for img in bpy.data.images:
    if img.has_data:
        try:img.pack()
        except RuntimeError:pass
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'xueqiu-v2.blend'))
report={'source':'static/models/petchat-snow-v1/xueqiu.glb','bones':len(rig.data.bones),'vertices':len(body.data.vertices)+len(detail.data.vertices)+len(lids.data.vertices),'original_clips':[a.name for a in original_actions],'new_clips':clips,'foot_ik_max_error_m':contact_error,'glb_bytes':ASSET_FILE.stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
for name in ['neutral',*clips]:
    rig.animation_data.action=bpy.data.actions.get(name);reset()
    keys.animation_data.action=dict(face_actions).get(name)
    if keys.animation_data.action:keys.animation_data.action_slot=keys.animation_data.action.slots[0]
    else:
        for key in list(keys.key_blocks)[1:]:key.value=0
    if rig.animation_data.action:rig.animation_data.action_slot=rig.animation_data.action.slots[0];scene.frame_set(round(clips[name]*30*.48)+1)
    else:scene.frame_set(1)
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
rig.animation_data.action=None;reset();scene.frame_set(1)
print('BUILD_COMPLETE',json.dumps(report))
