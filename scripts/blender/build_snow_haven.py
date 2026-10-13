"""Model the approved snow-haven design board as a compact material-batched GLB."""
import bpy, math, random, json, re
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2];OUT=R/'art/snow-haven-v2';ASSET=R/'static/models/petchat-snow-v2'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True)
layout=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(R/'static/js/den/snow-haven-layout.js').read_text()).group(1))
random.seed(182)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
pieces=[]
def mat(name,c,rough=.7,metal=0,emission=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*c,1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
 p.inputs['Base Color'].default_value=(*c,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 if emission:p.inputs['Emission Color'].default_value=(*c,1);p.inputs['Emission Strength'].default_value=emission
 return m
snow=mat('Powder_snow',(.85,.92,.96),.9);snowblue=mat('Snow_shadow',(.57,.72,.81),.9)
ice=mat('Glacier_blue',(.15,.36,.51),.32,.08);icebright=mat('Ice_facet_light',(.36,.62,.73),.27,.06)
rock=mat('Winter_slate',(.24,.32,.38),.95);wood=mat('Lodge_cedar',(.32,.15,.07));woodlight=mat('Cut_timber',(.48,.28,.13));grain=mat('Wood_grain',(.17,.075,.035))
pine=mat('Fir_needles',(.09,.22,.18),.95);metal=mat('Iron_fittings',(.15,.22,.26),.37,.65);brass=mat('Lantern_brass',(.55,.34,.10),.32,.65)
amber=mat('Warm_windows',(1,.54,.16),.5,0,.65);dark=mat('Doorway_shadow',(.045,.038,.034))
red=mat('Wool_and_rubber_red',(.52,.07,.065),.83);carrot=mat('Carrot',(.90,.29,.035));pond=mat('Frozen_pond',(.18,.54,.66),.23,.05)
mats=[snow,snowblue,ice,icebright,rock,wood,woodlight,grain,pine,metal,brass,amber,dark,red,carrot,pond]
def finish(o,name,m):o.name=name;o.data.materials.append(m);pieces.append(o);return o
def bevel(o,w=.012):
 mod=o.modifiers.new('Soft crafted edges','BEVEL');mod.width=w;mod.segments=2
 bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=mod.name)
def box(name,p,s,m,w=.008):
 bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=finish(bpy.context.object,name,m);o.scale=s
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if w:bevel(o,w)
 return o
def sphere(name,p,s,m,seg=12,rings=8):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=seg,ring_count=rings,radius=1,location=p);o=finish(bpy.context.object,name,m);o.scale=s
 for f in o.data.polygons:f.use_smooth=True
 return o
def cone(name,p,r1,r2,h,m,n=12):
 bpy.ops.mesh.primitive_cone_add(vertices=n,radius1=r1,radius2=r2,depth=h,location=p);return finish(bpy.context.object,name,m)
def rod(name,a,b,r,m,n=10):
 d=Vector(b)-Vector(a);o=cone(name,(Vector(a)+Vector(b))/2,r,r,d.length,m,n);o.rotation_euler=d.to_track_quat('Z','Y').to_euler();return o
def line(name,points,r,m):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=1;sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 for v,p in zip(sp.points,points):v.co=(*p,1)
 o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);cu.materials.append(m)
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH');pieces.append(o);return o
def mesh(name,vs,fs,m):
 data=bpy.data.meshes.new(name);data.from_pydata(vs,[],fs);data.update();o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);return finish(o,name,m)
def torus(name,p,major,minor,m):
 bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=24,minor_segments=8,location=p);o=finish(bpy.context.object,name,m)
 for f in o.data.polygons:f.use_smooth=True
 return o

# Faceted glacial underside and a level, clear playable snow surface.
N=80;vs=[]
for layer in range(4):
 for i in range(N):
  a=i*math.tau/N;noise=random.uniform(-.07,.07)
  radius=[3.18,3.08,2.68,1.45][layer]+noise
  z=[-.06,-.32,-.74,-1.08][layer]+(random.uniform(-.10,.06) if layer else 0)
  vs.append((radius*math.cos(a),radius*math.sin(a),z))
