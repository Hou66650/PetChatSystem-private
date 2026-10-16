"""Offline, deterministic high-detail master of the grassland cat island.

Blender 5.x: blender -b --python scripts/blender/build_cinematic_meadow.py
Optional -- --preview (1280px / 32 samples), --no-render, --no-export.
Does not replace the browser scene or edit account-owned planting data.
"""
import bpy
import math
import random
import json
import sys
import hashlib
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art/cloud-meadow-cinematic-v1'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).parent))
from shepherd_geometry import Batch, material

SEED = 171026
random.seed(SEED)
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
PREVIEW = '--preview' in args
BASE = ROOT / 'static/models/petchat-meadow-v1/mistwood-meadow.glb'
layout = json.loads((ROOT / 'static/data/farm-layout.json').read_text(encoding='utf-8'))
expansion = layout['expansion']
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(BASE))
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
base_objects = list(scene.objects)


def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


BASE_COLL = collection('01 Existing island • shared layout')
DETAIL_COLL = collection('02 Architectural craftsmanship')
BOTANY_COLL = collection('03 Meadow ecology')
WATER_COLL = collection('04 Stream and falling water')
PROP_COLL = collection('05 Demonstration props • no account data')
ATM_COLL = collection('90 Presentation atmosphere • not gameplay')
LIGHT_COLL = collection('91 Cinematic lighting')


def move(o, c):
    for old in list(o.users_collection):
        old.objects.unlink(o)
    c.objects.link(o)


for o in base_objects:
    move(o, BASE_COLL)


def finish(batch, name, c, bevel=0):
    result = batch.objects(name)
    for o in result:
        move(o, c)
        o['asset_role'] = 'visual_detail_not_collision'
        if bevel:
            mod = o.modifiers.new('Hand softened edges', 'BEVEL')
            mod.width = bevel
            mod.segments = 3
            mod.limit_method = 'ANGLE'
    return result


def bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def set_input(mat, key, value):
    node = bsdf(mat)
    for link in list(node.inputs[key].links):
        mat.node_tree.links.remove(link)
    node.inputs[key].default_value = value


def micro_surface(mat, scale, distance, strength=.3):
    """Master-only world-space surface relief; explicit in export manifest."""
    nt = mat.node_tree
    p = bsdf(mat)
    tex = nt.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = scale
    tex.inputs['Detail'].default_value = 4
    co = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(co.outputs['Object'], tex.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    nt.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    if p.inputs['Normal'].is_linked:
        nt.links.new(p.inputs['Normal'].links[0].from_socket, bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], p.inputs['Normal'])


def pbr_tile(name, color, kind):
    """Tiled albedo/normal/roughness, retained by glTF (not a lighting bake)."""
    m = material(name, color, .82)
    size = 1024
    y, x = np.mgrid[0:size, 0:size] / size
    rng = np.random.default_rng(SEED + sum(map(ord, name)))
    value = np.zeros((size, size))
    for freq, amp in [(2, .25), (7, .17), (19, .10), (61, .045), (173, .024)]:
        for i in range(3):
            a = rng.uniform(0, math.tau)
            value += amp / 3 * np.sin(math.tau * freq * (x * math.cos(a) + y * math.sin(a)) + rng.uniform(0, 7))
    noise = rng.random((size, size))
    if kind == 'stone':
        value -= .15 * np.exp(-((np.sin(y * 40 + value * 5)) / .12) ** 2)
        value -= (noise > .985) * .12
    elif kind == 'clay':
        value += .014 * np.sin(y * 950 + np.sin(x * 10))
    elif kind == 'wood':
        value += .09 * np.sin(x * 340 + value * 14) + .045 * np.sin(x * 1100)
    elif kind == 'earth':
        value += (noise - .5) * .25
    rgb = np.clip(np.array(color)[None, None, :] * (1 + value[:, :, None]), .004, .94)
    dy, dx = np.gradient(value)
    normal = np.dstack((-dx * 9, -dy * 9, np.ones_like(dx)))
    normal /= np.linalg.norm(normal, axis=2)[:, :, None]
    nt = m.node_tree
    p = bsdf(m)
    for suffix, values, key in [('albedo', rgb, 'Base Color'), ('normal', normal * .5 + .5, None), ('roughness', np.repeat(np.clip(.78 + value * .20, .5, .98)[:, :, None], 3, 2), 'Roughness')]:
        im = bpy.data.images.new(name + '_' + suffix, width=size, height=size)
        if suffix != 'albedo':
            im.colorspace_settings.name = 'Non-Color'
        im.pixels.foreach_set(np.dstack((values, np.ones_like(x))).astype(np.float32).ravel())
        im.pack()
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = im
        if key:
            nt.links.new(tex.outputs['Color'], p.inputs[key])
        else:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value = .55
            nt.links.new(tex.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    return m


def leaf_surface():
    """Vein-bearing PBR leaf tile; leaf-local UVs are assigned below."""
    n=512
    v,u=np.mgrid[0:n,0:n]/(n-1)
    centre=np.exp(-((v-.5)/.014)**2)
    side=np.exp(-(np.sin((u-np.abs(v-.5)*.54)*math.pi*10)/.10)**2)
    edge=np.abs(v-.5)*2
    grain=np.random.default_rng(SEED).random((n,n))
    value=1+.12*np.sin(u*17)*np.cos(v*23)+grain*.07
    rgb=np.array([.28,.43,.12])[None,None,:]*value[:,:,None]
    rgb+=centre[:,:,None]*np.array([.045,.035,.008])+side[:,:,None]*.018
    rgb*=1-edge[:,:,None]*.09
    height=centre*.018+side*.006+grain*.002
    dy,dx=np.gradient(height)
    norm=np.dstack((-dx*26,-dy*26,np.ones_like(dx)))
    norm/=np.linalg.norm(norm,axis=2)[:,:,None]
    m=material('Veined birch leaf',(.10,.21,.035),.58)
    nt=m.node_tree;p=bsdf(m)
    p.inputs['Subsurface Weight'].default_value=.08
    p.inputs['Subsurface Radius'].default_value=(.008,.016,.004)
    for suffix,values in [('albedo',rgb),('normal',norm*.5+.5)]:
        im=bpy.data.images.new('Birch_leaf_'+suffix,width=n,height=n)
        if suffix=='normal':im.colorspace_settings.name='Non-Color'
        im.pixels.foreach_set(np.dstack((values,np.ones_like(u))).astype(np.float32).ravel());im.pack()
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
        if suffix=='albedo':nt.links.new(tex.outputs['Color'],p.inputs['Base Color'])
        else:
            nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.5
            nt.links.new(tex.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],p.inputs['Normal'])
    return m


