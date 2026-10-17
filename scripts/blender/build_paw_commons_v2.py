"""Measured Blender design master derived from paw-commons-v2 concept boards.

Own textures and deterministic geometry; never reads private models or modifies
the four existing islands. Run Blender --background --python THIS -- --render.
"""
import bpy
import hashlib
import json
import math
import random
import sys
import numpy as np
from pathlib import Path
from mathutils import Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from shepherd_geometry import Batch, material
from cinematic_island_tools import tile, finish, collection, camera, leaf, lathe, principled

ROOT=HERE.parents[1]
OUT=ROOT/'art/paw-commons-v2'
ASSET=ROOT/'static/models/paw-commons-v2'
for p in [OUT/'review',ASSET]:p.mkdir(parents=True,exist_ok=True)
layout=json.loads((OUT/'design/layout.json').read_text())
random.seed(73)
bpy.ops.wm.read_factory_settings(use_empty=True)
M={
 'oak':tile('Honey oak',(.46,.27,.12),'wood'),
 'bark':tile('Weathered bark',(.20,.12,.065),'wood',31),
 'rock':tile('Layered limestone',(.32,.30,.24),'stone'),
 'gravel':tile('Warm gravel',(.63,.56,.42),'stone',45),
 'grass':material('Living turf',(.24,.36,.10)),
 'rope':tile('Woven natural fibre',(.46,.39,.24),'wood',53),
 'sage':material('Sage painted edges',(.29,.43,.29)),
 'apricot':material('Apricot painted edges',(.69,.35,.20)),
 'cream':material('Warm ivory',(.79,.74,.58)),
 'metal':material('Brushed metal',(.42,.46,.46),.3,.75),
 'leaf':material('Leaf green',(.12,.26,.055)),
 'leafLight':material('Leaf sun tips',(.28,.42,.08)),
 'pink':material('Small blush flowers',(.65,.25,.28)),
 'gold':material('Small cream flowers',(.83,.7,.30)),
 'water':material('Bowl water',(.21,.43,.46),.18,.25)
}
# One island-wide turf map: low contrast variation without a repeating tile grid.
n=1024;yy,xx=np.mgrid[0:n,0:n]/n
field=.035*np.sin(xx*19+yy*7)+.025*np.sin(yy*27-xx*11)
field+=np.random.default_rng(72).normal(0,.018,(n,n))
rgb=np.clip(np.array([.26,.37,.115])[None,None,:]+field[:,:,None],0,1)
im=bpy.data.images.new('Island-wide turf albedo',width=n,height=n)
im.pixels.foreach_set(np.dstack((rgb,np.ones((n,n)))).astype(np.float32).ravel());im.pack()
nt=M['grass'].node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
nt.links.new(tex.outputs['Color'],principled(M['grass']).inputs['Base Color'])
groups={}
def batch(name):
    b=Batch();groups[name]=b;return b
def tube(b,key,points,r,n=12):b.tube(M[key],points,r,n)
def box(b,key,p,s,a=0):b.box(M[key],p,s,a)
def sphere(b,key,p,s,n=12,rings=8):b.ellipsoid(M[key],p,s,n,rings)
def arch(b,key,x,y,z,w,h,r=.07):
    tube(b,key,[(x+w*math.cos(t),y,z+h*math.sin(t)) for t in [i*math.pi/32 for i in range(33)]],r)
def ring(b,key,x,y,z,r,axis='y',thick=.06):
    pts=[(x+r*math.cos(i*math.tau/48),y,z+r*math.sin(i*math.tau/48)) if axis=='y' else (x+r*math.cos(i*math.tau/48),y+r*math.sin(i*math.tau/48),z) for i in range(49)]
    tube(b,key,pts,thick,8)
def bolt(b,x,y,z):sphere(b,'metal',(x,y,z),(.035,.018,.035),8,5)

