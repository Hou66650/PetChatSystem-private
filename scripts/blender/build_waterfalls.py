"""Extend the existing river with silver-lit spillways and descending water ribbons."""
import bpy, math, json, random, re
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/waterfalls-v1';ASSET=ROOT/'static/models/petchat-waterfalls-v1'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
layout=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(ROOT/'static/js/den/sakura-river-layout.js').read_text()).group(1))
river=layout['water'][0];random.seed(717)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-river-v1/sakura.glb'))
original=[o for o in bpy.context.scene.objects if o.type=='MESH'];new=[]
def material(name,color,rough=.3,alpha=1,metal=.08,emission=.06):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,alpha);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;p.inputs['Alpha'].default_value=alpha
    p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
    if alpha<1:m.surface_render_method='BLENDED';m.use_transparency_overlap=False
    return m
sheet=material('Cascading_jade_silver',(.24,.62,.65),.2,.88,.16)
silver=material('Silver_water_filaments',(.66,.88,.90),.22,.84,.12)
white=material('Aerated_water_foam',(.79,.94,.94),.5,.82,0,.10)
drops=material('Water_spray_drops',(.52,.81,.84),.19,.85,.08)
def path(side,u,t,split=0):
    # At t=0 the lip follows the exact circular edge of the previous river.
    z=river['z']+(u-.5)*river['d']
    edge=math.sqrt(3.2**2-z*z)
    outward=-.025+.46*(1-math.exp(-4*t))+.10*t*t
    spread=(u-.5)*.17*t+split*t*t
    return (side*(edge+outward+.013*math.sin(u*31+t*16)*math.sin(math.pi*t)),
            -z+spread,-.055-1.48*t*t)
def ribbon(name,side,u0,u1,length,m,role='curtain'):
    verts=[];uv=[];faces=[];rows=48;cols=12
    for j in range(rows+1):
        t=j/rows*length
        taper=1 if t<.60 else max(.035,1-(t-.60)/max(.001,length-.60)*.94)
        for i in range(cols+1):
            u=(u0+u1)/2+(i/cols-.5)*(u1-u0)*taper
            p=path(side,u,t)
            verts.append(p);uv.append((u,t))
    for j in range(rows):
        for i in range(cols):
            a=j*(cols+1)+i;faces.append((a,a+1,a+cols+2,a+cols+1))
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    layer=data.uv_layers.new(name='FlowUV')
    for poly in data.polygons:
        poly.use_smooth=True
        for k in poly.loop_indices:layer.data[k].uv=uv[data.loops[k].vertex_index]
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);data.materials.append(m)
    o['waterfall_role']=role;new.append(o);return o
def tube(name,points,r,m):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=2
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for i,(p,v) in enumerate(zip(points,sp.points)):
        v.co=(*p,1);v.radius=max(.05,math.sin(math.pi*i/max(1,len(points)-1))**.35)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);cu.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH')
    o['waterfall_role']='filament';new.append(o);return o
for side in [-1,1]:
    # Adjacent tongues form a continuous lip, then separate at uneven lengths.
    for k in range(7):
        a=k/7-.001;b=(k+1)/7+.001;length=.78+random.random()*.20
        ribbon(f'Waterfall_{side}_tongue_{k}',side,a,b,length,sheet)
    for k in range(9):
        u=(k+.5+random.uniform(-.2,.2))/9;length=random.uniform(.7,1.02)
        points=[]
        for j in range(42):
            t=j/41*length;p=Vector(path(side,u,t));p.x+=side*.007;p.y+=.009*math.sin(j*.4+k)
            points.append(p)
        tube('Silver_stream',points,random.uniform(.0018,.0035),silver)
    # Thin foam crests spill over the lip, not bulky white cylinders.
    for k in range(18):
        t=random.uniform(.012,.2);a=random.uniform(.01,.86);length=random.uniform(.025,.13)
        tube('Lip_foam',[(lambda p:(p[0],p[1],p[2]+.006))(path(side,a+length*i/8,t+.005*math.sin(i*.6))) for i in range(9)],.0025,white)
    for i in range(32):
        t=random.uniform(.52,1.13);u=random.random();p=Vector(path(side,u,t,random.uniform(-.18,.18)))
        p.x+=side*random.uniform(.015,.17);p.y+=random.uniform(-.08,.08)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=p);o=bpy.context.object
        r=random.uniform(.005,.013);o.scale=(r,r,r*random.uniform(1.8,3.8));o.data.materials.append(drops)
        o.name='Falling_droplet';o['waterfall_role']='spray';new.append(o)

# A small packed radial texture makes wisps fade smoothly into the sky.
image=bpy.data.images.new('Soft_water_mist',width=64,height=64,alpha=True)
pixels=[]
for y in range(64):
    for x in range(64):
        r=math.hypot((x-31.5)/31.5,(y-31.5)/31.5)
        a=max(0,1-r*r)**3*.23
        pixels.extend((.73,.86,.90,a))
image.pixels=pixels;image.pack()
mist=material('Soft_silver_mist',(.73,.86,.9),1,.2,0,.2)
p=mist.node_tree.nodes.get('Principled BSDF');tex=mist.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
mist.node_tree.links.new(tex.outputs['Color'],p.inputs['Base Color']);mist.node_tree.links.new(tex.outputs['Alpha'],p.inputs['Alpha'])
for side in [-1,1]:
    for i in range(6):
        t=.72+i*.065;center=Vector(path(side,.5,t));center.y+=random.uniform(-.17,.17)
        # Crossed vertical quads remain soft from both the normal view and orbit views.
        for angle in [0,math.pi/2]:
            bpy.ops.mesh.primitive_plane_add(size=1,location=center);o=bpy.context.object
            o.rotation_euler=(math.pi/2,0,angle);o.scale=(.46+i*.048,.33,1);o.data.materials.append(mist)
            o.name='Mist_wisp';o['waterfall_role']='mist';new.append(o)

# Join small parts by material to keep additional draw calls bounded.
groups=[(m,[o for o in new if o.data.materials[0]==m]) for m in [silver,white,drops,mist]]
for m,objects in groups:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();bpy.context.object.name='Waterfall_v1_'+m.name
stage=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in stage:
    if o not in original:
        for m in o.data.materials:m.use_backface_culling=False
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'sakura.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5,-9,5.5));camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=9.1;look(camera,(0,0,.45))
for loc,power,size in [((-3,-4,7),1100,5),((4,-2,4),700,4),((-4,4,3),800,4)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;look(o,(0,0,0))
scene.world=bpy.data.worlds.new('Waterfall_studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.27,.36,.54,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'waterfalls.blend'))
for name,loc,target,scale in [('courtyard',(5,-9,5.5),(0,0,.45),9.1),('waterfall-detail',(6,-5,2),(3.05,-1.3,-.5),3.1)]:
    camera.location=loc;look(camera,target);camera.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'preserved_meshes':len(original),'added_mesh_batches':len(stage)-len(original),'glb_bytes':(ASSET/'sakura.glb').stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('WATERFALL_COMPLETE',json.dumps(report))