fs=[]
for layer in range(3):
 for i in range(N):
  a=layer*N+i;b=layer*N+(i+1)%N;c=b+N;d=a+N;fs.extend([(a,b,d),(b,c,d)])
fs.append(tuple(range(3*N,4*N)))
o=mesh('Faceted_floating_glacier',vs,fs,ice);o.data.materials.append(icebright);o.data.materials.append(rock)
for p in o.data.polygons:p.material_index=random.choices([0,1,2],[.50,.25,.25])[0]
cone('Solid_snow_platform',(0,0,-.052),3.19,3.19,.14,snow,96)
for i in range(92):
 a=(i+random.uniform(-.2,.2))*math.tau/92;r=3.02
 o=sphere('Snow_overhang',(r*math.cos(a),r*math.sin(a),random.uniform(-.03,.0)),(random.uniform(.16,.25),random.uniform(.15,.23),random.uniform(.08,.16)),snow);o.rotation_euler.z=a
 if i%2==0:
  h=random.uniform(.16,.48);o=cone('Rim_icicle',(3.13*math.cos(a),3.13*math.sin(a),-.08-h/2),.009,.035,h,icebright,7)
# Perimeter rock clusters, all outside the free central area.
for x,z,r in [(-2.5,-1.3,.24),(-1.3,-2.6,.24),(2.65,1.1,.2),(-2.6,1.3,.18),(1.9,2.3,.18)]:
 sphere('Snow_rock',(x,-z,.08),(r,r*.82,r*.7),rock,10,6)
 sphere('Rock_snow_cap',(x,-z,.16),(r*.95,r*.8,r*.33),snow)

# Three varied firs: trunks, radial wood branches, needle tiers and individual snow pillows.
for ti,(x,z,h,r) in enumerate([(-1.85,-1.65,2.12,.58),(-.75,-2.35,1.65,.46),(-2.5,-.65,1.48,.43)]):
 y=-z;cone('Fir_trunk',(x,y,h*.42),.073,.042,h*.84,wood)
 for k in range(5):
  level=.34+k*(h-.50)/5;rr=r*(1-k*.17)
  cone('Fir_needle_tier',(x,y,level+.17),rr,.035,.44,pine,14)
  for j in range(8):
   a=j*math.tau/8+k*.38+ti+random.uniform(-.14,.14)
   tip=(x+rr*.92*math.cos(a),y+rr*.92*math.sin(a),level+.01)
   rod('Fir_branch',(x,y,level+.13),tip,.013,wood)
   p=(x+rr*.61*math.cos(a),y+rr*.61*math.sin(a),level+.19)
   o=sphere('Branch_snow_pillow',p,(rr*random.uniform(.32,.44),rr*random.uniform(.18,.28),random.uniform(.07,.12)),snow);o.rotation_euler.z=a
   for side in [-1,1]:
    b=a+side*.21
    q=(x+rr*.83*math.cos(b),y+rr*.83*math.sin(b),level+.105)
    o=sphere('Uneven_snow_branch_tip',q,(rr*.20,rr*.15,.046),snow);o.rotation_euler.z=b
    rod('Needle_branch_tip',tip,(x+rr*1.04*math.cos(b),y+rr*1.04*math.sin(b),level-.016),.016,pine,6)
 cone('Snowy_tree_tip',(x,y,h-.025),.115,0,.27,snow)

# Warm timber dog lodge, with a gabled shingle roof and thick irregular snow blanket.
cx,cy=layout['obstacles'][3]['x'],-layout['obstacles'][3]['z'];front=cy-.53
box('Lodge_stone_foundation',(cx,cy,.075),(1.30,1.13,.12),rock,.035)
for k in range(7):
 zz=.16+k*.108
 for side in [-1,1]:box('Side_wall_log',(cx+side*.565,cy,zz),(.13,1.10,.112),wood,.026)
 box('Back_wall_log',(cx,cy+.50,zz),(1.10,.13,.112),wood,.026)
 # Leave the doorway opening between the front jambs.
 for side in [-1,1]:box('Front_wall_log',(cx+side*.425,front,zz),(.30,.135,.112),wood,.022)
