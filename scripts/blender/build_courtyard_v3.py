"""Detailed garden lantern and timber fence; preserve the v2 tree and courtyard."""
import bpy,bmesh,math,random,json
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[2];OUT=R/'art/courtyard-v3';ASSET=R/'static/models/petchat-courtyard-v3'
OUT.mkdir(parents=True,exist_ok=True);ASSET.mkdir(parents=True,exist_ok=True);random.seed(415)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(R/'static/models/petchat-sakura-v2/sakura.glb'))
for o in list(bpy.context.scene.objects):
    if any(s in o.name for s in ['_wood.','_wood_light.','_lamp.']):bpy.data.objects.remove(o,do_unlink=True)
    elif '_stone' in o.name:
        bm=bmesh.new();bm.from_mesh(o.data)
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if (o.matrix_world@v.co).x>1.93 and (o.matrix_world@v.co).y>.9],context='VERTS')
        bm.to_mesh(o.data);bm.free()

def mat(name,rgb,rough=.65,metal=0,emission=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*rgb,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    if emission:p.inputs['Emission Color'].default_value=(*rgb,1);p.inputs['Emission Strength'].default_value=emission
    return m
wood=mat('Honey_cedar',(.47,.255,.105));endgrain=mat('Cedar_endgrain',(.60,.36,.16));groove=mat('Wood_grain',(.32,.15,.063))
stone=mat('Warm_grey_granite',(.38,.41,.365),.95);stoneedge=mat('Carved_stone_edges',(.49,.51,.445),.92)
bronze=mat('Aged_bronze',(.18,.225,.18),.38,.65);brass=mat('Brass_pegs',(.51,.32,.115),.32,.72)
roofmat=mat('Glazed_sage_roof',(.20,.32,.29),.32,.25);roofedge=mat('Roof_edge_highlight',(.31,.43,.37),.38,.25)
paper=mat('Warm_luminous_window',(1,.66,.29),.72,0,.75);moss=mat('Moss',(.21,.30,.11),1)
pieces=[]
def finish(o,name,material):
    o.name=name;o.data.materials.append(material);pieces.append(o);return o
def bevel(o,width=.015):
    m=o.modifiers.new('Soft edges','BEVEL');m.width=width;m.segments=3
    bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=m.name)
    m=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');bpy.ops.object.modifier_apply(modifier=m.name)
def cube(name,p,scale,material,edge=.012):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=bpy.context.object;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);finish(o,name,material)
    if edge:bevel(o,edge)
    return o
def cylinder(name,p,r,depth,material,vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=p);o=finish(bpy.context.object,name,material);bevel(o,min(.009,depth*.13));return o
def ball(name,p,scale,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,radius=1,location=p);o=finish(bpy.context.object,name,material);o.scale=scale
    for f in o.data.polygons:f.use_smooth=True
    return o
def line(name,points,r,material):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=r;cu.bevel_resolution=1;cu.resolution_u=1
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for v,p in zip(sp.points,points):v.co=(*p,1)
    o=bpy.data.objects.new(name,cu);bpy.context.collection.objects.link(o);cu.materials.append(material)
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH');pieces.append(o);return o
# Stout chamfered posts, stone shoes and copper caps with round pegs.
fy=2.65
for i,x in enumerate([-1.72,-.86,0,.86,1.72]):
    cube('Fence_stone_shoe',(x,fy,.055),(.24,.24,.10),stone,.023)
    cube('Fence_post',(x,fy,.37),(.135,.15,.62),wood,.018)
    cube('Post_collar',(x,fy,.625),(.163,.176,.055),endgrain,.013)
    cube('Copper_post_cap',(x,fy,.673),(.195,.21,.045),bronze,.015)
    ball('Cap_finial',(x,fy,.704),(.031,.031,.025),brass)
    for z in [.205,.53]:
        cube('Peg_plate',(x,fy-.081,z),(.073,.013,.062),bronze,.008)
        peg=cylinder('Joinery_pin',(x,fy-.093,z),.013,.013,brass);peg.rotation_euler.x=math.pi/2
    for j in range(4):
        xx=x+(-.046+j*.03)
        line('Post_grain',[(xx+.004*math.sin(k+j),fy-.076,.13+k*.073) for k in range(7)],.0018,groove)
for i in range(4):
    a=-1.72+i*.86;b=a+.86;center=(a+b)/2
    for z in [.20,.53]:
        cube('Mortised_rail',(center,fy,z),(.85,.105,.085),wood,.011)
        for j in range(3):
            line('Rail_grain',[(a+.08+k*.07,fy-.054,z-.021+j*.019+.003*math.sin(k*.9+j)) for k in range(11)],.0017,groove)
    # Open spaced slats leave the cherry tree silhouette visible.
    for j in range(1,5):
        x=a+.086+j*.138
        cube('Vertical_slat',(x,fy+.016,.363),(.033,.045,.29),endgrain,.006)
    # Small diagonal shoulder braces under the top rail.
    for side in [-1,1]:
        x=center+side*.295
        o=cube('Shoulder_brace',(x,fy+.002,.436),(.175,.05,.035),wood,.005);o.rotation_euler.y=side*-.55

# Carved garden lantern at the established position.
cx,cy=2.25,1.2
def at(x,y,z):return (cx+x,cy+y,z)
cylinder('Foundation',at(0,0,.045),.32,.08,stone,8)
cylinder('Base_bevel',at(0,0,.104),.275,.045,stoneedge,8)
cylinder('Lotus_plinth',at(0,0,.157),.22,.065,stone,8)
cylinder('Pedestal',at(0,0,.385),.105,.42,stone,8)
for z,r,d in [(.21,.135,.036),(.57,.143,.047),(.612,.205,.045),(.649,.26,.038)]:cylinder('Carved_collar',at(0,0,z),r,d,stoneedge,8)
for side in [-1,1]:
    line('Stem_carving',[at(side*(.018+.009*math.sin(k*.7)),-.101,.27+k*.027) for k in range(9)],.0024,stoneedge)
