import bpy, math, random
from pathlib import Path
from mathutils import Vector
random.seed(18)
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'static/models/petchat-cat-home-v1';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def mat(n,c,rough=.65,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*c,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal;return m
wood=[mat('cedar_'+str(i),(.23+i*.018,.115+i*.012,.055+i*.008)) for i in range(5)]
roof=mat('sage_roof',(.16,.28,.22));trim=mat('end_grain',(.43,.27,.13));cloth=mat('linen',(.52,.62,.48));thread=mat('piping',(.78,.72,.53));ceramic=mat('glazed_cream',(.72,.67,.49),.22);water=mat('water',(.12,.36,.38),.12,.25);food=mat('kibble',(.24,.095,.035));brass=mat('brass',(.55,.34,.12),.3,.7)
def finish(o,n,m):
 o.name=n;o.data.materials.append(m);return o
def cube(n,x,z,y,w,d,h,m,bevel=.025):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(x,-z,y));o=bpy.context.object;o.dimensions=(w,d,h);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:mod=o.modifiers.new('soft edges','BEVEL');mod.width=bevel;mod.segments=2;bpy.ops.object.modifier_apply(modifier=mod.name)
 return finish(o,n,m)
def sphere(n,x,z,y,scale,m):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=10,location=(x,-z,y));o=bpy.context.object;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 for f in o.data.polygons:f.use_smooth=True
 return finish(o,n,m)
def torus(n,x,z,y,r,t,m):
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=t,major_segments=40,minor_segments=10,location=(x,-z,y));return finish(bpy.context.object,n,m)
# World coordinates shared with the browser navigation; entrance faces +Z.
for row in range(8):
 y=.14+row*.16
 for x in [-4.4,-1.6]:cube('side_plank',x,4.35,y,.14,2.3,.15,wood[row%5])
 cube('back_plank',-3,3.25,y,2.8,.14,.15,wood[(row+2)%5])
for x in [-4.4,-1.6]:
 for z in [3.25,5.45]:cube('corner_post',x,z,.77,.19,.19,1.48,trim)
# Shingled sloping roof, high enough for the cat to stand inside.
for side in [-1,1]:
 for row in range(7):
  for col in range(7):
   x=-3+side*(.12+row*.21);z=3.06+col*.4;y=2.0-(abs(x+3))*.38
   o=cube('roof_shingle',x,z,y,.30,.43,.065,roof,.015);o.rotation_euler[1]=side*math.atan(.38)
cube('ridge',-3,4.26,2.04,.12,3.05,.12,trim)
for x in [-4.4,-1.6]:cube('front_trim',x,5.48,1.47,.22,.2,.12,trim)
# Flat sleeping pad: no hidden platform requiring a vertical teleport.
sphere('quilted_pad',-3,4.62,.065,(1.04,.76,.065),cloth)
for i in range(12):
 a=i*math.tau/12;sphere('stitched_button',-3+math.cos(a)*.81,4.62+math.sin(a)*.54,.11,(.022,.022,.012),thread)
for i in range(5):cube('threshold_board',-3+(i-2)*.48,5.65,.045,.46,.36,.04,wood[i])
for x in [-4.4,-1.6]:
 for y in [.22,.65,1.08]:sphere('bronze_pin',x,5.56,y,(.026,.014,.026),brass)
cube('nameplate',-3,5.56,1.65,.65,.08,.22,trim)
# Paw sign without font dependency.
for x,z in [(-3,1.64),(-3.17,1.72),(-3.06,1.76),(-2.94,1.76),(-2.83,1.72)]:sphere('paw_inlay',x,5.61,z,(.055,.014,.045),brass)
# Feeding station: cat approaches from Z=4.85, mouth reaches the bowl at Z=5.38.
cube('feeding_stand',.45,5.38,.265,1.35,.65,.05,trim)
for x in [-.16,1.06]:
 for z in [5.13,5.63]:cube('stand_leg',x,z,.135,.055,.055,.23,trim,.01)
for x,kind in [(.1,'food'),(.8,'water')]:
 torus(kind+'_bowl',x,5.38,.36,.24,.055,ceramic)
 sphere(kind+'_base',x,5.38,.275,(.24,.24,.06),ceramic)
 if kind=='water':sphere('water_surface',x,5.38,.325,(.205,.205,.012),water)
 else:
  for i in range(42):
   a=random.random()*math.tau;r=math.sqrt(random.random())*.18;sphere('kibble',x+math.cos(a)*r,5.38+math.sin(a)*r,.33+random.random()*.025,(.026,.02,.018),food)
# Batch by material to keep browser draw calls low.
for material in list(bpy.data.materials):
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.active_material==material]
 if not objects:continue
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();objects[0].name='cat_home_'+material.name
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'cat-home.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'cat-home.glb'),export_format='GLB',export_yup=True)
# Preview render only, not exported.
cube('preview_floor',-2,4.4,-.05,8,7,.1,mat('preview_ground',(.11,.17,.13)))
bpy.ops.object.camera_add(location=(3,-10,5));cam=bpy.context.object;cam.rotation_euler=(Vector((-2,-4.5,.7))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=7;bpy.context.scene.camera=cam
for loc,power,size in [((0,-7,7),1400,5),((-6,-3,5),1000,4)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((-2,-4,0))-o.location).to_track_quat('-Z','Y').to_euler()
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=24;s.render.resolution_x=1000;s.render.resolution_y=800;s.render.resolution_percentage=100;s.world.color=(.25,.25,.25);s.render.filepath=str(OUT/'preview.png');bpy.ops.render.render(write_still=True)