for side in [-1,1]:
 box('Front_corner_post',(cx+side*.53,front-.045,.48),(.09,.08,.85),woodlight)
 for j in range(5):line('Timber_grain',[(cx+side*.59,cy-.44+k*.10,.18+j*.13+.004*math.sin(k+j)) for k in range(10)],.0016,grain)
mesh('Front_gable',[(cx-.59,front,.86),(cx+.59,front,.86),(cx,front,1.45)],[(0,1,2)],wood)
mesh('Rear_gable',[(cx-.59,cy+.52,.86),(cx+.59,cy+.52,.86),(cx,cy+.52,1.45)],[(2,1,0)],wood)
box('Doorway_dark_interior',(cx,front+.045,.34),(.51,.026,.65),dark)
for i in range(5):box('Door_back_plank',(cx-.20+i*.10,front+.04,.34),(.085,.02,.60),wood)
arch=[(cx-.27,front-.082,.025),(cx-.27,front-.082,.48)]
arch += [(cx+.27*math.cos(math.pi-i*math.pi/18),front-.082,.48+.27*math.sin(math.pi-i*math.pi/18)) for i in range(19)]
arch += [(cx+.27,front-.082,.025)]
line('Carved_door_arch',arch,.041,woodlight)
box('Door_header',(cx,front,.815),(.60,.135,.13),wood,.018)
for side in [-1,1]:
 points=[(cx+side*.27,front-.069,.76)]
 points += [(cx+side*.27*math.cos(a),front-.069,.48+.27*math.sin(a)) for a in [i*math.pi/2/12 for i in range(13)]]
 mesh('Arch_timber_spandrel',points,[tuple(range(len(points)))],wood)
box('Door_threshold',(cx,front-.055,.055),(.61,.25,.08),woodlight,.02)
for side in [-1,1]:
 # Two roof planes; each has visible shingles and a sculpted snow cover.
 angle=side*math.atan2(.64,.70)
 o=box('Roof_board',(cx+side*.35,cy,1.155),(.97,1.30,.075),woodlight,.008);o.rotation_euler.y=angle
 for row in range(5):
  xx=.08+row*.145;hh=1.475-xx*.91
  for j in range(7):
   yy=cy-.58+j*.18+(row%2)*.015
   o=box('Overlapping_roof_shingle',(cx+side*xx,yy,hh),(.21,.169,.024),wood,.004);o.rotation_euler.y=angle
   if row==4:line('Shingle_end_grain',[(cx+side*(xx-.04+k*.012),yy,hh+.019) for k in range(7)],.0014,grain)
 o=box('Roof_snow_blanket',(cx+side*.34,cy,1.242),(.97,1.35,.12),snow,.048);o.rotation_euler.y=angle
 for j in range(9):
  yy=cy-.62+j*.155
  sphere('Eave_snow_lobe',(cx+side*random.uniform(.66,.70),yy,.965),(.11,random.uniform(.08,.15),random.uniform(.065,.13)),snow)
  if j%2==0:cone('Eave_icicle',(cx+side*.70,yy,.85),.003,.019,.16,icebright,7)
for j in range(8):sphere('Ridge_snow',(cx,cy-.59+j*.17,1.535),(.13,.145,.10),snow)
# Round attic window with glowing panes and cross mullions.
o=cone('Attic_glow',(cx,front-.026,1.075),.126,.126,.023,amber,32);o.rotation_euler.x=math.pi/2
o=torus('Attic_window_frame',(cx,front-.054,1.075),.128,.020,woodlight);o.rotation_euler.x=math.pi/2
box('Window_cross',(cx,front-.068,1.075),(.235,.017,.018),woodlight,.003)
box('Window_cross',(cx,front-.068,1.075),(.018,.017,.235),woodlight,.003)
# Stone chimney, cap and log stack.
for k in range(5):
 for j in range(2):box('Chimney_brick',(cx+.34+(j-.5)*.13,cy+.30,1.38+k*.10),(.122,.24,.092),rock,.01)
