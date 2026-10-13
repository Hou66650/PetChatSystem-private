"""Reproducible Qiuqiu v3 authoring. Run in Blender or through the local MCP bridge.

Preserves v2 mesh, materials and 20 clips; adds weighted expression controls,
small sculpted details and 12 acting clips with baked foot IK. No remote assets.
"""
import bpy, math, json, bmesh
from pathlib import Path
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/shiba-v3'; ASSET=ROOT/'static/models/petchat-v3'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions): bpy.data.actions.remove(a)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-v2/qiuqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
body=next(o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig)
for o in list(bpy.data.objects):
    if o not in (rig,body): bpy.data.objects.remove(o,do_unlink=True)
rig.name='Qiuqiu_V3_Rig';body.name='Qiuqiu_V3_Body'
original_actions=list(bpy.data.actions)
rig.animation_data_clear()
for p in rig.pose.bones:p.matrix_basis.identity()
# Weld exporter seams before skin smoothing; corner color/UV data stays on loops.
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
bpy.context.view_layer.objects.active=rig;rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for side,s in [('L',-1),('R',1)]:
    for name,head,tail,parent in [
        ('ear_'+side,(s*.186,-.37,.871),(s*.23,-.37,1.05),'head'),
        ('brow_'+side,(s*.115,-.513,.863),(s*.115,-.513,.915),'head'),
        ('cheek_'+side,(s*.146,-.563,.685),(s*.185,-.563,.735),'head')]:
        b=rig.data.edit_bones.new(name);b.head=head;b.tail=tail;b.parent=rig.data.edit_bones[parent]
b=rig.data.edit_bones.new('tongue');b.head=(0,-.605,.551);b.tail=(0,-.66,.543);b.parent=rig.data.edit_bones['jaw']
b=rig.data.edit_bones.new('tail_tip');b.head=(.03,.4,.79);b.tail=(.05,.34,.81);b.parent=rig.data.edit_bones['tail']
bpy.ops.object.mode_set(mode='OBJECT')
for name in ['ear_L','ear_R','brow_L','brow_R','cheek_L','cheek_R','tongue','tail_tip']:body.vertex_groups.new(name=name)
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def transfer(v,source,dest,f):
    vg=body.vertex_groups[source]
    weight=next((g.weight for g in v.groups if g.group==vg.index),0)
    if weight*f<.0001:return
    vg.add([v.index],weight*(1-f),'REPLACE');body.vertex_groups[dest].add([v.index],weight*f,'REPLACE')
for v in body.data.vertices:
    x,y,z=v.co;side='L' if x<0 else 'R'
    # Continuous feathered ear roots avoid hard seams at the scalp.
    if abs(x)>.135 and -.45<y<-.30 and z>.883:
        transfer(v,'head','ear_'+side,smooth(.885,.945,z)*smooth(.13,.175,abs(x)))
    if -.57<y<-.47 and .835<z<.91:
        strength=math.exp(-((abs(x)-.113)/.05)**2-((z-.867)/.034)**2)*.85
        transfer(v,'head','brow_'+side,strength)
    if -.65<y<-.5 and .64<z<.75:
        transfer(v,'head','cheek_'+side,.55*math.exp(-((abs(x)-.16)/.048)**2-((z-.691)/.055)**2))
    if abs(x)<.039 and y<-.613 and z<.561:transfer(v,'jaw','tongue',.9)
    if y<.4 and z>.77:transfer(v,'tail','tail_tip',smooth(.77,.865,z)*.65)
    # Seat the eyes inside the sockets instead of leaving protruding buttons.
    if any(body.vertex_groups[g.group].name in ('eye_L','eye_R') and g.weight>.6 for g in v.groups):
        center=Vector((-.116 if x<0 else .116,-.538,.797));v.co=center+(v.co-center)*.92;v.co.y+=.008
    if any(body.vertex_groups[g.group].name in ('lid_L','lid_R') and g.weight>.6 for g in v.groups):v.co.y+=.020