# A flat navigable palm surrounded by a low planted rim and layered rock.
b=batch('01 Palm terrain');N=128
def contour(a,r=1):
    f=1+.065*math.sin(3*a)-.025*math.cos(5*a)
    return 13.7*math.cos(a)*f*r,11.25*math.sin(a)*f*r
top=[(0,0,0)]+[(*contour(i*math.tau/N),0) for i in range(N)]
b.mesh(M['grass'],top,[(0,i+1,(i+1)%N+1) for i in range(N)])
levels=[(1,-.04),(.985,-.8),(.93,-1.9),(.8,-3.3),(.5,-4.8),(.05,-5.5)]
vs=[(*contour(i*math.tau/N,r*(1+.015*math.sin(i*7+j))),z+.12*math.sin(i*3+j)) for j,(r,z) in enumerate(levels) for i in range(N)]
b.mesh(M['rock'],vs,[(j*N+i,(j+1)*N+i,(j+1)*N+(i+1)%N,j*N+(i+1)%N) for j in range(len(levels)-1) for i in range(N)])
for i in range(120):
    a=i*math.tau/120;x,y=contour(a,.97);sphere(b,'rock',(x,y,-.35-random.random()*1.4),(.45+random.random()*.4,.4,.4+random.random()*.4),9,5)
# Winding two-metre promenade and individual paving slabs.
b=batch('02 Paths');vs=[]
for i in range(N):
    a=i*math.tau/N
    for rx,ry in [(9.5,7.1),(11.3,8.9)]:vs.append((rx*math.cos(a),ry*math.sin(a),.018))
b.mesh(M['gravel'],vs,[(2*i,2*((i+1)%N),2*((i+1)%N)+1,2*i+1) for i in range(N)])
for i in range(100):
    a=i*math.tau/100;sphere(b,'rock',(11.35*math.cos(a),8.95*math.sin(a),.08),(.16,.13,.1),8,4)
for y in [-10.5,-9.8,-9.1,-8.4,-7.7]:
    for x in [-.9,0,.9]:box(b,'rock',(x+random.uniform(-.08,.08),y,.045),(.82,.6,.08),random.uniform(-.1,.1))
# Entrance timber arch, visible bases and paired laminated beams.
b=batch('03 Entrance')
for x in [-1.8,1.8]:
    box(b,'rock',(x,-9.2,.28),(.55,.6,.56));tube(b,'oak',[(x,-9.2,.5),(x,-9.2,2.65)],.15)
    for z in [.8,2.3]:bolt(b,x,-9.36,z)
for y in [-9.45,-8.95]:tube(b,'oak',[(x,y,2.75+.42*(1-(x/2.15)**2)) for x in [-2.15+i*4.3/32 for i in range(33)]],.11)
for x in [-1.8,-1.2,-.6,0,.6,1.2,1.8]:tube(b,'oak',[(x,-9.58,2.9),(x,-8.82,2.9)],.055)
sphere(b,'cream',(0,-9.58,2.6),(.15,.035,.12))
for dx,dz in [(-.20,.16),(-.07,.26),(.07,.26),(.20,.16)]:sphere(b,'cream',(dx,-9.58,2.6+dz),(.055,.035,.075))
# Perimeter posts and ropes, with an open welcome gap at the entrance.
b=batch('04 Boundary')
for i in range(64):
    a=i*math.tau/64;x,y=contour(a,.94)
    if y<-8 and abs(x)<2.4:continue
    tube(b,'oak',[(x,y,0),(x,y,.9)],.065,8)
    aa=(i+1)*math.tau/64;xx,yy=contour(aa,.94)
    if yy<-8 and abs(xx)<2.4:continue
    tube(b,'rope',[(x,y,.75),((x+xx)/2,(y+yy)/2,.61),(xx,yy,.75)],.022,6)
# True open tunnel: continuous outer/inner arches, open front and back.
b=batch('05 Ear tunnel');x=-10;y=.8;length=3.;radius=.66
for j in range(33):
    a=j*math.pi/32
    tube(b,'oak',[(x+radius*math.cos(a),y-length/2,.07+1.27*math.sin(a)),(x+radius*math.cos(a),y+length/2,.07+1.27*math.sin(a))],.045,8)
