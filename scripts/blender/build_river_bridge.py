"""Build the courtyard river and walkable arched bridge in an isolated Blender scene."""
import bpy, bmesh, math, random, json, re
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'art/river-v1'
ASSET = ROOT/'static/models/petchat-river-v1'
OUT.mkdir(parents=True, exist_ok=True)
ASSET.mkdir(parents=True, exist_ok=True)
layout = json.loads(re.search(r'const layout = (\{[\s\S]+?\});', (ROOT/'static/js/den/sakura-river-layout.js').read_text()).group(1))
river, bridge, rug = layout['water'][0], layout['bridges'][0], layout['rug']
random.seed(616)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-courtyard-v3/sakura.glb'))
lo, hi = river['z']-river['d']/2, river['z']+river['d']/2

# Cut an actual channel through the grass and island edge, not a blue overlay.
for o in list(bpy.context.scene.objects):
    if o.type != 'MESH': continue
    if '_rug' in o.name:
        # Previous rug edge radius is 1.60 m. Move the whole cushion behind the bank.
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            p.x *= rug['radius']/1.6
            p.y = p.y*rug['radius']/1.6-rug['z']
            v.co = p
        o.matrix_world = Matrix.Identity(4)
    if '_grass.' in o.name or '_edge.' in o.name and '_rug_' not in o.name:
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.transform(bm, matrix=o.matrix_world, verts=list(bm.verts))
        for z in (lo,hi):
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces), dist=0.000001,
                plane_co=(0,-z,0), plane_no=(0,1,0))
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if -hi+1e-6 < f.calc_center_median().y < -lo-1e-6], context='FACES')
        bm.to_mesh(o.data); bm.free(); o.matrix_world=Matrix.Identity(4)

pieces=[]
def material(name, color, rough=.7, metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    return m
cedar=material('Bridge_cedar',(.43,.21,.085))
lightwood=material('Bridge_board_alternate',(.57,.32,.135))
grain=material('Bridge_grain',(.26,.115,.041))
metal=material('Bridge_bronze',(.20,.26,.22),.4,.65)
brass=material('Bridge_brass',(.6,.37,.12),.35,.6)
stone=material('River_bank_stone',(.43,.47,.41))
water=material('River_jade_water',(.10,.43,.46),.24,.12)
foam=material('River_silver_ripples',(.48,.77,.74),.36)
reed=material('River_reeds',(.30,.41,.16))
flower=material('River_iris',(.51,.39,.67))
def finish(o,name,m):
    o.name=name;o.data.materials.append(m);pieces.append(o);return o
def soften(o,w=.009):
    mod=o.modifiers.new('Rounded crafted edges','BEVEL');mod.width=w;mod.segments=2
    bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
    mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=mod.name)
def box(name,p,d,m,w=.008):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=finish(bpy.context.object,name,m);o.scale=d
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if w:soften(o,w)
    return o
def line(name,points,r,m):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=1
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,v in zip(points,sp.points):v.co=(*p,1)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);cu.materials.append(m)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    bpy.ops.object.convert(target='MESH');pieces.append(o);return o
def mesh(name,verts,faces,m):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o);return finish(o,name,m)
def ground(x,z):
    return rug['base']+rug['rise']*max(0,min(1,(rug['radius']-math.hypot(x-rug['x'],z-rug['z']))/rug['fade']))
def deck(x,z):
    t=(z-bridge['z'])/bridge['d']+.5
    return max(ground(x,z),bridge['base']+bridge['rise']*math.sin(math.pi*t)**2)

# Jade water with a real recessed bed, clipped to the circular island boundary.
verts=[];faces=[]
for j in range(17):
    z=lo+(hi-lo)*j/16;span=math.sqrt(3.2**2-z*z)
    for i in range(65):verts.append((-span+2*span*i/64,-z,-.055))
for j in range(16):
    for i in range(64):
        a=j*65+i;faces.append((a+65,a+66,a+1,a))
o=mesh('Recessed_river',verts,faces,water)
mod=o.modifiers.new('Visible river edge depth','SOLIDIFY');mod.thickness=.12
bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
# Subtle long current marks and short concentric ripples.
for i in range(46):
    z=random.uniform(lo+.07,hi-.07);span=math.sqrt(3.2**2-z*z)-.15
    x=random.uniform(-span,span);length=random.uniform(.06,.23)
    if abs(x)<1.06:continue
    line('Current_ripple',[(x+length*k/8,-z+.006*math.sin(k*.7),-.050) for k in range(9) if abs(x+length*k/8)<span],.0025,foam)
