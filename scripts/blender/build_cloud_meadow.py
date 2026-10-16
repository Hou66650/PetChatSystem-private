"""Cloud meadow: metric, contiguous extension of the shipped farm. Blender 5.2.

Keeps all existing coordinates. Shared JSON drives terrain, paths, trees and
navigation. Planar ground is partitioned, never layered over the old lawn.
"""
import bpy, bmesh, json, math, random, sys
import numpy as np
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from build_farm_garden import BotanicalBatch, exposed_floor, camera, export
from shepherd_geometry import material
R=Path(__file__).resolve().parents[2]
ART=R/'art/cloud-meadow-v1';OUT=R/'static/models/petchat-meadow-v1'
ART.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
layout=json.loads((R/'static/data/farm-layout.json').read_text(encoding='utf-8'))['expansion']
random.seed(10716)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-farm-v1/mistwood-farm.glb'))
original=list(bpy.context.selected_objects)
relocation=layout['relocatedBench'];shift=Vector((relocation['to']['x']-relocation['from']['x'],relocation['from']['z']-relocation['to']['z'],0))
# The old bench pinched the east approach against the feeding stand for larger
# uploaded cats. Move only its wood/iron pieces onto the adjacent riverbank.
for o in original:
    if o.type!='MESH' or not o.data.materials or o.data.materials[0].name not in ('Weathered_bench','Patinated_iron'):continue
    indices=set()
    for f in o.data.polygons:
        p=o.matrix_world@f.center
        if 2.69<p.x<4.71 and -4.65<p.y<-4.0 and .055<p.z<1.12:indices.update(f.vertices)
    local=o.matrix_world.inverted().to_3x3()@shift
    for i in indices:o.data.vertices[i].co+=local
    o.data.update()
domains=layout['domains'];old=dict(x=0,z=0,rx=7.84,rz=7.84)
def inside(x,z,d,margin=0):return ((x-d['x'])/(d['rx']-margin))**2+((z-d['z'])/(d['rz']-margin))**2<1
def added(x,z):return not inside(x,z,old) and any(inside(x,z,d,.06) for d in domains)
def polygon(d,n=192):return [(d['x']+d['rx']*math.cos(i*math.tau/n),-d['z']+d['rz']*math.sin(i*math.tau/n)) for i in range(n)]
def path_distance(x,z):
    best=1000
    for a,c in zip(layout['loop'],layout['loop'][1:]):
        dx,dz=c[0]-a[0],c[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz)))
        best=min(best,math.hypot(x-a[0]-t*dx,z-a[1]-t*dz))
    return best

# Remove only the old low edge wall in the broad land connection. Preserve
# greenhouse, trees, feeding station, bridge, original floor and both waterfalls.
trimmed=0
for o in original:
    if o.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(o.data);remove=[]
    for f in bm.faces:
        p=o.matrix_world@f.calc_center_median()
        if p.x>0 and .065<p.z<.68 and 7.25<math.hypot(p.x,p.y)<7.86 and any(inside(p.x,-p.y,d,.35) for d in domains):remove.append(f)
    trimmed+=len(remove);bmesh.ops.delete(bm,geom=remove,context='FACES');bm.to_mesh(o.data);bm.free()

stone=bpy.data.materials.get('Weathered_limestone') or material('Meadow_limestone',(.36,.38,.31))
cliff=bpy.data.materials.get('Stratified_cliff') or stone
bark=bpy.data.materials.get('Cedar_bark') or material('Meadow_bark',(.18,.12,.07))
iron=material('Meadow_patinated_iron',(.075,.10,.075),.62,.45)
lawn=material('Meadow_living_turf',(.23,.32,.12),.94)
# Exportable multiscale texture and physical normal map. No engine-only noise.
n=1024;y,x=np.mgrid[0:n,0:n]/n;rng=np.random.default_rng(10716)
field=np.zeros((n,n))
for f,amp in [(2,.12),(5,.09),(19,.07),(51,.05),(137,.03),(307,.018)]:
    field+=amp*np.sin((x*.8+y*.3)*math.tau*f+.5)*np.cos((y*.9-x*.2)*math.tau*f)