stone = pbr_tile('Craft cut warm limestone', (.43, .40, .33), 'stone')
stone_light = pbr_tile('Chalk coping stone', (.57, .53, .44), 'stone')
wood = pbr_tile('Oiled oak grain', (.22, .12, .048), 'wood')
clay = pbr_tile('Hand thrown terracotta', (.38, .14, .066), 'clay')
soil = pbr_tile('Moist potting earth', (.052, .034, .019), 'earth')
iron = material('Deep botanical green iron', (.025, .057, .043), .34, .75)
brass = material('Brushed antique brass', (.39, .25, .092), .31, .78)
vein = material('Living stems', (.14, .22, .035), .7)
petal = material('Warm ivory petals', (.88, .82, .60), .48)
gold = material('Ochre pollen', (.70, .33, .025), .85)
lavender = material('Soft violet petals', (.30, .18, .42), .58)
leaf_mats = [material('Meadow broadleaf ' + str(i), c, .5) for i, c in enumerate([(.065, .17, .025), (.12, .25, .045), (.19, .31, .065)])]
grass_mats = [material('Fine grass ' + str(i), c, .69) for i, c in enumerate([(.055, .13, .017), (.095, .21, .028), (.17, .28, .049), (.29, .35, .09)])]
for m in leaf_mats + grass_mats + [petal, lavender]:
    bsdf(m).inputs['Subsurface Weight'].default_value = .12
    bsdf(m).inputs['Subsurface Radius'].default_value = (.15, .32, .08)
    bsdf(m).inputs['Sheen Weight'].default_value = .12
    m.use_backface_culling = False

# The old viewport glass is alpha-blended and milky in path tracing. Model real
# 4 mm panes instead, keeping the entrance and the cat passage unobstructed.
for o in list(base_objects):
    if 'Conservatory_glass' in o.name or o.name.startswith('Mistwood_Water_highlights') or 'Mistwood_waterfall_' in o.name or o.name == 'Mistwood_River_water':
        bpy.data.objects.remove(o, do_unlink=True)
        base_objects.remove(o)

for m in list(bpy.data.materials):
    if not m.use_nodes or not any(n.type == 'BSDF_PRINCIPLED' for n in m.node_tree.nodes):
        continue
    name = m.name.lower()
    if any(s in name for s in ['canopy_leaf', 'birch_leaves', 'young_leaves']):
        idx = sum(map(ord, name)) % 3
        set_input(m, 'Base Color', (*[(.07, .15, .025), (.12, .23, .045), (.17, .28, .07)][idx], 1))
        set_input(m, 'Roughness', .57)
        bsdf(m).inputs['Subsurface Weight'].default_value = .16
        bsdf(m).inputs['Sheen Weight'].default_value = .16
        micro_surface(m, 140, .0015)
    elif 'cedar_sprays' in name:
        set_input(m, 'Base Color', (.035, .105, .045, 1))
    elif 'limestone' in name or 'stratified' in name:
        micro_surface(m, 24, .016, .38)
    elif 'bark' in name:
        micro_surface(m, 55, .012, .55)
    elif 'forest_floor' in name:
        micro_surface(m, 70, .008, .5)


