"""Refine an actual reconstructed Tangyuan mesh, preserving its UV identity.

Blender --background --python this.py -- --input raw-review.blend --output DIR
The source is never overwritten. Grooming is a film asset, not a validated rig.
"""
import argparse,bisect,hashlib,json,math,random,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector,Matrix

parser=argparse.ArgumentParser()
parser.add_argument('--input',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--yaw',type=float,default=47.24459585922732)
parser.add_argument('--fibres',type=int,default=90000)
opt=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source=Path(opt.input).resolve();out=Path(opt.output).resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'Tangyuan-refined.blend').exists():raise FileExistsError('Use a new revision directory')
random.seed(7161)
bpy.ops.wm.open_mainfile(filepath=str(source))
body=bpy.data.objects.get('node_0')
if body is None:raise ValueError('Expected the inspected reconstruction mesh node_0')
rotation=Matrix.Rotation(math.radians(opt.yaw),4,'Z')
for vertex in body.data.vertices:vertex.co=rotation@vertex.co
body.name='Tangyuan | reconstructed surface, original UV retained'
bm=bmesh.new();bm.from_mesh(body.data);before=len(bm.verts)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(body.data);bm.free()
welded=before-len(body.data.vertices)
def smooth(a,b,x):
    t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
group=body.vertex_groups.new(name='Leg edge cleanup | excludes face')
for v in body.data.vertices:
    w=1-smooth(.38,.57,v.co.z)
    if w>.001:group.add([v.index],w,'REPLACE')
bpy.context.view_layer.objects.active=body
mod=body.modifiers.new('Soften reconstructed leg spikes','SMOOTH');mod.factor=.5;mod.iterations=5;mod.vertex_group=group.name
bpy.ops.object.modifier_apply(modifier=mod.name)
scalp=body.vertex_groups.new(name='Crown cleanup | preserves face')
for v in body.data.vertices:
    w=smooth(.85,.92,v.co.z)*(1-smooth(-.22,-.1,v.co.y))
    if w>.001:scalp.add([v.index],w,'REPLACE')
mod=body.modifiers.new('Soften hard crown reconstruction spikes','SMOOTH');mod.factor=.5;mod.iterations=4;mod.vertex_group=scalp.name
bpy.ops.object.modifier_apply(modifier=mod.name)
for polygon in body.data.polygons:polygon.use_smooth=True
mat=body.data.materials[0];nodes=mat.node_tree.nodes;links=mat.node_tree.links
bs=nodes.get('Principled BSDF');albedo=bs.inputs['Base Color'].links[0].from_node.image
for name in ['Metallic','Roughness']:
    for link in list(bs.inputs[name].links):links.remove(link)
bs.inputs['Metallic'].default_value=0;bs.inputs['Roughness'].default_value=.84;bs.inputs['Specular IOR Level'].default_value=.25
for node in nodes:
    if node.type=='NORMAL_MAP':node.inputs['Strength'].default_value=.22

# Darken the unsupported pale torso while retaining pale furnishings. All shape
# and facial texture still come from the reconstructed mesh, not a stock dog.
def tone_factor(p):
    x,y,z=p
    factor=.17
    factor=1-(1-factor)*smooth(.23,.43,z)
    if y<-.31 and z>.58:
        factor=.32
        if y<-.49 and z<.78:factor=.92  # moustache and beard
        if z>.8:factor=.48             # gray eyebrows and crown details
    if y>.38 and z>.72:factor=.2
    return factor
attr=body.data.color_attributes.new(name='ReferenceCoatCorrection',type='FLOAT_COLOR',domain='POINT')
for v in body.data.vertices:
    fac=tone_factor(v.co);attr.data[v.index].color=(fac*.97,fac,fac*1.02,1)
vc=nodes.new('ShaderNodeVertexColor');vc.layer_name=attr.name
mul=nodes.new('ShaderNodeMixRGB');mul.blend_type='MULTIPLY';mul.inputs[0].default_value=1
image_node=bs.inputs['Base Color'].links[0].from_node
links.new(image_node.outputs['Color'],mul.inputs[1]);links.new(vc.outputs['Color'],mul.inputs[2]);links.new(mul.outputs[0],bs.inputs['Base Color'])
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=64;scene.cycles.use_denoising=True;scene.render.use_persistent_data=True
try:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type!='CPU'
    scene.cycles.device='GPU'
except Exception:scene.cycles.device='CPU'

# Bake the spatial correction into a real albedo texture for portable GLB output.
baked=bpy.data.images.new('Tangyuan | corrected 4K albedo',width=4096,height=4096,alpha=False)
target=nodes.new('ShaderNodeTexImage');target.image=baked;nodes.active=target
emission=nodes.new('ShaderNodeEmission');links.new(mul.outputs[0],emission.inputs['Color'])
output=nodes.get('Material Output');links.new(emission.outputs[0],output.inputs['Surface'])
bpy.ops.object.select_all(action='DESELECT');body.select_set(True)
scene.render.bake.margin=12;bpy.ops.object.bake(type='EMIT')
links.new(bs.outputs[0],output.inputs['Surface']);links.new(target.outputs['Color'],bs.inputs['Base Color'])
baked.filepath_raw=str(out/'Tangyuan-corrected-albedo.png');baked.file_format='PNG';baked.save();baked.pack()

