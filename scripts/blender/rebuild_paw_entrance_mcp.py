"""Replace the symbolic entrance with an assembled timber/stone gateway via MCP.

Author in metres; keep the island and facility routes fixed. Export for UE import
separately from the Web runtime. The render is not evidence of a UE deployment.
"""
import bpy,bmesh,math,random,sys,json,hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'art/paw-commons-v3'
sys.path.insert(0,str(HERE))
from shepherd_geometry import Batch,material
from cinematic_island_tools import finish,collection,camera,leaf,principled
bpy.ops.wm.open_mainfile(filepath=str(OUT/'paw-commons-quality.blend'))
random.seed(2410)
# Delete only the previous gateway and its disconnected decorative components.
for c in list(bpy.data.collections):
    if c.name.startswith(('03 Entrance','E0')):
        for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(c)
for o in list(bpy.context.scene.objects):
    if o.type!='MESH' or not o.name.startswith(('D08','02 Paths')):continue
    bm=bmesh.new();bm.from_mesh(o.data);seen=set();discard=[]
    for v in bm.verts:
        if v in seen:continue
        stack=[v];seen.add(v);component=[]
        while stack:
            q=stack.pop();component.append(q)
            for edge in q.link_edges:
                other=edge.other_vert(q)
                if other not in seen:seen.add(other);stack.append(other)
        if all(abs(v.co.x)<2.45 and -11.3<v.co.y<-7.35 for v in component):discard.extend(component)
    bmesh.ops.delete(bm,geom=discard,context='VERTS');bm.to_mesh(o.data);bm.free()

M={'wood':material('E Oiled chestnut',(.39,.235,.12),.65),
   'end':material('E Chestnut end grain',(.32,.19,.09),.76),
   'iron':material('E Oxidised bronze hardware',(.12,.10,.065),.48,.72),
   'dark':material('E Dark stone paw mosaic',(.105,.11,.085),.92),
   'mortar':material('E Recessed lime joints',(.28,.265,.22),.97),
   'glass':material('E Lantern frosted glass',(.85,.61,.26),.30,0,.65),
   'leaf':bpy.data.materials['Leaf green'],'tip':bpy.data.materials['Leaf sun tips'],
   'soil':material('E Planted earth',(.065,.045,.025),1),'flower':bpy.data.materials['Daisy ivory petals']}
for i in range(5):M['stone'+str(i)]=material('E Hand split limestone '+str(i),(.45+i*.023,.425+i*.021,.34+i*.019),.91)

def baked(mat,end=False):
    n=1024;y,x=np.mgrid[0:n,0:n]/n;rng=np.random.default_rng(41 if end else 42)
    if end:
        r=np.sqrt(((x-.36)*1.1)**2+((y-.55)*.82)**2)
        f=.025*np.sin(r*145+np.sin(x*13)*.7)+rng.normal(0,.008,(n,n))
        rgb=np.array([.50,.37,.24])+f[:,:,None]
    else:
        warp=x+.006*np.sin(y*19)+.003*np.sin(y*51)+.025*np.exp(-((x-.43)/.075)**2-((y-.57)/.17)**2)
        f=.009*np.sin(warp*480)+.006*np.sin(warp*1100)+.013*np.sin(x*19)+rng.normal(0,.006,(n,n))
        rgb=np.array([.57,.43,.285])+f[:,:,None]
    nt=mat.node_tree;p=principled(mat)
    image=bpy.data.images.new(mat.name+' albedo',width=n,height=n);image.pixels.foreach_set(np.dstack((np.clip(rgb,0,1),np.ones_like(x))).astype(np.float32).ravel());image.pack()
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image;nt.links.new(tex.outputs['Color'],p.inputs['Base Color'])
    dy,dx=np.gradient(f);normal=np.dstack((-dx*2,-dy*2,np.ones_like(f)));normal/=np.linalg.norm(normal,axis=2)[:,:,None]
    normal_texture(mat,normal*.5+.5,.22)
def normal_texture(mat,rgb,strength):
    h,w=rgb.shape[:2];im=bpy.data.images.new(mat.name+' normal',width=w,height=h);im.colorspace_settings.name='Non-Color'
    im.pixels.foreach_set(np.dstack((rgb,np.ones((h,w)))).astype(np.float32).ravel());im.pack()
    nt=mat.node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im;nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=strength
    nt.links.new(tex.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],principled(mat).inputs['Normal'])
