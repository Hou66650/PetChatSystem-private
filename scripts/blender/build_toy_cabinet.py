"""Author cabinet and removable toys, and detach existing island balls without changing scenery."""
import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2];OUT=R/'art/toy-cabinet-v1';ASSET=R/'static/models/petchat-toys-v1'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
def clear():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
# Keep the original island ball geometry, now as an addressable movable node.
reports={}
for theme,source,centre,material in [('snow','petchat-snow-v2/snow.glb',(1.35,-1.8,.15),'red'),('sakura','petchat-waterfalls-v1/sakura.glb',(-1.75,-.6,.13),'teal')]:
 clear();bpy.ops.import_scene.gltf(filepath=str(R/'static/models'/source));centre=Vector(centre);found=False
 for obj in list(bpy.context.scene.objects):
  if obj.type!='MESH' or not any(material in m.name.lower() for m in obj.data.materials):continue
  ids={v.index for v in obj.data.vertices if (obj.matrix_world@v.co-centre).length<.22}
  faces=[p for p in obj.data.polygons if all(i in ids for i in p.vertices)]
  if len(faces)<20:continue
  verts=sorted(set(i for p in faces for i in p.vertices));assert len(verts)<1500
  remap={v:i for i,v in enumerate(verts)};mesh=bpy.data.meshes.new('Detached_original_ball')
  mesh.from_pydata([tuple(obj.matrix_world@obj.data.vertices[i].co-centre) for i in verts],[],[[remap[i] for i in p.vertices] for p in faces]);mesh.update()
  for m in obj.data.materials:mesh.materials.append(m)
  for p,old in zip(mesh.polygons,faces):p.material_index=old.material_index;p.use_smooth=True
  ball=bpy.data.objects.new('IslandToy_ball',mesh);bpy.context.collection.objects.link(ball);ball.location=centre;ball['toy_id']='ball';ball['toy_source']='island'
  bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in verts],context='VERTS');bm.to_mesh(obj.data);bm.free();found=True;break
 assert found,theme+' original ball not found'
 bpy.ops.export_scene.gltf(filepath=str(ASSET/(theme+'.glb')),export_format='GLB',export_extras=True,export_animations=False)
 reports[theme]={'detached_vertices':len(verts),'bytes':(ASSET/(theme+'.glb')).stat().st_size}
clear();parts=[]
def mat(n,c,rough=.6,metal=0):
 m=bpy.data.materials.new(n);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal;return m
wood=mat('Honey oak',(.54,.31,.13));cream=mat('Warm ivory',(.86,.78,.59));sage=mat('Sage lacquer',(.28,.40,.29));brass=mat('Brass',(.69,.43,.15),.3,.65);red=mat('Coral rubber',(.76,.18,.12));teal=mat('Teal rope',(.09,.36,.35));yellow=mat('Duck ochre',(.88,.54,.07));orange=mat('Orange beak',(.85,.22,.025));dark=mat('Dark eyes',(.035,.025,.017));weave=mat('Basket weave',(.43,.31,.18))
def finish(o,m):o.data.materials.append(m);parts.append(o);return o
def box(p,s,m,bevel=.015):
 bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=finish(bpy.context.object,m);o.scale=s;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  mod=o.modifiers.new('Rounded edges','BEVEL');mod.width=bevel;mod.segments=3;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 return o
def uv(p,s,m,seg=16,rings=10):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=seg,ring_count=rings,radius=1,location=p);o=finish(bpy.context.object,m);o.scale=s
 for f in o.data.polygons:f.use_smooth=True
 return o
def rod(a,b,r,m,n=10):
 d=Vector(b)-Vector(a);bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=d.length,location=(Vector(a)+Vector(b))/2);o=finish(bpy.context.object,m);o.rotation_euler=d.to_track_quat('Z','Y').to_euler();return o
