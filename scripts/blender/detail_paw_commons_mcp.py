"""High-detail design master, dispatched using paw_mcp_client.py.

Run build_paw_commons_v2.py first to produce the measured base. This pass reads
that base and writes a separate master, so it is repeatable without duplication.
"""
import bpy, math, random, sys, json, hashlib, traceback
import numpy as np
from contextlib import nullcontext
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1];OUT=ROOT/'art/paw-commons-v2';ASSET=ROOT/'static/models/paw-commons-v2'
sys.path.insert(0,str(HERE))
from shepherd_geometry import Batch,material
from cinematic_island_tools import finish,collection,leaf,lathe,camera,principled

bpy.ops.wm.open_mainfile(filepath=str(OUT/'paw-commons.blend'))
random.seed(891)
M={k:bpy.data.materials[v] for k,v in {'oak':'Honey oak','bark':'Weathered bark','rock':'Layered limestone','grass':'Living turf','rope':'Woven natural fibre','leaf':'Leaf green','light':'Leaf sun tips','sage':'Sage painted edges','apricot':'Apricot painted edges','cream':'Warm ivory','metal':'Brushed metal','pink':'Small blush flowers','gold':'Small cream flowers'}.items()}
M['white']=material('Daisy ivory petals',(.87,.85,.68));M['purple']=material('Verbena lilac petals',(.45,.25,.49))
M['soil']=material('Planted earth',(.075,.058,.033));M['moss']=material('Rock crevice moss',(.13,.22,.05))
M['lamp']=material('Amber lantern glass',(.95,.55,.14),.3,0,1.3)
# Bright, fine-grained honey timber and seamless gravel, authored albedo maps.
for key,base in [('oak',(.57,.36,.18)),('rock',(.43,.40,.32))]:
    mat=M[key]
    for node in mat.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image.name.endswith('_albedo'):
            im=node.image;w,h=im.size;pixels=np.empty(w*h*4,dtype=np.float32);im.pixels.foreach_get(pixels)
            pix=pixels.reshape(h,w,4);avg=pix[:,:,:3].mean(axis=(0,1));pix[:,:,:3]*=np.array(base)/avg
            im.pixels.foreach_set(np.clip(pix,0,1).ravel());im.pack()
gravel=bpy.data.materials['Warm gravel']
for node in gravel.node_tree.nodes:
    if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=.10
    if node.type=='TEX_IMAGE' and node.image.name.endswith('_albedo'):
        im=node.image;w,h=im.size;yy,xx=np.mgrid[0:h,0:w]/w
        rng=np.random.default_rng(31);noise=rng.normal(0,.027,(h,w))+.015*np.sin(xx*math.tau*17)*np.cos(yy*math.tau*13)
        rgb=np.clip(np.array([.68,.61,.48])[None,None,:]+noise[:,:,None],0,1)
        im.pixels.foreach_set(np.dstack((rgb,np.ones((h,w)))).astype(np.float32).ravel());im.pack()

def remove_group(prefix):
    for c in list(bpy.data.collections):
        if c.name.startswith(prefix):
            for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
            bpy.data.collections.remove(c)

groups={}
def batch(name):
    b=Batch();groups[name]=b;return b
def box(b,m,p,s,a=0):b.box(M[m],p,s,a)
def tube(b,m,points,r,n=10):b.tube(M[m],points,r,n)
def ball(b,m,p,s,n=10,rings=6):b.ellipsoid(M[m],p,s,n,rings)
def foliage(b,p,scale=1,count=160):
    for i in range(count):
        a=random.random()*math.tau;r=math.sqrt(random.random())*scale
        pos=(p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]+random.uniform(-.35,.45)*scale)
        leaf(b,M['leaf' if i%3 else 'light'],pos,random.random()*math.tau,.16+random.random()*.14,.045+random.random()*.025,.4)
def flower_patch(b,x,y,r,count=60):
    for i in range(count):
        a=random.random()*math.tau;rr=r*math.sqrt(random.random());xx=x+rr*math.cos(a);yy=y+rr*math.sin(a);h=random.uniform(.15,.48)
        tube(b,'leaf',[(xx,yy,0),(xx+.025,yy,h)],.005,4)
        for j in range(2):leaf(b,M['leaf'],(xx,yy,h*.35),a+j*2,.18,.035,.6)
        for j in range(5):
            aa=j*math.tau/5;ball(b,['white','pink','purple'][i%3],(xx+.034*math.cos(aa),yy+.034*math.sin(aa),h),(.032,.022,.012),6,3)
        ball(b,'gold',(xx,yy,h+.006),(.015,.015,.012),6,3)