# Details are real skinned geometry; keep them low enough for the web renderer.
def mat(name,color,rough=.55,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m
cream=mat('V3_cream_fur',(.82,.69,.50),.8)
tan=mat('V3_ear_fur',(.60,.31,.12),.8)
pad=mat('V3_paw_pads',(.07,.034,.024),.64)
claw=mat('V3_short_claws',(.48,.37,.26),.48)
nose=mat('V3_nostril',(.014,.009,.007),.28)
oral=mat('V3_mouth_interior',(.035,.012,.012),.65)
details=[]
def skin(o,name,bone,material):
    o.name=name;o.data.materials.clear();o.data.materials.append(material)
    bpy.context.view_layer.objects.active=o;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    o.parent=rig;g=o.vertex_groups.new(name=bone);g.add(list(range(len(o.data.vertices))),1,'REPLACE')
    m=o.modifiers.new('Skin','ARMATURE');m.object=rig
    for p in o.data.polygons:p.use_smooth=True
    details.append(o);return o
def ellipsoid(name,loc,scale,bone,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=loc)
    o=bpy.context.object;o.scale=scale;return skin(o,name,bone,material)
def tuft(name,start,end,width,bone,material):
    # Rounded leaf-shaped clumps with a broad embedded root, not cones or spikes.
    axis=Vector(end)-Vector(start);q=axis.to_track_quat('Z','Y');verts=[];faces=[]
    rings=6;sides=8
    for j in range(rings):
        t=j/(rings-1);r=width*(.58+.65*math.sin(math.pi*t))*(1-t)**.65+.0002
        for i in range(sides):
            a=i*2*math.pi/sides;v=q@Vector((r*math.cos(a),r*.4*math.sin(a),axis.length*t))+Vector(start);verts.append(v)
    for j in range(rings-1):
        for i in range(sides):faces.append((j*sides+i,j*sides+(i+1)%sides,(j+1)*sides+(i+1)%sides,(j+1)*sides+i))
    faces.extend([tuple(reversed(range(sides))),tuple(range((rings-1)*sides,rings*sides))])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);return skin(o,name,bone,material)
for side,s in [('L',-1),('R',1)]:
    for i in range(5):
        z=.635+i*.018
        tuft('Cheek_fur_'+side+str(i),(s*(.196+i*.002),-.454,z),(s*(.227+i*.003),-.445,z-.022),.011,'head',cream)
    for i in range(3):tuft('Inner_ear_'+side+str(i),(s*(.17+i*.018),-.419,.916+i*.024),(s*(.178+i*.018),-.419,.941+i*.024),.006,'ear_'+side,cream)
    ellipsoid('Nostril_'+side,(s*.026,-.693,.698),(.009,.0035,.0045),'head',nose)
ellipsoid('Mouth_cavity',(0,-.570,.597),(.096,.069,.046),'head',oral)
for leg,x,y in [('FL',-.155,-.259),('FR',.155,-.259),('HL',-.155,.26),('HR',.155,.26)]:
    ellipsoid(leg+'_metacarpal_pad',(x,y,.009),(.032,.036,.006),leg+'_foot',pad)
    for i in range(4):
        dx=(i-1.5)*.020
        ellipsoid(leg+'_toe_pad_'+str(i),(x+dx,y-.040,.012),(.009,.014,.005),leg+'_foot',pad)
        ellipsoid(leg+'_claw_'+str(i),(x+dx,y-.075,.031),(.0038,.009,.0035),leg+'_foot',claw)
for i in range(7):
    x=(i-3)*.022
    tuft('Chest_fur_'+str(i),(x,-.36,.434),(x*1.04,-.367,.401+abs(x)*.2),.012,'neck',cream)
