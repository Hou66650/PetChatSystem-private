"""New shepherd sculpt, fitted to the shared 45-joint companion animation rig."""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector,Quaternion
from mathutils.kdtree import KDTree
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch,material,studio
R=Path(__file__).resolve().parents[2];OUT=R/'art/shepherd-v1';ASSET=R/'static/models/petchat-shepherd-v1'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True);random.seed(941)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-motion-v1/xueqiu.glb'))
rig=next(o for o in bpy.data.objects if o.type=='ARMATURE');rig.name='Shepherd_Companion_Rig'
source=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
kd=KDTree(len(source.data.vertices));weights=[]
for v in source.data.vertices:
    kd.insert(v.co,v.index);weights.append({source.vertex_groups[g.group].name:g.weight for g in v.groups})
kd.balance()
for o in list(bpy.data.objects):
    if o.type=='MESH':bpy.data.objects.remove(o,do_unlink=True)
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
for p in rig.pose.bones:p.matrix_basis.identity()
tan=material('Shepherd_sable_coat',(.46,.24,.09),.86)
charcoal=material('Charcoal_guard_hair',(.027,.023,.020),.8)
gold=material('Warm_undercoat',(.52,.30,.12),.85)
black=material('Nose_and_lips',(.012,.009,.008),.28)
inner=material('Ear_velvet',(.16,.09,.065),.95)
amber=material('Amber_iris',(.30,.12,.022),.18)
pupil=material('Dark_pupils',(.004,.003,.002),.13)
white=material('Eye_catchlight',(.95,.97,1),.09)
teal=material('Woven_teal_collar',(.025,.17,.16),.73)
brass=material('Brushed_brass',(.62,.39,.12),.3,.72)
pink=material('Tongue',(.47,.13,.16),.5)
skin=[]
def bind(o,bone=None):
    o.parent=rig
    if bone:
        g=o.vertex_groups.new(name=bone);g.add(list(range(len(o.data.vertices))),1,'REPLACE')
    else:
        groups={}
        for v in o.data.vertices:
            nearest=kd.find_n(v.co,3);merged={};total=sum(1/max(d,.006)**2 for _,_,d in nearest)
            for _,i,d in nearest:
                f=(1/max(d,.006)**2)/total
                for name,w in weights[i].items():merged[name]=merged.get(name,0)+f*w
            for name,w in merged.items():
                if w>.001:
                    if name not in groups:groups[name]=o.vertex_groups.new(name=name)
                    groups[name].add([v.index],w,'REPLACE')
    mod=o.modifiers.new('Companion skin','ARMATURE');mod.object=rig;skin.append(o)
def part(name,b,bone=None):
    for o in b.objects(name):bind(o,bone)

# Continuous volumetric anatomy, with long muzzle and substantial straight limbs.
b=Batch()
for p,s in [((0,.075,.52),(.205,.40,.235)),((0,-.22,.53),(.21,.20,.27)),((0,.36,.51),(.19,.20,.215)),((0,-.29,.66),(.16,.17,.24)),((0,-.43,.80),(.156,.18,.177)),((0,-.57,.70),(.12,.13,.103)),((0,-.67,.68),(.095,.18,.076))]:b.ellipsoid(tan,p,s,24,16)
for side in [-1,1]:
    x=side*.138
    for p,s in [((x,-.25,.39),(.075,.079,.18)),((x,-.265,.19),(.049,.052,.16)),((x,-.31,.064),(.067,.11,.051)),((x,.37,.40),(.10,.13,.18)),((x,.31,.245),(.059,.065,.13)),((x,.34,.13),(.045,.045,.10)),((x,.29,.054),(.066,.105,.046))]:b.ellipsoid(tan,p,s,20,12)