for yy in [y-length/2-.06,y+length/2+.06]:
    arch(b,'oak',x,yy,.07,.72,1.33,.10)
    for side in [-1,1]:tube(b,'oak',[(x+side*.48,yy,1.12),(x+side*.62,yy,1.67),(x+side*.25,yy,1.36)],.06,8)
for i in range(13):box(b,'oak',(x,y-length/2+i*.25,.035),(1.2,.23,.07))
for side in [-1,1]:
    for j in range(9):sphere(b,'rock',(x+side*.86,y-1.4+j*.35,.14),(.22,.2,.18),9,5)
# Grass-covered shell above the tunnel, keeping both ends and the bore clear.
vs=[]
for j in range(25):
    a=j*math.pi/24
    for q in range(17):
        yy=y-1.35+q*2.7/16
        vs.append((x+.92*math.cos(a),yy,.06+1.50*math.sin(a)))
b.mesh(M['grass'],vs,[(j*17+q,j*17+q+1,(j+1)*17+q+1,(j+1)*17+q) for j in range(24) for q in range(16)],True)
# Low bridge runs along north/south, each ramp plank follows the actual slope.
b=batch('06 Balance bridge');x=-9;y=-4.7
for yy in [-.82,.82]:
    for xx in [-.45,.45]:tube(b,'oak',[(x+xx,y+yy,0),(x+xx,y+yy,.45)],.085)
for i in range(10):box(b,'oak',(x,y-.9+i*.2,.4),(1.15,.18,.09))
for side in [-1,1]:
    for i in range(8):
        t=(i+.5)/8;yy=y+side*(1+t*1.5);zz=.4*(1-t)
        box(b,'oak',(x,yy,zz),(1.15,.175,.06))
    for xx in [-.45,.45]:tube(b,'oak',[(x+xx,y+side, .34),(x+xx,y+side*2.5,.015)],.045)
# Grounded flower hoops and removable low bars.
b=batch('07 Flower hoops')
for i in range(3):
    x=10;y=-2.8+i*1.8
    for xx in [-.68,.68]:
        box(b,'oak',(x+xx,y,.06),(.35,.65,.12));tube(b,'oak',[(x+xx,y,.12),(x+xx,y,.9)],.065)
        bolt(b,x+xx,y-.07,.4)
    pts=[]
    for k in range(49):
        a=k*math.pi/48;r=.68+.065*math.sin(a*7)**2;pts.append((x+r*math.cos(a),y,.75+r*math.sin(a)))
    tube(b,'sage' if i%2 else 'apricot',pts,.08,10)
    tube(b,'cream',[(x-.65,y,.25),(x+.65,y,.25)],.035)
# Cat corner: low broad platforms, wrapped posts, two-exit cabin, stepped access.
b=batch('08 Cat tree');x=-6.5;y=7.4
platforms=[(-1,-.3,.65),(.8,0,1.2),(-.4,.65,2.1)]
for px,py,z in platforms:
    xx=x+px;yy=y+py;tube(b,'oak',[(xx,yy,0),(xx,yy,z)],.12)
    for k in range(int(z/.045)):ring(b,'rope',xx,yy,.06+k*.045,.13,'z',.018)
    sphere(b,'oak',(xx,yy,z),(.78,.58,.09),24,4)
    leaf(b,M['sage'],(xx-.55,yy,z+.09),0,1.15,.42,.04)
cx=x-.4;cy=y+.65;cz=2.19
box(b,'oak',(cx,cy,cz),(1.15,1,.12))
for side in [-1,1]:
    box(b,'oak',(cx+side*.55,cy,cz+.42),(.08,1,.78))
    for xx in [-.48+i*.12 for i in range(9)]:
        if abs(xx)>.27:box(b,'oak',(cx+xx,cy+side*.49,cz+.4),(.105,.07,.8))
        else:box(b,'oak',(cx+xx,cy+side*.49,cz+.74),(.105,.07,.13))