def lathe(batch, mat, center, profile, segments=64):
    x, y, z = center
    verts = [(x + r * math.cos(i * math.tau / segments), y + r * math.sin(i * math.tau / segments), z + h) for r, h in profile for i in range(segments)]
    faces = []
    for j in range(len(profile) - 1):
        for i in range(segments):
            a = j * segments + i
            b = j * segments + (i + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    batch.mesh(mat, verts, faces, True)


def leaf(batch, mat, origin, angle, length, width, rise=.35):
    p = Vector(origin)
    axis = Vector((math.cos(angle), math.sin(angle), 0))
    side = Vector((-math.sin(angle), math.cos(angle), 0))
    vs = []
    for j in range(9):
        t = j / 8
        mid = p + axis * (length * t) + Vector((0, 0, length * (rise * t - .23 * t * t)))
        w = width * math.sin(math.pi * t) ** .7
        for k in [-1, 0, 1]:
            vs.append(mid + side * (k * w) + Vector((0, 0, (.012 if k == 0 else 0) * math.sin(math.pi * t))))
    batch.mesh(mat, vs, [(j * 3 + k, j * 3 + k + 3, j * 3 + k + 4, j * 3 + k + 1) for j in range(8) for k in range(2)], True)


def fern(batch, x, y, z, scale=1):
    for arm in range(9):
        a = arm * math.tau / 9 + random.uniform(-.14, .14)
        length = random.uniform(.32, .61) * scale
        pts = [(x + math.cos(a) * length * t, y + math.sin(a) * length * t, z + scale * (.07 + .36 * math.sin(math.pi * t * .8))) for t in np.linspace(0, 1, 15)]
        batch.tube(vein, pts, [.004 * scale * (1 - j / 16) for j in range(15)], 5)
        for j in range(2, 14):
            for side in [-1, 1]:
                leaf(batch, leaf_mats[arm % 3], pts[j], a + side * 1.0, scale * (.13 * math.sin(j / 15 * math.pi) + .018), .018 * scale, .15)


def daisy(batch, x, y, z, height=.22):
    dx, dy = random.uniform(-.04, .04), random.uniform(-.04, .04)
    tip = (x + dx, y + dy, z + height)
    batch.tube(vein, [(x, y, z), (x + dx * .3, y + dy * .3, z + height * .6), tip], [.003, .002, .001], 5)
    for i in range(12):
        a = i * math.tau / 12
        leaf(batch, petal, tip, a, .055, .014, .0)
    batch.ellipsoid(gold, (tip[0], tip[1], tip[2] + .006), (.017, .017, .010), 14, 6)
    leaf(batch, leaf_mats[1], (x, y, z + height * .25), random.uniform(0, 7), .09, .018)


def vase(batch, x, y, z, r=.32):
    # Continuous inner wall and rolled lip, not a capped cylinder.
    profile = [(0, 0), (.70*r, 0), (.74*r, .04), (.95*r, .48), (1.03*r, .50), (1.04*r, .55), (.95*r, .57), (.89*r, .55), (.87*r, .50), (.67*r, .07), (0, .07)]
    lathe(batch, clay, (x, y, z), profile)
    lathe(batch, soil, (x, y, z), [(0, .49), (.87*r, .49)])
    for j in range(60):
        a = random.random() * math.tau
        rr = math.sqrt(random.random()) * r * .82
        batch.ellipsoid(stone if j % 4 == 0 else soil, (x + rr*math.cos(a), y + rr*math.sin(a), z+.495), (.008, .011, .006), 6, 4)


# Replace the old five-vertex diamond canopy with curved, serrated, veined
# leaves. Retain every leaf origin so the planted trees do not move.
leaf_mat=leaf_surface()
refined_leaf_count=0
for o in list(base_objects):
    if not o.name.startswith('Cloud_meadow_Canopy_leaf_'):continue
    old=o.data
    if len(old.vertices)%5 or any(tuple(old.polygons[i].vertices)!=(i//4*5,i//4*5+1,i//4*5+4) for i in range(0,len(old.polygons),4)):
        raise ValueError('Source leaf topology changed: '+o.name)
    vs=[];uvs=[];faces=[]
    for k in range(0,len(old.vertices),5):
        p=old.vertices[k].co.copy();tip=old.vertices[k+2].co.copy()
        side=(old.vertices[k+1].co-old.vertices[k+3].co)*.5*.88
        axis=(tip-p)*.88;off=len(vs)
        for j in range(9):
            t=j/8
            middle=p+axis*t+Vector((0,0,axis.length*.055*math.sin(math.pi*t)))
            width=math.sin(math.pi*t)**.73*(.91 if j%2 else 1)
            for q in [-1,0,1]:
                vs.append(middle+side*q*width+Vector((0,0,(.0025 if q==0 else -.001)*math.sin(math.pi*t))))
                uvs.append((t,(q+1)/2))
        for j in range(8):
            for q in range(2):
                a=off+j*3+q;faces.append((a,a+3,a+4,a+1))
        refined_leaf_count+=1
    mesh=bpy.data.meshes.new(o.name+' curved leaves');mesh.from_pydata(vs,[],faces);mesh.update();mesh.materials.append(leaf_mat)
    uv=mesh.uv_layers.new(name='LeafUV')
    for f in mesh.polygons:
        f.use_smooth=True
        for i in f.loop_indices:uv.data[i].uv=uvs[mesh.loops[i].vertex_index]
    o.data=mesh
    bpy.data.meshes.remove(old)
print('LEAVES_REBUILT',refined_leaf_count,flush=True)

# Conservatory columns, sill moldings, glazing bars, ridge crest and fanlights.
arch = Batch()
for x in [.9, 1.9, 4.1, 5.1]:
    for y in ([1.75, 5.05] if x in [.9, 5.1] else [1.75]):
        arch.box(stone_light, (x, y, .23), (.23, .23, .44))
        lathe(arch, iron, (x, y, .44), [(.09, 0), (.10, .04), (.065, .10), (.046, .18), (.046, 1.92), (.07, 1.96), (.095, 2.05), (.095, 2.11)], 24)
        for h in [.6, 2.38, 2.50]:
            lathe(arch, brass, (x, y, h), [(.05, 0), (.055, .015), (.05, .03)], 24)

for x in [.9, 5.1]:
    for h, w in [(.34, .19), (2.61, .12), (2.70, .16)]:
        arch.box(iron, (x, 3.4, h), (w, 3.48, .055))
    for y in np.linspace(1.75, 5.05, 9):
        arch.box(iron, (x, y, 1.49), (.038, .036, 2.27))
        for z in [1.10, 1.88]:
            arch.ellipsoid(brass, (x + (.025 if x > 3 else -.025), y, z), (.011, .014, .014), 8, 6)
    for z in [1.1, 1.88]:
        arch.box(iron, (x, 3.4, z), (.04, 3.3, .029))
for y in [1.75, 5.05]:
    arch.box(iron, (3, y, 2.64), (4.36, .12, .11))
    # Fine sunburst within the triangular gable.
    for x in np.linspace(1.13, 4.87, 17):
        h = 3.95 - abs(x - 3) * 1.30 / 2.10
        arch.tube(iron, [(3, y-.015, 2.68), (x, y-.015, h-.04)], .012, 8)
    for r in [.26, .40]:
        arch.tube(brass, [(3+r*math.cos(t), y-.03, 2.68+r*math.sin(t)) for t in np.linspace(0, math.pi, 33)], .012, 8)
    for x in [.9, 5.1]:
        # Curled corner bracket kept entirely above the walk-through portal.
        sign = 1 if x < 3 else -1
        arch.tube(iron, [(x+sign*(.28+.21*math.cos(t)), y, 2.35+.19*math.sin(t)) for t in np.linspace(-math.pi, math.pi*1.6, 54)], .014, 8)
for y in np.linspace(1.72, 5.08, 12):
    lathe(arch, iron, (3, y, 3.95), [(.035, 0), (.058, .06), (.035, .13), (.015, .24), (0, .30)], 16)
    arch.tube(iron, [(3, y, 4.03), (3, min(y+.3, 5.12), 4.03)], .014, 8)
for x in [1.6, 2.3, 3.7, 4.4]:
    h = 3.95 - abs(x-3)*1.3/2.1
    arch.tube(iron, [(x, 1.73, h+.012), (x, 5.07, h+.012)], .016, 8)
finish(arch, 'Conservatory craft', DETAIL_COLL, .006)

glass = material('Four millimetre clear horticultural glass', (.96, .99, .97), .045)
bsdf(glass).inputs['Transmission Weight'].default_value = 1
bsdf(glass).inputs['IOR'].default_value = 1.46
panes = Batch()
for x in [.907, 5.093]:
    for y in np.linspace(1.78, 4.6675, 8):
        for low, high in [(.39, 1.08), (1.12, 1.86), (1.90, 2.59)]:
            panes.mesh(glass, [(x,y,low),(x,y+.366,low),(x,y+.366,high),(x,y,high)], [(0,1,2,3)])
for y in [1.76, 5.04]:
    spans = [(1.0, 1.87), (4.13, 5.0)] if y < 2 else [(.96, 1.94), (1.98, 2.98), (3.02, 4.02), (4.06, 5.04)]
    for lo, hi in spans:
        panes.mesh(glass, [(lo,y,.40),(hi,y,.40),(hi,y,2.58),(lo,y,2.58)], [(0,1,2,3)])
    panes.mesh(glass, [(.96,y,2.70),(5.04,y,2.70),(3,y,3.91)], [(0,1,2)])
for y in np.linspace(1.78, 4.6675, 8):
    for x in [.94, 5.06]:
        panes.mesh(glass, [(x,y,2.69),(3,y,3.94),(3,y+.36,3.94),(x,y+.36,2.69)], [(0,1,2,3)])
for o in finish(panes, 'Individual glazing', DETAIL_COLL):
    mod = o.modifiers.new('Gable and roof sheet thickness', 'SOLIDIFY')
    mod.thickness = .004

# The bridge keeps the original top profile, with individual stones and deep
# outer arch masonry below its traversable deck. No new steps on pet routes.
bridge = Batch()
def deck(y):
    return .035 + .32 * math.sin(math.pi * ((-y-1.8)/4+.5))**2
for row in range(20):
    y = -3.8 + (row+.5)*.2
    for col in range(9):
        x = -1.51 + col*.377
        bridge.box(stone if (row+col)%3 else stone_light, (x,y,deck(y)+.012), (.361,.184,.023))
for x in [-1.76, 1.76]:
    # Elliptical arch ring with independent radial joints.
    for j in range(32):
        a = j*math.pi/32+.004
        b = (j+1)*math.pi/32-.004
        verts=[]
        for xx in [x-.15,x+.15]:
            for r in [1,1.20]:
                for t in [a,b]:
                    verts.append((xx,-1.8+1.90*r*math.cos(t),-1.02+1.03*r*math.sin(t)))
        bridge.mesh(stone if j%3 else stone_light,verts,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)])
    for y in np.linspace(-3.72,.12,25):
        bridge.box(stone_light,(x,y,deck(y)+.10),(.36,.147,.16))
    for y in [-3.72,.12]:
        bridge.box(stone,(x,y,.44),(.46,.43,.82))
        bridge.box(stone_light,(x,y,.87),(.52,.49,.075))
    for y in np.linspace(-3.48,-.12,9):
        z=deck(y)+.45
        bridge.tube(iron,[(x,y+.11*math.cos(t),z+.13*math.sin(t)) for t in np.linspace(0,math.tau,25)],.008,6)
finish(bridge,'Dressed bridge masonry',DETAIL_COLL,.008)

# Furnished borders: real fern pinnae, potted specimens, flowers, loose grains.
plants=Batch()
for x,y,s in [(.45,1.65,.9),(5.55,1.8,1.1),(5.7,3.2,1.0),(-2.0,-.9,.65),(2.15,-2.6,.6),(-3.1,1.4,.9),(6.0,4.3,1.15),(-5.4,3.2,1.1)]:
    fern(plants,x,y,.035,s)
for x,y in [(.42,2.4),(5.56,2.5),(1.3,4.6),(4.7,4.6)]:
    vase(plants,x,y,.04,.30)
    fern(plants,x,y,.54,.75)
for i in range(320):
    x=random.uniform(-6.8,6.8);y=random.uniform(-6.8,6.8)
    r=math.hypot(x,y)
    if 6.2<r<7.1 and abs(y+1.8)>.8:
        daisy(plants,x,y,.04,random.uniform(.14,.34))
finish(plants,'Botanical borders',BOTANY_COLL)

# Fine grass: curved tapered blades, irregular density and islands of clover.
# Keep the central meadow mostly clear; preserve the exact navigable loop.
loop=expansion['loop']
segments=[]
for a,b in zip(loop,loop[1:]):
    ax,ay=a[0],-a[1];dx,dy=b[0]-a[0],-b[1]+a[1]
    segments.append((ax,ay,dx,dy,dx*dx+dy*dy))
def path_distance(x,y):
    return min(math.hypot(x-ax-max(0,min(1,((x-ax)*dx+(y-ay)*dy)/den))*dx,y-ay-max(0,min(1,((x-ax)*dx+(y-ay)*dy)/den))*dy) for ax,ay,dx,dy,den in segments)
def meadow(x,y):
    return math.hypot(x,y)>7.9 and any(((x-d['x'])/(d['rx']-.38))**2+((-y-d['z'])/(d['rz']-.38))**2<1 for d in expansion['domains'])
blades=Batch()
grass_count=0
for i in range(165000):
    x=random.uniform(1,19);y=random.uniform(-13.5,2.8)
    if not meadow(x,y) or path_distance(x,y)<.38:continue
    h=random.uniform(.055,.17)*(1+.22*math.sin(x*2+y*1.2))
    a=random.random()*math.tau;w=random.uniform(.003,.007)
    lean=random.uniform(.02,.065)
    side=Vector((-math.sin(a)*w,math.cos(a)*w,0));p=Vector((x,y,.028))
    vs=[]
    for j in range(5):
        t=j/4;mid=p+Vector((math.cos(a)*lean*t*t,math.sin(a)*lean*t*t,h*t))
        vs.extend([mid-side*(1-t),mid+side*(1-t)])
    blades.mesh(grass_mats[i%4],vs,[(j*2,j*2+1,j*2+3,j*2+2) for j in range(4)],True)
    grass_count+=1
finish(blades,'Fine curved lawn',BOTANY_COLL)
clovers=Batch()
for i in range(800):
    x=random.uniform(2,18);y=random.uniform(-13,2)
    if not meadow(x,y) or path_distance(x,y)<.43:continue
    # Clusters instead of uniform sprinkles.
    if math.sin(x*1.3)*math.cos(y*.9)<.15:continue
    for j in range(9):
        px=x+random.uniform(-.12,.12);py=y+random.uniform(-.12,.12);h=random.uniform(.07,.12)
        clovers.tube(vein,[(px,py,.03),(px,py,h)],.001,4)
        for q in range(3):leaf(clovers,leaf_mats[j%3],(px,py,h),q*math.tau/3,.038,.020,.15)
    if i%4==0:daisy(clovers,x,y,.04,random.uniform(.16,.28))
finish(clovers,'Clover colonies',BOTANY_COLL)

# Mossy strata at island rims, with small ferns in occasional crevices.
rim=Batch()
for d in expansion['domains']:
    for i in range(180):
        a=i*math.tau/180
        x=d['x']+d['rx']*math.cos(a);y=-d['z']+d['rz']*math.sin(a)
        if math.hypot(x,y)<8 or any(q is not d and ((x-q['x'])/q['rx'])**2+((-y-q['z'])/q['rz'])**2<1 for q in expansion['domains']):continue
        if i%6==0:
            fern(rim,x-.35*math.cos(a),y-.35*math.sin(a),.035,.5)
        if i%3==0:
            for k in range(random.randrange(2,5)):
                xx=x-random.uniform(.2,.55)*math.cos(a);yy=y-random.uniform(.2,.55)*math.sin(a)
                daisy(rim,xx,yy,.04,random.uniform(.18,.32))
finish(rim,'Living meadow edge',BOTANY_COLL)

# Physically transmissive shallow stream, real rounded bed pebbles and thin
# cascading sheets. Surface ripples are geometry, portable to other engines.
water=material('Clear shallow stream',(.64,.85,.79),.105)
bsdf(water).inputs['Transmission Weight'].default_value=.96
bsdf(water).inputs['IOR'].default_value=1.333
waterbatch=Batch();bed=Batch()
nx,ny=250,20
vs=[]
for j in range(ny+1):
    y=-2.28+j*.96/ny
    for i in range(nx+1):
        x=-7.70+i*15.4/nx
        z=-.087+.005*math.sin(x*17+y*24)+.003*math.sin(x*7-y*37)
        vs.append((x,y,z))
waterbatch.mesh(water,vs,[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)],True)
bed.box(soil,(0,-1.8,-.36),(15.4,.98,.07))
for i in range(1800):
    x=random.uniform(-7.65,7.65);y=random.uniform(-2.25,-1.35)
    r=random.uniform(.015,.065)
    bed.ellipsoid(stone if i%3 else stone_light,(x,y,-.28),(r,r*.7,r*.5),10,6)
