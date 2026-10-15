"""Reproducible, metric botanical meshes. Blender 5.2 -b --python ... -- plants|terrace|render.

Every species has ten above-ground stages; seeds are not counted. Leaf topology,
branch hierarchy and reproductive organs change across stages, not just scale.
Generated material reference maps and procedural normals are packed into .blend.
"""
import bpy, math, random, json, sys
import numpy as np
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch, material
R=Path(__file__).resolve().parents[2]
OUT=R/'static/models/petchat-farm-v1'; ART=R/'art/farm-garden-v1/blender'
OUT.mkdir(parents=True,exist_ok=True); ART.mkdir(parents=True,exist_ok=True)
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'plants'
TAU=math.tau
TEXTURES=R/'art/farm-garden-v1/materials'

class BotanicalBatch(Batch):
    def __init__(self):super().__init__();self.uvs={}
    def tube(self,m,points,radii,n=10):
        if len(points)==3:
            p,q,r=map(Vector,points);ts=np.linspace(0,1,9)
            points=[p*(1-t)**2+q*2*t*(1-t)+r*t*t for t in ts]
            if isinstance(radii,(list,tuple)):radii=[radii[0]*(1-t)**2+radii[1]*2*t*(1-t)+radii[2]*t*t for t in ts]
        super().tube(m,points,radii,n)
    def mesh(self,m,vs,fs,smooth=False,uv=None):
        vs=list(vs); super().mesh(m,vs,fs,smooth)
        self.uvs.setdefault(m,[]).extend(uv if uv is not None else [(v[0]*2,v[2]*2+v[1]) for v in vs])
    def objects(self,prefix):
        obs=super().objects(prefix)
        for o in obs:
            uv=o.data.uv_layers.new(name='BotanicalUV');coords=self.uvs[o.data.materials[0]]
            for p in o.data.polygons:
                for i in p.loop_indices:uv.data[i].uv=coords[o.data.loops[i].vertex_index]
        return obs

def pigment(name,color,kind):
    m=material(name,color,.64 if kind in ('leaf','petal') else .88)
    m.use_backface_culling=False
    n=512;v,u=np.mgrid[0:n,0:n]/(n-1);rng=np.random.default_rng(310)
    if kind=='leaf':
        mid=np.exp(-((u-.5)/.012)**2)
        veins=np.exp(-(np.sin((v-np.abs(u-.5)*.65)*math.pi*9)/.07)**2)
        field=.12*np.sin(v*8)+.20*mid+.12*veins-.10*np.abs(u-.5)+rng.normal(0,.015,(n,n))
    elif kind=='petal':field=.20*np.sin(u*math.pi)-.18*(1-v)**2+.035*np.cos(u*TAU*15)+rng.normal(0,.01,(n,n))
    elif kind=='wood':field=.15*np.sin(u*180+np.sin(v*15)*3)+.09*np.sin(u*390+np.sin(v*35)*2)+rng.normal(0,.04,(n,n))
    elif kind=='bark':field=.12*np.sin(u*120+np.sin(v*27))-.22*(np.sin(v*130+u*23)>.98)+rng.normal(0,.025,(n,n))
    elif kind=='fruit':field=.025*np.sin(u*11+np.sin(v*7))+.018*np.sin(v*17+u*13)+rng.normal(0,.008,(n,n))
    else:field=.1*np.sin(u*28+v*17)*np.cos(v*31)+rng.normal(0,.075,(n,n))
    rgb=np.clip(np.array(color)[None,None,:]*(1+field[:,:,None]),.004,.94)
    im=bpy.data.images.new(name+'_pigment',width=n,height=n)
    im.pixels.foreach_set(np.dstack((rgb,np.ones((n,n)))).astype(np.float32).ravel());im.pack()
    nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');t=nt.nodes.new('ShaderNodeTexImage');t.image=im;nt.links.new(t.outputs['Color'],bs.inputs['Base Color'])
    dy,dx=np.gradient(field);normal=np.dstack((-dx*6,-dy*6,np.ones((n,n))));normal/=np.linalg.norm(normal,axis=2)[:,:,None]
    ni=bpy.data.images.new(name+'_micro_normal',width=n,height=n);ni.colorspace_settings.name='Non-Color'
    ni.pixels.foreach_set(np.dstack((normal*.5+.5,np.ones((n,n)))).astype(np.float32).ravel());ni.pack()
    t=nt.nodes.new('ShaderNodeTexImage');t.image=ni;normalNode=nt.nodes.new('ShaderNodeNormalMap');normalNode.inputs['Strength'].default_value=.38
    nt.links.new(t.outputs['Color'],normalNode.inputs['Color']);nt.links.new(normalNode.outputs['Normal'],bs.inputs['Normal'])
    if kind in ('leaf','petal'):bs.inputs['Subsurface Weight'].default_value=.07
    source={'leaf':'leaf.png','palmate':'pumpkin-leaf.png','clay':'clay.png','loam':'soil.png'}.get(kind)
    if source and (TEXTURES/source).exists():
        im=bpy.data.images.load(str(TEXTURES/source),check_existing=True);im.pack()
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
        nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        # Real exported normal map, not a Cycles-only procedural bump node.
        # Fine multi-scale relief remains restrained; silhouette is actual geometry.
        normalNode.inputs['Strength'].default_value=.12 if kind in ('leaf','clay') else .3
    if kind=='clay':bs.inputs['Roughness'].default_value=.87
    if kind=='loam':bs.inputs['Roughness'].default_value=.98
    if kind=='petal':
        bs.inputs['Roughness'].default_value=.78
        bs.inputs['Subsurface Weight'].default_value=.16
    if kind=='fruit':
        normalNode.inputs['Strength'].default_value=.08
        bs.inputs['Roughness'].default_value=.66
    return m