for z in (lo,hi):
    span=math.sqrt(3.2**2-z*z)
    count=math.ceil(2*span/.20)
    for i in range(count):
        x=-span+(i+.5)*2*span/count
        o=box('Dressed_bank_stone',(x,-z,-.07),(2*span/count-.008,.085,.23),stone,.023)
        o.rotation_euler.z=random.uniform(-.035,.035)

# Planks have continuous arched top profiles, separated by narrow joinery seams.
start=bridge['z']-bridge['d']/2;end=bridge['z']+bridge['d']/2
width=bridge['w'];boards=30
for i in range(boards):
    a=start+bridge['d']*i/boards+.0015;b=start+bridge['d']*(i+1)/boards-.0015
    corners=[(-width/2,a),(width/2,a),(width/2,b),(-width/2,b)]
    vs=[(x,-z,deck(x,z)-depth) for depth in (.045,0) for x,z in corners]
    o=mesh('Arched_deck_plank',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],cedar if i%3 else lightwood)
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
    soften(o,.002)
    z=(a+b)/2
    for lane in [-1,1]:
        line('Fine_board_grain',[(x,-z+lane*.018+.002*math.sin(k),deck(x,z)+.003) for k,x in enumerate([-.75+j*.1 for j in range(16)])],.0013,grain)
    for x in [-.76,.76]:
        box('Deck_fastener',(x,-z,deck(x,z)+.003),(.014,.016,.004),metal,.002)
for side in [-1,1]:
    x=side*(width-bridge['rail'])/2
    # Curved structural beams and two handrail levels, aligned to the navigation rails.
    for offset,r,m,name in [(-.052,.038,cedar,'Load_bearing_arch'),(.25,.022,lightwood,'Lower_rail'),(.49,.035,cedar,'Handrail')]:
        line(name,[(x,-(start+(end-start)*i/40),deck(x,start+(end-start)*i/40)+offset) for i in range(41)],r,m)
    for i in range(7):
        z=start+(end-start)*i/6;h=deck(x,z)
        box('Rail_post',(x,-z,h+.24),(.075,.075,.49),cedar,.008)
        box('Bronze_post_cap',(x,-z,h+.51),(.085,.085,.035),metal,.009)
        box('Brass_cap_inlay',(x,-z,h+.533),(.03,.03,.01),brass,.004)
    for i in range(18):
        z=start+(end-start)*(i+.5)/18;h=deck(x,z)
        box('Bridge_baluster',(x,-z,h+.135),(.024,.027,.23),lightwood,.005)
    for z in (lo,hi):box('Stone_bridge_abutment',(x,-z,-.085),(.20,.30,.24),stone,.02)
# Small bank plants outside the walking clearance and away from the bridge.
for x,z in [(-2.35,lo),(-1.45,hi),(1.6,lo),(2.35,hi)]:
    for i in range(6):
        dx=random.uniform(-.065,.065);h=random.uniform(.09,.21)
        line('Bank_reed',[(x+dx,-z,.025),(x+dx+.018,-z-.02,h*.6),(x+dx+.04,-z-.03,h)],.005,reed)
    for i in [-1,0,1]:
        box('Iris_petal',(x+i*.021,-z,.18+abs(i)*.006),(.037,.025,.015),flower,.009)

groups=[(m,[o for o in pieces if o.data.materials[0]==m]) for m in [cedar,lightwood,grain,metal,brass,stone,water,foam,reed,flower]]
for m,objects in groups:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();bpy.context.object.name='River_v1_'+m.name
stage=[o for o in bpy.context.scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'sakura.glb'),export_format='GLB',use_selection=True,export_animations=False)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5,-9,6));camera=bpy.context.object;scene.camera=camera
camera.data.type='ORTHO';camera.data.ortho_scale=8;look(camera,(0,0,.6))
for loc,power,size in [((-3,-4,7),1050,5),((4,-1,5),650,5),((-2,5,6),850,4)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;look(o,(0,0,0))
scene.world=bpy.data.worlds.new('River_studio');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.66,.78,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'river-bridge.blend'))
for name,loc,target,scale in [('courtyard',(5,-9,6),(0,0,.9),8.4),('bridge-detail',(3.6,-5,3.2),(0,-1.3,.1),4.7)]:
    camera.location=loc;look(camera,target);camera.data.ortho_scale=scale
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'mesh_batches':len(stage),'glb_bytes':(ASSET/'sakura.glb').stat().st_size,'layout':layout}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('RIVER_COMPLETE',json.dumps(report))