# Match the layered landscape rather than sparse trees made of isolated blobs.
remove_group('12 Trees')
b=batch('D01 Branching trees')
trees=[(-11,5.8,4.0),(-7.8,9,5.0),(-.8,10.1,4.5),(10.5,6,4.0),(-12,-5.4,2.7),(11.8,-6.7,2.4),(.3,.8,3.3)]
for tx,ty,h in trees:
    trunk=[(tx,ty,0),(tx+.18,ty-.12,h*.4),(tx-.1,ty+.1,h*.73),(tx+.25,ty,h)]
    tube(b,'bark',trunk,[.23,.17,.10,.025],16)
    for i in range(5):
        a=i*math.tau/5;tube(b,'bark',[(tx+math.cos(a)*.5,ty+math.sin(a)*.5,.02),(tx+.1*math.cos(a),ty+.1*math.sin(a),.25)],[.025,.10],9)
    for j in range(11):
        a=j*2.399;z=h*(.38+.045*j);r=1.0+.6*math.sin(j*.8)**2
        end=Vector((tx+math.cos(a)*r,ty+math.sin(a)*r,z+.8))
        tube(b,'bark',[(tx,ty,z),((tx+end.x)*.5,(ty+end.y)*.5,z+.25),end],[.075,.045,.015],10)
        for k in range(4):
            aa=a+(k-1.5)*.8;q=end+Vector((math.cos(aa)*.6,math.sin(aa)*.6,(k%2)*.4))
            tube(b,'bark',[end,q],[.018,.004],6);foliage(b,q,.7,75)

# Vegetated rock ledges and individual trailing vines.
b=batch('D02 Rock ledges and trailing vines')
for i in range(165):
    a=i*math.tau/165;rr=random.uniform(.80,.99);z=random.uniform(-2.8,-.2)
    x=13.7*math.cos(a)*rr;y=11.25*math.sin(a)*rr
    ball(b,'rock',(x,y,z),(.40+random.random()*.55,.45+random.random()*.4,.3+random.random()*.45),9,5)
    if i%3==0:ball(b,'moss',(x,y,z+.22),(.35,.35,.12),9,4)
for i in range(74):
    a=i*math.tau/74;x=13.3*math.cos(a);y=10.8*math.sin(a);length=random.uniform(1.2,3.6)
    points=[(x+.16*math.sin(j*.8),y+.12*math.cos(j),.1-j*length/17) for j in range(18)]
    tube(b,'bark',points,.013,5)
    for j,p in enumerate(points):
        for side in [-1,1]:leaf(b,M['leaf' if j%2 else 'light'],p,a+side*1.4,.20+random.random()*.12,.085,.25)

# Dense but clustered beds, ground grasses, and fern-like tufted plants.
b=batch('D03 Ground planting')
for i in range(75):
    a=i*math.tau/75;r=random.uniform(.85,.96);x=13.5*math.cos(a)*r;y=11.2*math.sin(a)*r
    if y<-8 and abs(x)<2.5:continue
    flower_patch(b,x,y,.50,40)
    for k in range(16):leaf(b,M['leaf' if k%2 else 'light'],(x,y,.03),k*math.tau/16,.32+random.random()*.38,.028,.8)
for i in range(28000):
    x=random.uniform(-13.6,13.6);y=random.uniform(-11.2,11.2);r=(x/13.6)**2+(y/11.2)**2
    if r>.98 or (x/11.3)**2+(y/8.9)**2<1 and (x/9.5)**2+(y/7.1)**2>1:continue
    if y<-7 and abs(x)<1.7:continue
    h=random.uniform(.025,.12);a=random.random()*math.tau;w=.008
    b.mesh(M['leaf' if i%4 else 'light'],[(x-w,y,0),(x+w,y,0),(x+.03*math.cos(a),y+.03*math.sin(a),h)],[(0,1,2)])
# Central tree bed matches the concept; future runtime navigation must exclude it.
for i in range(18):
    a=i*math.tau/18;ball(b,'rock',(.3+1.25*math.cos(a),.8+1.10*math.sin(a),.16),(.28,.23,.25),10,5)