def palette():
    return dict(leaf=pigment('Leaf_chlorophyll',(.14,.30,.055),'leaf'),palmate=pigment('Pumpkin_palmate_leaf',(.14,.30,.055),'palmate'),young=pigment('Leaf_new_growth',(.27,.40,.09),'leaf'),
                stem=pigment('Stem_fibres',(.18,.27,.07),'bark'),bark=pigment('Young_birch_bark',(.31,.23,.14),'bark'),
                pink=pigment('Cosmos_rose_petals',(.78,.24,.43),'petal'),yellow=pigment('Pumpkin_corolla',(.94,.53,.035),'petal'),
                pollen=material('Pollen_ochre',(.65,.34,.025),.82),fruit=pigment('Pumpkin_rind',(.72,.25,.028),'fruit'),
                greenfruit=pigment('Pumpkin_immature_rind',(.13,.23,.055),'fruit'),vein=material('Leaf_raised_veins',(.26,.36,.10),.8))

def blade(b,m,p,a,L,W,kind='birch',detail=True,tilt=.2):
    """Curved, folded leaf with real edge silhouette, midrib and secondaries."""
    p=Vector(p);forward=Vector((math.cos(a),math.sin(a),tilt));side=Vector((-math.sin(a),math.cos(a),0))
    rows=24 if detail else 8;cols=8 if detail else 2;vs=[];uv=[]
    phase=random.uniform(0,TAU);twist=random.uniform(-.25,.25);skew=random.uniform(-.10,.10)
    for i in range(rows+1):
        t=i/rows;shape=math.sin(math.pi*t)**(.75 if kind=='birch' else .55)
        edge=1-(.075 if kind=='birch' else .015)*(i%2)
        for j in range(cols+1):
            s=2*j/cols-1
            lateral=W*shape*edge*s*(1+skew*s)+W*.10*math.sin(t*4+phase)*t
            fold=W*(twist*s-.12*abs(s))*math.sin(t*math.pi)+L*.018*math.sin(t*13+phase)*abs(s)
            vs.append(p+forward*(L*t)+side*lateral+Vector((0,0,L*(.10*math.sin(t*math.pi)-.25*t*t)+fold)))
            uv.append((j/cols,t))
    faces=[(i*(cols+1)+j,i*(cols+1)+j+1,(i+1)*(cols+1)+j+1,(i+1)*(cols+1)+j) for i in range(rows) for j in range(cols)]
    b.mesh(m,vs,faces,True,uv)
    if detail and W>.012:
        points=[vs[i*(cols+1)+cols//2]+Vector((0,0,.0008)) for i in range(rows+1)]
        b.tube(M['vein'],points,[max(.00012,.00045*(1-i/rows)) for i in range(rows+1)],5)
        for i in range(3,rows-2,4):
            for s in [0,cols]:b.tube(M['vein'],[points[max(0,i-2)],vs[i*(cols+1)+s]+Vector((0,0,.0003))],[.00022,.00008],4)

def cosmos_leaf(b,p,a,L,detail):
    points=[Vector(p)+Vector((math.cos(a)*L*t,math.sin(a)*L*t,.06*math.sin(t*math.pi))) for t in np.linspace(0,1,9)]
    b.tube(M['stem'],points,[.0025*(1-i/10) for i in range(9)],6)
    for j in range(1,8):
        for s in [-1,1]:
            length=L*.38*(1-j/11)*random.uniform(.85,1.12);angle=a+s*random.uniform(.65,1.05)
            blade(b,M['leaf'],points[j],angle,length,.005,'needle',detail,tilt=.12)
            if detail and j<5:
                for k in [1,2]:blade(b,M['leaf'],points[j]+Vector((math.cos(angle),math.sin(angle),.05))*length*k/3,angle+s*.75,length*.35,.003,'needle',False)

def petal(b,p,a,L,W,open_amount,mat,detail):
    p=Vector(p);rows=18 if detail else 7;cols=8 if detail else 4;vs=[];uv=[]
    curl=random.uniform(-.09,.05);twist=random.uniform(-.07,.07);L*=random.uniform(.92,1.08);W*=random.uniform(.91,1.08)
    for i in range(rows+1):
        t=i/rows
        for j in range(cols+1):
            s=j/cols*2-1;edge=(.95+.05*math.cos(s*math.pi*4)) if i==rows else 1
            r=L*t*open_amount*edge;h=L*((1-open_amount)*t+.04*math.sin(t*math.pi)+curl*t*t)
            width=W*(1-math.exp(-t*7))*s
            vs.append(p+Vector((math.cos(a)*r-math.sin(a)*width,math.sin(a)*r+math.cos(a)*width,h+L*(.045*s*s*t+twist*s*t+.009*math.sin(s*16)*t))))
            uv.append((j/cols,t))
    b.mesh(mat,vs,[(i*(cols+1)+j,i*(cols+1)+j+1,(i+1)*(cols+1)+j+1,(i+1)*(cols+1)+j) for i in range(rows) for j in range(cols)],True,uv)

def bloom(b,p,opening,detail,pumpkin=False):
    p=Vector(p);size=.18 if pumpkin else .095;count=5 if pumpkin else 8
    offsets={m:len(data[0]) for m,data in b.data.items()}
    b.ellipsoid(M['young'],p-Vector((0,0,.010)),(.024,.024,.035) if pumpkin else (.018,.018,.018),16,10)
    for k in range(7):blade(b,M['young'],p-Vector((0,0,.02)),k*TAU/7,.05,.009,'needle',detail,tilt=.7)
    if opening<=0:
        b.ellipsoid(M['young'],p+Vector((0,0,.008)),(.015,.015,.019),16,10)
        b.ellipsoid(M['yellow'] if pumpkin else M['pink'],p+Vector((0,0,.020)),(.009,.009,.008),16,10);return
    for k in range(count):petal(b,p,k*TAU/count+random.uniform(-.045,.045),size,size*(.50 if pumpkin else .37),opening,M['yellow'] if pumpkin else M['pink'],detail)
    b.ellipsoid(M['pollen'],p+Vector((0,0,.004)),(.016,.016,.004),20,10)
    for k in range(90 if detail else 18):
        a=k*2.39996;r=.015*math.sqrt(k/(90 if detail else 18));h=.005+.003*(1-r/.016)
        b.ellipsoid(M['yellow'],p+Vector((r*math.cos(a),r*math.sin(a),h)),(.0008,.0008,.0017),5,4)
    normal=Vector((random.uniform(-.3,.3),random.uniform(-.3,.3),1)).normalized();q=Vector((0,0,1)).rotation_difference(normal)
    for m,data in b.data.items():
        for i in range(offsets.get(m,0),len(data[0])):data[0][i]=p+q@(Vector(data[0][i])-p)

def pumpkin_leaf(b,p,a,L,detail):
    p=Vector(p);q=Vector((0,0,1)).rotation_difference(Vector((math.cos(a)*.45,math.sin(a)*.45,1)).normalized())
    rows=9 if detail else 4;cols=70 if detail else 30;vs=[];uv=[]
    for j in range(rows+1):
        r=j/rows
        for k in range(cols):
            t=k*TAU/cols;edge=(.91+.09*math.cos(5*t))*(.985+.015*math.cos(35*t))*(1+.045*math.sin(3*t+a))
            # Five lobes, slight basal sinus, cupped membrane.
            edge*=1-.24*max(0,math.cos(t+math.pi/2))**12
            x=L*r*math.cos(t)*edge;y=L*r*math.sin(t)*edge
            vs.append(p+q@Vector((x,y,L*(-.21*r*r+.045*math.cos(t*5)*r+.035*math.sin(t*3+a)*r*r))))
            uv.append((.5+x/(2*L),.5+y/(2*L)))
    b.mesh(M['palmate'],vs,[(j*cols+k,j*cols+(k+1)%cols,(j+1)*cols+(k+1)%cols,(j+1)*cols+k) for j in range(rows) for k in range(cols)],True,uv)
    if detail:
        for k in range(5):
            t=k*TAU/5;points=[p+q@Vector((L*r*math.cos(t),L*r*math.sin(t),-L*.18*r*r+.001)) for r in np.linspace(0,.95,9)]
            b.tube(M['vein'],points,[.0009*(1-j/10) for j in range(9)],5)
            for j in [3,5,7]:
                for s in [-1,1]:
                    target=p+q@Vector((L*(j/9+.12)*math.cos(t+s*.25),L*(j/9+.12)*math.sin(t+s*.25),-L*.18*(j/9+.12)**2+.001))
                    b.tube(M['vein'],[points[j],target],[.00035,.0001],4)

def fruit(b,p,r,mature,detail):
    p=Vector(p);n=64 if detail else 32;rows=40 if detail else 18;vs=[];uv=[]
    for j in range(rows+1):
        t=j*math.pi/rows
        for k in range(n):
            a=k*TAU/n;rr=r*math.sin(t)*(.94+.06*math.cos(a*10));z=r*.83*math.cos(t)
            vs.append(p+Vector((rr*math.cos(a),rr*math.sin(a),z)));uv.append((k/n,j/rows))
    b.mesh(M['fruit'] if mature else M['greenfruit'],vs,[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(rows) for k in range(n)],True,uv)
    stem=[p+Vector((0,0,r*.78)),p+Vector((.006,0,r*.99)),p+Vector((.02,.015,r*1.10))]
    b.tube(M['bark'] if mature else M['stem'],stem,[r*.09,r*.065,r*.05],12)

def plant(spec,stage,detail=True):
    b=BotanicalBatch();random.seed(941);s=stage
    if spec=='cosmos':
        h=[.035,.065,.10,.16,.25,.36,.48,.58,.67,.78][s-1]
        trunk=[(math.sin(t*3)*.016,t*.012,h*t) for t in np.linspace(0,1,14)]
        b.tube(M['stem'],trunk,[.0035+(1-t)*.004*(s/10) for t in np.linspace(0,1,14)],10)
        if s<5:
            for a in [0,math.pi]:blade(b,M['young'],(0,0,h*.4),a,.025+s*.004,.009,'cotyledon',detail)
        if s>=2:
            for j in range(1,min(7,s+1)):
                t=j/(min(7,s+1)+1)
                for side in [0,1]:cosmos_leaf(b,(.012,0,h*t),j*2.4+side*math.pi,.035+.018*s,detail)
        branches=max(0,s-4)
        tips=[Vector(trunk[-1])]
        for j in range(branches):
            a=j*2.399+.11*math.sin(j*5);t=.32+j*.07;start=Vector((.012,0,h*t));end=start+Vector((math.cos(a)*.045*s,math.sin(a)*.045*s,h*(.37+.09*math.sin(j*3.1))))
            control=start.lerp(end,.57)-Vector((0,0,h*.14));path=[start,control,end];b.tube(M['stem'],path,[.004,.003,.0015],8);tips.append(end)
            for k in [1,2]:
                t=k/3;point=start*(1-t)**2+control*2*t*(1-t)+end*t*t
                cosmos_leaf(b,point,a+1.3,.018*s,detail)
        if s>=7:
            for j,p in enumerate(tips):bloom(b,p,0 if s<9 or j%3==2 else .42 if s==9 else .95,detail)
    elif spec=='pumpkin':
        extent=[.04,.06,.10,.17,.28,.40,.55,.65,.76,.83][s-1]
        if s<=3:
            b.tube(M['stem'],[(0,0,0),(.004,0,.045+s*.015)],[.006,.004],10)
            for a in [0,math.pi]:blade(b,M['young'],(.004,0,.045+s*.015),a,.045,.021,'cotyledon',detail,tilt=.12)
        branches=1 if s<6 else 2
        for branch in range(branches):
            a=branch*2.65;nodes=max(2,s);path=[Vector((math.cos(a)*extent*t,math.sin(a)*extent*t+.07*math.sin(t*6),.03+.015*math.sin(t*5))) for t in np.linspace(0,1,nodes)]
            b.tube(M['stem'],path,[.012*(1-j/(nodes+2)) for j in range(nodes)],12)
            if s>=2:
                for j in range(1,nodes):
                    p=path[j];angle=a+j*2.4+.12*math.sin(j*5);L=min(.21,.025+s*.018)*(1-.3*j/nodes)*(.88+random.random()*.22);top=p+Vector((math.cos(angle)*L*.4,math.sin(angle)*L*.4,.07+.012*s+.018*math.sin(j*2)))
                    b.tube(M['stem'],[p,p.lerp(top,.6),top],[.006,.004,.002],8);pumpkin_leaf(b,top,angle,L,detail)
                    if s>=5:
                        points=[p+Vector((.12*t,.02*math.sin(t*TAU*3)*t,.07*t+.02*math.cos(t*TAU*3)*t)) for t in np.linspace(0,1,35 if detail else 16)]
                        b.tube(M['young'],points,.0018,5)
            if s>=7:
                p=path[-2]+Vector((0,.1,.12));b.tube(M['stem'],[path[-2],p],[.008,.005],8);bloom(b,p,0 if s==7 else .85,detail,True)
        if s>=9:
            r=.14 if s==9 else .24;p=Vector((extent*.5,-.22,r*.83));fruit(b,p,r,s==10,detail)
            b.tube(M['stem'],[Vector((extent*.42,0,.035)),p+Vector((0,.18,r*.9)),p+Vector((.02,.015,r*1.10))],[.012,.014,.012],10)
    else:
        h=[.035,.07,.13,.22,.35,.53,.77,1.02,1.36,1.75][s-1]
        trunk=[Vector((.035*math.sin(t*4)*s/10,.025*math.sin(t*5),h*t)) for t in np.linspace(0,1,18)]
        b.tube(M['stem'] if s<6 else M['bark'],trunk,[.002+(1-t)*.027*(s/10)**2 for t in np.linspace(0,1,18)],14)
        if s==1:
            for a in [0,math.pi]:blade(b,M['young'],(0,0,h*.7),a,.022,.008,'cotyledon',detail)
        else:
            for j in range(2,min(15,s*2)):
                p=trunk[j];a=j*2.399;L=.026+min(s,6)*.009
                blade(b,M['young'] if j%4==0 else M['leaf'],p,a,L,L*.42,'birch',detail)
        for j in range(max(0,s-4)):
            t=.28+j*.095;a=j*2.399;start=Vector((.035*math.sin(t*4)*s/10,.025*math.sin(t*5),h*t));end=start+Vector((math.cos(a)*h*(.28-.018*j),math.sin(a)*h*(.28-.018*j),h*(.15+random.uniform(-.035,.07))))
            control=start.lerp(end,.55)+Vector((0,0,h*.09));b.tube(M['bark'],[start,control,end],[.011*s/10,.005*s/10,.0015],9)
            for k in range(1,7):
                t=k/6;q=start*(1-t)**2+control*2*t*(1-t)+end*t*t;angle=a+(-1 if k%2 else 1)*random.uniform(.5,1.2);tip=q+Vector((math.cos(angle)*h*.12,math.sin(angle)*h*.12,h*random.uniform(-.025,.05)))
                mid=q.lerp(tip,.5)+Vector((0,0,h*.02));b.tube(M['bark'],[q,mid,tip],[.003,.0018,.0005],6)
                for u in range(1,5):
                    t=u/4;pos=q*(1-t)**2+mid*2*t*(1-t)+tip*t*t;L=.065+random.random()*.025;la=angle+(-1 if u%2 else 1)*.9
                    blade(b,M['leaf'] if u<4 else M['young'],pos,la,L,L*(.35+random.random()*.13),'birch',detail,tilt=random.uniform(-.15,.55) if u<4 else .8)
        if s>=4:
            for j in range(3):
                p=trunk[-1]-Vector((0,0,.026*j));blade(b,M['young'],p,j*2.4,.04,.017,'birch',detail,tilt=.35)
        if s>=6:
            # Small lenticels and lateral buds: no adult peeling bark on seedlings.
            for j in range(16 if detail else 5):
                z=h*.7*j/16;a=j*2.4;r=.002+.027*(s/10)**2*(1-z/h)
                b.tube(M['vein'],[(r*math.cos(a+t),r*math.sin(a+t),z) for t in [-.15,0,.15]],.0005,4)
    return b.objects(spec+'_stage_'+str(stage).zfill(2)+('_near' if detail else '_far'))

def export(obs,path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)

def soil_surface(b,m,x,y,z,w,d,circular=False,density=1):
    """Uneven loam with irregular aggregates, rather than a flat slab of pebbles."""
    nx=max(12,int(w*38));ny=max(12,int(d*38));vs=[];uv=[];faces=[]
    for j in range(ny+1):
        for i in range(nx+1):
            u=i/nx;v=j/ny;px=(u-.5)*w;py=(v-.5)*d
            relief=.004*math.sin(px*21+py*8)+.003*math.cos(py*37-px*13)+random.uniform(-.003,.003)
            vs.append((x+px,y+py,z+relief));uv.append((px*2.1,py*2.1))
    for j in range(ny):
        for i in range(nx):
            if circular and ((i+.5)/nx*2-1)**2+((j+.5)/ny*2-1)**2>.94:continue
            a=j*(nx+1)+i;faces.extend([(a,a+1,a+nx+2),(a,a+nx+2,a+nx+1)])
    if circular:
        vs=[];uv=[];faces=[];rings=16;n=96
        for j in range(rings+1):
            r=j/rings
            for k in range(n):
                a=k*TAU/n;px=w*.5*r*math.cos(a);py=d*.5*r*math.sin(a)
                vs.append((x+px,y+py,z+.003*math.sin(px*31+py*24)*r+random.uniform(-.0015,.0015)*r));uv.append((px*2.1,py*2.1))
        faces=[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(rings) for k in range(n)]
    b.mesh(m,vs,faces,True,uv)
    grit=material('Loam_small_mineral_grains',(.17,.13,.085),.96)
    fibre=material('Loam_organic_fragments',(.105,.067,.032),.98)
    for k in range(int(w*d*470*density)):
        px=random.uniform(-w*.48,w*.48);py=random.uniform(-d*.48,d*.48)
        if circular and (px/(w/2))**2+(py/(d/2))**2>.89:continue
        radius=random.uniform(.0025,.014)*(1.8 if k%19==0 else 1);verts=[];n=9;rings=5
        for j in range(rings+1):
            t=j*math.pi/rings
            for i in range(n):
                a=i*TAU/n;rr=radius*random.uniform(.7,1.25)
                verts.append((x+px+rr*math.sin(t)*math.cos(a),y+py+rr*math.sin(t)*math.sin(a),z+rr*.65*math.cos(t)))
        fs=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(rings) for i in range(n)]
        b.mesh(grit if k%23==0 else m,verts,fs,True)
        if k%21==0:
            b.tube(fibre,[(x+px,y+py,z+.005),(x+px+.01,y+py+.006,z+.008),(x+px+.026,y+py+.008,z+.006)],.0009,4)

def lathe(b,m,profile,n=96):
    vs=[];uv=[]
    for j,(r,z) in enumerate(profile):
        for k in range(n+1):
            a=k*TAU/n
            rr=r+(.0007*math.sin(3*a+.3)+.0004*math.sin(11*a+z*27))*(r/.23)
            vs.append((rr*math.cos(a),rr*math.sin(a),z+.0006*math.sin(a*2)*r/.23))
            # Arc-length coordinate avoids stretched radial streaks on saucer floors.
            distance=sum(math.hypot(profile[t][0]-profile[t-1][0],profile[t][1]-profile[t-1][1]) for t in range(1,j+1))
            uv.append((k/n,distance*2.4))
    b.mesh(m,vs,[(j*(n+1)+k,j*(n+1)+k+1,(j+1)*(n+1)+k+1,(j+1)*(n+1)+k) for j in range(len(profile)-1) for k in range(n)],True,uv)

def make_pot(clay,earth):
    b=BotanicalBatch()
    # Closed thick-wall section around a genuine drainage opening, rounded rolled rim.
    profile=[(.018,.015),(.12,.015),(.139,.018),(.146,.025),(.148,.04)]
    profile += [(.148+.055*t+.001*math.sin(t*52),.04+.267*t) for t in np.linspace(0,1,25)]
    profile += [(.214,.309),(.222,.315),(.225,.325),(.223,.338),(.217,.345),(.205,.347),(.196,.342),(.191,.332),(.190,.311)]
    profile += [(.134+.056*t,.054+.257*t) for t in np.linspace(1,0,17)]
    profile += [(.12,.047),(.018,.047),(.018,.015)]
    lathe(b,clay,profile)
    # Separate concave saucer and its thick rounded edge.
    lathe(b,clay,[(0,-.012),(.231,-.012),(.246,-.006),(.253,.009),(.253,.032),(.248,.040),(.240,.040),(.233,.018),(.22,.004),(0,.004)])
    soil_surface(b,earth,0,0,.288,.373,.373,True,2.5)
    return b.objects('Farm_pot')

def material_detail():
    """Close-up validation render using the same mesh functions as shipped GLBs."""
    global M
    bpy.ops.wm.read_factory_settings(use_empty=True);M=palette();random.seed(811)
    clay=pigment('Garden_terracotta',(.47,.23,.12),'clay');earth=pigment('Garden_friable_soil',(.075,.047,.026),'loam')
    make_pot(clay,earth)
    for o in plant('cosmos',10,True):o.location.z=.29;o.scale=(.8,)*3
    floor=material('Neutral_warm_studio',(.24,.245,.20),.93)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.014));bpy.context.object.data.materials.append(floor)
    scene=camera((0,0,.53),(1.5,-2,1.15),1.5,1500,1500);scene.cycles.samples=96
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/'pot-botanical-detail.blend'),compress=True)
    scene.render.filepath=str(ART/'pot-botanical-detail.png');bpy.ops.render.render(write_still=True)
    scene.camera.location=(.8,-1,1.4);target=Vector((0,0,.23));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=.66
    for o in bpy.data.objects:
        if o.name.startswith('cosmos'):o.hide_render=True
    scene.render.filepath=str(ART/'pot-soil-macro.png');bpy.ops.render.render(write_still=True)

