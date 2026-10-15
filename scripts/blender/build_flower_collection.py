"""Ten botanical silhouettes, ten structural stages, mature dream cultivars and LODs.
Blender -b --python scripts/blender/build_flower_collection.py [-- species]
All images in art/flower-collection-v1 are renders of the shipped geometry.
"""
import bpy, math, random, sys, json
from pathlib import Path
from mathutils import Vector
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
import build_farm_garden as B
from shepherd_geometry import material
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/models/petchat-farm-v1';ART=ROOT/'art/flower-collection-v1'
ART.mkdir(parents=True,exist_ok=True)
CAT=json.loads((ROOT/'static/data/farm-flowers.json').read_text(encoding='utf-8'))
TAU=math.tau

def skin(name,base,tip,leaf=False,dream=False):
    m=material(name,base,.68);m.use_backface_culling=False
    n=192;v,u=np.mgrid[0:n,0:n]/(n-1)
    stripes=.025*np.cos(u*TAU*(17 if leaf else 23))+.016*np.sin(v*21+u*33)
    veins=.1*np.exp(-((u-.5)/.015)**2) if leaf else .025*np.sin(u*TAU*9+v*3)
    mix=v**1.5;rgb=np.array(base)[None,None,:]*(1-mix[:,:,None])+np.array(tip)[None,None,:]*mix[:,:,None]
    rgb=np.clip(rgb*(1+stripes[:,:,None]+veins[:,:,None]),.005,1)
    im=bpy.data.images.new(name+'_pigment',width=n,height=n);im.pixels.foreach_set(np.dstack((rgb,np.ones((n,n)))).astype(np.float32).ravel());im.pack()
    nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im;nt.links.new(tex.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Subsurface Weight'].default_value=.12
    if dream:nt.links.new(tex.outputs['Color'],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.12
    return m

def palette(c,dream):
    base=c['variantColor'] if dream else c['color'];tip=c['variantTip'] if dream else [min(1,x*1.18+.05) for x in base]
    return dict(stem=material('stem_fibres',(.13,.24,.065),.86),leaf=skin('leaf_veins',(.065,.16,.035),(.23,.34,.10),True),young=skin('young_leaf',(.18,.31,.07),(.34,.43,.14),True),vein=material('raised_midveins',(.28,.38,.12),.8),petal=skin(c['id']+'_petal',base,tip,dream=dream),pollen=material('pollen_granules',(.91,.54,.08),.88),heart=material('receptacle',(.19,.085,.027),.9))

def petal(b,p,a,L,W,opening,m,detail,form='oval'):
    """Folded membrane: tapered base, pointed/rounded apex, radial ribs and ruffle."""
    rows=(8 if detail else 3) if form=='floret' else (16 if detail else 6);cols=(4 if detail else 2) if form=='floret' else (8 if detail else 3);p=Vector(p);vs=[];uv=[];phase=random.random()*6
    for i in range(rows+1):
        t=i/rows;profile=math.sin(math.pi*t)**(.38 if form=='round' else .7)
        for j in range(cols+1):
            q=j/cols*2-1;w=W*profile*q
            r=L*t*opening
            z=L*((1-opening)*t+.18*math.sin(math.pi*t)+.10*q*q*t+.023*math.sin(q*14+phase)*abs(q)*t)
            if form=='reflex':z-=L*.65*t*t
            if form=='rolled':z+=W*.55*q*q
            vs.append(p+Vector((r*math.cos(a)-w*math.sin(a),r*math.sin(a)+w*math.cos(a),z)))
            uv.append((j/cols,t))
    fs=[(i*(cols+1)+j,i*(cols+1)+j+1,(i+1)*(cols+1)+j+1,(i+1)*(cols+1)+j) for i in range(rows) for j in range(cols)]
    b.mesh(m,vs,fs,True,uv)

def _florets(b,p,r,opening,M,detail,form):
    p=Vector(p)
    # Green involucre and five pointed sepals remain visible below every corolla.
    if form not in ('cluster','spike'):
        b.ellipsoid(M['young'],p-Vector((0,0,.009)),(r*.22,r*.22,r*.14),10,6)
        for k in range(5):petal(b,p-Vector((0,0,.01)),k*TAU/5,r*.47,r*.09,.8,M['leaf'],False,'reflex')
    if opening<=0:
        b.ellipsoid(M['petal'],p+Vector((0,0,r*.24)),(r*.24,r*.24,r*.4),14,10);return
    if form in ('rose','dahlia'):
        layers=5 if form=='rose' else 6
        for layer in range(layers):
            count=7+layer*3;length=r*(.31+layer*.14)
            for k in range(count):petal(b,p+Vector((0,0,r*(.32-layer*.055))),k*TAU/count+layer*.53,length,length*(.55 if form=='rose' else .24),opening*(.35+layer*.13),M['petal'],detail,'round' if form=='rose' else 'rolled')
    elif form=='cup':
        for layer in range(2):
            for k in range(3):petal(b,p,k*TAU/3+layer*math.pi/3,r,r*.53,.34*opening,M['petal'],detail,'round')
    elif form=='iris':
        for k in range(3):
            a=k*TAU/3;petal(b,p,a,r,r*.39,opening,M['petal'],detail,'reflex');petal(b,p,a+.6,r*.85,r*.28,.28,M['petal'],detail,'round')
            for j in range(12 if detail else 4):
                t=j/12;b.ellipsoid(M['pollen'],p+Vector((math.cos(a)*r*t,math.sin(a)*r*t,-r*.48*t*t+.008)),(.0015,.0015,.004),5,4)
    elif form=='bell':
        # Continuous five-lobed hanging bell, not disconnected flat petals.
        ns=40 if detail else 15;nr=16 if detail else 6;vs=[];uv=[]
        for j in range(nr+1):
            t=j/nr
            for k in range(ns):
                a=k*TAU/ns;rr=r*(.14+.33*math.sin(math.pi*t*.9)+.23*t**4)*opening
                vs.append(p+Vector((rr*math.cos(a),rr*math.sin(a),-r*(t+.07*math.cos(a*5)*t**5))))
                uv.append((k/ns,t))
        b.mesh(M['petal'],vs,[(j*ns+k,j*ns+(k+1)%ns,(j+1)*ns+(k+1)%ns,(j+1)*ns+k) for j in range(nr) for k in range(ns)],True,uv)
    else:
        count={'sun':26,'daisy':24,'poppy':4,'cluster':4,'spike':5}[form]
        for k in range(count):petal(b,p,k*TAU/count,r,r*(.86 if form=='poppy' else .42 if form=='cluster' else .13 if form in ('sun','daisy') else .38),opening,M['petal'],detail,'floret' if form in ('cluster','spike') else 'round')
    if form not in ('rose','dahlia','bell'):
        disk=r*(.40 if form=='sun' else .23 if form=='daisy' else .12)
        b.ellipsoid(M['heart'] if form in ('sun','poppy') else M['pollen'],p+Vector((0,0,.005)),(disk,disk,disk*.35),6 if form in ('cluster','spike') else 16,4 if form in ('cluster','spike') else 7)
        count=110 if detail and form in ('sun','poppy','daisy') else 0 if form in ('cluster','spike') else 12
        for k in range(count):
            a=k*2.39996;rr=disk*math.sqrt(k/count)
            b.ellipsoid(M['pollen'],p+Vector((rr*math.cos(a),rr*math.sin(a),.008+disk*.28*(1-rr/disk))),(.0015,.0015,.0024),5,4)

def florets(b,p,r,opening,M,detail,form,normal=None):
    p=Vector(p);offsets={m:len(d[0]) for m,d in b.data.items()}
    _florets(b,p,r,opening,M,detail,form)
    normal=Vector(normal or (random.uniform(-.28,.28),random.uniform(-.28,.28),1)).normalized()
    q=Vector((0,0,1)).rotation_difference(normal)
    for m,d in b.data.items():
        for i in range(offsets.get(m,0),len(d[0])):d[0][i]=p+q@(Vector(d[0][i])-p)

def plant(c,s,detail,dream=False):
    random.seed(1900+sum(map(ord,c['id'])));M=palette(c,dream);B.M=M;b=B.BotanicalBatch();form=c['form'];h=c['height']*[.055,.10,.17,.25,.38,.55,.72,.86,.95,1][s-1]
    stems=1 if s<5 or form in ('cup','sun','iris') else min(s-3,3 if form in ('rose','cluster') else 5 if form!='spike' else 7)
    for branch in range(stems):
        a=branch*2.39996;spread=0 if branch==0 else .10+.02*branch;end=Vector((math.cos(a)*spread,math.sin(a)*spread,h*(1-.07*branch+random.uniform(-.035,.035))))
        base=Vector((0,0,0));mid=Vector((end.x*.25,end.y*.25,end.z*.55));b.tube(M['stem'],[base,mid,end],[.004,.003,.0015],10 if detail else 5)
        leaves=min(4 if form in ('cup','cluster','rose') else 7,s+1)
        for k in range(leaves):
            t=.15+k*.68/leaves;p=base*(1-t)**2+mid*2*t*(1-t)+end*t*t;angle=k*2.4+a
            L=min(.16,.018+s*.014)*(1-.055*branch);W=L*(.06 if form=='spike' else .13 if form=='iris' else .24 if form=='cup' else .48 if form in ('sun','cluster') else .32)
            B.blade(b,M['young'] if k==leaves-1 else M['leaf'],p,angle,L,W,'birch' if form in ('rose','dahlia','cluster') else 'needle',detail,tilt=1.6 if form in ('iris','cup') else .2)
            if form in ('rose','dahlia') and s>=4:
                for side in [-1,1]:B.blade(b,M['leaf'],p+Vector((math.cos(angle)*L*.4,math.sin(angle)*L*.4,.01)),angle+side*.8,L*.65,W*.65,'birch',detail)
        if form=='rose' and s>5 and detail:
            for k in range(4):
                t=.15+k*.13;p=mid*t*2;b.tube(M['stem'],[p,p+Vector((.008,0,-.004)),p+Vector((.012,0,-.013))],[.0025,.0015,.0001],5)
        if s<7:continue
        opening=0 if s<9 else .5 if s==9 else .95
        if s==7:M={**M,'petal':M['young']}
        r={'rose':.105,'cup':.13,'sun':.16,'dahlia':.115,'daisy':.065,'iris':.13,'poppy':.12,'bell':.065,'spike':.016,'cluster':.025}[form]
        if form=='cluster':
            n=12 if s==7 else 30 if s==8 else 55 if s==9 else 82
            if not detail:n=max(6,n//3)
            for k in range(n):
                z=.02+.105*k/n;theta=k*2.39996;rr=.115*math.sqrt(max(0,1-((z-.045)/.12)**2));p=end+Vector((rr*math.cos(theta),rr*math.sin(theta),z));b.tube(M['stem'],[end,p],.001,4);florets(b,p,r,opening,M,detail,form,normal=(p-end).normalized())
        elif form=='spike':
            for k in range(5+s if detail else 6):
                for j in range(3):
                    theta=j*TAU/3+k*.7;p=end+Vector((.014*math.cos(theta),.014*math.sin(theta),k*(.009 if detail else .022)));florets(b,p,r,opening,M,detail,form)
        elif form=='bell':
            for k in range(max(1,s-6)):
                theta=k*2.4;p=end+Vector((.05*math.cos(theta),.05*math.sin(theta),-.06*k));b.tube(M['stem'],[end,p+Vector((0,0,.02)),p],.0018,6);florets(b,p,r,opening,M,detail,form)
        else:florets(b,end,r,opening,M,detail,form)
    obs=b.objects(c['id']+('_dream' if dream else '')+f'_stage_{s:02}')
    for o in obs:o['farm_species']=c['id']+('-dream' if dream else '');o['farm_stage']=s;o['cultivar']='dream' if dream else 'natural'
    return obs

def build(c):
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.preferences.filepaths.save_version=0;report=[];allobs=[]
    for stage in range(1,12):
        dream=stage==11;s=min(stage,10);key=c['id']+('-dream' if dream else '')
        near=plant(c,s,True,dream);far=plant(c,s,False,dream)
        for obs,suffix in [(near,''),(far,'-lod')]:B.export(obs,OUT/f'{key}-{s:02}{suffix}.glb')
        report.append(dict(stage=s,variant=dream,triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in near),lodTriangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in far)))
        for o in far:bpy.data.objects.remove(o,do_unlink=True)
        for o in near:o.location.x=(stage-1)%6*.9;o.location.y=0 if stage<=6 else -1.2
        allobs+=near
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/(c['id']+'-growth.blend')),compress=True)
    floor=material('studio',(.30,.37,.32),.85);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.012));bpy.context.object.data.materials.append(floor)
    scene=B.camera((2.1,-.5,.3),(2.1,-7,4.6),6.2,1600,900);scene.cycles.samples=24;scene.render.filepath=str(ART/(c['id']+'-growth.png'));bpy.ops.render.render(write_still=True)
    # Separate natural and variant specimens in a close portrait for inspection.
    for o in allobs:
        if o.get('farm_stage')!=10:o.hide_render=True
        else:o.location.x=0 if o.get('cultivar')=='natural' else .8;o.location.y=0
    target=Vector((.4,0,c['height']*.5));scene.camera.location=target+Vector((1,-3,1.2));scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=1.55;scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.filepath=str(ART/(c['id']+'-detail.png'));bpy.ops.render.render(write_still=True)
    (ART/(c['id']+'-report.json')).write_text(json.dumps(report,indent=2))
    print('FLOWER_COMPLETE',c['id'],flush=True)

if __name__=='__main__':
    selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for c in CAT:
        if not selected or c['id'] in selected:build(c)