noise=rng.random((n,n));strand=np.maximum(0,np.sin(x*1700+np.sin(y*90)*3))**12
rgb=np.clip(np.array([.31,.40,.17])[None,None,:]*(.83+field[:,:,None]+noise[:,:,None]*.17)+strand[:,:,None]*np.array([.023,.026,.007]),0,1)
def image_texture(name,data,color=True):
    im=bpy.data.images.new(name,width=n,height=n)
    if not color:im.colorspace_settings.name='Non-Color'
    im.pixels.foreach_set(np.dstack((data,np.ones((n,n)))).astype(np.float32).ravel());im.pack();return im
nt=lawn.node_tree;bs=nt.nodes.get('Principled BSDF');tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image_texture('Meadow_turf_albedo',rgb);nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
dy,dx=np.gradient(noise*.08+strand*.04);normal=np.dstack((-dx,-dy,np.ones((n,n))));normal/=np.linalg.norm(normal,axis=2)[:,:,None]
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image_texture('Meadow_turf_normal',normal*.5+.5,False);nn=nt.nodes.new('ShaderNodeNormalMap');nn.inputs['Strength'].default_value=.45;nt.links.new(tex.outputs['Color'],nn.inputs['Color']);nt.links.new(nn.outputs['Normal'],bs.inputs['Normal'])
grass=[material('Meadow_blades_'+str(i),c,.91) for i,c in enumerate([(.19,.28,.075),(.27,.36,.12),(.36,.41,.16)])]
leaf=[material('Meadow_leaf_'+str(i),c,.85) for i,c in enumerate([(.18,.30,.085),(.28,.39,.12),(.37,.46,.18)])]
for m in grass+leaf:m.use_backface_culling=False
b=BotanicalBatch()
for di,d in enumerate(domains):
    masks=[polygon(old,384)]+[polygon(q) for q in domains[:di]]
    exposed_floor(b,lawn,[(px,py,.025) for px,py in polygon(d)],masks)
    # Continuous stratified skirt, only on exposed union boundaries.
    for k in range(192):
        a=k*math.tau/192;c=(k+1)*math.tau/192;mid=(a+c)/2
        px=d['x']+d['rx']*math.cos(mid);pz=d['z']-d['rz']*math.sin(mid)
        if any(inside(px,pz,q,.02) for q in [old]+[q for q in domains if q is not d]):continue
        vs=[]
        for j in range(13):
            h=.025 if j==0 else -j*.40
            f=1 if j==0 else 1-j*.041+.018*math.sin(mid*23+j*.8)
            for ang in (a,c):vs.append((d['x']+d['rx']*f*math.cos(ang),-d['z']+d['rz']*f*math.sin(ang),h))
        b.mesh(cliff,vs,[(j*2,j*2+2,j*2+3,j*2+1) for j in range(12)])
        # Irregular coping blocks are outside the navigable clearance margin.
        if k%2==0:
            ix=d['x']+(d['rx']-.13)*math.cos(mid);iz=d['z']-(d['rz']-.13)*math.sin(mid)
            if any(inside(ix,iz,q,.0) for q in [old]+[q for q in domains if q is not d]):continue
            b.box(stone,(ix,-iz,.14),(.30,.24,.23),mid+math.pi/2)
            if k%12==0:b.box(stone,(ix,-iz,.29),(.27,.27,.46))
        if k%2==0:
            h=random.uniform(-4.2,-.3);f=1+h*.10
            b.ellipsoid(stone if k%4 else cliff,(d['x']+d['rx']*f*math.cos(mid),-d['z']+d['rz']*f*math.sin(mid),h),(random.uniform(.23,.54),random.uniform(.20,.49),random.uniform(.14,.32)),12,7)

# Low, irregular inset paving follows the shared reserved path exactly.
for a,c in zip(layout['loop'],layout['loop'][1:]):
    length=math.hypot(c[0]-a[0],c[1]-a[1]);angle=math.atan2(-(c[1]-a[1]),c[0]-a[0])
    for j in range(max(1,int(length/.25))):
        t=(j+.5)/max(1,int(length/.25));px=a[0]+(c[0]-a[0])*t;pz=a[1]+(c[1]-a[1])*t
        if not added(px,pz):continue
        for side in [-1,0,1]:
            off=side*.23;xx=px-math.sin(angle)*off;yy=-pz+math.cos(angle)*off
            b.box(stone,(xx,yy,.030),(.23,.21,.012),angle+random.uniform(-.07,.07))