for side in [-1,1]:
    for i in range(7):box(b,'sage',(cx+side*(i*.1),cy,cz+1.04-i*.035),(.12,1.3,.07))
for i in range(9):
    t=i/8;box(b,'oak',(x-1,y-2.1+t*1.4,.06+t*.58),(.75,.19,.08))
for dx in [-.3,.3]:tube(b,'oak',[(x-1+dx,y-2.1,.02),(x-1+dx,y-.7,.6)],.05)
# Continuous staggered stairways connect all three platforms.
for start,end in [(platforms[0],platforms[1]),(platforms[1],platforms[2])]:
    p=Vector((x+start[0],y+start[1],start[2]));q=Vector((x+end[0],y+end[1],end[2]))
    direction=q-p;angle=math.atan2(direction.y,direction.x)
    steps=max(6,math.ceil(abs(direction.z)/.12))
    for i in range(steps+1):
        pos=p.lerp(q,i/steps);box(b,'oak',tuple(pos),(.25,.55,.065),angle)
    for side in [-1,1]:
        offset=Vector((-math.sin(angle)*.22*side,math.cos(angle)*.22*side,-.07))
        tube(b,'oak',[p+offset,q+offset],.04,8)
# Leaf-rib shade over a curved slatted bench, with four real supports.
b=batch('09 Shade bench');x=6.5;y=7.3
for xx in [-1.6,1.6]:
    for yy in [-.85,.85]:tube(b,'oak',[(x+xx,y+yy,0),(x+xx,y+yy,2.4)],.075)
for i in range(13):
    xx=-1.8+i*.3
    tube(b,'oak',[(x+xx,y+q,2.5+.4*(1-(q/1.4)**2)-.12*(xx/1.8)**2) for q in [-1.4+j*2.8/24 for j in range(25)]],.045,8)
for yy in [-1.35,0,1.35]:tube(b,'oak',[(x-1.8,y+yy,2.5),(x+1.8,y+yy,2.5)],.07)
for i in range(17):
    t=-.8+i*1.6/16;xx=x+math.sin(t)*1.9;yy=y+math.cos(t)*1.9-1.4
    box(b,'oak',(xx,yy,.45),(.18,.6,.07),-t)
    box(b,'oak',(xx,yy+.32,.77),(.18,.08,.55),-t)
for xx in [-1.15,0,1.15]:box(b,'oak',(x+xx,y+.1,.23),(.12,.4,.46))
# Drinking bowls: lathed concave basins and drained stone apron.
b=batch('10 Water');x=4.3;y=5.7
box(b,'rock',(x,y,.035),(1.45,.9,.07))
for xx in [-.35,.35]:
    lathe(b,M['metal'],(x+xx,y,.07),[(0,0),(.18,0),(.24,.09),(.24,.13),(.21,.13),(.16,.04),(0,.04)],32)
    sphere(b,'water',(x+xx,y,.115),(.17,.17,.005),24,3)