# Read original albedo only for strand pigment; sampling never invents texture.
width,height=albedo.size;pixels=np.empty(width*height*4,dtype=np.float32);albedo.pixels.foreach_get(pixels);pixels=pixels.reshape(height,width,4)
def color_at(uv,p):
    rgb=pixels[min(height-1,max(0,int(uv.y*(height-1)))),min(width-1,max(0,int(uv.x*(width-1)))),:3]
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    return linear*tone_factor(p)

collection=bpy.data.collections.new('Tangyuan | subtle directional film groom');scene.collection.children.link(collection)
levels=[.003,.007,.013,.022,.035,.052,.075,.105,.15,.21,.29,.39,.51,.65]
curves=[]
for i,level in enumerate(levels):
    hairmat=bpy.data.materials.new('UV sampled fibre '+str(i));hairmat.use_nodes=True
    shader=hairmat.node_tree.nodes.get('Principled BSDF');shader.inputs['Base Color'].default_value=(level,level,level*.97,1);shader.inputs['Roughness'].default_value=.78;shader.inputs['Specular IOR Level'].default_value=.15
    curve=bpy.data.curves.new('Editable directional fibres '+str(i),'CURVE');curve.dimensions='3D';curve.resolution_u=1;curve.bevel_depth=.00023;curve.bevel_resolution=0;curve.materials.append(hairmat)
    ob=bpy.data.objects.new('Fine groom '+str(i),curve);collection.objects.link(ob);curves.append(curve)
mesh=body.data;mesh.calc_loop_triangles();triangles=list(mesh.loop_triangles);areas=[];total=0
for tri in triangles:total+=tri.area;areas.append(total)
uvs=mesh.uv_layers.active.data;count=0
for _ in range(opt.fibres):
    tri=triangles[bisect.bisect_left(areas,random.random()*total)]
    verts=[mesh.vertices[i] for i in tri.vertices];u=math.sqrt(random.random());v=random.random();weights=[1-u,u*(1-v),u*v]
    p=sum((vertex.co*w for vertex,w in zip(verts,weights)),Vector());normal=sum((vertex.normal*w for vertex,w in zip(verts,weights)),Vector()).normalized()
    if p.z<.035:continue
    uv=sum((uvs[index].uv*w for index,w in zip(tri.loops,weights)),Vector((0,0)))
    rgb=color_at(uv,p);tone=float(np.mean(rgb))
    if p.y<-.45 and .58<p.z<.86 and tone<.09:continue  # keep eyes and nose clean
    if rgb[0]>rgb[1]*1.4 and rgb[1]>rgb[2]*1.4:continue # collar tag
    length=random.uniform(.003,.008);direction=Vector((p.x*.2,.8,-.3))
    if p.z<.4:length=random.uniform(.009,.018);direction=Vector((p.x*.2,0,-1))
    if p.y<-.28 and p.z>.8:length=random.uniform(.015,.028);direction=normal*.4+Vector((p.x*.2,-.2,-.1))
    if p.y<-.48 and .52<p.z<.78:length=random.uniform(.012,.028);direction=Vector((p.x*.4,-.1,-1))
    direction=(direction-normal*direction.dot(normal)*.7).normalized();side=normal.cross(direction)
    if side.length<.01:side=normal.cross(Vector((.4,.6,.2)))
    side.normalize();index=min(range(len(levels)),key=lambda i:abs(levels[i]-tone*random.uniform(.85,1.15)))
    spline=curves[index].splines.new('POLY');spline.points.add(5);phase=random.random()*math.tau
    for j,point in enumerate(spline.points):
        t=j/5;co=p+normal*(.0002+length*.18*math.sin(t*math.pi))+direction*length*t+side*math.sin(t*math.pi*2+phase)*length*.09*t
        point.co=(*co,1);point.radius=max(.03,(1-t)**.7)
    count+=1

# Export a portable mesh version separately; cinematic groom remains in Blender.
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
bpy.ops.export_scene.gltf(filepath=str(out/'Tangyuan-refined-surface.glb'),export_format='GLB',use_selection=True,export_animations=False)
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
scene['status']='Actual Hunyuan base refined locally; likeness review still required; no verified rig'
scene['changes']='UV preserved; -Y forward alignment; welded seams; softened leg edges; corrected coat albedo; restrained normal map; individual fibres'
camera=scene.camera;camera.data.ortho_scale=1.65
def view(loc,target,scale=1.65):
    camera.location=loc;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
view((2.1,-3,1.6),(0,-.05,.5))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Tangyuan-refined.blend'))
report={'input':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'welded_vertices':welded,'vertices':len(body.data.vertices),'faces':len(body.data.polygons),'groom_fibres':count,'albedo_resolution':4096,'original_uv_preserved':True,'rigged':False,'owner_approved':False,'anatomy':'four legs and one primary tail observed in initial multiview review; no automatic semantic certification','changes':['canonical forward orientation','seam welding','softened leg spikes','spatial coat-color correction baked to 4K','nonmetallic coat and restrained normal map','UV sampled individual film fibres']}
(out/'refinement-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for name,loc,target,scale in [('three-quarter',(2.1,-3,1.6),(0,-.05,.5),1.65),('side',(3,0,1.1),(0,-.05,.5),1.65),('rear',(0,3,1.1),(0,-.05,.5),1.65),('face',(1,-2,1.1),(.05,-.46,.78),.7)]:
    view(loc,target,scale);scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('REFINEMENT_COMPLETE',json.dumps(report),flush=True)
