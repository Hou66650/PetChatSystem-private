"""MCP authoring pass: reference-matched timber, planting and crafted details.

Input is the previous editable master. Facility collision centre lines stay fixed.
Dispatch with paw_mcp_client.py; never modifies the user's open Blender session.
"""
import bpy, bmesh, math, random, json, sys, hashlib
import numpy as np
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from shepherd_geometry import Batch,material
from cinematic_island_tools import finish,collection,principled,camera,leaf
OUT=ROOT/'art/paw-commons-v3';OUT.mkdir(exist_ok=True);(OUT/'review').mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'art/paw-commons-v2/paw-commons-detailed.blend'))
bpy.context.preferences.edit.use_global_undo=False
random.seed(1937)
M={k:bpy.data.materials[v] for k,v in {'oak':'Honey oak','bark':'Weathered bark','rock':'Layered limestone','grass':'Living turf','rope':'Woven natural fibre','leaf':'Leaf green','tip':'Leaf sun tips','sage':'Sage painted edges','apricot':'Apricot painted edges','cream':'Warm ivory','metal':'Brushed metal','white':'Daisy ivory petals','purple':'Verbena lilac petals','pink':'Small blush flowers','gold':'Small cream flowers'}.items()}

def texture(mat,name,rgb,normal=None):
    nt=mat.node_tree;p=principled(mat)
    for n in list(nt.nodes):
        if n.type in ('TEX_IMAGE','NORMAL_MAP'):nt.nodes.remove(n)
    h,w=rgb.shape[:2]
    for suffix,data in [('albedo',rgb),('normal',normal)]:
        if data is None:continue
        im=bpy.data.images.new(name+' '+suffix,width=w,height=h)
        if suffix=='normal':im.colorspace_settings.name='Non-Color'
        im.pixels.foreach_set(np.dstack((np.clip(data,0,1),np.ones((h,w)))).astype(np.float32).ravel());im.pack()
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
        if suffix=='albedo':nt.links.new(tex.outputs['Color'],p.inputs['Base Color'])
        else:
            nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.26
            nt.links.new(tex.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],p.inputs['Normal'])

# Neutral warm oak, fine long fibres and sparse growth knots, rather than orange stripes.
n=1024;y,x=np.mgrid[0:n,0:n]/n;rng=np.random.default_rng(917)
warp=x+.014*np.sin(y*math.tau*2)+.007*np.sin(y*math.tau*7)
for kx,ky in [(.19,.24),(.71,.72)]:
    warp+=.028*np.exp(-((x-kx)/.09)**2-((y-ky)/.15)**2)*np.sin(np.arctan2((y-ky)*.5,x-kx)*2)
grain=.013*np.sin(warp*math.tau*42)+.009*np.sin(warp*math.tau*117)+rng.normal(0,.006,(n,n))
broad=.018*np.sin(x*math.tau*3)+.009*np.cos(y*math.tau)
wood=np.array([.67,.56,.415])[None,None,:]+(grain+broad)[:,:,None]*np.array([.8,.72,.52])
dy,dx=np.gradient(grain);normal=np.dstack((-dx*1.7,-dy*1.7,np.ones_like(x)));normal/=np.linalg.norm(normal,axis=2)[:,:,None]
texture(M['oak'],'Q honey oak fibres',wood,normal*.5+.5);principled(M['oak']).inputs['Roughness'].default_value=.63
texture(M['rope'],'Q woven flax',np.array([.58,.52,.39])+(.03*np.sin(x*math.tau*190)*np.sin(y*math.tau*110))[:,:,None])
# Turf has broad dry/green patches and close-up cut blades, no uniform green carpet.
n=2048;v,u=np.mgrid[0:n,0:n]/n;xx=u*30-15;yy=v*26-13
field=.027*np.sin(xx*.66+yy*.25)+.023*np.sin(yy*.9-xx*.47)+.012*np.sin(xx*2.5+yy*1.8)
fine=np.random.default_rng(88).normal(0,.018,(n,n));blades=.012*np.sin(xx*330+np.sin(yy*52)*3)
rgb=np.array([.335,.383,.187])[None,None,:]+(field+fine+blades)[:,:,None]*np.array([1,.9,.55])
# Exportable contact shading around tree bed/planting, independent of renderer lights.
shade=np.ones((n,n))
for px,py,r in [(.3,.8,1.7),(-11,5.8,1.5),(-7.8,9,1.6),(-.8,10.1,1.4),(10.5,6,1.3),(-12,-5.4,1.2),(11.8,-6.7,1.2)]:
    shade-=.16*np.exp(-((xx-px)**2+(yy-py)**2)/(r*r))