# Fine three-dimensional grass blades, short enough not to hide paws or pots.
for k in range(35000):
    px=random.uniform(1,19);pz=random.uniform(-2.8,13.5)
    if not added(px,pz) or path_distance(px,pz)<.45:continue
    a=random.random()*math.tau;h=random.uniform(.028,.075);w=random.uniform(.004,.009);bend=random.uniform(.006,.022)
    p=Vector((px,-pz,.026));side=Vector((math.cos(a)*w,math.sin(a)*w,0));tip=p+Vector((math.sin(a)*bend,-math.cos(a)*bend,h))
    b.mesh(grass[k%3],[p-side,p+side,(p+tip)/2+side*.5,tip,(p+tip)/2-side*.5],[(0,1,2,4),(4,2,3)],True)

# Broad branching trees with real folded leaves; sparse along the far rim only.
for ti,t in enumerate(layout['trees']):
    px,py,h=t['x'],-t['z'],t['h'];lean=Vector((.15*math.sin(ti),.14*math.cos(ti),0))
    trunk=[Vector((px,py,h*j/12))+lean*(j/12)**2 for j in range(13)]
    b.tube(bark,trunk,[.17*(1-j/14) for j in range(13)],12)
    for j in range(16):
        u=.30+j/24;a=j*2.399+ti;reach=h*.34*(1-u)**.55
        start=Vector((px,py,h*u))+lean*u*u;end=start+Vector((math.cos(a)*reach,math.sin(a)*reach,.18))
        b.tube(bark,[start,start.lerp(end,.5)+Vector((0,0,-.1)),end],[.045,.025,.004],8)
        for twig in range(5):
            at=start.lerp(end,.35+twig*.15);aa=a+random.uniform(-1.3,1.3);tip=at+Vector((.42*math.cos(aa),.42*math.sin(aa),random.uniform(-.1,.35)))
            b.tube(bark,[at,tip],[.009,.0018],5)
            for q in range(28):
                p=tip+Vector((random.uniform(-.28,.28),random.uniform(-.28,.28),random.uniform(-.17,.17)));an=random.random()*math.tau;L=random.uniform(.065,.12);W=L*.40;v=Vector((math.cos(an),math.sin(an),random.uniform(-.3,.2)));s=Vector((-math.sin(an)*W,math.cos(an)*W,0))
                b.mesh(leaf[(q+j)%3],[p,p+v*L*.48+s,p+v*L,p+v*L*.48-s,p+v*L*.50+Vector((0,0,.012))],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],True)
new=b.objects('Cloud_meadow')
# World UV scale also applies to clipped polygons, avoiding stretched join textures.
for o in new:
    if o.data.uv_layers:o.data.uv_layers.remove(o.data.uv_layers.active)
    uv=o.data.uv_layers.new(name='WorldUV')
    for face in o.data.polygons:
        axis=max(range(3),key=lambda i:abs(face.normal[i]));axes=[i for i in range(3) if i!=axis]
        for idx in face.loop_indices:
            p=o.data.vertices[o.data.loops[idx].vertex_index].co;scale=.06 if o.data.materials[0]==lawn else .55;uv.data[idx].uv=(p[axes[0]]*scale,p[axes[1]]*scale)
    o['meadow_extension']=True
all_objects=original+new
export(all_objects,OUT/'mistwood-meadow.glb')
scene=camera((2,-3,1),(23,-37,31),43,1800,1250)
bpy.ops.object.light_add(type='SUN',location=(0,0,15));sun=bpy.context.object;sun.rotation_euler=(.45,-.5,-.4);sun.data.energy=2;sun.data.angle=.15
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.48,.57,.62,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
scene.cycles.samples=40
bpy.ops.wm.save_as_mainfile(filepath=str(ART/'cloud-meadow.blend'),compress=True)
report=dict(meshes=len(all_objects),newMeshes=len(new),triangles=sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in all_objects if o.type=='MESH'),bytes=(OUT/'mistwood-meadow.glb').stat().st_size,trimmedWallFaces=trimmed,domains=domains)
(ART/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene.render.filepath=str(ART/'perspective.png');bpy.ops.render.render(write_still=True)
scene.camera.location=(2,-3,50);scene.camera.rotation_euler=(0,0,0);scene.camera.data.ortho_scale=39
scene.render.filepath=str(ART/'plan.png');bpy.ops.render.render(write_still=True)
print('CLOUD_MEADOW_COMPLETE',json.dumps(report),flush=True)
