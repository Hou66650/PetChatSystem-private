"""Offline detailed sakura, snow and camp masters. Never writes static/ or templates/.

blender -b --python scripts/blender/build_cinematic_islands.py -- all [--preview]
Sources are frozen under art/cinematic-islands-v1/source on first use.
"""
import bpy,bmesh,math,random,json,re,sys,hashlib,shutil
from pathlib import Path
from mathutils import Vector
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from cinematic_island_tools import *

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/cinematic-islands-v1';SOURCES=OUT/'source';SOURCES.mkdir(parents=True,exist_ok=True)
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['all']
THEMES=['sakura','snow','camp'] if args[0]=='all' else [args[0]]
assert all(t in ['sakura','snow','camp'] for t in THEMES)
PREVIEW='--preview' in args
LAYOUT=ROOT/'static/js/den/realistic-island-layouts.js'
web_paths=[LAYOUT,ROOT/'templates/den.html']+[ROOT/('static/models/petchat-realistic-islands-v1/'+t+'.glb') for t in ['sakura','snow','camp']]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before_hash={p.relative_to(ROOT).as_posix():digest(p) for p in web_paths}
snapshot=SOURCES/'layouts.json'
if not snapshot.exists():
    snapshot.write_text(json.dumps(json.loads(re.search(r'const layouts = (\{[\s\S]+?\});',LAYOUT.read_text(encoding='utf-8')).group(1)),ensure_ascii=False,indent=2),encoding='utf-8')
layouts=json.loads(snapshot.read_text(encoding='utf-8'))