def ring(p,r,t,m,rot=(0,0,0)):
 bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=t,major_segments=32,minor_segments=8,location=p,rotation=rot);return finish(bpy.context.object,m)
def line(points,r,m):
 cu=bpy.data.curves.new('Detail curve','CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_depth=r;cu.bevel_resolution=1;s=cu.splines.new('POLY');s.points.add(len(points)-1)
 for v,p in zip(s.points,points):v.co=(*p,1)
 o=bpy.data.objects.new('Curve',cu);bpy.context.collection.objects.link(o);bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o.select_set(False);return finish(o,m)
def group(name,start,toy=None):
 selected=parts[start:];bpy.ops.object.select_all(action='DESELECT')
 for o in selected:o.select_set(True)
 bpy.context.view_layer.objects.active=selected[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
 if toy:bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY',center='BOUNDS')
 else:
  bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
 if toy:o['toy_id']=toy;o['toy_source']='cabinet'
 return o
# Cabinet: rounded side cheeks, separate back slats, shelf lips, pegs, paws and woven basket.
start=len(parts)
for x in [-.51,.51]:
 box((x,0,.59),(.07,.46,.98),wood,.032)
 for y in [-.16,.16]:rod((x,y,.015),(x,y,.17),.032,wood)
 for z in [.3,.6,.98]:uv((x,-.246,z),(.014,.007,.014),brass,10,6)
for i in range(9):box((-.44+i*.11,.21,.59),(.102,.034,.91),cream,.004)
for z in [.15,.39,.70,1.02]:box((0,0,z),(1.04,.49,.045),wood,.014);box((0,-.249,z+.015),(1.0,.015,.028),cream,.004)
for z,h in [(.55,.27),(.86,.27)]:
 for x in [-.175,.175]:box((x,.015,z),(.022,.41,h),sage,.006)
box((0,.02,1.08),(1.02,.46,.08),sage,.04)
uv((0,-.228,1.102),(.026,.008,.022),brass)
for x,z in [(-.031,1.129),(-.011,1.142),(.014,1.142),(.034,1.129)]:uv((x,-.228,z),(.009,.007,.012),brass,10,6)
box((0,-.03,.265),(.91,.35,.19),weave,.018)
for i in range(31):rod((-.435+i*.029,-.214,.19),(-.435+i*.029,-.214,.342),.0055,cream,6)
for j in range(9):rod((-.45,-.219,.19+j*.018),(.45,-.219,.19+j*.018),.0055,wood,6)
box((0,-.231,.32),(.15,.014,.025),dark,.006)
for x in [-.505,.505]:
 for k in range(3):line([(x,-.14+i*.024,.25+k*.20+.008*math.sin(i*.6)) for i in range(13)],.0018,cream)
cabinet=group('ToyCabinet',start);cabinet['toy_cabinet']=True
# Each toy is exported separately, centered at its own origin for natural carrying.
toys=[]
for kind in ['ball','disc','rope','bone','duck','brush','rattle']:
 start=len(parts)
 if kind=='ball':
  uv((0,0,0),(.105,.105,.105),red,24,16);ring((0,0,0),.104,.007,cream,(.7,.4,0))
 elif kind=='disc':
  uv((0,0,0),(.14,.14,.021),sage,24,8);ring((0,0,.007),.13,.012,cream);uv((0,0,.024),(.029,.031,.007),cream)
  for x,y in [(-.037,.033),(-.014,.049),(.014,.049),(.037,.033)]:uv((x,y,.026),(.01,.013,.005),cream,10,6)
 elif kind=='rope':
  for strand,m in enumerate([teal,cream,teal]):
   pts=[]
   for i in range(100):
    t=i/99*math.tau;a=t*7+strand*math.tau/3;r=.071+.014*math.cos(a);pts.append((r*math.cos(t),r*math.sin(t),.014*math.sin(a)))
   line(pts,.009,m)
  for side in [-1,1]:
   uv((side*.083,0,0),(.033,.038,.03),cream)
   for j in range(6):rod((side*.10,(j-2.5)*.007,0),(side*.145,(j-2.5)*.012,-.008),.005,teal if j%2 else cream,6)
 elif kind=='bone':
  uv((0,0,0),(.11,.037,.035),cream)
  for x in [-.10,.10]:
   for y in [-.028,.028]:uv((x,y,0),(.039,.032,.035),cream)
  for x in [-.075+i*.015 for i in range(11)]:rod((x,-.019,.028),(x,-.011,.034),.0018,weave,6)
 elif kind=='duck':
  uv((0,0,0),(.10,.065,.065),yellow);uv((0,-.035,.075),(.056,.051,.055),yellow);uv((0,-.085,.055),(.037,.04,.014),orange)
  for x in [-.044,.044]:uv((x,-.066,.094),(.009,.006,.009),dark,10,6);uv((x*1.9,0,.012),(.021,.05,.038),yellow)
  uv((0,.066,.034),(.036,.045,.021),yellow)
 elif kind=='brush':
  uv((0,0,0),(.065,.092,.019),wood);box((0,.115,-.006),(.045,.11,.025),wood,.014)
  for x in range(-3,4):
   for y in range(-4,5):
    if (x/3.4)**2+(y/4.4)**2<1:rod((x*.016,y*.017,.012),(x*.016,y*.017,.038),.004,cream,6)
 elif kind=='rattle':
  rod((0,0,-.13),(0,0,0),.022,wood,12);ring((0,0,.06),.062,.014,wood,(math.pi/2,0,0))
  for x,z in [(-.035,.06),(.035,.06),(0,.095)]:uv((x,-.005,z),(.025,.025,.025),brass);rod((x-.011,-.029,z),(x+.011,-.029,z),.002,dark,6)
 o=group('Toy_'+kind,start,kind);toys.append(o)
slots=[(-.35,-.045,.85),(0,-.03,.84),(.35,-.03,.82),(-.35,-.03,.51),(0,-.03,.49),(.34,-.02,.46),(.37,-.10,.59)]
for o,at in zip(toys,slots):o.location=at
# Force each prop to one vertex-colour batch, preserving material colors and independent pickup.
for o in [cabinet]+toys:
 attr=o.data.color_attributes.new(name='ToyColor',type='FLOAT_COLOR',domain='CORNER')
 for poly in o.data.polygons:
  color=o.data.materials[poly.material_index].diffuse_color
  for i in poly.loop_indices:attr.data[i].color=color
 o.data.materials.clear();o.data.materials.append(mat(o.name+'_paint',(1,1,1),.65))
 for poly in o.data.polygons:poly.material_index=0
# Material preview reads the same vertex colours as the WebGL asset.
for o in [cabinet]+toys:
 m=o.data.materials[0];node=m.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name='ToyColor';m.node_tree.links.new(node.outputs['Color'],m.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
bpy.ops.object.select_all(action='DESELECT')
for o in [cabinet]+toys:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'cabinet.glb'),export_format='GLB',use_selection=True,export_extras=True,export_animations=False)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2,-3,1.9));cam=bpy.context.object;scene.camera=cam;look(cam,(0,0,.55));cam.data.type='ORTHO';cam.data.ortho_scale=1.7
for at,energy in [((-2,-3,4),400),((3,-1,3),300),((0,2,3),350)]:bpy.ops.object.light_add(type='AREA',location=at);o=bpy.context.object;o.data.energy=energy;o.data.size=3;look(o,(0,0,.5))
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.world.color=(.3,.3,.3);scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'toy-cabinet.blend'));scene.render.filepath=str(OUT/'model.png');bpy.ops.render.render(write_still=True)
reports['cabinet']={'meshes':8,'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in [cabinet]+toys),'bytes':(ASSET/'cabinet.glb').stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(reports,indent=2));print('TOY_CABINET_COMPLETE',json.dumps(reports))