texture(M['grass'],'Q island turf',rgb*shade[:,:,None])
# Fine warm gravel and muted painted trims, matching the six-facility board.
gravel=bpy.data.materials['Warm gravel'];n=1024;y,x=np.mgrid[0:n,0:n]/n
noise=np.random.default_rng(82).normal(0,.043,(n,n));texture(gravel,'Q fine path aggregate',np.array([.69,.635,.525])+noise[:,:,None]);principled(gravel).inputs['Roughness'].default_value=.93
for key,col in [('sage',(.29,.38,.24)),('apricot',(.65,.39,.24)),('cream',(.73,.67,.51)),('leaf',(.065,.14,.026)),('tip',(.16,.25,.053)),('pink',(.58,.25,.29)),('purple',(.32,.22,.40))]:
    M[key].diffuse_color=(*col,1);principled(M[key]).inputs['Base Color'].default_value=(*col,1)
M['deep']=material('Q Leaf deep olive',(.045,.095,.018),.86)
# Existing leaf components keep their organic silhouette, now with shaded interiors.
for o in bpy.context.scene.objects:
    if o.type!='MESH' or not o.name.startswith('D01') or 'Leaf' not in o.data.materials[0].name:continue
    o.data.materials.clear()
    for mat in (M['deep'],M['leaf'],M['tip']):o.data.materials.append(mat)
    for poly in o.data.polygons:
        group=poly.index//12;value=((group*1103515245+12345)&0xffff)/65535
        poly.material_index=0 if value<.24 else 1 if value<.84 else 2

# Remove the older open triangular ear tubes before adding solid inset ears.
# Only disconnected, elevated, shallow components at the two portal faces qualify.
for c in list(bpy.data.collections):
    if not c.name.startswith(('05 Ear tunnel','D04 Second')):continue
    for o in c.objects:
        if o.type!='MESH' or o.data.materials[0]!=M['oak']:continue
        bm=bmesh.new();bm.from_mesh(o.data);seen=set();remove=[]
        for v in bm.verts:
            if v in seen:continue
            group=[];stack=[v];seen.add(v)
            while stack:
                q=stack.pop();group.append(q)
                for e in q.link_edges:
                    other=e.other_vert(q)
                    if other not in seen:seen.add(other);stack.append(other)
            lo=[min(v.co[k] for v in group) for k in range(3)];hi=[max(v.co[k] for v in group) for k in range(3)]
            scale=.82 if c.name.startswith('D04') else 1
            if lo[2]>1.0*scale and hi[1]-lo[1]<.18*scale and hi[0]-lo[0]<.6*scale:remove.extend(group)
        bmesh.ops.delete(bm,geom=remove,context='VERTS');bm.to_mesh(o.data);bm.free()

