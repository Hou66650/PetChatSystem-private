"""Blender-only, deterministic grand sakura archipelago art master.

Never changes the web scene or account data. Units: metres, Z-up.
blender -b --python-exit-code 1 --python this.py -- --preview
Use --render-only to reuse the saved master; --no-render for geometry only.
"""
import bpy, bmesh, math, random, json, hashlib, sys, argparse, time
import numpy as np
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/sakura-cinematic-v2';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path('D:/PetChatSystem/art/cinematic-islands-v1/sakura/island-master.blend')
MASTER=OUT/'sakura-archipelago.blend'
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch, material
from cinematic_island_tools import collection, move, finish, principled, lathe, micro, snow_lobe, leaf, lighting
parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');parser.add_argument('--render-only',action='store_true');parser.add_argument('--no-render',action='store_true');parser.add_argument('--shot',default='all');args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SEED=271017;random.seed(SEED)
stats={'newBlossoms':0,'newBranches':0,'roofTilePieces':0,'newGrassBlades':0,'newIslands':0,'lanterns':0}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lin(c):return tuple(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c)
def surface(name,low,high,scale=6,stretch=(1,1,1),rough=.8,relief=.004):
    m=material(name,lin(low),rough);nt=m.node_tree;p=principled(m)
    co=nt.nodes.new('ShaderNodeTexCoord');mul=nt.nodes.new('ShaderNodeVectorMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=stretch
    noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=5
    ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(*lin(low),1);ramp.color_ramp.elements[1].color=(*lin(high),1)
    nt.links.new(co.outputs['Object'],mul.inputs[0]);nt.links.new(mul.outputs[0],noise.inputs['Vector']);nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=relief;bump.inputs['Strength'].default_value=.5;nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs[0],p.inputs['Normal'])
    micro(m,scale*30,relief*.12);return m
def look(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
def disk(b,m,p,r,h,n=64):lathe(b,m,p,[(0,0),(r,0),(r,h),(0,h)],n)

def refine_atmosphere():
    scene=bpy.context.scene
    if scene.get('atmosphere_revision')==2:return
    for o in scene.objects:
        if o.type=='MESH' and o.name.startswith('Far geological ridges'):
            layer=int(o.data.materials[0].name.rsplit(' ',1)[1])
            for vert in o.data.vertices:
                x,y,z=vert.co
                rough=(2.2*math.sin(x*.27+y*.16)+1.1*math.sin(x*.61-y*.33)+.45*math.sin(x*1.37+y*.91))*max(0,min(1,(z+18)/15))
                vert.co.z=z*.52-24-layer*5+rough
            m=o.data.materials[0];p=principled(m);col=(.015+layer*.009,.038+layer*.012,.045+layer*.015)
            p.inputs['Base Color'].default_value=(*col,1);p.inputs['Emission Color'].default_value=(*col,1);p.inputs['Emission Strength'].default_value=.5
    for node in scene.world.node_tree.nodes:
        if node.type=='VALTORGB':
            node.color_ramp.elements[0].color=(.065,.13,.16,1);node.color_ramp.elements[-1].color=(.025,.065,.10,1)
    far=bpy.data.materials.new('Distant atmospheric depth');far.use_nodes=True;n=far.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');v=n.new('ShaderNodeVolumePrincipled');v.inputs['Density'].default_value=.0035;v.inputs['Color'].default_value=(.38,.55,.62,1);v.inputs['Anisotropy'].default_value=.15;far.node_tree.links.new(v.outputs[0],out.inputs['Volume'])
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,120,-2));o=bpy.context.object;o.name='Far atmospheric depth volume';o.scale=(350,160,150);o.data.materials.append(far)
    move(o,bpy.data.collections['V2 90 Distant mountains and layered mist - presentation only'])
    scene['atmosphere_revision']=2