for i in range(8):box(b,'metal',(x-.55+i*.15,y-.35,.08),(.075,.15,.018))
# Rounded toy cabinet with individually visible slats and balls.
b=batch('11 Toy cabinet');x=10;y=-5.1
for z in [.08,.52,1.04]:box(b,'oak',(x,y,z),(1.7,.5,.07))
for xx in [-.82,.82]:box(b,'oak',(x+xx,y,.56),(.065,.5,1.05))
for i in range(9):box(b,'oak',(x-.76+i*.19,y+.23,.55),(.17,.045,.97))
for i in range(8):sphere(b,['sage','apricot','cream'][i%3],(x-.65+(i%4)*.41,y-.08,.24+(i//4)*.45),(.16,.16,.16),16,8)
# Planting: layered branching trees and individual leaves instead of round blobs.
b=batch('12 Trees and planting')
for tx,ty,h in [(-10,5.4,3.2),(-4,9,4),(1,9.6,3.1),(9,6,3.5),(-11,-6,2.6),(11,-6.5,2.5)]:
    tube(b,'bark',[(tx,ty,0),(tx+.12,ty,h*.65),(tx-.1,ty+.12,h)],[.18,.12,.035])
    for j in range(7):
        a=j*math.tau/7;cx=tx+math.cos(a)*(1+j%2*.4);cy=ty+math.sin(a)*(1+j%2*.4);cz=h*.8+(j%3)*.32
        tube(b,'bark',[(tx,ty,h*.5),(cx,cy,cz)],[.065,.012],8)
        for k in range(145):
            a=random.random()*math.tau;r=math.sqrt(random.random())*.95
            px=cx+math.cos(a)*r;py=cy+math.sin(a)*r;pz=cz+random.uniform(-.4,.65)
            leaf(b,M['leaf' if k%3 else 'leafLight'],(px,py,pz),random.random()*math.tau,.28+random.random()*.18,.10,.25)
# Peripheral grasses and flowering pockets never obstruct the walking ellipse.
for i in range(2600):
    a=random.random()*math.tau;r=random.uniform(.84,.97);x,y=contour(a,r)
    if y<-8 and abs(x)<2.5:continue
    height=random.uniform(.10,.38)
    tube(b,'leaf',[(x,y,.015),(x+.04,y+.025,height)],.008,3)
    if i%7==0:
        for j in range(5):
            t=j*math.tau/5;sphere(b,'pink' if i%2 else 'gold',(x+.035*math.cos(t),y+.035*math.sin(t),height),(.035,.022,.018),6,3)
    if i%3==0:leaf(b,M['leafLight'],(x,y,.02),a,.23,.065,.6)

model_objects=[]
for name,b in groups.items():
    col=collection(name);model_objects+=finish(b,name,col)
for o in model_objects:
    if o.data.materials[0]==M['grass']:
        for loop in o.data.loops:
            v=o.data.vertices[loop.vertex_index].co
            o.data.uv_layers.active.data[loop.index].uv=((v.x+15)/30,(v.y+13)/26)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.world=bpy.data.worlds.new('Cloud daylight');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.66,.75,.78,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
bpy.ops.object.light_add(type='SUN',location=(-12,-14,20));sun=bpy.context.object;sun.rotation_euler=(.4,-.5,-.45);sun.data.energy=2.2;sun.data.angle=.15
bpy.ops.object.light_add(type='AREA',location=(4,-12,15));light=bpy.context.object;light.data.energy=1800;light.data.shape='DISK';light.data.size=15
light.rotation_euler=(Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();scene.camera=bpy.context.object
camera(scene,(28,-38,30),(0,0,-.2),36)
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    if any(d.use for d in prefs.devices):scene.cycles.device='GPU'
except Exception:pass
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.camera.data.lens=45
# The geometry is editable and its GLB carries textures, without studio cameras.
blend=OUT/'paw-commons.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
bpy.ops.object.select_all(action='DESELECT')
for o in model_objects:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'park.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=False)
triangles=0
for o in model_objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
raw=(ASSET/'park.glb').read_bytes()
report=dict(triangles=triangles,meshes=len(model_objects),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),units='metres',source='scripts/blender/build_paw_commons_v2.py',status='design model; facility gameplay not implemented',walkingEllipse=layout['walkArea'])
(OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if '--render' in sys.argv:
    for name,loc,target,scale in [('03-model-overview',(28,-38,30),(0,0,-.2),36),('04-model-top',(0,0,45),(0,0,0),31),('05-model-facilities',(-17,-13,10),(-8,-1,1),15)]:
        camera(scene,loc,target,scale);scene.render.filepath=str(OUT/'review'/f'{name}.png');bpy.ops.render.render(write_still=True)
print('PAW_COMMONS_BUILD '+json.dumps(report))