# Closed lid creases follow the actual head surface, rather than floating discs.
head_group=body.vertex_groups['head'].index
head_polys=[list(p.vertices) for p in body.data.polygons if all(any(g.group==head_group and g.weight>.45 for g in body.data.vertices[i].groups) for i in p.vertices)]
head_bvh=BVHTree.FromPolygons([v.co for v in body.data.vertices],head_polys)
for side,s in [('L',-1),('R',1)]:
    points=[]
    for j in range(17):
        u=-1+j/8;x=s*.116+u*.034;z=.792+.008*(1-u*u)
        hit,_,_,_=head_bvh.ray_cast(Vector((x,-2,z)),Vector((0,1,0)))
        points.append((x,(hit.y if hit else -.565)-.003,z))
    curve=bpy.data.curves.new('Closed_lid_crease_'+side,'CURVE');curve.dimensions='3D';curve.bevel_depth=.0016;curve.bevel_resolution=2
    spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):p.co=(*co,1)
    o=bpy.data.objects.new(curve.name,curve);bpy.context.collection.objects.link(o);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH');skin(bpy.context.object,curve.name,'lid_'+side,nose)
# Consolidate detail meshes into one skinned object and five draw-call materials.
bpy.ops.object.select_all(action='DESELECT')
for o in details:o.select_set(True)
bpy.context.view_layer.objects.active=details[0];bpy.ops.object.join();detail=bpy.context.object;detail.name='Qiuqiu_V3_Details'
# Anatomical eyelid shells: open lids tuck around the rim; closing lids cover
# the unchanged eyeballs. Two morph channels allow asymmetric blinks/squints.
lidverts=[];lidfaces=[];lidmats=[];lidmeta=[]
def lidpoint(side,upper,col,row,close):
    xn=-1+2*col/20;cap=math.sqrt(max(0,1-xn*xn))
    edge=(.94*(1-close)-.025*close) if upper else (-.94*(1-close)+.025*close)
    zn=(edge+(1-edge)*row/8) if upper else (edge+(-1-edge)*row/8)
    z=zn*cap;depth=math.sqrt(max(0,1-xn*xn-z*z))
    return (side*.116+xn*.042,-.530-depth*.031-.001+close*.042,.797+z*.049)
for side in (-1,1):
    for upper in (True,False):
        offset=len(lidverts)
        for row in range(9):
            for col in range(21):lidverts.append(lidpoint(side,upper,col,row,0));lidmeta.append((side,upper,col,row))
        for row in range(8):
            for col in range(20):
                a=offset+row*21+col;lidfaces.append((a,a+1,a+22,a+21));lidmats.append(0 if upper else 1)
mesh=bpy.data.meshes.new('Anatomical_eyelids');mesh.from_pydata(lidverts,[],lidfaces);mesh.update()
lids=bpy.data.objects.new('Qiuqiu_V3_Eyelids',mesh);bpy.context.collection.objects.link(lids);lids.parent=rig
lids.data.materials.append(tan);lids.data.materials.append(tan)
for p,mi in zip(mesh.polygons,lidmats):p.material_index=mi;p.use_smooth=True
g=lids.vertex_groups.new(name='head');g.add(list(range(len(lidverts))),1,'REPLACE');mod=lids.modifiers.new('Skin','ARMATURE');mod.object=rig
lids.shape_key_add(name='Basis')
for name,sign in [('Blink_L',-1),('Blink_R',1)]:
    key=lids.shape_key_add(name=name)
    for i,(side,upper,col,row) in enumerate(lidmeta):
        if side==sign:key.data[i].co=lidpoint(side,upper,col,row,1)
rig['design_sheet']='art/shiba-v3/expression-design.png'
rig['motion_sheet']='art/shiba-v3/motion-blueprint.png'
rig['expression_controls']='ear_L/R, brow_L/R, cheek_L/R, tongue, tail_tip; eye/lid controls retained'
body['surface_finished']=True;body['asset_version']='3.0'

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
ASSET_FILE=ASSET/'qiuqiu.glb'
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
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.frame_start=1;scene.frame_end=97
for img in bpy.data.images:
    if img.has_data:
        try:img.pack()
        except RuntimeError:pass
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'qiuqiu-v3.blend'))
report={'source':'static/models/petchat-v2/qiuqiu.glb','bones':len(rig.data.bones),'vertices':len(body.data.vertices)+len(detail.data.vertices)+len(lids.data.vertices),'original_clips':[a.name for a in original_actions],'new_clips':clips,'foot_ik_max_error_m':contact_error,'glb_bytes':ASSET_FILE.stat().st_size}
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