body=b.objects('Shepherd_anatomy')[0]
bpy.context.view_layer.objects.active=body;body.select_set(True)
remesh=body.modifiers.new('Continuous sculpt','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.0065;remesh.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=remesh.name)
sm=body.modifiers.new('Polished anatomy','SMOOTH');sm.factor=.65;sm.iterations=5;bpy.ops.object.modifier_apply(modifier=sm.name)
bind(body)
# Smooth transferred weights on the new continuous topology. Nearest-source
# weights alone create visible creases where the breed's chest is broader.
neighbors=[set() for _ in body.data.vertices]
for edge in body.data.edges:
    a,c=edge.vertices;neighbors[a].add(c);neighbors[c].add(a)
weight_names=[g.name for g in body.vertex_groups]
smoothed=[{g.group:g.weight for g in v.groups} for v in body.data.vertices]
for iteration in range(18):
    updated=[]
    for i,w in enumerate(smoothed):
        near=neighbors[i];mixed={k:v*.5 for k,v in w.items()}
        if not near:updated.append(w);continue
        for j in near:
            for k,v in smoothed[j].items():mixed[k]=mixed.get(k,0)+v*.5/len(near)
        updated.append({k:v for k,v in mixed.items() if v>.0003})
    smoothed=updated
for g in body.vertex_groups:g.remove(list(range(len(body.data.vertices))))
for v,w in zip(body.data.vertices,smoothed):
    if v.co.z<.105:
        name=('F' if v.co.y<0 else 'H')+('L' if v.co.x<0 else 'R')+'_foot'
        w={weight_names.index(name):1}
    strongest=sorted(w.items(),key=lambda item:item[1],reverse=True)[:4];total=sum(value for _,value in strongest)
    for index,value in strongest:body.vertex_groups[index].add([v.index],value/total,'REPLACE')
kd=KDTree(len(body.data.vertices));weights=[]
for v in body.data.vertices:
    kd.insert(v.co,v.index);weights.append({body.vertex_groups[g.group].name:g.weight for g in v.groups})
kd.balance()

def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def coat(p):
    x,y,z=p
    saddle=smooth(.48,.62,z)*smooth(-.32,-.11,y)*(1-smooth(.46,.60,y))
    mask=(1-smooth(-.60,-.47,y))*(1-smooth(.73,.79,z))*smooth(.56,.62,z)
    forehead=smooth(.84,.94,z)*(1-smooth(-.39,-.24,y))
    dark=max(saddle,mask,forehead*.75);noise=.98+.02*math.sin(x*23+y*13+z*18)
    return tuple((a*(1-dark)+b*dark)*noise for a,b in zip((.50,.27,.105),(.027,.023,.020)))
colors=body.data.color_attributes.new(name='Coat',type='FLOAT_COLOR',domain='POINT')
for v,c in zip(body.data.vertices,colors.data):c.color=(*coat(v.co),1)
nodes=tan.node_tree.nodes;vc=nodes.new('ShaderNodeVertexColor');vc.layer_name='Coat';tan.node_tree.links.new(vc.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])

# Layered guard-hair tufts follow the surface and its skin weights, not separate rigid ornaments.
tufts=Batch()
verts=[v for v in body.data.vertices if v.co.z>.30 and v.co.y>-.56]
for v in random.sample(verts,min(2400,len(verts))):
    p=v.co;n=v.normal.normalized();axis=Vector((0,.5,-.8));axis=(axis-n*axis.dot(n)).normalized();side=n.cross(axis).normalized()
    length=random.uniform(.012,.030);width=random.uniform(.001,.002)
    a=p+n*.001;tip=p+axis*length+n*.002
    m=charcoal if sum(coat(p))<.3 else gold
    tufts.tube(m,[a,a+axis*length*.4+n*.002,tip],[width,width*.6,.0007],6)
part('Layered_guard_coat',tufts)

