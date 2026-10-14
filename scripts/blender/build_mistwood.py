"""Mistwood Conservatory: textured masonry, real branches/leaves, shared navigation."""
import bpy,math,random,json,re,sys
import numpy as np
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch,material,studio
R=Path(__file__).resolve().parents[2];OUT=R/'art/mistwood-v1';DEST=R/'static/models/petchat-mistwood-v1'
OUT.mkdir(exist_ok=True);DEST.mkdir(exist_ok=True)
layout=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(R/'static/js/den/mistwood-layout.js').read_text()).group(1))
bpy.ops.wm.read_factory_settings(use_empty=True);random.seed(2841);b=Batch();rng=np.random.default_rng(2841)

def textured(name,color,kind):
 m=material(name,color,.88);n=1024;y,x=np.mgrid[0:n,0:n]/n;field=np.zeros((n,n))
 for frequency,amp in [(2,.35),(5,.22),(13,.12),(37,.07),(91,.035),(243,.015)]:
  for _ in range(4):
   a=rng.uniform(0,math.tau);phase=rng.uniform(0,math.tau)
   field+=amp*np.sin((x*np.cos(a)+y*np.sin(a))*math.tau*frequency+phase)/4
 if kind=='bark':field+=.13*np.sin(x*170+np.sin(y*13)*2)+.06*np.sin(x*425+y*6)
 if kind=='stone':field-=.12*np.exp(-((np.sin(y*60+field*5))/.15)**2)
 rgb=np.clip(np.array(color)[None,None,:]*(1+field[:,:,None]*1.1),.01,.95)
 im=bpy.data.images.new(name+'_albedo',width=n,height=n);rgba=np.dstack((rgb,np.ones((n,n)))).astype(np.float32);im.pixels.foreach_set(rgba.ravel());im.pack()
 if kind in ('stone','soil'):
  im=bpy.data.images.load(str(OUT/('limestone-albedo.png' if kind=='stone' else 'forest-floor-albedo.png')),check_existing=True);im.pack()
 node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=im;bs=m.node_tree.nodes.get('Principled BSDF');m.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
 dy,dx=np.gradient(field);norm=np.dstack((-dx*35,-dy*35,np.ones((n,n))));norm/=np.linalg.norm(norm,axis=2)[:,:,None]
 normal=bpy.data.images.new(name+'_normal',width=n,height=n);normal.colorspace_settings.name='Non-Color';normal.pixels.foreach_set(np.dstack((norm*.5+.5,np.ones((n,n)))).astype(np.float32).ravel());normal.pack()
 tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=normal;convert=m.node_tree.nodes.new('ShaderNodeNormalMap');convert.inputs['Strength'].default_value=.55;m.node_tree.links.new(tex.outputs['Color'],convert.inputs['Color']);m.node_tree.links.new(convert.outputs['Normal'],bs.inputs['Normal'])
 return m
stone=textured('Weathered_limestone',(.34,.36,.32),'stone');cliff=textured('Stratified_cliff',(.22,.24,.21),'stone');bark=textured('Cedar_bark',(.20,.12,.065),'bark');soil=textured('Forest_floor',(.20,.24,.13),'soil')
iron=material('Patinated_iron',(.055,.075,.065),.46,.65);bronze=material('Aged_brass',(.34,.24,.09),.42,.65)
wood=material('Weathered_bench',(.22,.16,.095),.82);moss=material('Moss',(.12,.20,.065),.95);leaves=material('Birch_leaves',(.13,.24,.065),.9);needles=material('Cedar_sprays',(.055,.12,.07),.94);leaflight=material('Young_leaves',(.12,.18,.045),.88)
for m in [moss,leaves,needles,leaflight]:m.use_backface_culling=False
water=material('River_water',(.10,.22,.20),.12,.30);foam=material('Water_highlights',(.62,.74,.71),.3);light=material('Lantern_glow',(.95,.63,.28),.35,0,1.8)
glass=material('Conservatory_glass',(.38,.53,.48),.16,.15);glass.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value=.20;glass.surface_render_method='DITHERED';glass.diffuse_color=(.38,.53,.48,.20)
terracotta=material('Aged_terracotta',(.31,.16,.09),.9);petal=material('Wildflower',(.62,.63,.49),.9)
radius=layout['radius'];river=layout['water'][0];ry=-river['z'];half=river['d']/2
# Closely sampled flat playable banks; all decorative relief stays outside routes.
for low,high in [(-radius,ry-half),(ry+half,radius)]:
 for j in range(math.ceil((high-low)/.20)):
  y0=low+j*.20;y1=min(high,y0+.20);extent=min(math.sqrt(max(0,radius**2-y0**2)),math.sqrt(max(0,radius**2-y1**2)))
  nx=max(1,math.ceil(extent*2/.20))
  for i in range(nx):
   x0=-extent+2*extent*i/nx;x1=-extent+2*extent*(i+1)/nx
   b.mesh(soil,[(x0,y0,.025),(x1,y0,.025),(x1,y1,.025),(x0,y1,.025)],[(0,1,2,3)])