def build():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene
    for o in list(scene.objects):
        if o.type in ['LIGHT','CAMERA'] or o.name in ['Cloud sea','Plan paper']:bpy.data.objects.remove(o,do_unlink=True)
        else:o.location.y-=8
    # Open the original back fence where the new ascent begins, preserving the gate.
    for o in list(scene.objects):
        if o.type=='MESH' and o.name in ['sakura_Aged_oiled_timber','sakura_Exposed_end_grain']:
            bm=bmesh.new();bm.from_mesh(o.data)
            blocked=[]
            for f in bm.faces:
                p=o.matrix_world@f.calc_center_median()
                if abs(p.x)<1.3 and p.y>-2.4 and p.z<1.35:blocked.append(f)
            bmesh.ops.delete(bm,geom=blocked,context='FACES');bm.to_mesh(o.data);bm.free()
    # The first courtyard remains a lived-in, human-scale arrival, not a scaled toy.
    rock=surface('V2 stratified basalt',( .18,.21,.21),(.46,.46,.40),3,(1,1,5),.9,.045)
    stone=surface('V2 warm cut granite',(.28,.29,.26),(.58,.56,.48),10,rough=.86,relief=.007)
    wood=surface('V2 aged chestnut timber',(.13,.065,.037),(.37,.21,.11),4,(28,.7,5),.69,.002)
    red=surface('V2 weathered cinnabar',(.23,.055,.043),(.48,.15,.095),5,(24,.7,4),.65,.001)
    slate=surface('V2 ink glazed roof',(.055,.085,.09),(.17,.23,.22),11,rough=.39,relief=.001)
    bark=surface('V2 cherry bark fissures',(.10,.068,.052),(.29,.22,.16),7,(4,4,.5),.94,.021)
    soil=surface('V2 mossy fertile ground',(.073,.11,.052),(.25,.30,.12),4,rough=.97,relief=.014)
    brass=surface('V2 patinated brass',(.20,.13,.035),(.57,.39,.13),17,rough=.38,relief=.0005);principled(brass).inputs['Metallic'].default_value=.76
    leaves=[material('V2 living moss '+str(i),lin(c),.83) for i,c in enumerate([(.12,.24,.10),(.19,.31,.13),(.31,.39,.18),(.40,.43,.22)])]
    petals=[material('V2 petal '+str(i),lin(c),.52) for i,c in enumerate([(.84,.32,.46),(.96,.57,.66),(.99,.77,.77),(.73,.20,.38)])]
    for m in petals:principled(m).inputs['Subsurface Weight'].default_value=.12;principled(m).inputs['Subsurface Radius'].default_value=(.004,.001,.002)
    centre=material('V2 flower calyx',lin((.42,.12,.19)),.7);pollen=material('V2 honey anthers',lin((.95,.66,.24)),.6)
    ceramic=surface('V2 celadon ceramic',(.08,.22,.18),(.25,.39,.30),18,rough=.25,relief=.0004)
    fabric=surface('V2 muted olive woven cushions',(.16,.20,.11),(.33,.37,.23),90,rough=.94,relief=.0005)
    glow=material('V2 amber lantern silk',(.9,.40,.09),.6,glow=2.8)
    water=material('V2 deep jade pool',(.012,.11,.095),.16);principled(water).inputs['Transmission Weight'].default_value=.6;principled(water).inputs['IOR'].default_value=1.333;micro(water,13,.013)
    falling=material('V2 falling water veil',(.20,.43,.39),.15);principled(falling).inputs['Transmission Weight'].default_value=.78;principled(falling).inputs['IOR'].default_value=1.333;micro(falling,30,.006)
    spray=material('V2 waterfall silver aeration',(.45,.65,.60),.32);principled(spray).inputs['Transmission Weight'].default_value=.32
    # Real repository rock albedo, box projected at a metric scale, with independent
    # geological fissures and small pores; not a flat-colour noise-only cliff.
    rock_image=bpy.data.images.load(str(ROOT/'art/mistwood-v1/limestone-albedo.png'),check_existing=True);rock_image.pack()
    for mat,tint,amount in [(rock,(.43,.49,.43),.026),(stone,(.70,.69,.61),.011)]:
        nt=mat.node_tree;p=principled(mat);co=nt.nodes.new('ShaderNodeTexCoord');mapping=nt.nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs[3].default_value=.32
        image=nt.nodes.new('ShaderNodeTexImage');image.image=rock_image;image.projection='BOX';image.projection_blend=.27
        nt.links.new(co.outputs['Object'],mapping.inputs[0]);nt.links.new(mapping.outputs[0],image.inputs['Vector'])
        tintnode=nt.nodes.new('ShaderNodeMixRGB');tintnode.blend_type='MULTIPLY';tintnode.inputs[0].default_value=1;tintnode.inputs[2].default_value=(*tint,1);nt.links.new(image.outputs['Color'],tintnode.inputs[1]);nt.links.new(tintnode.outputs[0],p.inputs['Base Color'])
        fine=nt.nodes.new('ShaderNodeBump');fine.inputs['Distance'].default_value=amount;fine.inputs['Strength'].default_value=.65;nt.links.new(image.outputs['Color'],fine.inputs['Height']);nt.links.new(fine.outputs[0],p.inputs['Normal'])
        vor=nt.nodes.new('ShaderNodeTexVoronoi');vor.feature='DISTANCE_TO_EDGE';vor.inputs['Scale'].default_value=2.6;nt.links.new(co.outputs['Object'],vor.inputs['Vector'])
        cracks=nt.nodes.new('ShaderNodeValToRGB');cracks.color_ramp.elements[0].position=.005;cracks.color_ramp.elements[0].color=(0,0,0,1);cracks.color_ramp.elements[1].position=.035;nt.links.new(vor.outputs['Distance'],cracks.inputs[0])
        b=nt.nodes.new('ShaderNodeBump');b.inputs['Distance'].default_value=.015 if mat==rock else .003;b.inputs['Strength'].default_value=.42;nt.links.new(cracks.outputs[0],b.inputs['Height']);nt.links.new(fine.outputs[0],b.inputs['Normal']);nt.links.new(b.outputs[0],p.inputs['Normal'])
    replacements={'Aged_oiled_timber':wood,'Exposed_end_grain':wood,'Fine aged oak':wood,'Timber_fine_grain':wood,'Weathered_slate':slate,'Split slate tiles':slate}
    for o in scene.objects:
        if o.type=='MESH':
            for slot in o.material_slots:
                if slot.material and slot.material.name in replacements:slot.material=replacements[slot.material.name]
    land=collection('V2 01 Terraces and geological structure');arch=collection('V2 02 Crafted architecture');bot=collection('V2 03 Root branch blossom ecology');wet=collection('V2 04 Water and waterfalls');props=collection('V2 05 Companion life and wayfinding')
    terrain=Batch();architecture=Batch();plants=Batch();waterb=Batch();details=Batch()

    def island(cx,cy,z,rx,ry,depth,seed):
        stats['newIslands']+=1;N=192;R=12
        def radius(a):return 1+.035*math.sin(a*5+seed)+.022*math.cos(a*9+seed*3)
        vs=[(cx,cy,z)]
        for j in range(1,R+1):
            r=j/R
            for k in range(N):
                a=k*math.tau/N;rr=r*radius(a);vs.append((cx+rx*rr*math.cos(a),cy+ry*rr*math.sin(a),z+.025*math.sin(a*7)*r))
        fs=[(0,1+k,1+(k+1)%N) for k in range(N)]
        for j in range(R-1):
            for k in range(N):a=1+j*N+k;b=1+j*N+(k+1)%N;fs.append((a,b,b+N,a+N))
        terrain.mesh(soil,vs,fs,True)
        # Fractured shelves, with an eroded inward taper; no spherical pebble wall.
        vs=[];rings=32
        for j in range(rings):
            t=j/(rings-1);rr=(1-.80*t**1.4)*(1+.016*math.sin(j*1.8));zz=z-depth*t
            for k in range(N):
                a=k*math.tau/N;f=radius(a) if j==0 else radius(a)+.012*math.sin(k*.9+j*.7)+.025*math.sin(a*17+j*.11)
                vz=z+.025*math.sin(a*7) if j==0 else zz+.11*math.sin(k*.8+j*2.1)
                vs.append((cx+rx*rr*f*math.cos(a),cy+ry*rr*f*math.sin(a),vz))
        terrain.mesh(rock,vs,[(j*N+k,j*N+(k+1)%N,(j+1)*N+(k+1)%N,(j+1)*N+k) for j in range(rings-1) for k in range(N)])
        # Edge retaining stones each have distinct dimensions and deliberate seams.
        for k in range(94):
            a=k*math.tau/94;rr=radius(a);architecture.box(stone,(cx+rx*.97*rr*math.cos(a),cy+ry*.97*rr*math.sin(a),z+.085),(random.uniform(.43,.62),.29,.20),a+math.pi/2)
    island(-4,10,2.8,8.7,7.4,11,4)
    island(8,22,5.5,4.6,4.3,7,7)
    island(-17,18,4,3.3,3.6,6,9)

    def path(points,width=1.65):
        for start,end in zip(points[:-1],points[1:]):
            a,b=Vector(start),Vector(end);dist=(b-a).length;steps=max(1,int(dist/.4));yaw=math.atan2(b.y-a.y,b.x-a.x)
            for i in range(steps):
                p=a.lerp(b,(i+.5)/steps)
                for k in range(3):
                    q=p+Vector((-math.sin(yaw),math.cos(yaw),0))*(k-1)*width/3
                    architecture.box(stone,q+Vector((0,0,.035)),(dist/steps*.96,width/3*.94,.07),yaw)
    path([(0,-3.1,.05),(0,-1.9,.05)])
    path([(-1,3.5,2.8),(-2,6,2.8),(-3,9,2.8),(-4,11,2.8)],2.0)
    path([(-3,9,2.8),(0,10.5,2.8),(2,12,2.8)],1.7)
    path([(-3,9,2.8),(-8,8,2.8),(-10.5,10.5,2.8)],1.4)
    path([(6,19,5.5),(8,22,5.5),(9,23.5,5.5)],1.5)

    def rail(points,width,mat=wood):
        a,b=Vector(points[0]),Vector(points[-1]);side=Vector((-(b-a).y,(b-a).x,0)).normalized()
        n=max(3,int((b-a).length/.8))
        for sign in [-1,1]:
            pts=[]
            for j in range(n+1):
                t=j/n;p=a.lerp(b,t)+side*sign*width/2;pts.append(p)
                architecture.box(mat,p+Vector((0,0,.48)),(.105,.105,.96))
                details.ellipsoid(brass,p+Vector((0,0,.98)),(.075,.075,.043),12,6)
                for h in [.31,.80]:
                    if j:architecture.tube(mat,[pts[j-1]+Vector((0,0,h)),p+Vector((0,0,h))],.042,10)
            architecture.tube(mat,[p+Vector((0,0,.97)) for p in pts],.055,12)

    def bridge(a,b,width,stair=False):
        a,b=Vector(a),Vector(b);v=b-a;yaw=math.atan2(v.y,v.x);side=Vector((-v.y,v.x,0)).normalized();n=int(v.length/(.28 if stair else .20))
        for i in range(n):
            t=(i+.5)/n;p=a.lerp(b,t);p.z+=0 if stair else .30*math.sin(math.pi*t)
            architecture.box(wood,p,(v.xy.length/n*.98,width,.16),yaw)
            for s in [-1,1]:
                details.ellipsoid(brass,p+side*s*(width/2-.12)+Vector((0,0,.09)),(.013,.013,.006),8,4)
        rail([a,b],width)
        for s in [-1,1]:
            pts=[a.lerp(b,j/24)+side*s*width*.39+Vector((0,0,-.30+.30*math.sin(math.pi*j/24))) for j in range(25)]
            architecture.tube(red,pts,.14,12)
        # Stone abutments support timber, leaving the ravine open below.
        for p in [a,b]:architecture.box(stone,p+Vector((0,0,-.4)),(width+.5,.7,.65),yaw+math.pi/2)
    bridge((0,-2,.15),(-1,3.5,2.85),2.2,True)
    bridge((2.5,15,2.85),(6,19,5.55),1.8,True)
    bridge((-11,12,2.85),(-15,16,4.05),1.45,True)

    def lantern(x,y,z,small=False):
        stats['lanterns']+=1;sc=.7 if small else 1
        architecture.box(stone,(x,y,z+.09*sc),(.58*sc,.58*sc,.18*sc))
        architecture.box(stone,(x,y,z+.47*sc),(.23*sc,.23*sc,.62*sc))
        architecture.box(stone,(x,y,z+.84*sc),(.57*sc,.57*sc,.13*sc))
        architecture.box(glow,(x,y,z+1.03*sc),(.24*sc,.24*sc,.28*sc))
        for sx in [-1,1]:
            for sy in [-1,1]:architecture.box(stone,(x+sx*.20*sc,y+sy*.20*sc,z+1.04*sc),(.065*sc,.065*sc,.33*sc))
        # Pitched stone cap with actual eaves.
        vv=[(x+sx*.39*sc,y+sy*.39*sc,z+1.23*sc) for sx,sy in [(-1,-1),(1,-1),(1,1),(-1,1)]]+[(x,y,z+1.48*sc)]
        architecture.mesh(stone,vv,[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(3,2,1,0)])
    for x,y,z in [(-1.6,-1,.1),(1,-1,.1),(-2.3,4,2.8),(.4,4,2.8),(-5,8,2.8),(-.5,9,2.8),(-8.8,8,2.8),(-10,11.5,2.8),(5,20,5.5),(9,22,5.5),(-16,17,4)]:lantern(x,y,z)

    def gate(cx,cy,z,w=3.7,h=3.2):
        for s in [-1,1]:
            x=cx+s*w*.38;disk(architecture,stone,(x,cy,z),.30,.25)
            architecture.tube(red,[(x,cy,z+.2),(x+s*.06,cy,z+h)],[.15,.12],16)
            architecture.box(wood,(x,cy,z+h-.6),(.35,.36,.16))
        architecture.box(red,(cx,cy,z+h-.45),(w,.17,.20))
        pts=[(cx+w*(j/24-.5),cy,z+h+.18*((j/12-1)**2)) for j in range(25)]
        architecture.tube(wood,pts,.16,16)
        architecture.box(brass,(cx,cy-.11,z+h-.32),(.28,.035,.38))
    gate(-1,4.7,2.8);gate(7.5,22.4,5.5,2.8,2.7)

    def roof(cx,cy,z,w,d):
        # Individually curved overlapping ceramic tiles; gable roof, front ridge ornaments.
        for sign in [-1,1]:
            for j in range(int(d/.17)+1):
                y=cy-d/2+j*.17
                for row in range(12):
                    t0=row/12;t1=(row+1.12)/12
                    vs=[]
                    for q in range(4):
                        t=t0+(t1-t0)*q/3;x=cx+sign*w/2*t;zz=z-1.35*t+.32*t**5
                        for k in range(5):
                            u=k/4;vs.append((x,y+(u-.5)*.18,zz+.018*math.sin(u*math.pi)))
                    architecture.mesh(slate,vs,[(q*5+k,q*5+k+1,(q+1)*5+k+1,(q+1)*5+k) for q in range(3) for k in range(4)],True);stats['roofTilePieces']+=1
            for y in [cy-d/2,cy+d/2]:
                pts=[(cx+sign*w/2*j/20,y,z-1.35*j/20+.32*(j/20)**5-.05) for j in range(21)]
                architecture.tube(wood,pts,.085,10)
            for j in range(int(d/.26)+1):
                y=cy-d/2+j*.26
                architecture.tube(wood,[(cx+sign*w*.50*q/16,y,z-1.35*q/16+.32*(q/16)**5-.10) for q in range(17)],.038,10)
        architecture.tube(slate,[(cx,cy-d/2-.05,z+.08),(cx,cy+d/2+.05,z+.08)],.13,16)
        for sign in [-1,1]:
            architecture.tube(brass,[(cx,cy+sign*d/2,z+.1),(cx,cy+sign*(d/2+.16),z+.24),(cx,cy+sign*(d/2+.21),z+.42)],[.065,.05,.005],12)

    def pavilion(cx,cy,z,w=4.2,d=3.9):
        # Sill foundation, visible floorboard seams, two levels of bracket sets.
        architecture.box(stone,(cx,cy,z+.20),(w+.50,d+.5,.40))
        for j in range(int(w/.15)):architecture.box(wood,(cx-w/2+(j+.5)*.15,cy,z+.46),(.143,d,.12))
        for i in range(4):architecture.box(stone,(cx,cy-d/2-.30-i*.27,z+.40-i*.10),(1.7,.28,.18))
        for x in [cx-w/2+.17,cx+w/2-.17]:
            for y in [cy-d/2+.17,cy+d/2-.17]:
                disk(architecture,stone,(x,y,z+.45),.21,.14)
                architecture.box(red,(x,y,z+1.90),(.19,.19,2.75))
                for j in range(4):
                    architecture.box(wood,(x,y,z+2.80+j*.10),(.36+j*.15,.28,.085))
                    architecture.box(wood,(x,y,z+2.83+j*.10),(.25,.35+j*.16,.08))
                for h in [.70,2.90]:details.box(brass,(x,y-.105,z+h),(.20,.018,.07))
        for h in [z+.67,z+3.25]:
            for sy in [-1,1]:architecture.box(wood,(cx,cy+sy*(d/2-.17),h),(w,.16,.17))
            for sx in [-1,1]:architecture.box(wood,(cx+sx*(w/2-.17),cy,h),(.16,d,.17))
        for sx in [-1,1]:
            x=cx+sx*(w/2-.17)
            for j in range(19):architecture.box(wood,(x,cy-d/2+.2+j*(d-.4)/18,z+1.63),(.038,.035,1.65))
            for h in [1.02,1.43,1.84,2.25]:architecture.box(wood,(x,cy,z+h),(.04,d-.35,.04))
        roof(cx,cy,z+4.4,w+1.3,d+1.25)
        # Open front and rear give pet passage, no opaque wall across the walking line.
        details.box(wood,(cx,cy,z+.95),(1.6,.86,.10))
        for sx in [-1,1]:
            for sy in [-1,1]:details.box(wood,(cx+sx*.63,cy+sy*.29,z+.70),(.075,.075,.48))
        for sx in [-1,1]:snow_lobe(details,fabric,(cx+sx*1.15,cy,z+.58),(.30,.40,.085),sx)
        lathe(details,ceramic,(cx,cy,z+1.01),[(0,0),(.11,0),(.15,.14),(.10,.22),(.06,.24),(0,.24)],48)
        for x in [cx-.4,cx+.4]:lathe(details,ceramic,(x,cy-.14,z+1.01),[(0,0),(.06,0),(.075,.08),(.07,.085),(.058,.02),(0,.02)],32)
        for sx in [-1,1]:
            x=cx+sx*1.5;y=cy-d/2+.2
            architecture.tube(brass,[(x,y,z+3.22),(x,y,z+2.93)],.009,8)
            lathe(details,glow,(x,y,z+2.54),[(.08,0),(.16,.06),(.18,.22),(.13,.36),(.06,.39)],32)
            for k in range(10):
                a=k*math.tau/10;details.tube(wood,[(x+.16*math.cos(a),y+.16*math.sin(a),z+2.61),(x+.18*math.cos(a),y+.18*math.sin(a),z+2.75),(x+.13*math.cos(a),y+.13*math.sin(a),z+2.9)],.006,6)
    pavilion(1,12.0,2.8)

    def flower(p,size,normal,attachment=None,detailed=False):
        stats['newBlossoms']+=1;n=Vector(normal).normalized();u=n.cross(Vector((.12,.23,1))).normalized();v=n.cross(u);spin=random.random()*math.tau
        if attachment is not None:
            plants.tube(centre,[Vector(attachment),p-n*size*.09,p],[size*.022,size*.018,size*.015],5)
        for k in range(5):
            a=spin+k*math.tau/5;axis=u*math.cos(a)+v*math.sin(a);side=n.cross(axis);vs=[]
            for j in range(5):
                t=j/4;w=size*.40*math.sin(math.pi*t*.96)**.65
                for q in [-1,0,1]:
                    axial=t-(.10 if j==4 and q==0 else 0)
                    vs.append(p+axis*(size*axial)+side*(q*w)+n*(size*(.35*t*t-.06*math.sin(t*math.pi))+(abs(q)*.10*size*math.sin(math.pi*t))))
            plants.mesh(random.choices(petals,[2,5,3,.3])[0],vs,[(j*3+q,j*3+q+3,j*3+q+4,j*3+q+1) for j in range(4) for q in range(2)],True)
        heart=[p+n*size*.11]+[p+(u*math.cos(j*math.tau/10)+v*math.sin(j*math.tau/10))*size*.19+n*size*.07 for j in range(10)]
        plants.mesh(centre,heart,[(0,j+1,(j+1)%10+1) for j in range(10)],True)
        count=12 if detailed else 6
        for j in range(count):
            a=j*math.tau/count;tip=p+n*size*.40+(u*math.cos(a)+v*math.sin(a))*size*.20
            plants.tube(pollen,[p+n*size*.09,tip],[size*.012,size*.023],4)
            if detailed:plants.ellipsoid(pollen,tip,(size*.035,size*.026,size*.035),8,4)

    def cherry(base,h,spread,seed,hero=False):
        rng=random.Random(seed);base=Vector(base);tr=[base+Vector((math.sin(t*3.9)*h*.055,math.sin(t*2.1)*h*.045,h*t)) for t in [0,.13,.3,.48,.60,.69,.77]]
        plants.tube(bark,tr,[h*x for x in [.062,.052,.040,.032,.023,.014,.003]],24 if hero else 14)
        for i in range(12):
            a=i*math.tau/12;rr=h*.18*rng.uniform(.7,1.2);end=base+Vector((math.cos(a)*rr,math.sin(a)*rr,.03))
            plants.tube(bark,[base+Vector((0,0,h*.12)),base+Vector((math.cos(a)*rr*.35,math.sin(a)*rr*.35,.13)),end],[h*.022,h*.014,.008],12)
        tips=[]
        # A true hierarchy: fewer structural limbs, then curved secondaries growing
        # from those limbs. Never connect a crown full of straight poles to one point.
        for i in range(16 if hero else 12):
            a=i*2.399+seed;r=spread*rng.uniform(.32,1)
            z=h*(.52+.42*(1-r/spread))+rng.uniform(-.2,.4)
            end=base+Vector((math.cos(a)*r,math.sin(a)*r,z))
            start=tr[2+i%3].lerp(tr[3+i%3],rng.uniform(.05,.55))
            sideways=Vector((-math.sin(a),math.cos(a),0))*rng.uniform(-.35,.35)
            pts=[start.lerp(end,j/10)+sideways*math.sin(math.pi*j/10)+Vector((0,0,-h*.06*math.sin(math.pi*j/10))) for j in range(11)]
            plants.tube(bark,pts,[h*.018*(1-j/11)**1.5+.003 for j in range(11)],16);stats['newBranches']+=1
            for k in range(10 if hero else 7):
                anchor=pts[4+k%6];aa=a+rng.uniform(-1.0,1.0);r2=spread*rng.uniform(.10,.22)
                tip=anchor+Vector((math.cos(aa)*r2,math.sin(aa)*r2,rng.uniform(.20,.70)*h/7))
                bend=Vector((-math.sin(aa),math.cos(aa),0))*rng.uniform(-.18,.18)
                tpts=[anchor.lerp(tip,j/6)+bend*math.sin(math.pi*j/6)+Vector((0,0,-.17*math.sin(math.pi*j/6))) for j in range(7)]
                plants.tube(bark,tpts,[h*.0038*(1-j/7)**1.5+.001 for j in range(7)],8);stats['newBranches']+=1;tips.append(tip)
                # Short alternating third-order shoots carry the flower banks.
                for j in range(3):
                    q=tip+Vector((rng.uniform(-.26,.26),rng.uniform(-.26,.26),rng.uniform(-.05,.26)))
                    plants.tube(bark,[tpts[3+j],tpts[3+j].lerp(q,.55)+bend*.4,q],[.007,.003,.0008],6)
            # A naturally continuing upper leader, not a broom of upright sticks.
            if i%4==0:
                tip=end+Vector((rng.uniform(-.5,.5),rng.uniform(-.5,.5),h*.12))
                plants.tube(bark,[pts[7],end,tip],[.025,.012,.001],8);tips.append(tip)
        # The leader forks into a flowering crown instead of ending in a cut cone.
        for side in [-1,1]:
            tip=tr[-1]+Vector((side*h*.045,side*h*.022,h*.035))
            plants.tube(bark,[tr[-2],tr[-1].lerp(tip,.45),tip],[h*.007,h*.003,.001],10)
            tips.extend([tip,tr[-1].lerp(tip,.4)])
        for tip in tips:
            for j in range(36 if hero else 12):
                n=Vector((rng.gauss(0,1),rng.gauss(0,1),rng.gauss(.3,.6))).normalized();r=rng.uniform(.23,.72 if hero else .42)
                end=tip+Vector((n.x*r,n.y*r,n.z*r*.65));mid=tip.lerp(end,.5)+Vector((0,0,-.035))
                plants.tube(bark,[tip,mid,end],[.0035,.002,.0006],5)
                for k in range(7 if hero else 6):
                    anchor=tip.lerp(end,.18+.82*k/(6 if hero else 5));normal=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(.2,1))).normalized();p=anchor+normal*rng.uniform(.024,.055)
                    flower(p,rng.uniform(.030,.046),normal,anchor)
        # A few low flowering twigs make the trunk-to-canopy transition natural.
        if hero:
            for k in range(9):
                a=k*2.4;start=tr[2];end=base+Vector((math.cos(a)*2.8,math.sin(a)*2.8,h*.41))
                plants.tube(bark,[start,start.lerp(end,.6),end],[.07,.035,.004],10)
                for j in range(45):flower(end+Vector((rng.uniform(-.4,.4),rng.uniform(-.3,.3),rng.uniform(-.13,.16))),rng.uniform(.03,.05),(rng.random(),-1,1))
        return tips
    hero_tips=cherry((-5.6,11.7,2.8),12.7,6.8,100,True)
    # An explicitly attached near-camera twig makes single-flower construction
    # inspectable, not hidden behind an aggregate canopy of many small silhouettes.
    anchor=min(hero_tips,key=lambda p:p.x+p.y*.35)
    macro_end=anchor+Vector((-1.0,-.80,.24));macro_mid=anchor.lerp(macro_end,.52)+Vector((0,0,-.08))
    plants.tube(bark,[anchor,macro_mid,macro_end],[.018,.009,.0015],12)
    for i in range(16):
        q=anchor.lerp(macro_end,.22+.76*i/15)+Vector((0,0,-.065*math.sin(math.pi*i/15)))
        side=Vector(((-1)**i*.10,-.08,.05));short=q+side;plants.tube(bark,[q,short],[.003,.0008],6)
        for j in range(3):
            a=j*math.tau/3;p=short+Vector((math.cos(a)*.035,math.sin(a)*.035,.025))
            flower(p,.025+random.random()*.009,(-.3,-.7,1),short,True)
        if i%4==0:leaf(plants,leaves[0],q,math.pi*.8,.13,.025,.4)
    scene['blossom_macro_target']=tuple(anchor.lerp(macro_end,.65)+Vector((0,0,.04)))
    for base,h,sp,seed in [((-10,6,2.8),4.5,2.2,3),((-10,14,2.8),5.2,2.3,7),((-1,16,2.8),5.3,2.5,8),((7,24,5.5),6.0,2.9,11),((-17,18,4),4.5,2.2,13),((10.3,20.8,5.5),4.0,1.7,14)]:cherry(base,h,sp,seed)

    # Circular root terrace, interrupted at its front entrance.
    for i in range(90):
        a=.32+(math.tau-.64)*i/89;x=-5.6+2.0*math.sin(a);y=11.7-2.0*math.cos(a)
        architecture.box(stone,(x,y,2.94),(.145,.32,.28),-a)
    # Reflecting pool beside the tea pavilion; no water across the main walking route.
    lathe(waterb,water,(1.8,7.8,2.815),[(0,0),(1.8,0),(1.8,.03),(0,.03)],100)
    for i in range(48):
        a=i*math.tau/48;snow_lobe(terrain,stone,(1.8+1.9*math.cos(a),7.8+1.9*math.sin(a),2.84),(.24,.19,.12),i,a)
    # A stream exits the rear terrace and drops through the ravine in articulated ribbons.
    waterb.box(water,(3.25,7.1,2.82),(3.0,.55,.04))
    curtain=[]
    for j in range(65):
        t=j/64
        for k in range(13):
            u=k/12;curtain.append((4.43+u*(.60+.13*t),7.0+.38*t+.026*math.sin(u*18+t*23),2.84-12*t))
    waterb.mesh(falling,curtain,[(j*13+k,j*13+k+1,(j+1)*13+k+1,(j+1)*13+k) for j in range(64) for k in range(12)],True)
    for k in range(19):
        xx=4.45+k*.030;pts=[]
        for j in range(45):
            t=j/44;pts.append((xx+.018*math.sin(t*8+k),6.99+.38*t+.008*math.sin(t*21+k),2.84-12*t))
        waterb.tube(spray if k%3==0 else falling,pts,[.004*(1-.45*j/44) for j in range(45)],5)
    # Companion shelter, bowls and an open cushion on the original arrival island.
    details.box(wood,(-2,-11.5,.15),(1.6,1.15,.22))
    for x in [-2.65,-1.35]:
        for y in [-11.95,-11.05]:details.box(wood,(x,y,.68),(.07,.07,1.1))
    details.mesh(slate,[(-2.9,-12.2,1.25),(-2.9,-10.8,1.25),(-2,-12.2,1.65),(-2,-10.8,1.65),(-1.1,-12.2,1.25),(-1.1,-10.8,1.25)],[(0,1,3,2),(2,3,5,4)])
    snow_lobe(details,fabric,(-2,-11.5,.29),(.53,.39,.09),2)
    for x in [-1,-.55]:lathe(details,ceramic,(x,-11.8,.06),[(0,0),(.19,0),(.22,.15),(.21,.17),(.17,.06),(0,.05)],40)
    # Sparse meadow blades leave the designed walking corridors and pavilion clear.
    for _ in range(44000):
        x=random.uniform(-12.3,4.2);y=random.uniform(3.4,17.1)
        if ((x+4)/8.4)**2+((y-10)/7.1)**2>1:continue
        if (x+5.6)**2+(y-11.7)**2<4.4 or (x-1.8)**2+(y-7.8)**2<4.5:continue
        if abs(x-1)<2.9 and abs(y-12)<2.8:continue
        if abs(x-(-1-(y-3.5)*.34))<1.25 and y<11:continue
        if abs(y-(9+(x+3)*.5))<1.0 and -3<x<3:continue
        if abs(y-(8-(x+8)*.2))<.85 and -10.5<x<-3:continue
        a=random.random()*math.tau;l=random.uniform(.07,.24);p=Vector((x,y,2.82));axis=Vector((math.cos(a),math.sin(a),0));side=Vector((-axis.y,axis.x,0));w=random.uniform(.004,.012)
        plants.mesh(random.choices(leaves,[4,5,3,1])[0],[p-side*w,p,p+side*w,p+axis*l*.18+Vector((0,0,l*.63)),p+axis*l*.42+Vector((0,0,l))],[(0,1,3),(1,2,3),(0,3,4),(3,2,4)],True);stats['newGrassBlades']+=1
    # Individual fallen petals, mostly in root terraces rather than a flat pink carpet.
    for _ in range(1800):
        a=random.random()*math.tau;r=random.random()**.5*6;x=-5.6+math.cos(a)*r;y=11.7+math.sin(a)*r
        if ((x+4)/8.5)**2+((y-10)/7.2)**2<1:
            p=Vector((x,y,2.84));s=random.uniform(.014,.026);plants.mesh(random.choice(petals),[p+Vector((-s,0,0)),p+Vector((0,s*.7,.002)),p+Vector((s,0,.007)),p+Vector((0,-s*.7,.002))],[(0,1,2),(0,2,3)],True)

    for cx,cy,z,rx,ry in [(8,22,5.5,4.35,4.05),(-17,18,4,3.05,3.35)]:
        for j in range(6500):
            a=random.random()*math.tau;r=random.random()**.5;x=cx+rx*r*math.cos(a);y=cy+ry*r*math.sin(a)
            if abs(x-cx)<.95 or ((x-cx)**2+(y-cy-1)**2)<.7:continue
            p=Vector((x,y,z+.02));aa=random.random()*math.tau;axis=Vector((math.cos(aa),math.sin(aa),0));side=Vector((-axis.y,axis.x,0));ll=random.uniform(.06,.20)
            plants.mesh(random.choice(leaves[:3]),[p-side*.006,p+side*.006,p+Vector((0,0,ll*.6))+axis*.025,p+Vector((0,0,ll))+axis*.06],[(0,1,2),(0,2,3)],True);stats['newGrassBlades']+=1

    terrain_objects=finish(terrain,'Terrain',land)
    for o in terrain_objects:
        if o.data.materials[0]==rock:
            for face in o.data.polygons:face.use_smooth=True
            sub=o.modifiers.new('Eroded continuous rock forms','SUBSURF');sub.levels=1;sub.render_levels=1
            tex=bpy.data.textures.new('Rock scale fracture relief',type='CLOUDS');tex.noise_scale=.23;tex.noise_depth=2
            disp=o.modifiers.new('Weathered rock relief','DISPLACE');disp.texture=tex;disp.strength=.10;disp.mid_level=.5;disp.texture_coords='GLOBAL'
    finish(architecture,'Crafted structures',arch,.008);finish(plants,'Cherry ecology',bot);finish(waterb,'Jade waters',wet);finish(details,'Companion detail',props,.003)
    scene,cloud,paper,devices=lighting('sakura',OUT,args.preview)
    # Broad landscape lighting, physically modelled cloud sea, deep chromatic shadows.
    bpy.data.objects.remove(cloud,do_unlink=True)
    for o in scene.objects:
        if o.type=='LIGHT':o.data.energy*=2.8;o.data.size*=1.5;o.location*=2.2;look(o,(-2,8,3))
    bpy.ops.object.light_add(type='SUN',location=(-15,-10,30));sun=bpy.context.object;sun.name='Late afternoon sun';sun.data.energy=1.8;sun.data.angle=.10;sun.rotation_euler=(.48,-.6,-.6)
    nt=scene.world.node_tree;bg=nt.nodes.get('Background');bg.inputs['Strength'].default_value=.075
    # Nishita's below-horizon black is inappropriate for a floating archipelago.
    # A camera-only hazy teal sky preserves the physical environment lighting.
    back=nt.nodes.new('ShaderNodeBackground');back.inputs['Color'].default_value=(.10,.20,.23,1);back.inputs['Strength'].default_value=.65
    wc=nt.nodes.new('ShaderNodeTexCoord');sep=nt.nodes.new('ShaderNodeSeparateXYZ');sky_ramp=nt.nodes.new('ShaderNodeValToRGB');sky_ramp.color_ramp.elements[0].color=(.18,.25,.25,1);sky_ramp.color_ramp.elements[1].color=(.035,.09,.13,1)
    nt.links.new(wc.outputs['Normal'],sep.inputs[0]);nt.links.new(sep.outputs['Z'],sky_ramp.inputs[0]);nt.links.new(sky_ramp.outputs[0],back.inputs['Color'])
    lp=nt.nodes.new('ShaderNodeLightPath');mix=nt.nodes.new('ShaderNodeMixShader');nt.links.new(lp.outputs['Is Camera Ray'],mix.inputs[0]);nt.links.new(bg.outputs[0],mix.inputs[1]);nt.links.new(back.outputs[0],mix.inputs[2]);nt.links.new(mix.outputs[0],nt.nodes.get('World Output').inputs['Surface'])
    scene.view_settings.exposure=-.55
    atmosphere=collection('V2 90 Distant mountains and layered mist - presentation only')
    # Three actual mountain ranges, progressively bluer and lower in contrast.
    mountain_batch=Batch()
    for layer,(ycentre,height,color) in enumerate([(58,40,(.10,.17,.17)),(98,55,(.14,.22,.23)),(148,72,(.19,.27,.28))]):
        m=material('Atmospheric mountain '+str(layer),color,.95,glow=.18+layer*.1)
        peaks=[(-130+q*26+random.uniform(-8,8),random.uniform(.55,1.2),random.uniform(9,20)) for q in range(11)]
        verts=[];nx,ny=160,42
        for j in range(ny+1):
            y=ycentre-22+j*44/ny
            for i in range(nx+1):
                x=-170+i*340/nx;ridge=max(amp*math.exp(-((x-px)/width)**2) for px,amp,width in peaks)
                transverse=math.exp(-((y-ycentre-5*math.sin(x*.045))/15)**2)
                serration=1+.09*math.sin(x*.43+y*.24)+.04*math.sin(x*1.03-y*.67)
                z=-18+height*ridge*transverse*serration;verts.append((x,y,z))
        mountain_batch.mesh(m,verts,[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)],True)
    finish(mountain_batch,'Far geological ridges',atmosphere)
    # Soft finite cloud banks fade in all three axes, so there is no white tabletop.
    mist=bpy.data.materials.new('Layered mountain mist');mist.use_nodes=True;nt=mist.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');vol=nt.nodes.new('ShaderNodeVolumePrincipled');vol.inputs['Color'].default_value=(.72,.82,.83,1);vol.inputs['Anisotropy'].default_value=.25
    co=nt.nodes.new('ShaderNodeTexCoord');distance=nt.nodes.new('ShaderNodeVectorMath');distance.operation='DISTANCE';distance.inputs[1].default_value=(.5,.5,.5);nt.links.new(co.outputs['Generated'],distance.inputs[0])
    fade=nt.nodes.new('ShaderNodeMapRange');fade.inputs['From Min'].default_value=.15;fade.inputs['From Max'].default_value=.53;fade.inputs['To Min'].default_value=1;fade.inputs['To Max'].default_value=0;nt.links.new(distance.outputs['Value'],fade.inputs[0])
    noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=5;noise.inputs['Detail'].default_value=4;nt.links.new(co.outputs['Generated'],noise.inputs[0])
    density=nt.nodes.new('ShaderNodeMath');density.operation='MULTIPLY';nt.links.new(fade.outputs[0],density.inputs[0]);nt.links.new(noise.outputs['Fac'],density.inputs[1]);amount=nt.nodes.new('ShaderNodeMath');amount.operation='MULTIPLY';amount.inputs[1].default_value=.16;nt.links.new(density.outputs[0],amount.inputs[0]);nt.links.new(amount.outputs[0],vol.inputs['Density']);nt.links.new(vol.outputs[0],out.inputs['Volume'])
    for centre_,scale_ in [((0,5,-11),(49,40,7)),((-27,19,-4),(24,17,5)),((25,30,-1),(25,22,5)),((-25,55,6),(45,16,5)),((27,86,10),(52,18,7)),((-45,120,16),(60,24,8))]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=centre_);o=bpy.context.object;o.name='Soft separated cloud bank';o.scale=scale_;o.data.materials.append(mist);move(o,atmosphere)
    # Fine mist at the waterfall's bottom, separate from the large background banks.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=1,location=(4.7,7.3,-7.5));o=bpy.context.object;o.name='Waterfall spray mist';o.scale=(1.1,.8,1.8);o.data.materials.append(mist);move(o,atmosphere)
    # Named, editable route markers. These are documentation, not certified UE navmesh.
    route=[('Arrival courtyard',(0,-8,.2)),('Ascent bridge',(-.5,1,1.5)),('Cherry threshold',(-1,4.7,3)),('Ancient cherry terrace',(-5.6,10,3)),('Tea pavilion',(1,12,3.3)),('Sky lookout',(8,22,5.7)),('Quiet blossom garden',(-17,18,4.2))]
    nav=collection('V2 06 Intended walking route markers')
    for label,p in route:
        o=bpy.data.objects.new(label,None);nav.objects.link(o);o.location=p;o.empty_display_size=.3;o['intent']='artist layout only; runtime navigation needs validation'
    scene.render.resolution_x=2400;scene.render.resolution_y=1800;scene.cycles.samples=128
    refine_atmosphere()
    scene.camera.location=(34,-48,25);look(scene.camera,(-3,7,4.8));scene.camera.data.type='PERSP';scene.camera.data.lens=48;scene.camera.data.sensor_width=36
    finite_count=0
    for o in scene.objects:
        if o.type=='MESH':
            coords=np.empty(len(o.data.vertices)*3,dtype=np.float32);o.data.vertices.foreach_get('co',coords)
            if not np.isfinite(coords).all():raise RuntimeError('Non-finite vertex: '+o.name)
            finite_count+=len(o.data.vertices)
    stats['finiteVerticesChecked']=finite_count
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    report={'title':'樱云长境 · Sakura Archipelago','revision':2,'source':str(SOURCE),'sourceSha256':digest(SOURCE),'master':MASTER.name,'masterSha256':digest(MASTER),'masterBytes':MASTER.stat().st_size,'seed':SEED,'units':'metres','upAxis':'Z','stats':stats,'palette':'deep chestnut / ink jade roofs / rose blush / moss green','renderer':'Cycles / OptiX','devices':devices,'webSceneChanged':False,'accountDataRead':False,'runtimeReady':False,'runtimeLimitations':['UE materials not baked or validated','LOD, collision and navmesh not built','No runtime FPS claim'],'route':[{'name':n,'position':p} for n,p in route],'collections':{},'renders':[]}
    for c in scene.collection.children:
        objects=[o for o in c.objects if o.type=='MESH'];report['collections'][c.name]={'meshes':len(objects),'baseTriangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects)}
    report['totalBaseTriangles']=sum(c['baseTriangles'] for c in report['collections'].values())
    (OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('BUILD_COMPLETE',json.dumps(stats),flush=True)

if not args.render_only:build()
else:
    bpy.ops.wm.open_mainfile(filepath=str(MASTER));refine_atmosphere()
if not args.no_render:
    scene=bpy.context.scene;prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='OPTIX'
    assert any(d.use for d in prefs.devices),'OptiX unavailable'
    scene.cycles.device='GPU';scene.cycles.samples=32 if args.preview else 128;scene.cycles.use_denoising=True;scene.render.resolution_x=1200 if args.preview else 2400;scene.render.resolution_y=900 if args.preview else 1800
    shots=[('01-grand-vista',(34,-48,25),(-3,7,4.8),50),('02-cherry-promenade',(-14,-8,7),(-4,10,6.5),24),('03-tea-pavilion',(10,2,7),(1,12,4.8),11),('04-blossom-detail',(-11,6,11),(-7,10,11.2),4.2),('05-plan',(-4,7,65),(-4,7,0),60)]
    report=json.loads((OUT/'build-report.json').read_text(encoding='utf8'))
    report['visualLimitations']=['Distant mountains remain stylized and need more natural silhouette and geological variation','Waterfall is a thin curtain but repeated aeration strands remain visible; fluid motion is not simulated','This is an art review master, not a photorealism acceptance or real-time performance signoff']
    if args.render_only and not args.preview:
        # Save a useful opening camera in the editable master, not an origin camera.
        scene.camera.location=(34,-48,25);look(scene.camera,(-3,7,4.8));scene.camera.data.type='PERSP';scene.camera.data.lens=48;scene.camera.data.sensor_width=36
        finite_count=0
        for o in scene.objects:
            if o.type=='MESH':
                coords=np.empty(len(o.data.vertices)*3,dtype=np.float32);o.data.vertices.foreach_get('co',coords)
                if not np.isfinite(coords).all():raise RuntimeError('Non-finite final vertex: '+o.name)
                finite_count+=len(o.data.vertices)
        report['stats']['finiteVerticesChecked']=finite_count
        report['collections']={}
        for c in scene.collection.children:
            obs=[o for o in c.objects if o.type=='MESH'];report['collections'][c.name]={'meshes':len(obs),'baseTriangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in obs)}
        report['totalBaseTriangles']=sum(c['baseTriangles'] for c in report['collections'].values())
        report['supportingAssets']=[{'file':'art/mistwood-v1/limestone-albedo.png','sha256':digest(ROOT/'art/mistwood-v1/limestone-albedo.png')}]
        report['reviewCorrections']=['Hierarchical curved branches with connected flower pedicels and calyx/stamens','Roof rafters and brackets remain below the roof skin','Continuous rock rim, packed rock albedo, fissure bump and local erosion relief','Thin waterfall curtain, silver aeration and separate spray mist','Three atmospheric mountain ranges, finite cloud banks and distance haze']
        bpy.ops.wm.save_as_mainfile(filepath=str(MASTER));report['masterSha256']=digest(MASTER);report['masterBytes']=MASTER.stat().st_size
    for name,pos,target,scale in shots:
        if args.shot!='all' and args.shot!=name:continue
        if args.preview and args.shot=='all' and name not in ['01-grand-vista','03-tea-pavilion']:continue
        cam=scene.camera
        if name=='04-blossom-detail':
            target=Vector(scene['blossom_macro_target']);pos=target+Vector((-1.0,-2.3,1.5));scale=1.35
        cam.location=pos;look(cam,target);cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.dof.use_dof=name=='04-blossom-detail'
        if name=='04-blossom-detail':cam.data.dof.focus_distance=(Vector(pos)-Vector(target)).length;cam.data.dof.aperture_fstop=48
        if name in ['01-grand-vista','02-cherry-promenade']:
            cam.data.type='PERSP';cam.data.lens=48 if name=='01-grand-vista' else 28;cam.data.sensor_width=36
        if name=='05-plan':cam.rotation_euler=(0,0,0)
        dest=OUT/(name+('-preview' if args.preview else '')+'.png');scene.render.filepath=str(dest);bpy.ops.render.render(write_still=True)
        item={'file':dest.name,'sha256':digest(dest),'bytes':dest.stat().st_size,'width':scene.render.resolution_x,'height':scene.render.resolution_y,'samples':scene.cycles.samples}
        report['renders']=[r for r in report['renders'] if r['file']!=dest.name]+[item];(OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('RENDER_COMPLETE',name,flush=True)