box('Chimney_snow_cap',(cx+.34,cy+.30,1.91),(.33,.32,.095),snow,.035)
box('Chimney_opening',(cx+.34,cy+.30,1.96),(.16,.15,.007),dark,.004)
for k in range(3):
 for j in range(3-k):
  x=2.11+j*.13+k*.065;z=.10+k*.12
  rod('Stacked_firewood',(x,1.24,z),(x,1.85,z),.073,wood,12)
  o=cone('Log_cut_end',(x,1.235,z),.062,.062,.012,woodlight,16);o.rotation_euler.x=math.pi/2
  o=torus('Log_growth_ring',(x,1.225,z),.036,.0025,grain);o.rotation_euler.x=math.pi/2
box('Log_stack_snow',(2.24,1.57,.39),(.39,.70,.055),snow,.024)

# Rear fence and two warm lantern posts.
for x in [-1.7,-.85,0,.85,1.7]:
 box('Fence_post',(x,2.83,.29),(.095,.12,.55),woodlight)
 sphere('Fence_post_snow',(x,2.83,.585),(.08,.085,.045),snow)
for z in [.20,.43]:
 box('Fence_rail',(0,2.83,z),(3.55,.075,.065),wood)
 box('Fence_rail_snow',(0,2.83,z+.045),(3.55,.082,.025),snow,.012)
for x,z in [(2.35,-.8),(0,-2.8)]:
 y=-z;cone('Lantern_stone_foot',(x,y,.065),.12,.10,.12,rock,8)
 box('Lantern_post',(x,y,.49),(.075,.075,.84),woodlight)
 box('Lantern_glass',(x,y,1.00),(.16,.16,.23),amber,.008)
 for a in [-1,1]:
  for b in [-1,1]:box('Lantern_corner',(x+a*.092,y+b*.092,1.0),(.018,.018,.27),brass,.003)
 for h in [.875,1.13]:box('Lantern_frame',(x,y,h),(.22,.22,.035),metal,.008)
 cone('Lantern_hip_roof',(x,y,1.18),.19,.04,.09,metal,4)
 sphere('Lantern_roof_snow',(x,y,1.22),(.145,.14,.048),snow)

# Snow-dusted sled with curled runners, slatted seat and rope.
sx,sy=layout['obstacles'][5]['x'],-layout['obstacles'][5]['z']
for side in [-1,1]:
 x=sx+side*.25
 line('Curved_sled_runner',[(x,sy-.60,.24),(x,sy-.61,.16),(x,sy-.56,.08),(x,sy-.42,.055),(x,sy+.53,.055)],.018,brass)
 for y in [-.35,.35]:rod('Sled_leg',(x,sy+y,.065),(x,sy+y,.26),.023,woodlight)
for i in range(5):
 x=sx-.24+i*.12
 box('Sled_seat_slat',(x,sy,.285),(.10,1.02,.045),woodlight,.009)
 for j in range(4):sphere('Sled_snow_patch',(x,sy-.35+j*.24,.32),(.045,.068,.022),snow)
line('Sled_pull_rope',[(sx-.23,sy-.47,.29),(sx-.22,sy-.74,.045),(sx,sy-.80,.032),(sx+.22,sy-.74,.045),(sx+.23,sy-.47,.29)],.008,wood)

# Snowman with knit scarf, coal details, twig arms and a carrot nose.
x,y=-2.35,-.55
sphere('Snowman_body',(x,y,.26),(.235,.22,.25),snow,20,12)
sphere('Snowman_head',(x,y,.60),(.16,.155,.16),snow,20,12)
torus('Knitted_scarf',(x,y,.47),.15,.031,red)
box('Scarf_tail',(x+.05,y-.175,.34),(.065,.035,.22),red,.01)
for dx in [-.055,.055]:sphere('Coal_eye',(x+dx,y-.145,.63),(.019,.014,.019),dark)
o=cone('Carrot_nose',(x,y-.205,.59),.036,0,.15,carrot);o.rotation_euler.x=math.pi/2
for z in [.21,.31,.4]:sphere('Coal_button',(x,y-.219,z),(.017,.012,.017),dark)
for side in [-1,1]:
 a=(x+side*.19,y,.32);b=(x+side*.40,y-.025,.49);rod('Snowman_twig_arm',a,b,.012,wood)
 rod('Twig_finger',b,(b[0]+side*.075,b[1],b[2]+.075),.008,wood)
 rod('Twig_finger',(b[0]-side*.03,b[1],b[2]-.025),(b[0]+side*.06,b[1],b[2]-.025),.007,wood)

