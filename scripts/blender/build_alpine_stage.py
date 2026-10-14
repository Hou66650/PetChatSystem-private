"""Grand alpine lookout: authored mesh batches, shared safe river/bridge dimensions."""
import bpy,math,random,json,re,sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch,material,studio
R=Path(__file__).resolve().parents[2];OUT=R/'art/shepherd-v1';ASSET=R/'static/models/petchat-shepherd-v1'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
layout=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(R/'static/js/den/alpine-layout.js').read_text()).group(1))
bpy.ops.wm.read_factory_settings(use_empty=True);random.seed(7914);b=Batch()
grass=material('Alpine_meadow',(.22,.34,.125));moss=material('Moss_lit',(.35,.43,.18));rock=material('Layered_granite',(.24,.28,.28),.95);lightrock=material('Granite_edges',(.38,.40,.36),.95)
darkrock=material('Cliff_shadows',(.13,.18,.20),.95);wood=material('Aged_cedar',(.25,.105,.043));cutwood=material('Carved_timber',(.44,.25,.105));roof=material('Slate_roof',(.10,.17,.19));pine=material('Pine_needles',(.045,.16,.115));pinebright=material('Pine_tips',(.13,.27,.16));metal=material('Forged_iron',(.08,.10,.10),.4,.65)
brass=material('Lantern_brass',(.55,.32,.08),.35,.65);lamp=material('Warm_glass',(.95,.57,.20),.4,0,1.2);water=material('Silver_jade_water',(.16,.47,.50),.2,.2);foam=material('Water_foam',(.65,.83,.82),.35,0,.04);purple=material('Alpine_lupine',(.35,.20,.55));yellow=material('Buttercup',(.88,.57,.13));cream=material('Daisy_petals',(.89,.86,.66))

# Flat playable terrain; genuine open channel rather than water painted over grass.
radius=layout['radius'];river=layout['water'][0];ry=-river['z'];half=river['d']/2
step=.14;verts=[];faces=[]
for banklo,bankhi in [(-radius,ry-half),(ry+half,radius)]:
    ny=math.ceil((bankhi-banklo)/step)
    for j in range(ny):
        y0=banklo+(bankhi-banklo)*j/ny;y1=banklo+(bankhi-banklo)*(j+1)/ny
        extent=min(math.sqrt(max(0,radius*radius-y0*y0)),math.sqrt(max(0,radius*radius-y1*y1)))
        nx=max(1,math.ceil(extent*2/step))
        for i in range(nx):
            x0=-extent+extent*2*i/nx;x1=-extent+extent*2*(i+1)/nx;k=len(verts)
            verts.extend([(x0,y0,.025),(x1,y0,.025),(x1,y1,.025),(x0,y1,.025)]);faces.append((k,k+1,k+2,k+3))
b.mesh(grass,verts,faces)
vs=[];fs=[];n=128
for layer,(rad,z) in enumerate([(5.6,0),(5.75,-.38),(5.15,-1.0),(4.7,-1.9),(3.55,-2.85),(1.7,-3.65)]):
    for i in range(n):
        a=i*math.tau/n;r=rad*(1+.035*math.sin(a*13)+.025*math.cos(a*7));vs.append((r*math.cos(a),r*math.sin(a),z+.05*math.sin(a*17)))
for j in range(5):
    for i in range(n):a=j*n+i;c=j*n+(i+1)%n;fs.append((a,a+n,c+n,c))
b.mesh(rock,vs,fs)
for i in range(180):
    a=random.random()*math.tau;z=random.uniform(-2.7,-.15);r=5.6+z*.55
    b.ellipsoid(random.choice([rock,lightrock,darkrock]),(r*math.cos(a),r*math.sin(a),z),(random.uniform(.2,.6),random.uniform(.2,.5),random.uniform(.25,.65)),9,5)
# Rear peaks build a monumental silhouette while leaving the playable center open.
for x,y,h in [(-4.4,3.3,1.6),(-3.5,4.8,3.1),(-1.8,5.4,2.0),(.5,5.5,3.4),(3.0,4.8,2.6),(4.5,3.7,1.8)]:
    for k in range(5):
        z=h*k/5;r=(1-k/6)*.85
        b.ellipsoid(rock if k%2 else lightrock,(x+.10*math.sin(k),y,z),(r,r*.8,h*.3),7,4)