flower_patch(b,.3,.8,1.05,180)

# A planted dome with broad shoulders, instead of a grass-colored half barrel.
for c in list(bpy.data.collections):
    if c.name.startswith('05 Ear tunnel'):
        for o in list(c.objects):
            if o.data.materials[0]==M['grass']:bpy.data.objects.remove(o,do_unlink=True)
b=batch('D04a Broad tunnel mound');vs=[]
for j in range(33):
    a=j*math.pi/32
    for q in range(25):
        t=q/24;yy=.8-1.38+t*2.76;width=.91+.75*math.sin(t*math.pi)**.7
        vs.append((-10+width*math.cos(a),yy,.035+(1.43+.12*math.sin(t*math.pi))*math.sin(a)))
b.mesh(M['grass'],vs,[(j*25+q,j*25+q+1,(j+1)*25+q+1,(j+1)*25+q) for j in range(32) for q in range(24)],True)
col=next(c for c in bpy.data.collections if c.name.startswith('05 Ear tunnel'))
finish(b,'05 Mound',col);groups.pop('D04a Broad tunnel mound')
# A second tunnel portal and mound, smaller for cats. The first remains dog-sized.
for c in list(bpy.data.collections):
    if c.name.startswith('05 Ear tunnel'):
        col=collection('D04 Second grassy tunnel')
        for o in c.objects:
            clone=o.copy();clone.data=o.data.copy();col.objects.link(clone)
            # Shared mesh coordinates are world authored: transform around first tunnel.
            for v in clone.data.vertices:
                v.co=Vector((-7.4,4.0,0))+(v.co-Vector((-10,.8,0)))*.82
            clone.name='Second tunnel '+o.name
b=batch('D05 Tunnel garden')
for x,y,scale in [(-10,.8,1),(-7.4,4,.82)]:
    for j in range(900):
        a=random.uniform(.18,math.pi-.18);t=random.random();width=.91+.75*math.sin(t*math.pi)**.7
        xx=x+scale*width*math.cos(a);yy=y+scale*(-1.38+t*2.76);zz=scale*(.035+(1.43+.12*math.sin(t*math.pi))*math.sin(a))
        leaf(b,M['leaf' if j%3 else 'light'],(xx,yy,zz),random.random()*math.tau,.09,.018,.8)

# Leaf-shaped canopy: central spine, outer rim and individually bowed ribs.
remove_group('09 Shade')
b=batch('D06 Leaf canopy and bench');x=6.5;y=7.3
def roof(q,t):return (x+q,y+t,2.65+.4*(1-(q/2.1)**2)+.12*(1-(t/1.35)**2))
for xx in [-1.8,1.8]:
    for yy in [-.65,.65]:
        tube(b,'oak',[(x+xx,y+yy,0),roof(xx,yy)],.075,12)
        tube(b,'oak',[(x+xx,y+yy,2.1),roof(xx*.6,yy)],.045,10)
        tube(b,'oak',[roof(xx,0),roof(xx,yy)],.045,10)
for side in [-1,1]:
    tube(b,'oak',[roof(q,side*1.35*math.sin(math.pi*(q+2.1)/4.2)**.65) for q in [-2.1+i*4.2/48 for i in range(49)]],.065,12)
tube(b,'oak',[roof(-2.1+i*4.2/48,0) for i in range(49)],.075,12)
for i in range(1,20):
    q=-2.1+i*4.2/20;w=1.35*math.sin(math.pi*i/20)**.65
    for side in [-1,1]:tube(b,'oak',[roof(q-.28*(1-t),side*w*t) for t in [j/12 for j in range(13)]],.038,8)
for i in range(27):
    t=-.92+i*1.84/26;xx=x+math.sin(t)*2;yy=y+math.cos(t)*2-1.45
    box(b,'oak',(xx,yy,.45),(.13,.64,.065),-t)
    for z in [.65,.82,.99]:box(b,'oak',(xx,yy+.34,z),(.13,.07,.14),-t)
for xx in [-1.4,0,1.4]:box(b,'oak',(x+xx,y,.23),(.10,.50,.46))
for xx in [-1.1,1.1]:ball(b,'sage' if xx<0 else 'apricot',(x+xx,y+.05,.65),(.29,.14,.24),24,12)