for side in [-1,1]:
    for strip in range(11):
        y=-2.28+strip*.087
        verts=[]
        for j in range(81):
            t=j/80;z=-.09-t*5.8
            x=side*(7.70+.23*math.sin(t*math.pi*.9)+.04*math.sin(t*37+strip))
            for yy in [y,y+.075]:verts.append((x,yy+.018*math.sin(t*40+strip),z))
        waterbatch.mesh(water,verts,[(j*2,j*2+1,j*2+3,j*2+2) for j in range(80)],True)
finish(waterbatch,'Flowing water',WATER_COLL)
finish(bed,'Pebble stream bed',WATER_COLL)

# Import the existing cat shelter for a complete scene. Its world-space
# position is authored by the same layout; no user uploads are read.
home=ROOT/'static/models/petchat-cat-home-v1/cat-home.glb'
if home.exists():
    before=set(scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(home))
    for o in set(scene.objects)-before:move(o,PROP_COLL)

# The farm is dressed with native, fully modeled plant assets solely for this
# art review. These are not persisted into anyone's planting slots.
for idx,kind in enumerate(['lavender','cosmos','tulip','daisy','rose','sunflower']):
    path=ROOT/('static/models/petchat-farm-v1/'+kind+'-10.glb')
    if not path.exists():raise FileNotFoundError(path)
    before=set(scene.objects);bpy.ops.import_scene.gltf(filepath=str(path));obs=list(set(scene.objects)-before)
    roots=[o for o in obs if o.parent not in obs]
    bed_info=layout['beds'][idx]
    for o in obs:
        move(o,PROP_COLL);o['demonstration_only']=True
    for o in roots:
        o.location+=Vector((bed_info['x'],-bed_info['z'],.22))
        o.scale*=.74
    # Linked duplicates preserve the detailed plant mesh without duplicating
    # mesh storage in the Blender master.
    for shift in [-.43,.43]:
        mapping={}
        for o in obs:
            dup=o.copy();PROP_COLL.objects.link(dup);mapping[o]=dup
        for original,dup in mapping.items():
            if original.parent in mapping:dup.parent=mapping[original.parent]
            elif original in roots:dup.location.x+=shift