# Stream and irregular cobbled shores.
b.box(water,(0,ry,-.105),(10.55,.64,.025))
for side in [-1,1]:
    for i in range(63):
        x=-5.27+i*.17
        if abs(x)<1.48:continue
        b.ellipsoid(lightrock,(x,ry+side*(half+.035),-.005),(.13,.085,.08),10,6)
        if i%3==0:b.ellipsoid(moss,(x,ry+side*(half+.07),.04),(.1,.065,.025),10,5)
for i in range(40):
    x=random.uniform(-5.2,5.2);y=ry+random.uniform(-.25,.25);b.tube(foam,[(x,y,-.082),(x+.16,y+.012,-.082)],.005,5)

# Broad arched deck, stone voussoirs, carved balustrades and rail-mounted lanterns.
bridge=layout['bridges'][0]
def deck(y):return bridge['base']+bridge['rise']*math.sin(math.pi*((-y-bridge['z'])/bridge['d']+.5))**2
deckvs=[];deckfs=[]
for j in range(65):
    y=ry-1.55+j*3.1/64;deckvs.extend([(-1.45,y,deck(y)-.018),(1.45,y,deck(y)-.018)])
for j in range(64):deckfs.append((j*2,j*2+1,j*2+3,j*2+2))
b.mesh(rock,deckvs,deckfs)
for j in range(32):
    y=ry-1.55+(j+.5)*3.1/32;z=deck(y)
    for i in range(9):b.box(lightrock if (i+j)%4 else rock,(-1.45+(i+.5)*2.9/9,y,z-.055),(2.9/9-.008,3.1/32-.005,.10))
for side in [-1,1]:
    for i in range(17):
        y=ry-1.55+i*3.1/16;z=deck(y)
        b.box(rock,(side*1.385,y,z+.25),(.13,.10,.5))
        b.ellipsoid(lightrock,(side*1.385,y,z+.53),(.10,.10,.055),12,6)
    for h in [.12,.40]:b.tube(cutwood,[(side*1.385,ry-1.55+i*3.1/64,deck(ry-1.55+i*3.1/64)+h) for i in range(65)],.035,10)
    for i in range(21):
        a=i*math.pi/20;y=ry+1.5*math.cos(a);z=-.55+.65*math.sin(a)
        b.box(rock,(side*1.28,y,z),(.24,.19,.19))