# Replace the tiny cubby with a detailed two-exit boarded house and leaf platforms.
remove_group('08 Cat tree')
b=batch('D07 Climbing grove');x=-6.5;y=7.4
platforms=[(-1.2,-1,.55),(.4,-.5,1.05),(-.7,.65,1.65),(.8,.9,2.35)]
def leafdeck(xx,yy,z):
    for k in range(15):
        t=k/14;w=.6*math.sin(math.pi*t)**.65
        if w>.01:box(b,'oak',(xx-1+t*2,yy,z),(.13,w*2,.09))
    tube(b,'sage',[(xx-1+2*t,yy+.6*math.sin(math.pi*t)**.65,z+.04) for t in [k/32 for k in range(33)]],.025,8)
    tube(b,'sage',[(xx-1+2*t,yy-.6*math.sin(math.pi*t)**.65,z+.04) for t in [k/32 for k in range(33)]],.025,8)
for px,py,z in platforms:
    xx=x+px;yy=y+py;tube(b,'oak',[(xx,yy,0),(xx,yy,z)],.12,16)
    # True helical rope rather than disconnected rings.
    turns=int(z/.035);pts=[(xx+.13*math.cos(a),yy+.13*math.sin(a),.04+a/(math.tau)*.035) for a in [i*math.tau/10 for i in range(turns*10)]]
    tube(b,'rope',pts,.018,6);leafdeck(xx,yy,z)
routes=[((x-1.2,y-3,.02),(x-1.2,y-1,.55))]+[((x+a[0],y+a[1],a[2]),(x+c[0],y+c[1],c[2])) for a,c in zip(platforms,platforms[1:])]
# The final stair reaches the front doorway landing, not a closed side wall.
routes[-1]=(routes[-1][0],(x+.8,y-.1,2.35))
for start,end in routes:
    p=Vector(start);q=Vector(end);a=math.atan2(q.y-p.y,q.x-p.x);steps=math.ceil((q-p).length/.16)
    for j in range(steps+1):box(b,'oak',tuple(p.lerp(q,j/steps)),(.18,.62,.07),a)
    for side in [-1,1]:
        offset=Vector((-math.sin(a)*side*.25,math.cos(a)*side*.25,-.07));tube(b,'oak',[p+offset,q+offset],.045,10)
cx=x+.8;cy=y+.9;z=2.4
box(b,'oak',(cx,cy,z),(1.35,1.25,.10))
for side in [-1,1]:
    for i in range(5):box(b,'oak',(cx,cy+side*(.60+i*.12),2.35),(.9,.11,.08))
    for dx in [-.35,.35]:tube(b,'oak',[(cx+dx,cy+side*.5,2.05),(cx+dx,cy+side*1.1,2.30)],.045,10)
for side in [-1,1]:
    for k in range(11):box(b,'oak',(cx+side*.65,cy-.56+k*.112,z+.55),(.07,.103,1.05))
    # Front and back consist of strips split around an actual circular opening.
    for k in range(13):
        dx=-.60+k*.1;r=.33;hole=math.sqrt(max(0,r*r-dx*dx))
        if abs(dx)<r:
            for lo,hi in [(0,.50-hole),(.50+hole,1.05)]:
                if hi>lo:box(b,'oak',(cx+dx,cy+side*.61,z+(lo+hi)/2),(.092,.07,hi-lo))
        else:box(b,'oak',(cx+dx,cy+side*.61,z+.525),(.092,.07,1.05))
    tube(b,'cream',[(cx+.34*math.cos(a),cy+side*.66,z+.5+.34*math.sin(a)) for a in [j*math.tau/48 for j in range(49)]],.028,8)
for side in [-1,1]:
    for row in range(5):
        for j in range(9):box(b,'sage',(cx+side*(.10+row*.15),cy-.70+j*.17,z+1.30-row*.085),(.19,.16,.06))
tube(b,'oak',[(cx,cy-.8,z+1.34),(cx,cy+.8,z+1.34)],.055,10)