# UVs for new material-batched geometry. Dominant face projection gives metre
# scale mortar/wood/soil texture and prevents stretched upright stone surfaces.
for c in [DETAIL_COLL,BOTANY_COLL,WATER_COLL]:
    for o in c.objects:
        if o.type!='MESH':continue
        uv=o.data.uv_layers.new(name='CraftUV')
        for f in o.data.polygons:
            axis=max(range(3),key=lambda i:abs(f.normal[i]));axes=[i for i in range(3) if i!=axis]
            for k in f.loop_indices:
                p=o.data.vertices[o.data.loops[k].vertex_index].co
                uv.data[k].uv=(p[axes[0]]*.8,p[axes[1]]*.8)

# Cycles sky and a bounded cloud layer entirely below the playable island.
world=bpy.data.worlds.new('Morning above the clouds');world.use_nodes=True;scene.world=world
nt=world.node_tree;sky=nt.nodes.new('ShaderNodeTexSky')
sky_types=sky.bl_rna.properties['sky_type'].enum_items.keys()
sky.sky_type='MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in sky_types else 'NISHITA'
sky.sun_elevation=math.radians(22);sky.sun_rotation=math.radians(135);sky.sun_disc=True
sky.sun_size=math.radians(2.5)
sky.altitude=1;sky.air_density=.9
setattr(sky, 'aerosol_density' if hasattr(sky, 'aerosol_density') else 'dust_density', .65)
nt.links.new(sky.outputs['Color'],nt.nodes['Background'].inputs['Color']);nt.nodes['Background'].inputs['Strength'].default_value=.10
bpy.ops.object.light_add(type='AREA',location=(-7,-4,16));key=bpy.context.object;key.name='Warm broad morning key';key.data.energy=2600;key.data.shape='DISK';key.data.size=12;key.data.color=(1,.86,.66);key.rotation_euler=(Vector((2,-2,0))-key.location).to_track_quat('-Z','Y').to_euler();move(key,LIGHT_COLL)
bpy.ops.object.light_add(type='AREA',location=(10,-16,9));fill=bpy.context.object;fill.name='Cool sky bounce';fill.data.energy=1500;fill.data.size=16;fill.data.color=(.65,.82,1);fill.rotation_euler=(Vector((3,-3,0))-fill.location).to_track_quat('-Z','Y').to_euler();move(fill,LIGHT_COLL)

