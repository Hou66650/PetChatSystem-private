"""Local, editable Tangyuan likeness study. No cloud reconstruction or stock dog.

Blender --background --python this.py -- --output DIR [--reference IMAGE]
Generated guide images are aids, never evidence of hidden anatomy. This is an
unapproved static sculpt, not a validated animated or production-ready pet.
"""
import argparse, bisect, json, math, random, sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

args = argparse.ArgumentParser()
args.add_argument('--output', required=True)
args.add_argument('--reference')
args.add_argument('--samples', type=int, default=96)
args.add_argument('--hairs', type=int, default=260000)
args.add_argument('--revision', default='v4')
opt = args.parse_args(sys.argv[sys.argv.index('--')+1:])
out = Path(opt.output); out.mkdir(parents=True, exist_ok=True)
random.seed(2761)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
dog = bpy.data.collections.new('Tangyuan | editable likeness study')
scene.collection.children.link(dog)
stage = bpy.data.collections.new('Studio | not part of dog')
scene.collection.children.link(stage)

def move_collection(o, collection=dog):
    for c in list(o.users_collection): c.objects.unlink(o)
    collection.objects.link(o)

def material(name, color, rough=.65, metallic=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metallic
    return m

skinmat=material('Coat | spatial salt-and-pepper pigment',(.12,.13,.14),.88)
nodes=skinmat.node_tree.nodes;links=skinmat.node_tree.links
attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='CoatPigment'
links.new(attr.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color'])
noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=280;noise.inputs['Detail'].default_value=3
bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.25;bump.inputs['Distance'].default_value=.0012
links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],nodes.get('Principled BSDF').inputs['Normal'])
black=material('Nose | black microtexture',(.009,.011,.013),.48)
nn=black.node_tree.nodes.new('ShaderNodeTexNoise');nn.inputs['Scale'].default_value=420
nb=black.node_tree.nodes.new('ShaderNodeBump');nb.inputs['Strength'].default_value=.3;nb.inputs['Distance'].default_value=.0007
black.node_tree.links.new(nn.outputs['Fac'],nb.inputs['Height']);black.node_tree.links.new(nb.outputs['Normal'],black.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
eye=material('Eye | very dark brown',(.026,.013,.007),.17)
pupil=material('Pupil and nostril',(.001,.0015,.002),.2)
nostril=material('Nostril | matte recessed appearance',(.001,.001,.001),.95)
gold=material('Tag | plain aged gold',(.5,.27,.055),.31,.72)
collar=material('Collar | charcoal fabric',(.018,.021,.023),.85)

def uv(name,loc,scale,mat=None,segments=32,rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for p in o.data.polygons:p.use_smooth=True
    if mat:o.data.materials.append(mat)
    move_collection(o);return o

def between(name,a,b,r1,r2):
    mid=(Vector(a)+Vector(b))*.5;o=uv(name,mid,(r1,r2,(Vector(a)-Vector(b)).length*.5+r1*.6))
    o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler();return o

# Low-volume anatomy is fused into an editable continuous skin before grooming.
parts=[]
for name,loc,scale in [
 ('Rib cage',(0,.015,.425),(.128,.24,.137)),
 ('Abdomen',(0,.175,.438),(.107,.173,.108)),
 ('Chest',(0,-.19,.423),(.137,.125,.164)),
 ('Rump',(0,.286,.425),(.127,.125,.135)),
 ('Neck',(0,-.255,.515),(.092,.106,.133)),
 ('Skull',(0,-.352,.625),(.112,.119,.119)),
 ('Cheek',(0,-.404,.581),(.108,.099,.086)),
 ('Muzzle bridge',(0,-.491,.572),(.073,.124,.057)),
 ('Lower jaw',(0,-.482,.535),(.065,.107,.033)),
 ('Left beard pad',(-.046,-.508,.531),(.047,.075,.048)),
 ('Right beard pad',(.046,-.508,.531),(.047,.075,.048)),
 ('Left brow',(-.065,-.433,.652),(.039,.027,.016)),
 ('Right brow',(.065,-.433,.652),(.039,.027,.016))]:parts.append(uv(name,loc,scale))
for side in [-1,1]:
    x=side*.105
    parts.extend([uv('Fore shoulder',(side*.083,-.18,.387),(.045,.064,.097)),
      between('Fore upper',(x,-.187,.365),(x,-.205,.235),.037,.039),
      between('Fore lower',(x,-.205,.24),(x,-.214,.075),.032,.034),
      uv('Fore paw',(x,-.235,.037),(.038,.058,.03)),
      uv('Hind thigh',(side*.083,.271,.352),(.059,.084,.105)),
      between('Hind shin',(x,.235,.3),(x,.314,.16),.034,.038),
      between('Hind hock',(x,.314,.16),(x,.295,.065),.03,.031),
      uv('Hind paw',(x,.274,.037),(.039,.058,.03))])
parts.append(between('Single short upright tail',(0,.363,.493),(0,.4,.606),.027,.029))
bpy.ops.object.select_all(action='DESELECT')
for p in parts:p.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();body=bpy.context.object;body.name='Tangyuan | continuous anatomical skin'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
rem=body.modifiers.new('Organic union','REMESH');rem.mode='VOXEL';rem.voxel_size=.004
bpy.ops.object.modifier_apply(modifier=rem.name)
sm=body.modifiers.new('Surface relaxation','SMOOTH');sm.factor=.85;sm.iterations=16;bpy.ops.object.modifier_apply(modifier=sm.name)
sub=body.modifiers.new('Sculpt refinement','SUBSURF');sub.levels=1;bpy.ops.object.modifier_apply(modifier=sub.name)
for p in body.data.polygons:p.use_smooth=True
body.data.materials.append(skinmat)

def sat(x):return max(0,min(1,x))
def blend(a,b,t):return tuple(x*(1-t)+y*t for x,y in zip(a,b))
def smooth(a,b,x):
    t=sat((x-a)/(b-a));return t*t*(3-2*t)
def pigment(p):
    x,y,z=p;rgb=(.035,.037,.04)
    if z<.31:
        rgb=blend((.48,.465,.42),(.065,.068,.07),smooth(.15,.31,z))
    if y<-.24 and z>.44:rgb=blend(rgb,(.007,.008,.009),smooth(.22,.33,-y))
    beard=smooth(.44,.505,-y)*(1-smooth(.55,.595,z))
    rgb=blend(rgb,(.42,.39,.33),beard)
    brow=smooth(.41,.45,-y)*smooth(.62,.642,z)*(1-smooth(.66,.68,z))*smooth(.025,.045,abs(x))*(1-smooth(.09,.112,abs(x)))
    rgb=blend(rgb,(.23,.225,.205),brow)
    chest=smooth(.23,.3,-y)*smooth(.31,.36,z)*(1-smooth(.42,.47,z))*(1-smooth(.035,.11,abs(x)))
    rgb=blend(rgb,(.28,.275,.25),chest)
    return rgb

def color_mesh(obj,override=None):
    attr=obj.data.color_attributes.new(name='CoatPigment',type='FLOAT_COLOR',domain='POINT')
    for v in obj.data.vertices:attr.data[v.index].color=(*(override or pigment(obj.matrix_world@v.co)),1)
color_mesh(body)

# Folded ears: tapered flattened lobes, not pointed upright breed substitutes.
ear_objects=[]
for side in [-1,1]:
    verts=[];faces=[];rings=14;segments=24
    for j in range(rings):
        t=j/(rings-1);width=.05*(math.sin(math.pi*(.18+t*.8))**.7);thick=.009
        center=Vector((side*(.096+.06*math.sin(t*math.pi*.7)),-.322-.043*t,.689-.124*t))
        for k in range(segments):
            a=k/segments*math.tau;verts.append(center+Vector((side*thick*math.sin(a),width*math.cos(a),.006*math.cos(a))))
    for j in range(rings-1):
        for k in range(segments):a=j*segments+k;b=j*segments+(k+1)%segments;faces.append((a,b,b+segments,a+segments))
    faces.extend([tuple(range(segments-1,-1,-1)),tuple((rings-1)*segments+k for k in range(segments))])
    mesh=bpy.data.meshes.new('Folded ear mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    o=bpy.data.objects.new('Folded ear '+str(side),mesh);dog.objects.link(o);o.data.materials.append(skinmat);color_mesh(o,(.012,.013,.015))
    sub=o.modifiers.new('Soft ear edge','SUBSURF');sub.levels=2;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=sub.name)
    for p in o.data.polygons:p.use_smooth=True
    ear_objects.append(o)

for side in [-1,1]:
    uv('Small brown eye '+str(side),(side*.075,-.444,.63),(.022,.013,.018),eye)
    uv('Dark pupil '+str(side),(side*.075,-.455,.631),(.009,.003,.011),pupil)
uv('Rounded canine nose',(0,-.602,.573),(.041,.027,.025),black)
for side in [-1,1]:uv('Nostril '+str(side),(side*.022,-.626,.572),(.008,.0015,.0045),nostril,24,12)

def line(name,points,radius,mat,collection=dog):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.resolution_u=1;curve.bevel_depth=radius;curve.bevel_resolution=2
    spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):p.co=(*co,1)
    ob=bpy.data.objects.new(name,curve);collection.objects.link(ob);curve.materials.append(mat);return ob

line('Subtle mouth seam',[(-.054,-.535,.538),(0,-.584,.536),(.054,-.535,.538)],.0015,pupil)
line('Slim charcoal collar',[(.103*math.cos(a),-.259+.082*math.sin(a),.492+.036*math.sin(a)) for a in [i/96*math.tau for i in range(97)]],.008,collar)
line('Tag loop',[(.006*math.cos(a),-.346,.451+.008*math.sin(a)) for a in [i/32*math.tau for i in range(33)]],.0014,gold)
uv('Plain bone tag center',(0,-.351,.428),(.013,.003,.005),gold)
for x in [-.013,.013]:
    for z in [.423,.433]:uv('Plain bone tag lobe',(x,-.351,z),(.006,.003,.0055),gold,20,12)

# Individual tapered fibres with region-dependent length, curl and pigment.
# Curves stay editable in the .blend; not falsely advertised as a lightweight GLB.
palette=[(.004,.005,.006),(.01,.011,.013),(.023,.025,.028),(.045,.048,.051),(.085,.09,.095),(.17,.175,.175),(.3,.295,.27),(.46,.44,.39),(.63,.61,.55)]
hairdata=[];haircount=0
# Stochastic guide clusters avoid the visible lattice produced by snapped cells.
guide_rng=random.Random(7711);guides=KDTree(120000)
for i in range(120000):guides.insert(Vector((guide_rng.uniform(-.22,.22),guide_rng.uniform(-.67,.47),guide_rng.uniform(0,.82))),i)
guides.balance()
for i,c in enumerate(palette):
    mat=material('Fibre pigment '+str(i),c,.68)
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Sheen Weight'].default_value=.08;bs.inputs['Specular IOR Level'].default_value=.18
    cu=bpy.data.curves.new('Editable groom fibres '+str(i),'CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_depth=.00022;cu.bevel_resolution=0
    cu.materials.append(mat);ob=bpy.data.objects.new('Groom | pigment '+str(i),cu);dog.objects.link(ob);hairdata.append(cu)

def strand(root,n,d,length,curl,index,phase=None):
    global haircount
    d=d.normalized();n=n.normalized();side=n.cross(d)
    if side.length<.01:side=n.cross(Vector((.3,.5,1)))
    side.normalize();binormal=d.cross(side).normalized()
    center,guide_id,_=guides.find(root);offset=center-root;offset-=n*offset.dot(n)
    phase=math.sin(guide_id*78.231)*math.pi+random.uniform(-.2,.2) if phase is None else phase
    curl*=random.uniform(.8,1.1)
    s=hairdata[index].splines.new('POLY');count=9;s.points.add(count-1)
    for j,p in enumerate(s.points):
        t=j/(count-1);co=root+n*(length*.2*math.sin(t*math.pi*.65))+d*(length*t)
        co+=side*(math.sin(t*math.tau*1.6+phase)-math.sin(phase))*curl*min(1,t*4)
        co+=binormal*(math.cos(t*math.tau*1.6+phase)-math.cos(phase))*curl*min(1,t*4)
        co+=offset*(t**1.3)*(.6 if root.z>.6 else .2)
        p.co=(*co,1);p.radius=max(.04,(1-t)**.65)*random.uniform(.8,1.1)
    haircount+=1

def surface_hair(obj,count,ear=False):
    mesh=obj.data;mesh.calc_loop_triangles();tris=list(mesh.loop_triangles);areas=[];total=0
    for tri in tris:total+=tri.area;areas.append(total)
    for _ in range(count):
        tri=tris[bisect.bisect_left(areas,random.random()*total)];a,b,c=[mesh.vertices[i] for i in tri.vertices]
        u=math.sqrt(random.random());v=random.random();weights=[1-u,u*(1-v),u*v]
        p=sum((vertex.co*w for vertex,w in zip([a,b,c],weights)),Vector());n=sum((vertex.normal*w for vertex,w in zip([a,b,c],weights)),Vector()).normalized()
        x,y,z=p
        if z<.022:continue
        if not ear and ((x/.043)**2+((y+.604)/.028)**2+((z-.573)/.026)**2)<1:continue
        # Keep eyes visible under brows, with no oversized exposed sclera.
        if not ear and min((p-Vector((s*.075,-.45,.63))).length for s in [-1,1])<.018:continue
        length=random.uniform(.007,.014);curl=.0008;d=Vector((x*.8,.7,-.35))
        rgb=pigment(p);tone=sum(rgb)/3
        if z<.30:length=random.uniform(.022,.038);curl=.0035;d=n*.3+Vector((x*.4,-.1,-.7))
        if y<-.27 and z>.47:
            length=random.uniform(.022,.036);curl=.005;d=(n*.35+Vector((0,-.4,-.35)))
        if y<-.3 and z>.66:
            length=random.uniform(.026,.046);curl=.006;d=(n*.2+Vector((x*2,-.4,.12)))
        if y<-.45 and z<.595:
            length=random.uniform(.028,.052);curl=.003;d=Vector((x*1.8,-.28,-1));tone=sum(pigment(p))/3
        if -.47<y<-.405 and .635<z<.675 and .03<abs(x)<.11:
            length=random.uniform(.016,.032);curl=.0035;d=Vector((x*2,-1,-.3))
        if y>.35 and z>.48:length=random.uniform(.015,.026);d=n*.7+Vector((0,.1,.6));curl=.003
        if ear:length=random.uniform(.01,.02);d=Vector((x*.3,-.1,-1));tone=random.choice([.008,.01,.012,.025,.09]);curl=.002
        variation=random.uniform(.65,1.4);tone*=variation
        index=min(range(len(palette)),key=lambda i:abs(sum(palette[i])/3-tone))
        strand(p+n*.0002,n,d,length,curl,index)
surface_hair(body,opt.hairs)
for ear in ear_objects:surface_hair(ear,7000,True)
print('GROOM_FIBRES',haircount,flush=True)

# Reference lives in a clearly labelled non-rendering collection and is packed.
if opt.reference:
    references=bpy.data.collections.new('REFERENCE ONLY | generated, unapproved');scene.collection.children.link(references)
    image=bpy.data.images.load(str(Path(opt.reference).resolve()));image.pack()
    ob=bpy.data.objects.new('Generated guide | verify against original videos',None);references.objects.link(ob);ob.empty_display_type='IMAGE';ob.data=image;ob.empty_display_size=1.5;ob.location=(1.2,1,.8);ob.hide_render=True
scene['approval_status']='UNAPPROVED likeness study; hidden anatomy inferred; static groom; no verified rig'
scene['reference_priority']='Original footage > generated guide. Owner recognition still required.'

floor=material('Studio warm gray',(.19,.185,.175),.9)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0));plane=bpy.context.object;plane.name='Studio floor';plane.data.materials.append(floor);move_collection(plane,stage)
world=bpy.data.worlds.new('Soft studio');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.38,.43,.5,1);world.node_tree.nodes['Background'].inputs[1].default_value=.35;scene.world=world
def area(name,loc,power,size,color):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    ob=bpy.data.objects.new(name,data);stage.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,.4))-ob.location).to_track_quat('-Z','Y').to_euler()
area('Large soft key',(-1.6,-1.8,2.4),190,2.2,(1,.92,.83))
area('Cool fill',(1.7,-.4,1.5),100,2,(.78,.87,1))
area('Fur rim',(.3,1.8,1.9),240,1.5,(1,.94,.85))
data=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',data);stage.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.ortho_scale=1.12
scene.render.engine='CYCLES';scene.cycles.samples=opt.samples;scene.cycles.use_denoising=True
scene.render.use_persistent_data=True
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for dev in prefs.devices:dev.use=dev.type!='CPU'
    scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'
scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
views=[('three-quarter',(1.05,-1.75,.95),(0,-.07,.37)),('side',(1.7,-.08,.7),(0,-.05,.38)),('face',(.05,-1.7,.74),(0,-.39,.61))]
def camera_view(loc,target,scale):
    cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();data.ortho_scale=scale
camera_view(views[0][1],views[0][2],1.12)
bpy.ops.wm.save_as_mainfile(filepath=str(out/('Tangyuan-likeness-study-'+opt.revision+'.blend')))
report={'status':'unapproved_static_likeness_study','cloud_model_generation':False,'stock_dog_used':False,'hair_fibres':haircount,'skin_vertices':len(body.data.vertices),'tail_count_by_construction':1,'limbs_by_construction':4,'rigged':False,'owner_approved':False,'generated_reference':bool(opt.reference),'limitations':['Unseen anatomy inferred, not measured','Procedural editable sculpt requires likeness review','Static grooming study, not a completed animation or optimized GLB']}
(out/'model-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for name,loc,target in views:
    camera_view(loc,target,.52 if name=='face' else 1.35 if name=='side' else 1.12)
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('STUDY_COMPLETE',out,flush=True)