# Real fasteners, carved end rings, lamps and entry stonework.
b=batch('D08 Crafted details')
for x in [-1.8,1.8]:
    for z in [.8,2.3]:
        ball(b,'metal',(x,-9.37,z),(.04,.014,.04),12,6)
        tube(b,'bark',[(x-.022,-9.386,z),(x+.022,-9.386,z)],.005,5)
    for z in [.34,1.85]:
        box(b,'oak',(x,-9.45,z),(.28,.25,.45));box(b,'lamp',(x,-9.59,z),(.18,.035,.32))
        for dx in [-.10,.10]:tube(b,'metal',[(x+dx,-9.62,z-.19),(x+dx,-9.62,z+.19)],.012,6)
for i in range(34):
    x=random.uniform(-1.5,1.5);y=random.uniform(-10.9,-7.4)
    ball(b,'rock',(x,y,.03),(.22+random.random()*.18,.20+random.random()*.12,.055),7,3)
for dx,dy,s in [(0,0,.28),(-.34,.32,.10),(-.12,.48,.11),(.12,.48,.11),(.34,.32,.10)]:ball(b,'bark',(dx,-8.8+dy,.10),(s,s*.85,.012),16,4)
# Toy ropes and woven basket on the accessible open cabinet.
for i in range(4):
    pts=[(9.5+i*.3+.09*math.cos(a),-5.2+.06*math.sin(a),.61+.015*a) for a in [j*.2 for j in range(50)]]
    tube(b,'rope',pts,.018,6)

newobs=[]
for name,b in groups.items():newobs+=finish(b,name,collection(name))
# Give key facilities the visual scale they have in the concept illustration.
for prefix,pivot,scale in [('D07',(-6.5,7.4,0),1.18),('D06',(6.5,7.3,0),1.12),('06 Balance',(-9,-4.7,0),1.25)]:
    for c in bpy.data.collections:
        if c.name.startswith(prefix):
            for o in c.objects:
                for v in o.data.vertices:v.co=Vector(pivot)+(v.co-Vector(pivot))*scale
for o in bpy.context.scene.objects:
    if o.type=='MESH' and o.data.materials and o.data.materials[0]==M['grass']:
        for loop in o.data.loops:
            v=o.data.vertices[loop.vertex_index].co;o.data.uv_layers.active.data[loop.index].uv=((v.x+15)/30,(v.y+13)/26)
# Small edge radii on constructed wood, retained editable in the Blender master.
for o in list(bpy.context.scene.objects):
    if o.type=='MESH' and ('oak' in o.name.lower() or 'painted' in o.name.lower()):
        mod=o.modifiers.new('Crafted softened edges','BEVEL');mod.width=.012;mod.segments=2;mod.limit_method='ANGLE'
        mod.angle_limit=.65
scene=bpy.context.scene
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.69,.78,.84,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
for o in scene.objects:
    if o.type=='LIGHT' and o.data.type=='SUN':o.data.energy=3.2;o.data.color=(1,.80,.55);o.rotation_euler=(.7,-.6,-.7);o.data.angle=.12
scene.cycles.samples=64;scene.render.resolution_x=2000;scene.render.resolution_y=1450
scene.view_settings.look='AgX - Medium High Contrast'
camera(scene,(12,-37,25),(0,0,-.1),34)
scene['authoring_transport']='MCP stdio -> mcp-for-blender -> addon execute_code'
scene['status']='High-detail design master, not runtime-optimized'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paw-commons-detailed.blend'),compress=True)
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
    if o.type=='MESH':o.select_set(True)
override=nullcontext()
if not bpy.app.background:
    window=bpy.context.window_manager.windows[0]
    area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
    region=next(r for r in area.regions if r.type=='WINDOW')
    override=bpy.context.temp_override(window=window,area=area,region=region)
with override:
    bpy.ops.export_scene.gltf(filepath=str(ASSET/'park-detailed.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=False,export_apply=True)
raw=(ASSET/'park-detailed.glb').read_bytes();tri=0
for o in scene.objects:
    if o.type=='MESH':
        mesh=o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh();mesh.calc_loop_triangles();tri+=len(mesh.loop_triangles);o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
report={'transport':scene['authoring_transport'],'triangles':tri,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'status':scene['status'],'centralTreeNavigationExclusion':{'center':[.3,.8],'radius':1.6},'source':'scripts/blender/detail_paw_commons_mcp.py'}
(OUT/'detailed-build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Presentation is a separate MCP job so geometry export can be verified first.
print('PAW_DETAILED_MCP_COMPLETE '+json.dumps(report),flush=True)