cloud=bpy.data.materials.new('Soft procedural cloud sea');cloud.use_nodes=True
n=cloud.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');volume=n.new('ShaderNodeVolumePrincipled');volume.inputs['Color'].default_value=(.90,.95,1,1);volume.inputs['Anisotropy'].default_value=.15
coord=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.14;noise.inputs['Detail'].default_value=3
cloud.node_tree.links.new(coord.outputs['Object'],noise.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.39;ramp.color_ramp.elements[0].color=(0,0,0,1);ramp.color_ramp.elements[1].position=.68;ramp.color_ramp.elements[1].color=(.20,.20,.20,1)
cloud.node_tree.links.new(noise.outputs['Fac'],ramp.inputs['Fac']);cloud.node_tree.links.new(ramp.outputs['Color'],volume.inputs['Density']);cloud.node_tree.links.new(volume.outputs['Volume'],out.inputs['Volume'])
# Gentle multiple-scattering approximation for the distant cloud bank only.
cloudglow=n.new('ShaderNodeMath');cloudglow.operation='MULTIPLY';cloudglow.inputs[1].default_value=.22
cloud.node_tree.links.new(ramp.outputs['Color'],cloudglow.inputs[0]);cloud.node_tree.links.new(cloudglow.outputs[0],volume.inputs['Emission Strength']);volume.inputs['Emission Color'].default_value=(.65,.79,1,1)
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-10));o=bpy.context.object;o.name='Cloud sea • presentation only';o.scale=(180,180,12);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(cloud);move(o,ATM_COLL)

