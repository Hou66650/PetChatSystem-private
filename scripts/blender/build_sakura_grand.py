"""Grand sakura landmark: replace only tree objects in the current interactive island."""
import bpy, bmesh, math, random, json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2]
OUT=R/'art/sakura-grand-v1';OUT.mkdir(parents=True,exist_ok=True)
ASSET=R/'static/models/petchat-sakura-grand-v1';ASSET.mkdir(parents=True,exist_ok=True)
random.seed(2718)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-toys-v1/sakura.glb'))
removed=[]
for o in list(bpy.context.scene.objects):
 if o.get('asset_role')=='remodeled_cherry_tree' or o.name.startswith('Sakura_v2_'):
  removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
assert len(removed)==8,removed
def material(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=.79
    return m
mats=[material('Bark_warm_umber',(.23,.10,.065)),material('Bark_ridges',(.36,.18,.12)),
      material('Petal_blush',(.95,.48,.63)),material('Petal_pearl',(1,.79,.84)),
      material('Petal_rose',(.72,.22,.39)),material('Flower_heart',(.55,.09,.21)),
      material('Pollen_honey',(.98,.62,.21)),material('Young_leaf',(.33,.46,.22))]
batches=[([],[]) for _ in mats]
def meshadd(mid,verts,faces):
    vs,fs=batches[mid];off=len(vs);vs.extend([tuple(v) for v in verts]);fs.extend([tuple(off+i for i in f) for f in faces])
def tube(points,radii,mid=0,sides=9):
    vs=[]
    for i,p in enumerate(points):
        p=Vector(p);t=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])).normalized()
        u=t.cross(Vector((0,1,0))).normalized();v=t.cross(u).normalized()
        for j in range(sides):
            a=j*math.tau/sides;rr=radii[i]*(1+.055*math.sin(j*3.1+i*.7))
            vs.append(p+rr*(u*math.cos(a)+v*math.sin(a)))
    fs=[tuple(range(sides-1,-1,-1))]
    for i in range(len(points)-1):
        for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;fs.append((a,b,b+sides,a+sides))
    fs.append(tuple((len(points)-1)*sides+j for j in range(sides)));meshadd(mid,vs,fs)
def path(start,end,curve=0):
    a,b=Vector(start),Vector(end)
    return [a.lerp(b,i/6)+Vector((curve*math.sin(math.pi*i/6),.04*math.sin(math.pi*i/6),.055*math.sin(math.pi*i/6))) for i in range(7)]
base=Vector((-2.1,1.5,0))
def pos(x,y,z):return base+Vector((x,y,z))
trunk=[pos(0,0,.012),pos(.04,.015,.35),pos(-.08,.04,.83),pos(-.15,.08,1.35),pos(.03,.10,1.9),pos(.23,.14,2.4),pos(.4,.18,3.05)]
tube(trunk,[.31,.245,.20,.165,.135,.085,.025],sides=20)
for i in range(9):
    a=i*math.tau/9;end=pos(math.cos(a)*.48,math.sin(a)*.48,.016)
    tube([pos(0,0,.24),pos(math.cos(a)*.15,math.sin(a)*.15,.045),end],[.10,.065,.009],sides=8)
# Fine longitudinal seams follow the bends of the trunk, rather than flat stripes.
for k in range(11):
    a=k*math.tau/11;points=[]
    for p,r in zip(trunk[:6],[.305,.244,.199,.164,.134,.084]):points.append(p+Vector((math.cos(a)*r,math.sin(a)*r,0)))
    tube(points,[.005,.005,.004,.003,.002,.001],1,5)
crowns=[]
limbs=[(-1.45,-.18,2.7),(1.48,-.12,2.95),(-.9,.76,3.3),(.5,.45,3.85),(-.3,-.65,3.65),(1.45,.65,3.45),(-1.4,.56,3.45),(.75,-.9,2.85),(-1.1,-.75,2.95),(1.85,.10,3.2),(.1,1.0,3.5),(-.15,.08,4.05),(1.0,-.5,3.75),(1.65,-.6,2.6),(-1.5,-.35,3.1)]
for i,(x,y,z) in enumerate(limbs):
    start=trunk[2+(i%4)];end=pos(x,y,z)
    pts=path(start,end,(-1 if x<0 else 1)*.12)
    tube(pts,[.10*(1-t/7)**1.2+.006 for t in range(7)],0,10)
    for k in range(5):
        a=k*math.tau/5+i*.67
        tip=end+Vector((math.cos(a)*random.uniform(.22,.44),math.sin(a)*random.uniform(.2,.42),random.uniform(-.1,.23)))
        start2=pts[4] if k==0 else pts[5]
        twig=path(start2,tip,.035);tube(twig,[.019*(1-t/7)+.002 for t in range(7)],0,7)
        crowns.append((tip,random.uniform(.30,.43)))
        for q in range(2):
            twig_tip=tip+Vector((random.uniform(-.14,.14),random.uniform(-.14,.14),random.uniform(.03,.16)))
            tube([twig[4],tip,twig_tip],[.008,.005,.0015],0,6)