# Upright pointed ears, inset velvet, ear-edge fur.
for sign,side in [(-1,'L'),(1,'R')]:
    ear=Batch();x=sign*.12
    vs=[];fs=[]
    for j in range(13):
        t=j/12;rx=.068*(1-t)**.8+.001;ry=.035*(1-t)**.7+.001
        for i in range(20):
            a=i*math.tau/20;vs.append((x+sign*.035*t+rx*math.cos(a),-.39+.018*t+ry*math.sin(a),.90+.27*t))
    for j in range(12):
        for i in range(20):a=j*20+i;c=j*20+(i+1)%20;fs.append((a,c,c+20,a+20))
    ear.mesh(charcoal,vs,fs,True)
    ear.mesh(inner,[(x-sign*.041,-.427,.94),(x+sign*.047,-.427,.94),(x+sign*.031,-.393,1.125)],[(0,1,2)],True)
    for i in range(13):
        t=i/12;p=Vector((x-sign*.046+sign*.032*t,-.434+.047*t,.95+.16*t))
        ear.tube(gold,[p,p+Vector((sign*.018,-.006,-.025))],[.005,.001],5)
    part('Pointed_ear_'+side,ear,'ear_'+side)

# Dark almond eyes; small amber irises rather than exposed cartoon white eyeballs.
for sign,side in [(-1,'L'),(1,'R')]:
    x=sign*.094;eye=Batch();eye.ellipsoid(black,(x,-.584,.795),(.041,.024,.028),24,14)
    eye.ellipsoid(amber,(x,-.608,.795),(.022,.005,.018),24,14)
    eye.ellipsoid(pupil,(x,-.614,.795),(.010,.003,.012),20,12)
    eye.ellipsoid(white,(x-.006,-.618,.803),(.004,.002,.004),12,8)
    part('Expressive_eye_'+side,eye,'eye_'+side)
    brow=Batch();brow.ellipsoid(gold,(x,-.575,.837),(.046,.021,.018),20,10);part('Brow_'+side,brow,'brow_'+side)
    lid=Batch();vs=[];closed=[];fs=[]
    for row in range(6):
        for col in range(21):
            u=-1+col/10;cap=math.sqrt(max(0,1-u*u));t=row/5
            vs.append((x+u*.043,-.588-.027*cap,.795+cap*(.027+t*.014)))
            closed.append((x+u*.043,-.588-.031*cap,.795+cap*(-.029+t*.070)))
    for row in range(5):
        for col in range(20):i=row*21+col;fs.append((i,i+1,i+22,i+21))
    lid.mesh(charcoal,vs,fs,True);o=lid.objects('Natural_eyelid_'+side)[0];bind(o,'head');o.shape_key_add(name='Basis')
    for name in ['Blink_L','Blink_R']:
        key=o.shape_key_add(name=name)
        if name=='Blink_'+side:
            for v,p in zip(key.data,closed):v.co=p

snout=Batch();snout.ellipsoid(black,(0,-.823,.685),(.066,.035,.041),28,16)
for sign in [-1,1]:
    snout.ellipsoid(pupil,(sign*.035,-.85,.69),(.018,.006,.011),16,10)
    snout.tube(black,[(sign*.012,-.80,.63),(sign*.07,-.72,.625),(sign*.09,-.62,.641)],.006,8)
    for i in range(4):snout.ellipsoid(charcoal,(sign*(.045+i*.012),-.76+i*.018,.685-i*.01),(.0025,.0025,.0025),8,6)
part('Nose_lips_whisker_roots',snout,'head')
jaw=Batch();jaw.ellipsoid(charcoal,(0,-.675,.607),(.077,.135,.028),24,12);part('Lower_jaw',jaw,'jaw')
tongue=Batch();tongue.ellipsoid(pink,(0,-.735,.598),(.029,.050,.008),20,10);part('Tongue',tongue,'tongue')

tail=Batch();points=[(.03,.46,.55),(.055,.62,.48),(.09,.77,.34),(.13,.90,.22),(.18,1.02,.20)]
tail.tube(charcoal,points,[.085,.09,.078,.055,.008],20)
for i in range(65):
    t=random.random()*3;j=int(t);p=Vector(points[j]).lerp(Vector(points[j+1]),t-j);a=random.random()*math.tau
    p+=Vector((math.cos(a)*.065,0,math.sin(a)*.06));tail.tube(charcoal,[p,p+Vector((.008,.055,-.015))],[.007,.001],6)