def lantern(x,y,z):
    b.tube(metal,[(x,y,z),(x,y,z+.7)],.025,10)
    b.box(brass,(x,y,z+.69),(.17,.17,.035));b.box(lamp,(x,y,z+.80),(.12,.12,.19))
    for dx in [-.075,.075]:
        for dy in [-.075,.075]:b.tube(metal,[(x+dx,y+dy,z+.69),(x+dx,y+dy,z+.92)],.009,6)
    b.mesh(roof,[(x-.12,y-.12,z+.93),(x+.12,y-.12,z+.93),(x+.12,y+.12,z+.93),(x-.12,y+.12,z+.93),(x,y,z+1.04)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
for x,y in [(-1.385,ry-1.45),(1.385,ry-1.45),(-1.385,ry+1.45),(1.385,ry+1.45),(-2.3,1.55),(3.2,.4),(-3.9,-3.1),(3.9,-3.1)]:lantern(x,y,deck(y) if abs(x)<1.5 else .035)

# Alpine lodge with real timber framing, inset windows, tiled pitched roof and chimney.
x,y=1.7,2.9
b.box(rock,(x,y,.20),(2.8,2.2,.4));b.box(wood,(x,y,.98),(2.65,2.05,1.55))
for z in [.3,.55,.8,1.05,1.30,1.55,1.75]:
    b.box(cutwood,(x,y-1.04,z),(2.8,.07,.055));b.box(cutwood,(x+1.35,y,z),(.07,2.15,.055))
for dx in [-1.3,0,1.3]:b.box(cutwood,(x+dx,y-1.09,1),(.13,.13,1.8))
for dx in [-.83,.83]:
    b.box(darkrock,(x+dx,y-1.08,1.03),(.66,.04,.73));b.box(lamp,(x+dx,y-1.105,1.03),(.51,.025,.58))
    for zz in [.72,1.03,1.34]:b.box(cutwood,(x+dx,y-1.13,zz),(.65,.06,.045))
    for xx in [-.29,0,.29]:b.box(cutwood,(x+dx+xx,y-1.13,1.03),(.045,.06,.67))
    b.box(cutwood,(x+dx,y-1.2,.65),(.8,.25,.12))
b.box(darkrock,(x,y-1.12,.75),(.45,.06,1.25))
for dx in [-.16,-.08,0,.08,.16]:b.box(wood,(x+dx,y-1.16,.74),(.073,.04,1.18))
b.ellipsoid(brass,(x+.12,y-1.20,.74),(.025,.02,.025),12,8)
for side in [-1,1]:
    b.mesh(wood,[(x,y-1.03,2.55),(x+side*1.35,y-1.03,1.76),(x,y-1.03,1.76)],[(0,1,2)])
    for row in range(12):
        t0=row/12;t1=(row+1)/12
        for col in range(16):
            ya=y-1.3+col*2.6/16;yb=ya+2.6/16-.008;xa=x+side*1.55*t0;xb=x+side*1.55*t1
            za=2.65-.86*t0+.025;zb=2.65-.86*t1+.025
            b.mesh(roof if (row+col)%4 else darkrock,[(xa,ya,za),(xb,ya,zb),(xb,yb,zb),(xa,yb,za)],[(0,1,2,3)])
    b.tube(cutwood,[(x,y-1.33,2.68),(x+side*1.60,y-1.33,1.78)],.065,10)
b.tube(cutwood,[(x,y-1.35,2.68),(x,y+1.35,2.68)],.065,10)
for z in [1.8,2,2.2,2.4,2.6,2.8]:
    for dx in [-.10,.10]:b.box(lightrock,(x+.8+dx,y+.55,z),(.19,.4,.19))
b.box(rock,(x+.8,y+.55,2.95),(.55,.55,.12))

# Stone lookout tower with a timber viewing gallery, cross braces and spire.
x,y=-1.4,3.6
for row in range(14):
    z=.12+row*.20
    for i in range(16):
        a=(i+(row%2)*.5)*math.tau/16
        b.box(lightrock if (i+row)%5 else rock,(x+.62*math.cos(a),y+.62*math.sin(a),z),(.25,.18,.19),a+math.pi/2)
b.box(wood,(x,y,2.95),(1.65,1.65,.14))
for dx in [-.72,.72]:
    for dy in [-.72,.72]:b.tube(cutwood,[(x+dx,y+dy,2.9),(x+dx,y+dy,4.0)],.065,10)
for side in [-1,1]:
    for t in range(7):
        xx=x-.72+t*1.44/6;b.tube(cutwood,[(xx,y+side*.72,3.02),(xx,y+side*.72,3.50)],.027,8)
        yy=y-.72+t*1.44/6;b.tube(cutwood,[(x+side*.72,yy,3.02),(x+side*.72,yy,3.50)],.027,8)
    b.tube(cutwood,[(x-.82,y+side*.72,3.5),(x+.82,y+side*.72,3.5)],.04,8)
    b.tube(cutwood,[(x+side*.72,y-.82,3.5),(x+side*.72,y+.82,3.5)],.04,8)
b.mesh(roof,[(x-1,y-1,3.93),(x+1,y-1,3.93),(x+1,y+1,3.93),(x-1,y+1,3.93),(x,y,4.82)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
b.tube(brass,[(x,y,4.8),(x,y,5.1)],.025,10);b.ellipsoid(lamp,(x,y,3.65),(.13,.13,.22),16,10)

# Branched pines, many needle clusters rather than stacked cone primitives.
def tree(x,y,h):
    b.tube(wood,[(x,y,.02),(x+.04,y,h)],[.09,.018],10)
    for tier in range(7):
        z=.45+tier*(h-.6)/7;rad=(1-tier/8)*h*.25
        for branch in range(7):
            a=branch*math.tau/7+tier*.8;end=(x+rad*math.cos(a),y+rad*math.sin(a),z-.14)
            b.tube(wood,[(x,y,z+.10),end],[.018,.004],6)
            for k in [.45,.8,1]:
                px=x+rad*k*math.cos(a);py=y+rad*k*math.sin(a)
                b.ellipsoid(pine if (tier+branch)%3 else pinebright,(px,py,z+.10*(1-k)),(rad*.35,rad*.35,.22),8,5)
for i in range(26):
    a=random.uniform(.03,math.pi-.03);r=random.uniform(4.6,5.35);tree(r*math.cos(a),r*math.sin(a),random.uniform(1.5,3.2))
for x,y in [(-4.3,1.8),(-3.8,-.2),(4.5,1.5),(4.2,-.25)]:tree(x,y,2.1)

# Safe edge timber fence, with gaps only at the river spillways.
for i in range(92):
    a=i*math.tau/92;x=5.38*math.cos(a);y=5.38*math.sin(a)
    if abs(y-ry)<.60:continue
    b.box(cutwood,(x,y,.29),(.09,.09,.54),a)
    a2=a+math.tau/92;x2=5.38*math.cos(a2);y2=5.38*math.sin(a2)
    if abs(y2-ry)<.60:continue
    for z in [.20,.43]:b.tube(wood,[(x,y,z),(x2,y2,z)],.028,8)

# Border vegetation concentrates detail at the sides, leaving the running area readable.
for i in range(1800):
    a=random.random()*math.tau;r=random.uniform(4.55,5.25);x=r*math.cos(a);y=r*math.sin(a)
    if abs(y-ry)<.60:continue
    h=random.uniform(.04,.18)
    b.mesh(moss,[(x-.014,y,.03),(x+.014,y,.03),(x+.025,y+.01,h)],[(0,1,2)])
    if i%7==0:
        b.tube(pinebright,[(x,y,.03),(x,y,h+.08)],.006,5)
        for k in range(5):
            ang=k*math.tau/5;b.ellipsoid(purple if i%3 else cream,(x+.027*math.cos(ang),y+.027*math.sin(ang),h+.08),(.024,.024,.009),8,5)
        b.ellipsoid(yellow,(x,y,h+.09),(.012,.012,.01),8,5)
# Crafted trail sign near tower, picnic resting spot and paving toward the lodge.
b.tube(wood,[(-2.8,2,.02),(-2.8,2,1.2)],.055,10)
for j in range(3):b.box(cutwood,(-2.8+(.05 if j%2 else -.05),2,1.08-j*.2),(.65,.09,.13),.08*(-1)**j)
for x,y in [(-3.3,1.1),(3.8,.9)]:
    for dx in [-.38,.38]:b.box(wood,(x+dx,y,.21),(.09,.38,.42))
    for dy in [-.16,0,.16]:b.box(cutwood,(x,y+dy,.44),(1,.13,.06))
for i in range(14):
    t=i/13;b.ellipsoid(lightrock,(.55+1.15*t,.25+1.45*t,.037),(.20,.14,.025),10,5)
stage=b.objects('Alpine')

# UV-equipped waterfall curtains join the real river lips; animated by the shared shader.
for side in [-1,1]:
    vs=[];fs=[];n=36;cols=12
    for j in range(n+1):
        t=j/n
        for i in range(cols+1):
            u=i/cols;y=ry+(u-.5)*.67
            x=side*(math.sqrt(radius*radius-y*y)+.23*math.sin(t*math.pi/2))
            vs.append((x,y+.035*math.sin(t*7+u*8)*t,-.10-3.8*t*t))
    for j in range(n):
        for i in range(cols):a=j*(cols+1)+i;fs.append((a,a+1,a+cols+2,a+cols+1))
    fall=Batch();fall.mesh(water,vs,fs,True);o=fall.objects('Alpine_waterfall')[0];o.data.materials[0]=water.copy();o['waterfall_role']='curtain'
    uv=o.data.uv_layers.new(name='FlowUV')
    for p in o.data.polygons:
        for idx in p.loop_indices:
            v=o.data.loops[idx].vertex_index;uv.data[idx].uv=(v%(cols+1)/cols,v//(cols+1)/n)
    stage.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'alpine.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
report={'mesh_batches':len(stage),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in stage),'bytes':(ASSET/'alpine.glb').stat().st_size,'radius':radius,'layout':layout}
(OUT/'stage-report.json').write_text(json.dumps(report,indent=2));print('ALPINE_COMPLETE',report)
studio(OUT,(0,0,.35),(9,-15,10),15.0,'alpine-studio',(1500,1200))