baked(M['wood']);baked(M['end'],True)
for i in range(5):
    n=512;y,x=np.mgrid[0:n,0:n]/n;rng=np.random.default_rng(130+i)
    f=.018*np.sin(x*27+y*19)+.012*np.sin(x*87-y*72)+rng.normal(0,.017,(n,n))
    f-=.055*(rng.random((n,n))>.975)
    rgb=np.array([.57+i*.015,.535+i*.014,.46+i*.013])+f[:,:,None]
    mat=M['stone'+str(i)];im=bpy.data.images.new(mat.name+' mineral grain',width=n,height=n)
    im.pixels.foreach_set(np.dstack((np.clip(rgb,0,1),np.ones_like(f))).astype(np.float32).ravel());im.pack()
    nt=mat.node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im;nt.links.new(tex.outputs['Color'],principled(mat).inputs['Base Color'])
    dy,dx=np.gradient(f);v=np.dstack((-dx*5,-dy*5,np.ones_like(f)));v/=np.linalg.norm(v,axis=2)[:,:,None];normal_texture(mat,v*.5+.5,.55)
groups={}
def group(name):
    b=Batch();groups[name]=b;return b
def box(b,m,p,s):b.box(M[m],p,s)
def tube(b,m,pts,r,n=12):b.tube(M[m],pts,r,n)
def sphere(b,m,p,s,n=12,rings=6):b.ellipsoid(M[m],p,s,n,rings)
def beam(b,a,c,width,depth):
    a,c=Vector(a),Vector(c);z=(c-a).normalized();reference=Vector((0,1,0)) if abs(z.y)<.9 else Vector((1,0,0));x=reference.cross(z).normalized();y=z.cross(x)
    vs=[p+x*s*width/2+y*t*depth/2 for p in [a,c] for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    b.mesh(M['wood'],vs,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    b.mesh(M['end'],vs,[(3,2,1,0),(4,5,6,7)])
def bolt(b,x,y,z,r=.019):
    tube(b,'iron',[(x,y+.008,z),(x,y-.005,z)],r*1.65,20)
    tube(b,'iron',[(x,y-.005,z),(x,y-.021,z)],r,6)

b=group('E01 Masonry foundations')
for x in [-1.85,1.85]:
    box(b,'mortar',(x,-9.2,.26),(.60,.64,.48))
    for row in range(3):
        for side in [-1,1]:
            for q in [-1,1]:
                box(b,'stone'+str((row+q+side)%5),(x+q*.154,-9.2+side*.163,.095+row*.155),(.298,.315,.145))
    box(b,'stone3',(x,-9.2,.535),(.72,.77,.10))
    box(b,'iron',(x,-9.2,.602),(.31,.33,.034))
    for sy in [-1,1]:box(b,'iron',(x,-9.2+sy*.142,.71),(.29,.014,.20))
    for dx in [-.12,.12]:
        for dy in [-.13,.13]:tube(b,'iron',[(x+dx,-9.2+dy,.615),(x+dx,-9.2+dy,.63)],.016,6)

b=group('E02 Timber frame and joinery')
for x in [-1.85,1.85]:
    beam(b,(x,-9.2,.635),(x,-9.2,3.16),.265,.265)
    # Slightly sloped sacrificial post cap, iron shoe keeps wood off damp masonry.
    box(b,'end',(x,-9.2,3.18),(.285,.285,.055))
    side=1 if x<0 else -1
    for y in [-9.36,-9.04]:beam(b,(x,y,2.31),(x+side*.63,y,2.98),.12,.105)
    for y in [-9.45,-8.95]:
        for z in [.72,2.42,2.95]:bolt(b,x,y,z)
    # Through-tenon end and dark pin at beam connection.
    box(b,'end',(x,-9.40,2.95),(.14,.035,.17))
    bolt(b,x,-9.43,2.95,.024)
# Rectangular laminated arch sections with real thickness and exposed ends.
for y in [-9.43,-8.97]:
    vs=[]
    for i in range(81):
        x=-2.30+i*4.60/80;z=3.02+.34*(1-(x/2.30)**2)
        for dy,dz in [(-.085,-.14),(.085,-.14),(.085,.14),(-.085,.14)]:vs.append((x,y+dy,z+dz))
    faces=[(i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j) for i in range(80) for j in range(4)]
    b.mesh(M['wood'],vs,faces);b.mesh(M['end'],vs,[(3,2,1,0),(320,321,322,323)])
    # Shallow lamination seams follow the beam instead of random stripes.
    for dz in [-.075,0,.075]:tube(b,'end',[(x,y-.087,3.02+.34*(1-(x/2.30)**2)+dz) for x in [-2.30+i*4.6/80 for i in range(81)]],.0016,4)
for i in range(11):
    x=-2.1+i*.42;z=3.02+.34*(1-(x/2.30)**2)+.175
    beam(b,(x,-9.82,z),(x,-8.58,z),.065,.09)

b=group('E03 Welcome badge and lanterns')
# Round board backed by a bracket; raised bronze inlay, no floating symbols.
tube(b,'wood',[(0,-9.54,3.17),(0,-9.63,3.17)],.295,72)
tube(b,'iron',[(0,-9.637,3.17),(0,-9.645,3.17)],.26,72)
tube(b,'end',[(0,-9.65,3.17),(0,-9.665,3.17)],.246,72)
for dx,dz,sx,sz in [(0,-.06,.105,.085),(-.14,.065,.040,.056),(-.052,.125,.044,.058),(.052,.125,.044,.058),(.14,.065,.040,.056)]:sphere(b,'iron',(dx,-9.683,3.17+dz),(sx,.012,sz),20,10)
for x in [-1.85,1.85]:
    box(b,'iron',(x,-9.355,1.95),(.12,.035,.34))
    tube(b,'iron',[(x,-9.38,2.14),(x,-9.61,2.14),(x,-9.66,2.09)],.015,10)
    box(b,'glass',(x,-9.64,1.92),(.135,.13,.225))
    for dx in [-.085,.085]:
        for dy in [-.08,.08]:tube(b,'iron',[(x+dx,-9.64+dy,1.77),(x+dx,-9.64+dy,2.07)],.009,8)
    for z in [1.765,2.075]:box(b,'iron',(x,-9.64,z),(.205,.20,.025))
    b.mesh(M['iron'],[(x-.12,-9.76,2.09),(x+.12,-9.76,2.09),(x+.12,-9.52,2.09),(x-.12,-9.52,2.09),(x,-9.64,2.17)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])

# Individually laid irregular flagstones, a continuous level threshold and mosaic paw.
b=group('E04 Flagstone threshold')
box(b,'mortar',(0,-9.22,.008),(3.22,3.10,.035))
seeds=[(-1.6+(i+.5+random.uniform(-.22,.22))*3.2/24,-10.75+(j+.5+random.uniform(-.22,.22))*3.1/24) for j in range(24) for i in range(24)]
def clip(poly,a,c,d):
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        u=a*p[0]+c*p[1]-d;v=a*q[0]+c*q[1]-d
        if u<=0:out.append(p)
        if (u<=0)!=(v<=0):t=u/(u-v);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return out
for x,y in seeds:
    poly=[(-1.6,-10.75),(1.6,-10.75),(1.6,-7.65),(-1.6,-7.65)]
    for xx,yy in seeds:
        if (xx,yy)==(x,y):continue
        poly=clip(poly,xx-x,yy-y,(xx*xx+yy*yy-x*x-y*y)/2)
        if not poly:break
    n=len(poly);poly=[(x+(a-x)*.965,y+(c-y)*.965) for a,c in poly]
    dark=any(((x-cx)/rx)**2+((y-cy)/ry)**2<1 for cx,cy,rx,ry in [(0,-9.65,.39,.32),(-.48,-9.26,.17,.20),(-.18,-9.06,.16,.20),(.18,-9.06,.16,.20),(.48,-9.26,.17,.20)])
    z=.049+random.uniform(-.003,.003);vs=[(a,c,h) for h in [.0,z] for a,c in poly]
    faces=[tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    b.mesh(M['dark' if dark else 'stone'+str(random.randrange(5))],vs,faces)

b=group('E05 Side planting bowls')
for cx in [-2.57,2.57]:
    cy=-9.45
    for row in range(3):
        for j in range(12):
            a=j*math.tau/12+(row%2)*math.pi/12;pts=[]
            for z in [.06+row*.17,.215+row*.17]:
                for r in [.32,.47]:
                    for ang in [a-.245,a+.245]:pts.append((cx+r*math.cos(ang),cy+r*math.sin(ang),z))
            b.mesh(M['stone'+str((j+row)%5)],pts,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)])
    tube(b,'soil',[(cx,cy,.40),(cx,cy,.47)],.315,32)
    for j in range(26):
        a=random.random()*math.tau;r=random.random()*.24;x=cx+r*math.cos(a);y=cy+r*math.sin(a);h=random.uniform(.18,.47)
        tube(b,'leaf',[(x,y,.46),(x+.03,y,.46+h)],.006,5)
        for k in range(4):leaf(b,M['leaf' if k%2 else 'tip'],(x,y,.48+h*k/4),a+k*2.3,.14,.033,.3)
        for k in range(6):aa=k*math.tau/6;sphere(b,'flower',(x+.028*math.cos(aa),y+.028*math.sin(aa),.46+h),(.025,.016,.009),6,3)

new=[]
for name,b in groups.items():new+=finish(b,name,collection(name),.006 if name.startswith(('E01','E02','E03','E04')) else .003)
# Long-grain UVs follow each timber component, including curved horizontal beams.
for o in new:
    if not o.name.startswith('E02') or o.data.materials[0]!=M['wood']:continue
    mesh=o.data;adj=[[] for _ in mesh.vertices]
    for e in mesh.edges:
        a,c=e.vertices;adj[a].append(c);adj[c].append(a)
    seen=set();axes={}
    for i in range(len(mesh.vertices)):
        if i in seen:continue
        stack=[i];seen.add(i);ids=[]
        while stack:
            j=stack.pop();ids.append(j)
            for k in adj[j]:
                if k not in seen:seen.add(k);stack.append(k)
        spans=[max(mesh.vertices[j].co[k] for j in ids)-min(mesh.vertices[j].co[k] for j in ids) for k in range(3)]
        long=max(range(3),key=lambda k:spans[k])
        for j in ids:axes[j]=long
    for p in mesh.polygons:
        long=axes[p.vertices[0]];cross=max((k for k in range(3) if k!=long),key=lambda k:1-abs(p.normal[k]))
        for li in p.loop_indices:
            v=mesh.vertices[mesh.loops[li].vertex_index].co;mesh.uv_layers.active.data[li].uv=(v[cross]*.8,v[long]*.8)
# Model-only export retains UVs and PBR textures. No cameras or lighting included.
bpy.ops.object.select_all(action='DESELECT')
for o in new:o.select_set(True)
dest=OUT/'entrance-crafted.glb'
bpy.ops.export_scene.gltf(filepath=str(dest),export_format='GLB',use_selection=True,export_animations=False,export_apply=True)
scene=bpy.context.scene
scene['entrance_revision']='Crafted masonry and laminated timber gateway'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paw-commons-quality.blend'),compress=True)
report={'source':'paw-commons-quality.blend','transport':'Blender MCP / execute_blender_code','groups':list(groups),'clearWidthMetres':3.435,'postSectionMetres':.265,'entranceGLB':dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'ueImported':False,'note':'Visual construction model, not a certified structural design.'}
(OUT/'entrance-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
scene.cycles.samples=64;scene.render.resolution_x=1800;scene.render.resolution_y=1350
for name,loc,target,scale in [('07-entrance-front',(4,-18,5),(0,-9.2,1.55),7.0),('08-entrance-joints',(4,-13,4.2),(1.65,-9.2,2.2),3.5),('09-entrance-threshold',(2,-14,6),(0,-9.4,.4),4.9),('01-overview',(10,-36,23),(0,0,-.2),33)]:
    camera(scene,loc,target,scale);scene.render.filepath=str(OUT/'review'/f'{name}.png');bpy.ops.render.render(write_still=True)
print('PAW_ENTRANCE_CRAFTED_COMPLETE',flush=True)