part('Long_sable_tail',tail,'tail')
for leg in ['FL','FR','HL','HR']:
    x=(-1 if leg[1]=='L' else 1)*.138;y=-.37 if leg[0]=='F' else .235;paw=Batch()
    for dx in [-.039,-.013,.013,.039]:
        paw.ellipsoid(gold,(x+dx,y,.048),(.018,.036,.025),12,8);paw.ellipsoid(black,(x+dx,y-.028,.042),(.007,.017,.008),12,8)
    paw.ellipsoid(black,(x,y+.027,.013),(.043,.045,.008),12,8);part('Detailed_paw_'+leg,paw,leg+'_foot')
collar=Batch();pts=[(.174*math.cos(i*math.tau/48),-.29+.155*math.sin(i*math.tau/48),.66) for i in range(49)]
collar.tube(teal,pts,.023,10);collar.ellipsoid(brass,(0,-.462,.603),(.035,.009,.040),24,14)
for i in range(32):
    a=i*math.tau/32;collar.ellipsoid(brass,(.178*math.cos(a),-.29+.159*math.sin(a),.675),(.003,.003,.003),8,6)
part('Stitched_collar_and_tag',collar,'neck')
for o in skin:
    for p in o.data.polygons:p.use_smooth=True
for o in skin:
    if o.data.shape_keys:
        for key in o.data.shape_keys.key_blocks:key.value=0
rig['breed']='German Shepherd';rig['reference']='art/shepherd-v1/design-board.png'
# The original rig carried a curled husky tail. Bake a ground-clearance
# correction for the new long tail so sitting/sleeping cannot bury its tip.
scene=bpy.context.scene;tailbone=rig.pose.bones['tail'];tailrest=tailbone.bone.matrix_local.inverted()
for track in rig.animation_data.nla_tracks:
    action=track.strips[0].action;rig.animation_data.action=action;rig.animation_data.action_slot=action.slots[0]
    frames=range(int(action.frame_range[0]),int(action.frame_range[1])+1)
    original=[]
    for frame in frames:
        scene.frame_set(frame);original.append(tailbone.rotation_quaternion.copy())
    corrected=[]
    for frame,q in zip(frames,original):
        scene.frame_set(frame);tailbone.rotation_quaternion=q;bpy.context.view_layer.update()
        axis=tailbone.matrix.to_quaternion().inverted()@Vector((1,0,0))
        for attempt in range(25):
            tip=tailbone.matrix@tailrest@Vector((.18,1.02,.20))
            if tip.z>=.045:break
            tailbone.rotation_quaternion=q@Quaternion(axis,(attempt+1)*.05);bpy.context.view_layer.update()
        corrected.append(tailbone.rotation_quaternion.copy())
    for frame,q in zip(frames,corrected):
        tailbone.rotation_quaternion=q;tailbone.keyframe_insert(data_path='rotation_quaternion',frame=frame,group='tail')
rig.animation_data.action=None
for p in rig.pose.bones:p.matrix_basis.identity()
scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
for o in skin:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'shepherd.glb'),export_format='GLB',use_selection=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,export_frame_range=False,export_def_bones=True,export_extras=True)
report={'bones':len(rig.data.bones),'mesh_batches':len(skin),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in skin),'bytes':(ASSET/'shepherd.glb').stat().st_size}
(OUT/'dog-report.json').write_text(json.dumps(report,indent=2));print('SHEPHERD_COMPLETE',report)
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
for p in rig.pose.bones:p.matrix_basis.identity()
for o in skin:
    if o.data.shape_keys:
        for key in o.data.shape_keys.key_blocks:key.value=0
print('EYE_POSES',[(p.name,list(p.location),list(p.scale)) for p in rig.pose.bones if 'eye_' in p.name])
bpy.context.view_layer.update()
studio(OUT,(0,0,.57),(1.7,-2.6,1.25),1.8,'shepherd-studio',(1100,1100))