groups={}
def batch(name):b=Batch();groups[name]=b;return b
def tube(b,key,pts,r,n=10):b.tube(M[key],pts,r,n)
def box(b,key,p,s):b.box(M[key],p,s)
def ball(b,key,p,s,n=12,rings=7):b.ellipsoid(M[key],p,s,n,rings)
def arch_band(b,x,y,scale):
    # Layered solid fascia, actual open inner arch (not a disc over the tunnel).
    vs=[]
    for depth in [-.075,.075]:
        for r in [0,1]:
            for i in range(65):
                a=i*math.pi/64;vs.append((x+scale*(.625+.17*r)*math.cos(a),y+depth*scale,scale*(.07+(1.20+.19*r)*math.sin(a))))
    faces=[]
    for i in range(64):
        faces.extend([(i,i+1,65+i+1,65+i),(130+i,195+i,195+i+1,130+i+1),(i,130+i,130+i+1,i+1),(65+i,65+i+1,195+i+1,195+i)])
    b.mesh(M['oak'],vs,faces)
    for side in [-1,1]:
        pts=[(.25,1.29),(.61,1.73),(.78,1.25)]
        verts=[(x+side*xx*scale,y+d*scale,zz*scale) for d in [-.07,.07] for xx,zz in pts]
        b.mesh(M['oak'],verts,[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)])
        for d in [-.079,.079]:
            b.mesh(M['apricot'],[(x+side*xx*scale,y+d*scale,zz*scale) for xx,zz in [(.40,1.35),(.59,1.59),(.66,1.33)]],[(0,1,2)])
        for a in [.35,.85,1.3]:ball(b,'metal',(x+side*.71*math.cos(a)*scale,y-.083*scale,(.07+1.29*math.sin(a))*scale),(.021*scale,.012*scale,.021*scale),8,4)
b=batch('Q01 Layered cat ear portal joinery')
for tx,ty,s in [(-10,.8,1),(-7.4,4,.82)]:
    for side in [-1,1]:arch_band(b,tx,ty+side*1.57*s,s)
# Bridge braces, end-grain post caps and flush bolts; deck elevation is unchanged.
b=batch('Q02 Bridge joinery')
for px in [-9-.56,-9+.56]:
    for py in [-4.7-1,-4.7+1]:
        tube(b,'oak',[(px,py,.02),(px,py,.48)],.115,16)
        tube(b,'oak',[(px,py-.25,.16),(px,py+.32,.45)],.055,10)
        ball(b,'metal',(px,py-.116,.32),(.035,.012,.035),10,6)
for py in [-4.7-1.125+i*.25 for i in range(10)]:
    for px in [-9-.51,-9+.51]:ball(b,'metal',(px,py,.559),(.013,.013,.005),8,4)