def build(theme):
    rng=random.Random({'sakura':17691,'snow':17692,'camp':17693}[theme]);random.seed(17690)
    dest=OUT/theme;dest.mkdir(exist_ok=True);src=SOURCES/(theme+'.glb')
    if not src.exists():shutil.copy2(ROOT/('static/models/petchat-realistic-islands-v1/'+theme+'.glb'),src)
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(src))
    scene=bpy.context.scene;L=layouts[theme];radius=L['radius'];house=L['building'];cx=house['x'];cy=-house['z'];w=house['w'];d=house['d'];eave=house['h'];ridge=eave+1.05;ry=-L['water'][0]['z'];river_width=L['water'][0]['d']
    base=collection('01 Source landscape');craft=collection('02 Architecture');ecology=collection('03 Botanical detail');hydro=collection('04 Water ice and snow')
    original=list(scene.objects)
    for o in original:move(o,base)
    stats={'needles':0,'blossoms':0,'grassBlades':0,'snowDeposits':0,'roofTiles':0}
    centres=set()
    for o in list(original):
        if o.type!='MESH':continue
        name=o.name
        if 'Cherry_petal' in name:
            # Each original petal starts at its blossom centre; four triangles.
            for f in list(o.data.polygons)[::4]:
                p=o.matrix_world@o.data.vertices[f.vertices[0]].co
                centres.add(tuple(round(v,5) for v in p))
        if any(k in name for k in ['Foliage_','Cherry_petal','Deep_stream','Silver_water_foam','waterfall','Glacial_ice']):
            bpy.data.objects.remove(o,do_unlink=True);original.remove(o)
        elif theme=='snow' and 'Snow_grains' in name:
            # Remove flat roof snow and disconnected old branch clumps; keep
            # the authored ground/rim. New snow follows actual branch axes.
            bm=bmesh.new();bm.from_mesh(o.data)
            bmesh.ops.delete(bm,geom=[f for f in bm.faces if (o.matrix_world@f.calc_center_median()).z>.35],context='FACES');bm.to_mesh(o.data);bm.free()
    for m in bpy.data.materials:
        if not m.use_nodes or not any(n.type=='BSDF_PRINCIPLED' for n in m.node_tree.nodes):continue
        if 'stone' in m.name.lower():micro(m,34,.012)
        if 'bark' in m.name.lower():micro(m,65,.009)
        if 'timber' in m.name.lower():micro(m,110,.002)
        if 'Warm_window' in m.name:
            set_input(m,'Base Color',(.36,.16,.035,1));set_input(m,'Emission Color',(1,.47,.12,1));set_input(m,'Emission Strength',1.4 if theme=='snow' else .45);set_input(m,'Roughness',.16)
    stone=tile('Dressed limestone',(.46,.44,.39))
    slate=tile('Split slate tiles',(.18,.21,.23))
    oak=tile('Fine aged oak',(.37,.23,.13),'wood')
    bark=tile('Deep bark',(.23,.16,.095),'wood')
    earth=tile('Dark fertile soil',(.14,.115,.07))
    snow=tile('Fine powder snow',(.85,.91,.95),'snow');principled(snow).inputs['Subsurface Weight'].default_value=.06;principled(snow).inputs['Subsurface Radius'].default_value=(.04,.07,.12)
    iron=material('Forged charcoal iron',(.027,.033,.03),.36,.72)
    bronze=material('Aged bronze',(.28,.16,.055),.35,.72)
    needles=[material('Pine green '+str(i),c,.67) for i,c in enumerate([(.025,.075,.036),(.045,.12,.057),(.075,.17,.075)])]
    moss=[material('Moss and grass '+str(i),c,.85) for i,c in enumerate([(.045,.10,.018),(.09,.17,.033),(.16,.23,.053)])]
    petal=[material('Sakura blush '+str(i),c,.54) for i,c in enumerate([(.75,.37,.43),(.93,.66,.68),(.94,.78,.76)])]
    pollen=material('Golden pollen',(.58,.28,.018),.78)
    for m in needles+moss+petal:
        principled(m).inputs['Subsurface Weight'].default_value=.07;principled(m).inputs['Subsurface Radius'].default_value=(.01,.02,.008);m.use_backface_culling=False
    arch=Batch();plants=Batch();winter=Batch()

    # Layered conifer crowns: secondary twigs carry paired tapered needles.
    for ti,t in enumerate(L['trees']):
        x,y,h=t['x'],-t['z'],t['h']
        for j in range(34):
            f=.20+.74*j/34;a=j*2.399+ti*.7;length=h*.40*(1-f)**.78
            start=Vector((x,y,h*f));end=start+Vector((math.cos(a)*length,math.sin(a)*length,.12-.15*f))
            plants.tube(bark,[start,start.lerp(end,.55)+Vector((0,0,-.08)),end],[.035,.017,.002],8)
            for k in range(15):
                p=start.lerp(end,.12+k*.060)
                for side in [-1,0,1]:
                    aa=a+side*.85;tl=.23+.23*(1-k/16);tip=p+Vector((math.cos(aa)*tl,math.sin(aa)*tl,.075 if side else .13))
                    plants.tube(bark,[p,tip],[.004,.0007],5)
                    direction=(tip-p).normalized();lateral=Vector((-direction.y,direction.x,0))
                    for q in range(20):
                        pos=p.lerp(tip,q/20)
                        for whorl in range(4):
                            phi=whorl*math.pi/2+q*2.399
                            axis=(direction*.35+lateral*math.cos(phi)+direction.cross(lateral)*math.sin(phi)).normalized();ll=rng.uniform(.050,.095)
                            spread=direction*.0024;vtip=pos+axis*ll
                            plants.mesh(needles[(q+j)%3],[pos-spread,pos+spread,vtip+Vector((0,0,.002)),vtip],[(0,1,2),(0,2,3)],True);stats['needles']+=1
                    if theme=='snow' and side and k in [2,5,8,11] and rng.random()<.75:
                        pos=p.lerp(tip,.5)+Vector((0,0,.047));snow_lobe(winter,snow,pos,(tl*.58,.066,.040),j+k+ti,aa);stats['snowDeposits']+=1
        if theme=='snow':snow_lobe(winter,snow,(x,y,.09),(.32,.27,.11),ti)

    # Cherry blossoms are cupped five-petal meshes with a central stamen crown.
    if theme=='sakura':
        for idx,centre in enumerate(sorted(centres)):
            # Three nearby blooms replace each large flat source flower.
            for repeat in range(3 if centre[2]>.8 else 1):
                p=Vector(centre)+Vector((rng.uniform(-.10,.10),rng.uniform(-.10,.10),rng.uniform(-.07,.07)))
                normal=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(.3,1))).normalized();u=normal.cross(Vector((.12,.2,1))).normalized();v=normal.cross(u);r=rng.uniform(.025,.042);spin=rng.random()*math.tau
                for k in range(5):
                    a=spin+k*math.tau/5;axis=u*math.cos(a)+v*math.sin(a);side=normal.cross(axis);vs=[]
                    for j in range(7):
                        t=j/6;mid=p+axis*r*t+normal*r*(.20*t*t-.06*math.sin(math.pi*t))
                        width=r*.42*math.sin(math.pi*t*.95)**.68
                        for q in [-1,0,1]:vs.append(mid+side*q*width+normal*(.03*r if q else -.02*r)*math.sin(math.pi*t))
                    plants.mesh(petal[(idx+repeat+k)%3],vs,[(j*3+q,j*3+q+3,j*3+q+4,j*3+q+1) for j in range(6) for q in range(2)],True)
                for q in range(4):
                    a=q*math.tau/4;tip=p+normal*.012+(u*math.cos(a)+v*math.sin(a))*.006
                    plants.tube(pollen,[p,tip],[.00065,.0012],4)
                stats['blossoms']+=1
        # Roof barrel caps and layered timber brackets on the tea pavilion.
        for side in [-1,1]:
            for j in range(23):
                y=cy-d/2-.28+j*(d+.56)/22
                pts=[]
                for q in range(15):
                    t=q/14;pts.append((cx+side*(w/2+.34)*t,y,ridge-1.05*t+.18*t**6+.02))
                arch.tube(slate,pts,.025,12);stats['roofTiles']+=14
            for y in [cy-d/2,cy+d/2]:
                x=cx+side*w/2
                for j in range(3):arch.box(oak,(x-side*.07*j,y,eave-.22-j*.07),(.38-j*.07,.27-j*.04,.055))
                arch.tube(oak,[(x,y,eave-.7),(x-side*.18,y,eave-.39),(x-side*.51,y,eave-.2)],.037,10)
        # Open lattice side screens leave the front entry clear.
        for x in [cx-w/2,cx+w/2]:
            for j in range(15):arch.box(oak,(x,cy-d/2+j*d/14,1.15),(.027,.028,1.35))
            for h in [.65,.92,1.19,1.46,1.73]:arch.box(oak,(x,cy,h),(.028,d,.026))
        # Tea table, rounded cushions and wheel-thrown ceramic tea service.
        arch.box(oak,(cx,cy,.67),(1.05,.65,.065))
        for x in [cx-.42,cx+.42]:
            for y in [cy-.23,cy+.23]:arch.box(oak,(x,y,.51),(.055,.055,.32))
        ceramic=material('Tea celadon glaze',(.16,.31,.24),.23)
        for x in [cx-.27,cx+.27]:lathe(arch,ceramic,(x,cy-.08,.71),[(0,0),(.035,0),(.05,.07),(.048,.075),(.043,.07),(.03,.008),(0,.008)],32)
        lathe(arch,ceramic,(cx,cy+.13,.71),[(0,0),(.07,0),(.10,.07),(.07,.14),(.035,.15),(0,.15)],48)
        linen=material('Tea cushion linen',(.31,.38,.25),.94)
        for x in [cx-.82,cx+.82]:snow_lobe(arch,linen,(x,cy,.44),(.20,.28,.075),x)
    else:
        # Cabin windows: real shutters, iron hinges, nails, sill drip edges.
        front=cy-d/2-.19
        for x in [cx-.88,cx+.88]:
            for sign in [-1,1]:
                for j in range(4):arch.box(oak,(x+sign*.47,front-.015,1.10+j*.21),(.21,.065,.19))
                for h in [1.15,1.75]:
                    arch.box(iron,(x+sign*.47,front-.052,h),(.23,.015,.035))
                    arch.ellipsoid(bronze,(x+sign*.40,front-.063,h),(.012,.006,.012),10,6)
            arch.box(oak,(x,front-.04,1.0),(.83,.24,.065))
        for j in range(15):
            z=.35+j*(eave-.35)/15
            for x in [cx-w/2-.13,cx+w/2+.13]:
                # End grain rings as actual geometry along the log axis.
                for rr in [.023,.047,.067]:
                    arch.tube(bark,[(x,cy-d/2+rr*math.cos(t),z+rr*math.sin(t)) for t in np.linspace(0,math.tau,25)],.0014,4)
        for x in [cx-.23,cx+.23]:
            for h in [.43,1.42]:arch.box(iron,(x,front-.015,h),(.18,.02,.045))
        # Stacked split firewood at the side wall, outside the entrance.
        for j in range(5):
            for k in range(4-j//2):
                x=cx+w/2+.28+k*.12;y=cy+.35;z=.19+j*.13
                arch.tube(oak,[(x,y-.33,z),(x,y+.33,z)],rng.uniform(.055,.069),16)
        for side in [-1,1]:
            for row in range(13):
                t0=row/13;t1=(row+1.14)/13
                for j in range(18):
                    y0=cy-d/2-.28+j*(d+.56)/18;y1=y0+(d+.56)/18*.95
                    points=[(cx+side*(w/2+.34)*t,y,ridge-1.05*t+.025) for t,y in [(t0,y0),(t1,y0),(t1,y1),(t0,y1)]]
                    arch.mesh(slate,points,[tuple(range(4))]);stats['roofTiles']+=1
        if theme=='snow':
            # Continuous undulating roof blanket with rounded eave overhang.
            for sign in [-1,1]:
                vs=[];fs=[];nu,nv=32,40
                for j in range(nv+1):
                    y=cy-d/2-.33+j*(d+.66)/nv
                    for i in range(nu+1):
                        t=i/nu;z=ridge-1.05*t+.115+.035*math.sin(y*3+t*5)+.018*math.sin(y*13+t*7)
                        vs.append((cx+sign*(w/2+.38)*t,y,z))
                for j in range(nv):
                    for i in range(nu):a=j*(nu+1)+i;fs.append((a,a+1,a+nu+2,a+nu+1))
                winter.mesh(snow,vs,fs,True)
                for j in range(32):
                    y=cy-d/2-.27+j*(d+.54)/31;snow_lobe(winter,snow,(cx+sign*(w/2+.35),y,eave+.10),(.075,.10,.067),j)
            ice=material('Clear blue ice',(.59,.79,.88),.11);principled(ice).inputs['Transmission Weight'].default_value=.82;principled(ice).inputs['IOR'].default_value=1.31
            for side in [-1,1]:
                for j in range(54):
                    y=cy-d/2-.24+j*(d+.48)/53;length=rng.uniform(.06,.38);x=cx+side*(w/2+.36)
                    winter.tube(ice,[(x,y,eave+.06),(x+.006,y,eave-length*.4),(x+.012,y,eave-length)],[.018,.009,.0008],12)
            pond=L['pond'];px,py,rr=pond['x'],-pond['z'],pond['r']
            lathe(winter,ice,(px,py,.043),[(0,0),(rr,0),(rr,.035),(0,.035)],96)
            frost=material('Frost fractures',(.50,.68,.73),.5)
            for i in range(22):
                a=rng.random()*math.tau;r=rng.uniform(.05,.7)
                pts=[(px+(r+j*.035)*math.cos(a)+.015*math.sin(j*2),py+(r+j*.035)*math.sin(a),.080) for j in range(7)]
                winter.tube(frost,pts,[.0025]*7,4)
            # Wind-shaped drifts concentrate around roots and island edges.
            for i in range(120):
                a=rng.random()*math.tau;r=rng.uniform(radius-.65,radius-.18);x,y=r*math.cos(a),r*math.sin(a)
                if abs(y-ry)<.8:continue
                snow_lobe(winter,snow,(x,y,.07),(rng.uniform(.2,.55),rng.uniform(.15,.32),rng.uniform(.045,.12)),i)

    if theme=='camp':
        tower=L['tower'];x,y,rr,h=tower['x'],-tower['z'],tower['r'],tower['h']
        for z in [.20,1.9,3.0,4.27]:
            for j in range(36):
                a=j*math.tau/36;arch.box(stone,(x+rr*.97*math.cos(a),y+rr*.97*math.sin(a),z),(.19,.22,.09),a+math.pi/2)
        for k in range(8):
            a=k*math.tau/8;b=(k+1)*math.tau/8
            for z in [h+.25,h+.62]:arch.tube(oak,[(x+.83*math.cos(a),y+.83*math.sin(a),z),(x+.83*math.cos(b),y+.83*math.sin(b),z)],.023,10)
            for j in range(4):
                t=a+(b-a)*(j+.5)/4;arch.tube(iron,[(x+.80*math.cos(t),y+.80*math.sin(t),h+.1),(x+.80*math.cos(t),y+.80*math.sin(t),h+.65)],.009,8)
            for row in range(9):
                r0=.12+row*.14;r1=r0+.165
                for j in range(5):
                    aa=a+(b-a)*j/5+.005;bb=a+(b-a)*(j+1)/5-.005
                    vs=[(x+r*math.cos(t),y+r*math.sin(t),h+1.93-r*.95/1.35+.008*(row%2)) for r,t in [(r0,aa),(r1,aa),(r1,bb),(r0,bb)]]
                    arch.mesh(slate,vs,[(0,1,2,3)]);stats['roofTiles']+=1
        lathe(arch,bronze,(x,y,h+1.92),[(.05,0),(.065,.06),(.025,.13),(0,.27)],32)
        for z in [2.3,3.25]:
            for dx in [-.17,.17]:arch.box(stone,(x+dx,y-rr-.04,z),(.07,.13,.62))
            for zz in [z-.30,z+.30]:arch.box(stone,(x,y-rr-.04,zz),(.40,.13,.06))

    # Close-range ground: short bent grass, moss, ferns and loose petals.
    def free(x,y):
        if math.hypot(x,y)>radius-.45 or abs(y-ry)<river_width/2+.18:return False
        if abs(x-cx)<w/2+.20 and abs(y-cy)<d/2+.35:return False
        if theme=='camp' and math.hypot(x-L['tower']['x'],y+L['tower']['z'])<1.22:return False
        if abs(x)<1.7 and -3.6<y<.1:return False
        # Keep a broad uninterrupted corridor through the middle of the island.
        if abs(x)<.85:return False
        return True
    if theme!='snow':
        for i in range(85000):
            x=rng.uniform(-radius,radius);y=rng.uniform(-radius,radius)
            if not free(x,y) or (math.sin(x*2.1)*math.cos(y*1.6)<-.3 and rng.random()<.7):continue
            a=rng.random()*math.tau;h=rng.uniform(.035,.105);width=rng.uniform(.002,.004)
            side=Vector((-math.sin(a)*width,math.cos(a)*width,0));p=Vector((x,y,.037));vs=[]
            for j in range(4):
                t=j/3;mid=p+Vector((math.cos(a)*h*.32*t*t,math.sin(a)*h*.32*t*t,h*t))
                vs.extend([mid-side*(1-t),mid+side*(1-t)])
            plants.mesh(moss[i%3],vs,[(j*2,j*2+1,j*2+3,j*2+2) for j in range(3)],True);stats['grassBlades']+=1
        for i in range(120):
            a=rng.random()*math.tau;r=rng.uniform(radius-.7,radius-.30);x,y=r*math.cos(a),r*math.sin(a)
            if not free(x,y):continue
            for j in range(7):
                aa=j*math.tau/7;length=rng.uniform(.25,.42)
                for k in range(8):
                    t=k/8;p=(x+math.cos(aa)*length*t,y+math.sin(aa)*length*t,.04+.20*math.sin(math.pi*t*.8))
                    for side in [-1,1]:leaf(plants,moss[j%3],p,aa+side*.9,.075*(1-t*.5),.013,.2)
        if theme=='sakura':
            for i in range(950):
                x=rng.gauss(-2.3,1.7);y=rng.gauss(1.8,1.8)
                if free(x,y):leaf(plants,petal[i%3],(x,y,.043),rng.random()*math.tau,.027,.011,.03)

    # New bridge finish retains the shared deck height and clearance.
    br=L['bridges'][0]
    for j in range(24):
        y=ry-br['d']/2+(j+.5)*br['d']/24;z=br['base']+br['rise']*math.sin(math.pi*((y-ry)/br['d']+.5))**2
        if theme=='snow':
            arch.box(oak,(0,y,z+.01),(br['w']-.06,br['d']/24*.95,.022))
        else:
            for k in range(9):arch.box(stone,(-br['w']/2+(k+.5)*br['w']/9,y,z+.012),(br['w']/9*.96,br['d']/24*.96,.022))
    # Detailed river bed, ripple geometry and broken cascading ribbons.
    water=material('Clear river water',(.54,.77,.76),.095);principled(water).inputs['Transmission Weight'].default_value=.93;principled(water).inputs['IOR'].default_value=1.333
    foam=material('Aerated waterfall',(.55,.72,.75),.24);principled(foam).inputs['Transmission Weight'].default_value=.25
    wb=Batch();bed=Batch();nx,ny=210,16;vs=[]
    for j in range(ny+1):
        y=ry-river_width/2+j*river_width/ny
        for i in range(nx+1):
            x=-radius+i*2*radius/nx;vs.append((x,y,-.08+.006*math.sin(x*15+y*31)+.002*math.sin(x*39-y*13)))
    wb.mesh(water,vs,[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)],True)
    bed.box(earth,(0,ry,-.31),(radius*2,river_width,.06))
    for i in range(700):
        x=rng.uniform(-radius,radius);y=ry+rng.uniform(-river_width*.45,river_width*.45);r=rng.uniform(.015,.055);bed.ellipsoid(stone,(x,y,-.24),(r,r*.7,r*.4),10,6)
    for sign in [-1,1]:
        for j in range(19):
            y=ry-river_width/2+(j+.5)*river_width/19;edge=math.sqrt(radius**2-y*y)+.24
            points=[]
            for k in range(65):
                t=k/64;points.append((sign*(edge+.19*math.sin(t*math.pi*.8)),y+.02*math.sin(t*38+j),-.08-5.5*t))
            wb.tube(foam if j%4==0 else water,points,[.007+.008*(1-k/65) for k in range(65)],6)
    finish(wb,'Fluid ribbons and ripples',hydro);finish(bed,'Pebble stream',hydro)
    finish(arch,'Architectural craft',craft,.004);finish(plants,'Fine botany',ecology);finish(winter,'Snow and ice',hydro)

    # Refine shared source architecture edges without rounding the whole cliff.
    for o in base.objects:
        if o.type=='MESH' and any(k in o.name for k in ['Aged_oiled_timber','Forged_iron']):
            mod=o.modifiers.new('Softened crafted edges','BEVEL');mod.width=.004;mod.segments=2;mod.limit_method='ANGLE'
    scene,cloud,plane,devices=lighting(theme,dest,PREVIEW)
    if theme=='snow':
        for x in [cx-.88,cx+.88]:
            bpy.ops.object.light_add(type='AREA',location=(x,cy-d/2-.35,1.45));o=bpy.context.object;o.name='Window warm spill';o.data.energy=24;o.data.color=(1,.38,.10);o.data.size=.6;o.rotation_euler=(Vector((x,cy-d/2-2,.4))-o.location).to_track_quat('-Z','Y').to_euler();move(o,bpy.data.collections['90 Presentation only'])
    cam_pos=(radius*1.55,-radius*2.4,radius*1.55);cam_target=(0,0,.85);scale=radius*3.35
    camera(scene,cam_pos,cam_target,scale)
    bpy.ops.file.pack_all();master=dest/'island-master.blend';bpy.ops.wm.save_as_mainfile(filepath=str(master),compress=True)
    report={'theme':theme,'title':{'sakura':'樱花庭院','snow':'雪境木屋','camp':'山岭营地'}[theme],'source':src.relative_to(OUT).as_posix(),'sourceSha256':digest(src),'layoutSha256':digest(snapshot),'masterBytes':master.stat().st_size,'masterSha256':digest(master),'packedImages':sum(bool(im.packed_file) for im in bpy.data.images),'renderer':'Cycles / OptiX','devices':devices,'detail':stats,'collections':{},'modules':[],'webSceneChanged':False,'accountDataRead':False,'units':'metres','masterUpAxis':'Z','glbUpAxis':'Y'}
    for c in [base,craft,ecology,hydro]:
        obs=[o for o in c.objects if o.type=='MESH'];report['collections'][c.name]={'meshes':len(obs),'triangles':sum(len(f.vertices)-2 for o in obs for f in o.data.polygons)}
        for o in obs:
            if not all(math.isfinite(v) for p in o.data.vertices for v in p.co):raise ValueError(o.name)
    report['totalBaseTriangles']=sum(x['triangles'] for x in report['collections'].values())
    if not PREVIEW:
        stage=dest/'client-staging';stage.mkdir(exist_ok=True)
        for name,c in [('landscape',base),('architecture',craft),('vegetation',ecology),('water-snow',hydro)]:
            bpy.ops.object.select_all(action='DESELECT')
            for o in c.objects:o.select_set(True)
            path=stage/(name+'.glb');bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_cameras=False,export_lights=False)
            report['modules'].append({'file':path.relative_to(dest).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)})
    (dest/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    shots=[('01-panorama',cam_pos,cam_target,scale),('02-architecture',(cx+5,cy-8,4.7),(cx,cy,1.65),7.3),('03-plan',(0,0,40),(0,0,0),radius*2.5)]
    if theme=='sakura':shots[1]=('02-architecture',(cx-5,cy-7,4.7),(cx,cy,1.55),7.3)
    if theme=='camp':shots[1]=('02-architecture',(5,-7,7.0),(-.25,3.9,2.55),10.5)
    for name,pos,target,zoom in shots:
        if PREVIEW and name!='01-panorama':continue
        camera(scene,pos,target,zoom);cloud.hide_render=name=='03-plan';plane.hide_render=name!='03-plan'
        scene.render.filepath=str(dest/(name+('-preview' if PREVIEW else '')+'.png'));bpy.ops.render.render(write_still=True)
    print('CINEMATIC_ISLAND_DONE',theme,json.dumps(report,ensure_ascii=False),flush=True)


for theme in THEMES:build(theme)
after_hash={p.relative_to(ROOT).as_posix():digest(p) for p in web_paths}
if before_hash!=after_hash:raise RuntimeError('Production input changed during build; inspect before publishing report')
(OUT/'web-unchanged.json').write_text(json.dumps({'unchanged':True,'sha256':after_hash},ensure_ascii=False,indent=2),encoding='utf-8')
print('ALL_REQUESTED_ISLANDS_COMPLETE',THEMES,flush=True)