# Frozen pool is a decorative obstacle; no walkable water or ice shortcuts.
px,py=layout['obstacles'][7]['x'],-layout['obstacles'][7]['z']
o=cone('Frozen_pool',(px,py,.020),1,1,.012,pond,48);o.scale=(.70,.43,1)
for i in range(24):
 a=i*math.tau/24;x=px+.76*math.cos(a);y=py+.47*math.sin(a)
 size=random.uniform(.8,1.2)
 o=sphere('Pond_border_rock',(x,y,.055),(.12*size,.10*size,.082),rock,10,6);o.rotation_euler.z=a
 o=sphere('Pond_border_snow',(x,y,.108),(.12*size,.105*size,.043),snow);o.rotation_euler.z=a
for i in range(13):
 a=random.random()*math.tau;r=random.uniform(.1,.55)
 x=px+r*math.cos(a);y=py+r*.53*math.sin(a)
 line('Ice_crack',[(x,y,.029),(x+.10*math.cos(a+.3),y+.07*math.sin(a+.3),.029),(x+.17*math.cos(a),y+.13*math.sin(a),.029)],.0018,snowblue)
 if i%3==0:line('Crack_branch',[(x,y,.029),(x-.08,y+.07,.029)],.0013,snow)

# Food, water, rubber ball and subtle paw impressions, leaving navigation centre clear.
for x,z,food in [(.3,2.4,True),(.8,2.35,False)]:
 y=-z;cone('Bowl_base',(x,y,.07),.16,.17,.10,metal,24);torus('Bowl_rim',(x,y,.125),.16,.018,brass)
 cone('Bowl_contents',(x,y,.13),.14,.14,.008,wood if food else pond,24)
 if food:
  for j in range(24):
   a=random.random()*math.tau;r=.12*math.sqrt(random.random());sphere('Kibble',(x+r*math.cos(a),y+r*math.sin(a),.148),(.018,.016,.013),woodlight,8,6)
sphere('Red_play_ball',(1.35,-1.8,.15),(.125,.125,.125),red,20,12)
for i in range(10):
 t=i/9;x=.2+.82*t+(-1 if i%2 else 1)*.065;y=.22+.50*t
 sphere('Paw_impression',(x,y,.021),(.035,.043,.003),snowblue,10,6)
 for dx in [-.027,0,.027]:sphere('Paw_toe',(x+dx,y+.05,.021),(.011,.014,.003),snowblue,8,6)

# Bake transforms and merge material batches. Original authored detail stays editable as mesh islands.
groups=[]
for m in mats:
 groups.append((m,[o for o in pieces if len(o.data.materials)==1 and o.data.materials[0]==m]))
for m,objects in groups:
 if not objects:continue
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();bpy.context.object.name='SnowHaven_'+m.name
stage=[o for o in bpy.context.scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'snow.glb'),export_format='GLB',use_selection=True,export_animations=False)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5,-9,6));cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=8.2;look(cam,(0,0,.45))
for loc,power,size in [((-3,-4,7),1000,5),((4,-2,5),700,5),((-2,5,6),900,4)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;look(o,(0,0,.3))
scene.world=bpy.data.worlds.new('Winter_studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.38,.53,.69,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1500;scene.render.resolution_y=1200;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'snow-haven.blend'))
for name,loc,target,scale in [('courtyard',(5,-9,6),(0,0,.45),8.2),('lodge-detail',(3,-3,2.6),(1.25,1.65,.9),2.5),('ice-detail',(-5,-6,3),(-1.4,-1.5,-.15),3.1)]:
 cam.location=loc;look(cam,target);cam.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'mesh_batches':len(stage),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in stage),'glb_bytes':(ASSET/'snow.glb').stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('SNOW_HAVEN_COMPLETE',json.dumps(report))