def subtract_convex(poly,mask):
    """Partition a polygon outside a CCW convex mask, without overlapping pieces."""
    remaining=poly;result=[]
    for a,c in zip(mask,mask[1:]+mask[:1]):
        if not remaining:break
        inside=[];outside=[]
        def distance(p):return (c[0]-a[0])*(p[1]-a[1])-(c[1]-a[1])*(p[0]-a[0])
        for p,q in zip(remaining,remaining[1:]+remaining[:1]):
            dp,dq=distance(p),distance(q)
            (inside if dp>=0 else outside).append(p)
            if (dp>=0)!=(dq>=0):
                t=dp/(dp-dq);cross=tuple(p[i]+t*(q[i]-p[i]) for i in range(3));inside.append(cross);outside.append(cross)
        if len(outside)>=3:result.append(outside)
        remaining=inside
    return result

def exposed_floor(b,mat,polygon,masks):
    pieces=[polygon]
    for mask in masks:pieces=[part for poly in pieces for part in subtract_convex(poly,mask)]
    for poly in pieces:
        area=sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(poly,poly[1:]+poly[:1]))
        if abs(area)>1e-9:b.mesh(mat,poly,[tuple(range(len(poly)))])

def camera(target,pos,scale,width,height):
    scene=bpy.context.scene;bpy.ops.object.camera_add(location=pos);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;scene.camera=cam
    for p,power,size in [((0,-5,8),1100,7),((-5,0,5),850,6),((4,6,9),1400,5)]:
        bpy.ops.object.light_add(type='AREA',location=p);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Soft botanical daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.60,.55,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
    scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
        for d in prefs.devices:d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
    except Exception:pass
    scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX';scene.render.film_transparent=False
    return scene