bpy.ops.mesh.primitive_plane_add(size=140,location=(0,0,-7))
plan_backdrop=bpy.context.object;plan_backdrop.name='Plan backdrop • presentation only'
plan_backdrop.data.materials.append(material('Quiet sage plan paper',(.43,.48,.45),1))
plan_backdrop.hide_render=True;move(plan_backdrop,LIGHT_COLL)

bpy.ops.object.camera_add(location=(30,-44,29));cam=bpy.context.object;cam.name='01 Meadow panorama';move(cam,LIGHT_COLL);scene.camera=cam
def aim(location,target,scale):
    cam.location=location;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale
aim((30,-44,29),(2,-2.5,.7),42)
scene.render.engine='CYCLES'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
gpu=[]
for d in prefs.devices:
    d.use=d.type=='OPTIX'
    if d.use:gpu.append(d.name)
if not gpu:raise RuntimeError('No OPTIX device: abort rather than silently using CPU')
scene.cycles.device='GPU';scene.cycles.samples=32 if PREVIEW else 96;scene.cycles.use_denoising=True
scene.cycles.max_bounces=10;scene.cycles.transmission_bounces=8;scene.cycles.transparent_max_bounces=8
scene.cycles.volume_bounces=1
scene.render.resolution_x=1280 if PREVIEW else 2400;scene.render.resolution_y=900 if PREVIEW else 1688;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=-.5