# Close the narrow seam between sampled banks and the outer cliff ring.
for i in range(384):
 a=i*math.tau/384;c=(i+1)*math.tau/384
 if min(abs(7.65*math.sin(a)-ry),abs(7.65*math.sin(c)-ry))<half+.05:continue
 b.mesh(soil,[(7.48*math.cos(a),7.48*math.sin(a),.025),(7.84*math.cos(a),7.84*math.sin(a),.025),(7.84*math.cos(c),7.84*math.sin(c),.025),(7.48*math.cos(c),7.48*math.sin(c),.025)],[(0,1,2,3)])
# Interlocking irregular paving, shallow enough to agree with navigation height.
for iy in range(-13,12):
 for ix in range(-13,14):
  x=ix*.24+(iy%2)*.12+random.uniform(-.035,.035);y=iy*.24+random.uniform(-.035,.035)
  if math.hypot(x,y)>3.05 or abs(y-ry)<half+.06:continue
  if random.random()<.13:continue
  rx=random.uniform(.10,.15);rr=random.uniform(.09,.13);vs=[(x,y,.036)]
  for k in range(7):
   a=k*math.tau/7+random.uniform(-.18,.18);vs.append((x+rx*random.uniform(.85,1.2)*math.cos(a),y+rr*random.uniform(.85,1.2)*math.sin(a),.035))
  b.mesh(stone,vs,[(0,k+1,(k+1)%7+1) for k in range(7)])
# A craggy vertical skirt built from stratified rings and broken rock faces.
vs=[];fs=[];n=192
for j in range(13):
 z=-j*.42
 for i in range(n):
  a=i*math.tau/n;r=(radius-j*.14)*(1+.035*math.sin(a*11)+.018*math.sin(a*29+j*.35));r=radius+.04 if j==0 else r;vs.append((r*math.cos(a),r*math.sin(a),.025 if j==0 else z+.06*math.sin(a*19+j)))
for j in range(12):
 for i in range(n):a=j*n+i;c=j*n+(i+1)%n;fs.append((a,a+n,c+n,c))
b.mesh(cliff,vs,fs)
for i in range(300):
 a=random.random()*math.tau;z=random.uniform(-4.7,-.25);r=radius+z*.3
 b.ellipsoid(cliff if i%3 else stone,(r*math.cos(a),r*math.sin(a),z),(random.uniform(.25,.60),random.uniform(.22,.52),random.uniform(.13,.43)),9,5)
 if i%3==0:b.ellipsoid(moss,((r+.05)*math.cos(a),(r+.05)*math.sin(a),z+.22),(.25,.19,.035),8,4)
# Stream has an actual gap in the bank geometry.
b.box(water,(0,ry,-.10),(15.4,1.0,.025))
for side in [-1,1]:
 for i in range(78):
  x=-7.6+i*.195
  if abs(x)<1.9:continue
  b.ellipsoid(stone,(x,ry+side*.57,-.025),(random.uniform(.10,.20),.12,.10),9,5)
for i in range(95):
 x=random.uniform(-7.5,7.5);y=ry+random.uniform(-.44,.44);b.tube(foam,[(x,y,-.083),(x+.10,y+.015,-.083)],.003,4)
bridge=layout['bridges'][0]
def deck(y):return bridge['base']+bridge['rise']*math.sin(math.pi*((-y-bridge['z'])/bridge['d']+.5))**2
vs=[];fs=[]
for j in range(81):
 y=ry-2+j*.05;vs.extend([(-1.75,y,deck(y)),(1.75,y,deck(y))])