for i in range(8):
    a=i*math.tau/8
    ball('Lotus_petal',at(.19*math.cos(a),.19*math.sin(a),.173),(.043,.043,.027),stoneedge)
cube('Light_box_base',at(0,0,.694),(.38,.38,.065),bronze,.016)
cube('Illuminated_core',at(0,0,.885),(.298,.298,.33),paper,.012)
for x in [-.166,.166]:
    for y in [-.166,.166]:cube('Corner_column',at(x,y,.897),(.036,.036,.40),bronze,.006)
for z in [.734,1.067]:cube('Window_frame',at(0,0,z),(.37,.37,.032),brass,.009)
for orientation in range(4):
    angle=orientation*math.pi/2
    def face(u,z):return at(u*math.cos(angle)+.161*math.sin(angle),u*math.sin(angle)-.161*math.cos(angle),z)
    for u in [-.09,0,.09]:
        o=cube('Window_mullion',face(u,.895),(.012,.014,.303),bronze,.003);o.rotation_euler.z=angle
    for z in [.795,.997]:
        o=cube('Window_crossbar',face(0,z),(.31,.014,.012),bronze,.003);o.rotation_euler.z=angle
    # A small five-petal brass blossom sits in each window, not a flat decal.
    ring=[face(.037*math.cos(t*math.tau/24),.90+.037*math.sin(t*math.tau/24)) for t in range(25)]
    line('Blossom_ring',ring,.0035,brass)
    for k in range(5):
        a=k*math.tau/5
        line('Blossom_petal',[face(.023*math.cos(a)+.015*math.cos(t*math.tau/12),.90+.023*math.sin(a)+.015*math.sin(t*math.tau/12)) for t in range(13)],.0023,brass)

# Four curved roof faces, raised corners and layered copper eaves.
verts=[];faces=[]
for radius,z in [(.375,1.10),(.362,1.125),(.29,1.16),(.195,1.245),(.085,1.305)]:
    for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]:verts.append(at(x*radius,y*radius,z+(radius/.375)**2*.028))
for ring in range(4):
    for j in range(4):faces.append((ring*4+j,ring*4+(j+1)%4,(ring+1)*4+(j+1)%4,(ring+1)*4+j))
faces.extend([(0,3,2,1),(16,17,18,19)])
mesh=bpy.data.meshes.new('Curved_hip_roof');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new('Lantern_roof',mesh);bpy.context.collection.objects.link(o);finish(o,'Lantern_roof',roofmat);bevel(o,.005)
for i in range(4):
    line('Roof_hip_ridge',[verts[k*4+i] for k in range(5)],.009,roofedge)
    line('Roof_eave_rim',[verts[i],verts[(i+1)%4]],.009,roofedge)
    # Fine seams on each hipped roof plane.
    for f in [.25,.5,.75]:
        line('Roof_panel_seam',[Vector(verts[k*4+i]).lerp(Vector(verts[k*4+(i+1)%4]),f)+Vector((0,0,.003)) for k in range(1,5)],.0024,roofedge)
cylinder('Roof_finial_seat',at(0,0,1.323),.094,.031,bronze,8)
ball('Roof_finial',at(0,0,1.381),(.046,.046,.06),brass)
for i in range(27):
    a=random.random()*math.tau;r=random.uniform(.24,.30)
    ball('Moss_on_base',at(r*math.cos(a),r*math.sin(a),.087),(.011+random.random()*.012,.013,.006),moss)

# Merge by material for runtime draw calls; components remain selectable as mesh islands.
batch=[]
groups=[(material,[o for o in pieces if o.data.materials[0]==material]) for material in [wood,endgrain,groove,stone,stoneedge,bronze,brass,roofmat,roofedge,paper,moss]]
for material,chosen in groups:
    if not chosen:continue
    bpy.ops.object.select_all(action='DESELECT')
    for o in chosen:o.select_set(True)
    bpy.context.view_layer.objects.active=chosen[0];bpy.ops.object.join();o=bpy.context.object;o.name='Garden_v3_'+material.name;o['asset_role']='lantern_and_fence';batch.append(o)
stage=[o for o in bpy.context.scene.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in stage:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ASSET/'sakura.glb'),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)
scene=bpy.context.scene
def look(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(5,-9,6));camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=8;look(camera,(-.1,.2,.8))
for name,loc,power,size in [('Key',(-3,-4,7),1000,5),('Fill',(4,-1,5),600,5),('Rim',(-2,5,6),850,4)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.size=size;look(o,(-1,1,1))
bpy.ops.object.light_add(type='POINT',location=at(0,0,.89));bpy.context.object.data.energy=8;bpy.context.object.data.color=(1,.65,.28);bpy.context.object.data.shadow_soft_size=.13
if not scene.world:scene.world=bpy.data.worlds.new('Courtyard_studio')
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.66,.78,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True;scene.view_settings.view_transform='AgX'
scene.render.resolution_x=1400;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'courtyard-v3.blend'))
for name,loc,target,scale in [('courtyard',(5,-9,6),(-.1,.2,.8),8),('lantern-detail',(3.8,-1.7,2.1),(2.25,1.2,.74),1.83),('fence-detail',(2.9,-1.5,2.0),(0,2.65,.36),4.25)]:
    camera.location=loc;look(camera,target);camera.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'new_material_batches':len(batch),'new_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in batch),'stage_meshes':len(stage),'glb_bytes':(ASSET/'sakura.glb').stat().st_size}
(OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('COURTYARD_COMPLETE',json.dumps(report))