# Interior blossom banks join the branch-tip clusters into a broad layered canopy.
for i in range(18):
    a=i*2.3999632297
    r=.3+.65*(i%6)/5
    crowns.append((pos(math.cos(a)*r,math.sin(a)*r*.65,3.25+.45*(1-r)),.38))

flower_count=0
def flower(center,size,normal,shade=None):
    global flower_count
    flower_count+=1;c=Vector(center);n=Vector(normal).normalized();u=n.cross(Vector((.12,.21,1))).normalized();v=n.cross(u).normalized()
    spin=random.random()*math.tau
    for k in range(5):
        angle=spin+k*math.tau/5;d=u*math.cos(angle)+v*math.sin(angle);w=n.cross(d)
        # Rounded petal outline, with the characteristic notch at the outer tip.
        outline=[(.10,-.07),(.33,-.26),(.65,-.29),(.91,-.18),(1,-.065),(.88,0),(1,.065),(.91,.18),(.65,.29),(.33,.26),(.10,.07)]
        verts=[c+d*size*.49+n*size*.08]
        verts += [c+d*(x*size)+w*(y*size)+n*size*(.04+.22*x*x) for x,y in outline]
        faces=[(0,1+i,1+(i+1)%len(outline)) for i in range(len(outline))]
        meshadd(shade if shade is not None else random.choices([2,3,4],[.42,.51,.07])[0],verts,faces)
    ring=[c+n*size*.10]+[c+(u*math.cos(j*math.tau/8)+v*math.sin(j*math.tau/8))*size*.16+n*size*.09 for j in range(8)]
    meshadd(5,ring,[(0,j+1,(j+1)%8+1) for j in range(8)])
    # Stamen tips are tiny low-poly diamonds, with no transparent cards.
    for j in range(5):
        a=spin+j*math.tau/5;p=c+(u*math.cos(a)+v*math.sin(a))*size*.22+n*size*.18;r=size*.045
        meshadd(6,[p+u*r,p+v*r,p-u*r,p-v*r,p+n*r],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
for center,radius in crowns:
    for j in range(53):
        n=Vector((random.gauss(0,1),random.gauss(0,1),random.gauss(.4,1))).normalized()
        dist=radius*random.uniform(.3,1)
        point=center+Vector((n.x*dist*1.05,n.y*dist,n.z*dist*.7))
        flower(point,random.uniform(.055,.09),n+Vector((0,-.25,.35)))
    for j in range(4):
        c=center+Vector((random.uniform(-radius,radius),random.uniform(-radius,radius),random.uniform(-.1,.12)))
        axis=Vector((random.uniform(-1,1),random.uniform(-1,1),.4)).normalized();side=axis.cross(Vector((0,0,1))).normalized()
        meshadd(7,[c,c+axis*.045+side*.018,c+axis*.10,c+axis*.045-side*.018,c+axis*.05+Vector((0,0,.013))],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
        tube([c,c+Vector((0,0,.025)),c+Vector((0,0,.045))],[.013,.018,.006],4,6)
# Fallen petals collect around the roots, away from the pet's central rug.
for i in range(180):
    a=random.random()*math.tau;dist=random.uniform(.18,.8);c=pos(math.cos(a)*dist,math.sin(a)*dist,.014)
    if c.x*c.x+c.y*c.y>3.13**2:continue
    u=Vector((math.cos(a),math.sin(a),0));v=Vector((-u.y,u.x,0));s=random.uniform(.018,.036)
    meshadd(random.choice([2,3]),[c-u*s,c+v*s*.6,c+u*s,c-v*s*.6,c+Vector((0,0,.007))],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
tree=[]
for i,(verts,faces) in enumerate(batches):
    mesh=bpy.data.meshes.new(mats[i].name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new('Sakura_Grand_'+mats[i].name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(mats[i]);tree.append(o)
    o['asset_role']='grand_cherry_tree'
    mats[i].surface_render_method='DITHERED'
    for poly in mesh.polygons:poly.use_smooth=i<2
stage=[o for o in bpy.context.scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'sakura.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5,-9,6));cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=10;look(cam,(-.5,.4,1.9))
for name,p,e,size in [('Key',(-3,-4,7),1000,5),('Fill',(4,-1,5),600,5),('Rim',(-2,5,6),850,4)]:
    bpy.ops.object.light_add(type='AREA',location=p);o=bpy.context.object;o.name=name;o.data.energy=e;o.data.shape='DISK';o.data.size=size;look(o,(-1,1,1))
if scene.world is None:scene.world=bpy.data.worlds.new('Pastel_studio')
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.66,.78,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'sakura-grand.blend'))
scene.render.filepath=str(OUT/'courtyard.png');bpy.ops.render.render(write_still=True)
cam.location=(.2,-5,4.5);look(cam,(-1.8,1.5,2.4));cam.data.ortho_scale=5.5
scene.render.filepath=str(OUT/'tree-detail.png');bpy.ops.render.render(write_still=True)
report={'flowers':flower_count,'tree_vertices':sum(len(o.data.vertices) for o in tree),'tree_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in tree),'tree_material_batches':len(tree),'stage_meshes':len(stage),'glb_bytes':(ASSET/'sakura.glb').stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('SAKURA_COMPLETE',json.dumps(report))