for j in range(80):fs.append((j*2,j*2+1,j*2+3,j*2+2))
b.mesh(stone,vs,fs)
for side in [-1,1]:
 for j in range(40):
  y=ry-2+(j+.5)*.1;z=deck(y)
  b.box(stone,(side*1.66,y,z+.16),(.18,.096,.32))
 for j in range(21):
  y=ry-2+j*.2;z=deck(y);b.tube(iron,[(side*1.66,y,z+.31),(side*1.66,y,z+.69)],.012,7)
 b.tube(iron,[(side*1.66,ry-2+j*.05,deck(ry-2+j*.05)+.71) for j in range(81)],.025,9)
 # Voussoirs outline a genuine open arch under the bridge.
 for j in range(32):
  a=math.pi*j/31;y=ry+1.95*math.cos(a);z=-.65+.70*math.sin(a)
  b.box(stone,(side*1.62,y,z),(.26,.17,.22))
def lantern(x,y,z):
 b.box(stone,(x,y,z+.22),(.30,.30,.44));b.box(bronze,(x,y,z+.46),(.22,.22,.045));b.box(light,(x,y,z+.61),(.14,.14,.25))
 for dx in [-.10,.10]:
  for dy in [-.10,.10]:b.tube(iron,[(x+dx,y+dy,z+.46),(x+dx,y+dy,z+.77)],.012,6)
 b.mesh(iron,[(x-.15,y-.15,z+.78),(x+.15,y-.15,z+.78),(x+.15,y+.15,z+.78),(x-.15,y+.15,z+.78),(x,y,z+.90)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
for x,y in [(-1.66,ry-1.8),(1.66,ry-1.8),(-1.66,ry+1.8),(1.66,ry+1.8),(-3.7,-3.8),(3.7,-3.8),(-2.5,2),(4.7,1.2)]:lantern(x,y,deck(y) if abs(x)<2 else .035)
# Detailed walk-in conservatory is authored separately, sharing the same world coordinates.
from greenhouse_garden import build as build_garden
garden_objects=build_garden(stone,iron,bronze,glass,wood)
cx,cy=3.0,3.4

def leaf(pos,angle,length,width,mat):
 p=Vector(pos);a=Vector((math.cos(angle),math.sin(angle),.18));q=Vector((-math.sin(angle),math.cos(angle),0));
 v=[p,p+a*length*.45+q*width,p+a*length+Vector((0,0,-.025)),p+a*length*.45-q*width,p+a*length*.5+Vector((0,0,.02))]
 b.mesh(mat,v,[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],True)
def fern(x,y,z,scale=1):
 for k in range(8):
  a=k*math.tau/8;points=[]
  for j in range(8):
   t=j/7;p=Vector((x+math.cos(a)*t*.46*scale,y+math.sin(a)*t*.46*scale,z+math.sin(t*math.pi)*.30*scale));points.append(p)
   if j:
    for side in [-1,1]:leaf(p,a+side*1.0,(1-t*.65)*.14*scale,.026*scale,leaves if k%3 else leaflight)
  b.tube(moss,points,.004*scale,4)
def tree(x,y,h,birch=False):
 # Branch forks and three-dimensional leaf clouds break the planar fern silhouette.
 lean=Vector((random.uniform(-.3,.3),random.uniform(-.3,.3),0))
 trunk=[Vector((x,y,j*h/10))+lean*(j/10)**2 for j in range(11)]
 b.tube(stone if birch else bark,trunk,[.20*(1-j/12) for j in range(11)],10)
 for j in range(26):
  t=random.uniform(.28,.94);a=j*2.4+random.uniform(-.5,.5)
  rad=h*(.25 if birch else .34)*(1-t)**.65*random.uniform(.7,1.15)
  start=Vector((x,y,h*t))+lean*t*t
  end=start+Vector((rad*math.cos(a),rad*math.sin(a),random.uniform(.1,.7)))
  b.tube(bark,[start,start.lerp(end,.55)+Vector((0,0,-.1)),end],[.045,.022,.007],7)
  for k in range(7):
   p=start.lerp(end,random.uniform(.35,1));aa=a+random.uniform(-1.4,1.4)
   tip=p+Vector((random.uniform(.25,.65)*math.cos(aa),random.uniform(.25,.65)*math.sin(aa),random.uniform(-.2,.4)))
   b.tube(bark,[p,tip],[.012,.002],5)
   for q in range(24):
    u=random.random()*math.tau;v=random.uniform(-1,1);rr=random.random()**(1/3)
    pp=tip+Vector((math.cos(u)*math.sqrt(1-v*v)*rr*.34,math.sin(u)*math.sqrt(1-v*v)*rr*.34,v*rr*.24))
    angle=random.random()*math.tau
    leaf(pp,angle,random.uniform(.08,.16),random.uniform(.018,.038),random.choice([leaves,leaflight]) if birch else needles)
for spec in layout['trees']:tree(spec['x'],-spec['z'],spec['h'],spec['birch'])
# Dense undergrowth stays at the edge or inside excluded building/garden beds.
for i in range(110):
 a=random.random()*math.tau;r=random.uniform(6.65,7.5);x=r*math.cos(a);y=r*math.sin(a)
 if abs(y-ry)<.7:continue
 fern(x,y,.035,random.uniform(.6,1.2))
for i in range(4200):
 a=random.random()*math.tau;r=random.uniform(5.8,7.5);x=r*math.cos(a);y=r*math.sin(a)
 if abs(y-ry)<.7:continue
 h=random.uniform(.07,.28);b.mesh(moss,[(x-.009,y,.03),(x+.009,y,.03),(x+.04,y+.02,h)],[(0,1,2)])
 if i%17==0:leaf((x,y,h),random.random()*math.tau,.05,.026,petal)
# Logs, benches, low perimeter masonry and decorative ironwork.
b.tube(bark,[(-4.1,.15,.19),(-2.8,.45,.22)],[.20,.17],16)
for x,y in [(-3.4,.3),(3.7,-4.3)]:
 for dx in [-.7,.7]:b.box(iron,(x+dx,y,.25),(.08,.43,.5))
 for dy in [-.2,-.1,0,.1,.2]:b.box(wood,(x,y+dy,.53),(1.8,.085,.07))
 for z in [.73,.87,1.01]:b.box(wood,(x,y+.24,z),(1.8,.055,.09))
for i in range(150):
 a=i*math.tau/150;x=7.55*math.cos(a);y=7.55*math.sin(a)
 if abs(y-ry)<.8:continue
 b.box(stone,(x,y,.16),(.31,.25,.28),a+math.pi/2)
 if i%5==0:b.box(stone,(x,y,.34),(.28,.28,.45))

stage=b.objects('Mistwood')+garden_objects
# Planar per-face UVs preserve real-world texel density on all textured batches.
for obj in stage:
 if obj.data.materials[0] not in [stone,cliff,bark,soil]:continue
 uv=obj.data.uv_layers.new(name='MaterialUV')
 for poly in obj.data.polygons:
  axis=max(range(3),key=lambda i:abs(poly.normal[i]));axes=[i for i in range(3) if i!=axis]
  for idx in poly.loop_indices:
   p=obj.data.vertices[obj.data.loops[idx].vertex_index].co;uv.data[idx].uv=(p[axes[0]]*.7,p[axes[1]]*.7)
for side in [-1,1]:
 vs=[];fs=[];rows,cols=56,16
 for j in range(rows+1):
  t=j/rows
  for i in range(cols+1):
   u=i/cols;y=ry+(u-.5)*1.03;x=side*(math.sqrt(radius**2-y*y)+.25*math.sin(t*math.pi/2));vs.append((x,y+.04*math.sin(t*9+u*8)*t,-.10-5.8*t*t))
 for j in range(rows):
  for i in range(cols):a=j*(cols+1)+i;fs.append((a,a+1,a+cols+2,a+cols+1))
 fallmat=water.copy();fallmat.name='Waterfall_silver_stream';fallmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.28,.40,.39,1);fallmat.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value=.74;fallmat.surface_render_method='DITHERED';fallmat.diffuse_color=(.28,.40,.39,.74);fallmat.use_backface_culling=False
 bb=Batch();bb.mesh(fallmat,vs,fs,True);o=bb.objects('Mistwood_waterfall')[0];o['waterfall_role']='curtain';uv=o.data.uv_layers.new(name='FlowUV')
 for p in o.data.polygons:
  for idx in p.loop_indices:
   v=o.data.loops[idx].vertex_index;uv.data[idx].uv=(v%(cols+1)/cols,v//(cols+1)/rows)
 stage.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(DEST/'mistwood.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
report={'mesh_batches':len(stage),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in stage),'bytes':(DEST/'mistwood.glb').stat().st_size,'radius':radius,'texture_size':1024,'layout':layout}
(OUT/'stage-report.json').write_text(json.dumps(report,indent=2));print('MISTWOOD_COMPLETE',report)
studio(OUT,(0,0,1.7),(13,-20,13),25,'mistwood-studio',(1600,1200))
scene=bpy.context.scene;scene.camera.location=(9,-10,5);scene.camera.rotation_euler=(Vector((2.1,2,1.4))-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=10;scene.render.filepath=str(OUT/'conservatory-detail.png');bpy.ops.render.render(write_still=True)