# Save packed editable master before rendering. Image paths are embedded, so
# reopening on a different workstation does not depend on this drive letter.
bpy.ops.file.pack_all()
report={
    'seed':SEED,'source':BASE.relative_to(ROOT).as_posix(),'sourceSha256':hashlib.sha256(BASE.read_bytes()).hexdigest(),
    'renderer':'Cycles / OptiX','devices':gpu,'units':'metres','masterUpAxis':'Z','runtimeUpAxis':'Y',
    'layoutSource':'static/data/farm-layout.json','newFineGrassBlades':grass_count,'refinedCanopyLeaves':refined_leaf_count,
    'renderOnlyCollections':[ATM_COLL.name,LIGHT_COLL.name],
    'webSceneChanged':False,'accountDataRead':False,
    'runtimeCaveats':['Master procedural micro-bump and atmospheric volumes require engine recreation or baking.', 'Visual meshes are not navigation/collision meshes. Keep the shared layout and bake client collision separately.', 'No client FPS claim: desktop runtime integration has not been performed.'],
    'collections':{},
}
for c in [BASE_COLL,DETAIL_COLL,BOTANY_COLL,WATER_COLL,PROP_COLL]:
    obs=[o for o in c.objects if o.type=='MESH']
    report['collections'][c.name]={'meshes':len(obs),'baseTriangles':sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in obs)}
    for o in obs:
        if not all(math.isfinite(v) for p in o.data.vertices for v in p.co):raise ValueError('Nonfinite mesh: '+o.name)
report['totalBaseTriangles']=sum(x['baseTriangles'] for x in report['collections'].values())
(OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'cloud-meadow-master.blend'),compress=True)
master=OUT/'cloud-meadow-master.blend'
report['masterBytes']=master.stat().st_size
report['masterSha256']=hashlib.sha256(master.read_bytes()).hexdigest()
report['packedImages']=sum(1 for im in bpy.data.images if im.packed_file)
(OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('MASTER_SAVED',json.dumps(report,ensure_ascii=False),flush=True)

if '--no-export' not in args:
    # Export complete, mutually exclusive modules in a single common origin.
    # The cloud volume and render lights deliberately stay in the master.
    destination=OUT/'client-staging';destination.mkdir(exist_ok=True)
    canopy=[o for o in BASE_COLL.objects if o.name.startswith('Cloud_meadow_Canopy_leaf_')]
    groups=[('base-island',[o for o in BASE_COLL.objects if o not in canopy])]
    groups += [('canopy-'+str(i),[o]) for i,o in enumerate(sorted(canopy,key=lambda o:o.name))]
    groups += [('architecture',list(DETAIL_COLL.objects)),('botany',list(BOTANY_COLL.objects)),('water',list(WATER_COLL.objects)),('demonstration-props',list(PROP_COLL.objects))]
    report['runtimeModules']=[]
    for name,obs in groups:
        bpy.ops.object.select_all(action='DESELECT')
        for o in obs:o.select_set(True)
        path=destination/(name+'.glb')
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_cameras=False,export_lights=False)
        report['runtimeModules'].append({'file':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'optional':name=='demonstration-props'})
    (OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if '--no-render' not in args:
    shots=[('01-meadow-panorama',(30,-44,29),(2,-2.5,.7),42),('02-conservatory-detail',(10,-9,6),(2.5,2.7,1.9),10),('03-grass-and-bridge',(15,-19,8),(6,-4,.6),18),('04-plan',(2,-2.8,55),(2,-2.8,0),39)]
    for name,pos,target,scale in shots:
        if PREVIEW and name!='01-meadow-panorama':continue
        aim(pos,target,scale)
        if name=='04-plan':
            ATM_COLL.hide_render=True
            plan_backdrop.hide_render=False
        else:ATM_COLL.hide_render=False
        scene.render.filepath=str(OUT/(name+('-preview' if PREVIEW else '')+'.png'))
        bpy.ops.render.render(write_still=True)
        print('RENDER_DONE',name,flush=True)
print('CINEMATIC_MEADOW_COMPLETE',flush=True)