def build_plants():
    global M
    report={}
    for spec in ['cosmos','pumpkin','birch']:
        bpy.ops.wm.read_factory_settings(use_empty=True);M=palette();stages=[];report[spec]=[]
        for s in range(1,11):
            near=plant(spec,s,True);far=plant(spec,s,False)
            for o in near+far:o['farm_species']=spec;o['farm_stage']=s
            for obs,suffix in [(near,''),(far,'-lod')]:export(obs,OUT/f'{spec}-{s:02}{suffix}.glb')
            count=lambda obs:sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in obs)
            report[spec].append(dict(stage=s,triangles=count(near),lodTriangles=count(far),bytes=(OUT/f'{spec}-{s:02}.glb').stat().st_size,meshes=len(near)))
            for o in far:bpy.data.objects.remove(o,do_unlink=True)
            x=(s-1)%5*2.2;y=0 if s<=5 else -2.7
            for o in near:o.location.x+=x;o.location.y+=y
            stages+=near
        bpy.ops.wm.save_as_mainfile(filepath=str(ART/f'{spec}-growth.blend'),compress=True)
        # Real renders of actual exported shapes, all specimens share metre scale.
        ground=material('Studio_ground',(.72,.72,.65),.85);bpy.ops.mesh.primitive_plane_add(size=200,location=(4,-1,-.015));bpy.context.object.data.materials.append(ground)
        for s in range(1,11):
            bpy.ops.object.text_add(location=((s-1)%5*2.2-.3,(0 if s<=5 else -2.7)-.7,.005));o=bpy.context.object;o.data.body=f'{s:02}';o.data.size=.14;o.data.extrude=.001;o.data.materials.append(M['bark'])
        scene=camera((4.2,-1.1,.35),(4.2,-10,7),11.5,1800,1050);scene.render.filepath=str(ART/f'{spec}-ten-stages.png');bpy.ops.render.render(write_still=True)
        # Additional real close-up: no concept image is used as evidence of modeling.
        late=[o for o in stages if o.get('farm_stage')==10]
        for o in stages:
            if o not in late:o.hide_render=True
        for o in bpy.data.objects:
            if o.type=='FONT':o.hide_render=True
        points=[o.matrix_world@Vector(c) for o in late for c in o.bound_box];lo=Vector(tuple(min(p[i] for p in points) for i in range(3)));hi=Vector(tuple(max(p[i] for p in points) for i in range(3)));target=(lo+hi)/2
        span=max(hi-lo);scene.camera.location=target+Vector((span*1.1,-span*2,span*.8));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=span*1.5
        scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.filepath=str(ART/f'{spec}-detail.png');bpy.ops.render.render(write_still=True)
        print('FARM_SPECIES_COMPLETE',spec,flush=True)
    (ART/'asset-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

def build_terrace():
    global M
    bpy.ops.wm.read_factory_settings(use_empty=True);M=palette();b=BotanicalBatch();random.seed(811)
    layout=json.loads((R/'static/data/farm-layout.json').read_text());t=layout['terrace'];cx,cy=t['x'],-t['z'];rx,ry=t['rx'],t['rz']
    e=layout['entry'];ex,ey,ew,ed=e['x'],-e['z'],e['w']/2,e['d']/2
    entry_mask=[(ex-ew,ey-ed),(ex+ew,ey-ed),(ex+ew,ey+ed),(ex-ew,ey+ed)]
    # Match the original forest-floor rim's 384-sided footprint exactly.
    original_mask=[(7.84*math.cos(k*TAU/384),7.84*math.sin(k*TAU/384)) for k in range(384)]
    stone=pigment('Garden_weathered_limestone',(.39,.40,.33),'soil');earth=pigment('Garden_friable_soil',(.075,.047,.026),'loam');wood=pigment('Garden_oiled_larch',(.29,.17,.078),'wood');gravel=pigment('Garden_fine_gravel',(.36,.36,.24),'soil');iron=material('Garden_patinated_iron',(.055,.085,.068),.48,.7);clay=pigment('Garden_terracotta',(.47,.23,.12),'clay');brass=material('Garden_brass',(.43,.31,.10),.35,.72)
    # The established island's photographed stone keeps the new masonry consistent.
    stone_image=R/'art/mistwood-v1/limestone-albedo.png'
    if stone_image.exists():
        image=bpy.data.images.load(str(stone_image),check_existing=True);image.pack();nt=stone.node_tree;tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image;nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
    # Irregular cliff rings; upper walking surface remains level and generous.
    vs=[];fs=[];n=160
    for j in range(10):
        h=-j*.36
        for k in range(n):
            a=k*TAU/n;factor=1-j*.055+.018*math.sin(a*13+j*.4);vs.append((cx+rx*factor*math.cos(a),cy+ry*factor*math.sin(a),.025+h))
    for j in range(9):
        for k in range(n):a=j*n+k;c=j*n+(k+1)%n;fs.append((a,c,c+n,a+n))
    b.mesh(stone,vs,fs,True)
    for j in range(82):
        y0=cy-ry+j*.1;y1=y0+.1
        extent=min(math.sqrt(max(0,1-((y0-cy)/ry)**2)),math.sqrt(max(0,1-((y1-cy)/ry)**2)))*rx
        nx=max(1,math.ceil(extent*2/.1))
        for i in range(nx):
            x0=cx-extent+2*extent*i/nx;x1=cx-extent+2*extent*(i+1)/nx
            if x1>-8.1 and -2.5<y0<-1.1:continue
            exposed_floor(b,gravel,[(x0,y0,.03),(x1,y0,.03),(x1,y1,.03),(x0,y1,.03)],[entry_mask,original_mask])
    for j in range(160):
        a=random.uniform(0,TAU);h=random.uniform(-3,-.15);f=1+h*.15
        b.ellipsoid(stone,(cx+rx*f*math.cos(a),cy+ry*f*math.sin(a),h),(.28+random.random()*.3,.22+random.random()*.2,.12+random.random()*.22),12,7)
    # The support sits below ground. Only the exposed connector gets a top face:
    # never draw a second ground sheet over the original lawn or farm gravel.
    b.box(stone,(ex,ey,-.055),(e['w'],e['d'],.09))
    exposed_floor(b,stone,[(x,y,.03) for x,y in entry_mask],[original_mask])
    for z in [3.65,7.45]:
        for x in np.linspace(-7.2,-5.2,12):b.tube(iron,[(x,-z,.04),(x,-z,.70)],.016,8)
        b.tube(iron,[(-7.2,-z,.72),(-5.2,-z,.72)],.028,12)
    for bed in layout['beds']:
        x,y,w,d=bed['x'],-bed['z'],bed['w'],bed['d']
        for side in [-1,1]:
            for z in [.11,.24]:b.box(wood,(x,y+side*d/2,z),(w+.1,.075,.12))
            for z in [.11,.24]:b.box(wood,(x+side*w/2,y,z),(.075,d,.12))
            for sy in [-1,1]:
                b.box(wood,(x+side*w/2,y+sy*d/2,.19),(.11,.11,.34))
                for z in [.12,.26]:b.ellipsoid(iron,(x+side*w/2,y+sy*(d/2+.055),z),(.012,.005,.012),8,6)
        b.box(earth,(x,y,.115),(w-.07,d-.07,.20))
        soil_surface(b,earth,x,y,.226,w-.08,d-.08)
        b.box(wood,(x,y-d*.37,.43),(.05,.022,.30));b.box(wood,(x,y-d*.37,.53),(.23,.025,.12))
    # Potting table, peg shelf, drawers, visible joinery and tool hooks.
    x,y=-8.8,-1.55
    for dx in [-.9,.9]:
        for dy in [-.26,.26]:b.box(wood,(x+dx,y+dy,.43),(.09,.09,.86))
    for z in [.16,.88,1.38]:
        for dy in [-.25,-.125,0,.125,.25]:b.box(wood,(x,y+dy,z),(2.1,.115,.065))
    for dx in [-.96,.96]:b.box(wood,(x+dx,y+.29,1.13),(.06,.06,.61))
    for dx in [-.65,0,.65]:
        b.box(wood,(x+dx,y-.27,.73),(.59,.05,.21));b.tube(brass,[(x+dx-.06,y-.31,.73),(x+dx+.06,y-.31,.73)],.009,8)
    for dx in [-.7,-.4,.4,.7]:
        b.tube(wood,[(x+dx,y+.31,1.04),(x+dx,y+.31,1.27)],.014,9)
        b.ellipsoid(iron,(x+dx,y+.31,1.02),(.038,.008,.055),12,7)
    # Shelved produce cabinet with slatted doors and a small tiled roof.
    x,y=-11,-1.65
    for dx in [-.43,.43]:b.box(wood,(x+dx,y,.72),(.075,.65,1.42))
    for z in [.08,.48,.92,1.42]:b.box(wood,(x,y,z),(.9,.65,.065))
    b.box(wood,(x,y+.30,.72),(.86,.05,1.4))
    for i in range(10):b.box(wood,(x-.4+i*.088,y-.31,.39),(.077,.035,.56))
    b.tube(brass,[(x+.17,y-.35,.38),(x+.24,y-.35,.38)],.012,10)
    for dx in [-.23,.23]:
        b.box(wood,(x+dx,y,.69),(.36,.49,.25))
        for j in range(4):b.box(wood,(x+dx,y-.25,.59+j*.055),(.36,.025,.035))
    for side in [-1,1]:
        for i in range(6):b.box(stone,(x+side*(i+.5)*.085,y,1.57-i*.027),(.085,.80,.05))
    # Individual paving stones and iron perimeter retain safe clear paths.
    for k in range(120):
        a=k*TAU/120;px=cx+(rx-.18)*math.cos(a);py=cy+(ry-.18)*math.sin(a)
        if abs(px-e['x'])<e['w']/2+.05 and abs(py+e['z'])<e['d']/2+.05:continue
        b.box(stone,(px,py,.13),(.25,.23,.21),a+math.pi/2)
        if k%3==0:b.tube(iron,[(px,py,.23),(px,py,.76)],.015,8)
        p2=(cx+(rx-.18)*math.cos(a+TAU/120),cy+(ry-.18)*math.sin(a+TAU/120),.78)
        b.tube(iron,[(px,py,.78),p2],.024,10)
    for row in range(35):
        for col in range(26):
            px=-13.5+col*.27;py=-8+row*.19
            if ((px-cx)/(rx-.4))**2+((py-cy)/(ry-.4))**2>1:continue
            if px>-8.1 and -2.5<py<-1.1:continue
            if math.hypot(px,py)<7.84+.16:continue
            if abs(px-ex)<ew+.16 and abs(py-ey)<ed+.12:continue
            if any(abs(px-bed['x'])<bed['w']/2+.16 and abs(py+bed['z'])<bed['d']/2+.16 for bed in layout['beds']):continue
            if random.random()<.36:continue
            b.box(stone,(px+random.uniform(-.02,.02),py,.043),(.24,.16,.018),random.uniform(-.08,.08))
    terrace=b.objects('Farm_terrace')
    for o in terrace:
        if o.data.materials[0]==wood:
            mod=o.modifiers.new('Rounded woodworking edges','BEVEL');mod.width=.009;mod.segments=3
    # Wheel-thrown pots have real hollow rims, interior soil and drainage saucers.
    pots=make_pot(clay,earth);export(pots,OUT/'flowerpot.glb')
    for k,(x,y,z) in enumerate([(-9.45,-1.55,.925),(-9.1,-1.55,.925),(-8.3,-1.55,.925),(-9.2,-1.55,1.425),(-8.6,-1.55,1.425),(-7.2,-6.6,.035),(-11.7,-2.0,.035)]):
        scale=.48 if k<5 else 1
        for src in pots:
            o=src.copy();o.data=src.data;bpy.context.collection.objects.link(o);o.location=(x,y,z);o.scale=(scale,)*3;terrace.append(o)
        if k>=5:
            for o in plant('cosmos',10,False):o.location=(x,y,z+.29);o.scale=(.7,)*3;terrace.append(o)
    export(terrace,OUT/'terrace.glb')
    for o in pots:o.hide_render=True;o.hide_set(True)
    # Import existing conservatory; trim only the join's low masonry faces.
    bpy.ops.object.select_all(action='DESELECT');bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-mistwood-v1/mistwood.glb'))
    original=list(bpy.context.selected_objects)
    import bmesh
    for o in original:
        if o.type!='MESH':continue
        bm=bmesh.new();bm.from_mesh(o.data);remove=[]
        for face in bm.faces:
            p=o.matrix_world@face.calc_center_median()
            if -7<p.x<-3.4 and -7.2<p.y<-3.6 and .065<p.z<.65 and 7.35<math.hypot(p.x,p.y)<7.82:remove.append(face)
        bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(o.data);bm.free()
    export(original+terrace,OUT/'mistwood-farm.glb')
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/'farm-island.blend'),compress=True)
    # Preview planted composition, independent from real account inventory.
    for i,bed in enumerate(layout['beds']):
        obs=plant('birch' if bed.get('nursery') else 'cosmos' if i%2 else 'pumpkin',10,True)
        for o in obs:o.location=(bed['x'],-bed['z'],.23)
    scene=camera((-3,-1,1),(16,-28,22),30,1800,1350)
    scene.render.filepath=str(ART/'farm-island-preview.png');bpy.ops.render.render(write_still=True)
    scene.camera.location=(-16,-13,9);target=Vector((-9.5,-4.7,.8));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=11
    scene.render.filepath=str(ART/'farm-closeup.png');bpy.ops.render.render(write_still=True)
    print('FARM_TERRACE_COMPLETE',flush=True)

if MODE=='plants':build_plants()
elif MODE=='terrace':build_terrace()
elif MODE=='detail':material_detail()
else:raise ValueError('Use plants, terrace or detail')