# Soft cushions and woven edges, natural pet-toy colours; retain original shelf.
b=batch('Q03 Playful craft details')
for i in range(8):
    px=9.46+(i%4)*.29;py=-5.18+(i//4)*.23
    ball(b,['sage','apricot','cream'][i%3],(px,py,.24),(.13,.13,.13),18,10)
    for j in range(12):
        a=j*math.tau/12;ball(b,'cream',(px+.13*math.cos(a),py+.13*math.sin(a),.25),(.012,.012,.012),6,4)
for i in range(4):
    pts=[]
    for j in range(100):
        a=j*math.tau/99;pts.append((9.45+i*.32+.10*math.cos(a),-5.1+.05*math.sin(a),.67+.025*math.sin(a*3)))
    tube(b,'rope',pts,.021,6)
# Dense planted islands of varied height instead of a uniform thin flower border.
nav=json.loads((ROOT/'static/models/paw-commons-v2/navigation.json').read_text(encoding='utf-8'))
route_segments=[(a,c) for f in nav['facilities'] for a,c in zip(f['path'],f['path'][1:])]
def clear_path(x,y):
    z=-y
    for a,c in route_segments:
        dx,dz=c[0]-a[0],c[2]-a[2];t=max(0,min(1,((x-a[0])*dx+(z-a[2])*dz)/(dx*dx+dz*dz)))
        if math.hypot(x-a[0]-t*dx,z-a[2]-t*dz)<.8:return False
    return True
b=batch('Q04 Botanical clusters')
for px,py,r in [(-11.4,3,.7),(-5.1,6.8,.7),(8.9,5.8,.8),(10.7,-4.2,.55),(1.9,9.2,.85),(-2.9,9.5,.65),(-11.5,-2.8,.55),(11,-7.3,.6),(.3,.8,1.55)]:
    for i in range(95):
        a=random.random()*math.tau;d=r*math.sqrt(random.random());x=px+d*math.cos(a);y=py+d*math.sin(a)
        if not clear_path(x,y):continue
        h=random.uniform(.18,.50)
        tube(b,'leaf',[(x,y,.02),(x+.02,y,h)],.0045,4)
        for side in [-1,1]:leaf(b,M['leaf'],(x,y,h*.35),a+side,.16,.028,.45)
        for j in range(5):
            aa=j*math.tau/5;ball(b,['white','purple','pink'][i%3],(x+.024*math.cos(aa),y+.024*math.sin(aa),h),(.029,.017,.009),6,3)
        ball(b,'gold',(x,y,h+.006),(.009,.009,.008),6,3)
    for i in range(7):
        a=i*math.tau/7;x=px+math.cos(a)*r*.6;y=py+math.sin(a)*r*.6
        if not clear_path(x,y):continue
        for j in range(9):
            angle=j*math.tau/9
            for k in range(6):
                t=k/6;cx=x+math.cos(angle)*.42*t;cy=y+math.sin(angle)*.42*t;z=.03+.33*math.sin(t*math.pi*.85)
                for side in [-1,1]:leaf(b,M['leaf' if j%3 else 'tip'],(cx,cy,z),angle+side*1.0,.13*(1-t*.7),.028,.12)

for name,b in groups.items():finish(b,name,collection(name),.008 if name.startswith(('Q01','Q02')) else 0)
scene=bpy.context.scene
# Warm late-afternoon key with cooler fill, matching concept direction and contrast.
for o in list(scene.objects):
    if o.get('preview_only') and o.type=='MESH':o.hide_render=True
    if o.type=='LIGHT':
        if o.data.type=='SUN':o.data.energy=2.0;o.data.color=(1,.87,.67);o.rotation_euler=(.7,-.55,-.7);o.data.angle=.10
        elif o.data.type=='AREA':o.data.energy=0
key=bpy.data.lights.new('Q afternoon sun','SUN');key.energy=2.8;key.color=(1,.91,.78);key.angle=.16
sun=bpy.data.objects.new('Q afternoon sun',key);scene.collection.objects.link(sun);sun.rotation_euler=(.48,-.38,-.5)
fill=bpy.data.lights.new('Q large sky fill','AREA');fill.energy=1700;fill.shape='DISK';fill.size=24;fill.color=(.80,.90,1)
lamp=bpy.data.objects.new('Q large sky fill',fill);scene.collection.objects.link(lamp);lamp.location=(4,-8,16)
lamp.rotation_euler=(Vector((0,0,0))-lamp.location).to_track_quat('-Z','Y').to_euler()
nt=scene.world.node_tree
for link in list(nt.nodes['Background'].inputs['Color'].links):nt.links.remove(link)
nt.nodes['Background'].inputs['Color'].default_value=(.68,.76,.82,1);nt.nodes['Background'].inputs['Strength'].default_value=.55
scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.25
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
scene.render.resolution_x=1800;scene.render.resolution_y=1300;scene.render.resolution_percentage=100
camera(scene,(10,-36,23),(0,0,-.2),33)
scene['authoring_transport']='MCP stdio -> mcp-for-blender 2.1.9 -> official addon execute_blender_code'
scene['reference']='art/paw-commons-v2/design/01-overall-concept.png + 02-facility-details.png'
scene['status']='Quality refinement; original facility paths retained'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paw-commons-quality.blend'),compress=True)
report={'transport':scene['authoring_transport'],'reference':scene['reference'],'newGroups':list(groups),'master':'paw-commons-quality.blend','facilityPathsChanged':False}
(OUT/'quality-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PAW_QUALITY_MASTER_SAVED',flush=True)
for name,loc,target,scale in [('01-overview',(10,-36,23),(0,0,-.2),33),('02-tunnel-bridge',(-18,-9,8),(-9,1,.8),10),('03-treehouse',(-11,0,7),(-6,7.5,1.9),8.5),('04-canopy-toys',(16,-2,8),(7.5,4,1.3),11)]:
    camera(scene,loc,target,scale);scene.render.filepath=str(OUT/'review'/f'{name}.png');bpy.ops.render.render(write_still=True)
print('PAW_QUALITY_RENDER_COMPLETE',flush=True)
