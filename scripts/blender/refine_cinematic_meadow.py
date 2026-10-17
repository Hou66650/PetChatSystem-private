"""Client art v2. Refines a packed v1 master; never writes web assets.

blender -b --python scripts/blender/refine_cinematic_meadow.py -- --source <v1.blend>
Use --preview for a quick pair of closeups; --render-only reopens the v2 master.
Procedural materials remain Blender materials pending UE baking/qualification.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).parent))
from shepherd_geometry import Batch, material
from cinematic_island_tools import collection, finish, leaf, lathe, principled

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=ROOT / 'art/cloud-meadow-cinematic-v1/cloud-meadow-master.blend')
parser.add_argument('--preview', action='store_true')
parser.add_argument('--render-only', action='store_true')
parser.add_argument('--no-render', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT = ROOT / 'art/cloud-meadow-cinematic-v2'
OUT.mkdir(parents=True, exist_ok=True)
master = OUT / 'cloud-meadow-refined.blend'
random.seed(271026)
stats = {}
EXPOSURE = -.5
PALETTE_REVISION = 'deep-botanical-2026-10-17'


def surface(name, colors, scale=8, relief=.001, rough=.7, stretch=(1, 1, 1)):
    """Metric multiscale relief and colour; not camera-dependent decoration."""
    m = material(name, colors[0], rough)
    nt=m.node_tree; n=nt.nodes; p=principled(m)
    co=n.new('ShaderNodeTexCoord'); mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
    mapping.inputs[1].default_value=stretch;nt.links.new(co.outputs['Object'],mapping.inputs[0])
    noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=5
    nt.links.new(mapping.outputs[0],noise.inputs['Vector'])
    ramp=n.new('ShaderNodeValToRGB')
    for e,c in zip(ramp.color_ramp.elements, colors): e.color=(*c,1)
    nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs[0],p.inputs['Base Color'])
    fine=n.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=scale*31;fine.inputs['Detail'].default_value=2
    nt.links.new(mapping.outputs[0],fine.inputs['Vector'])
    bump=n.new('ShaderNodeBump');bump.inputs['Distance'].default_value=relief;bump.inputs['Strength'].default_value=.32
    nt.links.new(fine.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs[0],p.inputs['Normal'])
    remap=n.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=max(.1,rough-.12);remap.inputs['To Max'].default_value=min(1,rough+.12)
    nt.links.new(noise.outputs['Fac'],remap.inputs['Value']);nt.links.new(remap.outputs[0],p.inputs['Roughness'])
    return m


def replace_material(old, new):
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        for i,m in enumerate(o.data.materials):
            if m and m.name==old:o.data.materials[i]=new


def soften(o,width=.008):
    if o.type=='MESH' and not any(m.type=='BEVEL' for m in o.modifiers):
        mod=o.modifiers.new('V2 worn joinery edge','BEVEL');mod.width=width;mod.segments=3
        mod.limit_method='ANGLE'


def blade(b,m,p,angle,h,width,lean):
    axis=Vector((math.cos(angle),math.sin(angle),0));side=Vector((-axis.y,axis.x,0))
    vs=[];p=Vector(p)
    # Folded cross-section and bowed, tapering tip rather than flat rectangles.
    for j in range(7):
        t=j/6;mid=p+axis*(lean*t*t)+Vector((0,0,h*(t-.12*t*t)))
        w=width*(1-t)**.8
        for q in [-1,0,1]:vs.append(mid+side*q*w+Vector((0,0,.0018*math.sin(math.pi*t) if q==0 else 0)))
    b.mesh(m,vs,[(j*3+q,j*3+q+1,(j+1)*3+q+1,(j+1)*3+q) for j in range(6) for q in range(2)],True)


def botanical_leaf_material(name):
    """Leaf-local albedo and relief; centre vein and lateral branching veins."""
    n=512;v,u=np.mgrid[0:n,0:n]/(n-1)
    mid=np.exp(-((v-.5)/.018)**2)
    lateral=np.exp(-(np.sin((u-np.abs(v-.5)*.55)*math.pi*9)/.12)**2)
    grain=np.random.default_rng(271026).random((n,n))
    rgb=np.array([.12,.24,.046])[None,None,:]*(.83+.10*np.sin(u*16)*np.cos(v*11)+grain*.06)[:,:,None]
    rgb+=mid[:,:,None]*np.array([.045,.06,.012])+lateral[:,:,None]*.016
    height=mid*.6+lateral*.22+grain*.03
    m=material(name,(.11,.23,.05),.71);nt=m.node_tree;p=principled(m)
    p.inputs['Subsurface Weight'].default_value=.08
    for suffix,values in [('albedo',rgb),('height',np.repeat(height[:,:,None],3,2))]:
        im=bpy.data.images.new(name+' '+suffix,width=n,height=n)
        if suffix=='height':im.colorspace_settings.name='Non-Color'
        im.pixels.foreach_set(np.dstack((values,np.ones_like(u))).astype(np.float32).ravel());im.pack()
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
        if suffix=='albedo':nt.links.new(tex.outputs[0],p.inputs['Base Color'])
        else:
            bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.001;bump.inputs['Strength'].default_value=.35
            nt.links.new(tex.outputs[0],bump.inputs['Height']);nt.links.new(bump.outputs[0],p.inputs['Normal'])
    return m


def build():
    if not args.source.is_file():raise FileNotFoundError('Pass --source pointing to the packed v1 Blender master')
    bpy.ops.wm.open_mainfile(filepath=str(args.source))
    scene=bpy.context.scene
    lawn_col=collection('06 V2 ground ecology')
    craft_col=collection('07 V2 conservatory fittings')
    flora_col=collection('08 V2 botanical specimens')
    soil_col=collection('09 V2 mineral and organic detail')
    clay=surface('V2 fired terracotta pores',[(.065,.012,.005),(.23,.055,.018)],18,.003,.82)
    loam=surface('V2 damp crumbly loam',[(.025,.016,.009),(.085,.052,.026)],14,.003,.95)
    bark=surface('V2 aged oak longitudinal grain',[(.022,.009,.004),(.10,.047,.018)],5,.0015,.76,(.6,32,5))
    cedar=surface('V2 cedar warm heartwood',[(.035,.012,.005),(.13,.055,.018)],4,.001,.78,(.65,30,7))
    roof=surface('V2 forest green roof',[(.012,.035,.026),(.035,.085,.055)],9,.0005,.58)
    replace_material('sage_roof',roof)
    replace_material('end_grain',bark)
    iron=surface('V2 aged conservatory enamel',[(.013,.038,.029),(.045,.085,.065)],11,.0003,.43)
    principled(iron).inputs['Metallic'].default_value=.62
    brass=surface('V2 oxidized fastener brass',[(.12,.085,.025),(.38,.26,.09)],17,.0002,.4)
    principled(brass).inputs['Metallic'].default_value=.78
    cream=surface('V2 woven natural linen',[(.33,.30,.22),(.63,.58,.43)],65,.0006,.93,(1,1,1))
    for old,new in [('Hand thrown terracotta',clay),('Garden_terracotta',clay),('Moist potting earth',loam),('Garden_friable_soil',loam),('Garden_potting_soil',loam),('Weathered_bench',bark),('Garden_oiled_larch',cedar),('Deep botanical green iron',iron),('linen',cream),('Garden_woven_linen',cream)]:
        replace_material(old,new)
    for i in range(5):replace_material('cedar_'+str(i),cedar)
    for o in scene.objects:
        if o.name.startswith(('cat_home_cedar','Mistwood_Weathered_bench','Farm_terrace_Garden_oiled_larch')):soften(o,.006)
        if o.name=='Mistwood_Weathered_limestone':soften(o,.012)
    # Retire the legacy flat diamond ground foliage, retaining the actual tree
    # canopy and all roots above 0.65 m. This removes the conspicuous paper shards.
    removed=0
    for o in list(scene.objects):
        if o.type!='MESH' or o.name not in ('Mistwood_Birch_leaves','Mistwood_Young_leaves'):continue
        bm=bmesh.new();bm.from_mesh(o.data)
        faces=[f for f in bm.faces if max((o.matrix_world@v.co).z for v in f.verts)<.65]
        removed+=len(faces);bmesh.ops.delete(bm,geom=faces,context='FACES');bm.to_mesh(o.data);bm.free();o.data.update()
    stats['removedLegacyGroundFaces']=removed
    legacy=bpy.data.objects.get('Mistwood_Wildflower')
    if legacy:
        stats['retiredPaperFlowerFaces']=len(legacy.data.polygons)
        bpy.data.objects.remove(legacy,do_unlink=True)
    legacy=bpy.data.objects.get('Mistwood_Moss')
    if legacy:
        bm=bmesh.new();bm.from_mesh(legacy.data)
        faces=[f for f in bm.faces if len(f.verts)==3 and .02<max(v.co.z for v in f.verts)-min(v.co.z for v in f.verts) and max(v.co.z for v in f.verts)<.5]
        stats['retiredFlatGrassTriangles']=len(faces)
        bmesh.ops.delete(bm,geom=faces,context='FACES');bm.to_mesh(legacy.data);bm.free();legacy.data.update()
    leaf_detail=botanical_leaf_material('V2 fern midrib and side veins')
    # Rebuild the obvious five-vertex ivy diamonds while preserving every vine
    # attachment. Curved lobes and their own UVs hold up in cliff closeups.
    ivy_count=0
    for o in list(scene.objects):
        if not o.name.startswith('Cloud_meadow_Cliff_ivy_'):continue
        old=o.data
        if len(old.vertices)%5 or len(old.polygons)!=len(old.vertices)//5*4:raise ValueError('Unexpected ivy topology '+o.name)
        vs=[];faces=[];uvs=[]
        for k in range(0,len(old.vertices),5):
            p=old.vertices[k].co.copy();axis=old.vertices[k+2].co-p
            side=(old.vertices[k+1].co-old.vertices[k+3].co)*.5
            start=len(vs)
            for j in range(11):
                t=j/10;w=math.sin(math.pi*t)**.65*(1+.20*math.sin(t*math.pi*5))
                mid=p+axis*t+Vector((0,0,.009*math.sin(t*math.pi)))
                for q in [-1,0,1]:
                    vs.append(mid+side*q*w+Vector((0,0,-.004*abs(q)*math.sin(t*math.pi))));uvs.append((t,(q+1)/2))
            for j in range(10):
                for q in range(2):
                    a=start+j*3+q;faces.append((a,a+3,a+4,a+1))
            ivy_count+=1
        mesh=bpy.data.meshes.new(o.name+' V2 lobed blades');mesh.from_pydata(vs,[],faces);mesh.update();mesh.materials.append(leaf_detail)
        uv=mesh.uv_layers.new(name='V2 IvyUV')
        for f in mesh.polygons:
            f.use_smooth=True
            for li in f.loop_indices:uv.data[li].uv=uvs[mesh.loops[li].vertex_index]
        o.data=mesh;bpy.data.meshes.remove(old)
    stats['refinedIvyLeaves']=ivy_count
    for o in scene.objects:
        if o.type!='MESH' or not o.name.startswith(('Botanical borders_Meadow broadleaf','Living meadow edge_Meadow broadleaf','Clover colonies_Meadow broadleaf')):continue
        if len(o.data.vertices)%27:raise ValueError('Unexpected botanical leaf topology '+o.name)
        o.data.materials.clear();o.data.materials.append(leaf_detail)
        uv=o.data.uv_layers.active or o.data.uv_layers.new(name='V2 LeafUV')
        for f in o.data.polygons:
            for li in f.loop_indices:
                index=o.data.loops[li].vertex_index%27
                uv.data[li].uv=(index//3/8,index%3/2)
    # Glazing gains faint roughness variation, avoiding opaque white dirt layers.
    g=bpy.data.materials.get('Four millimetre clear horticultural glass')
    if g:
        nt=g.node_tree;tex=nt.nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=36
        remap=nt.nodes.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=.035;remap.inputs['To Max'].default_value=.085
        nt.links.new(tex.outputs['Fac'],remap.inputs['Value']);nt.links.new(remap.outputs[0],principled(g).inputs['Roughness'])
    # A leaf's 27-vertex topology is validated before local, seed-stable variation.
    leafbase=bpy.data.materials.get('Veined birch leaf');tints=[]
    for i,tint in enumerate([(.67,.78,.56,1),(.85,.88,.68,1),(1,.98,.82,1),(.70,.86,.68,1)]):
        m=leafbase.copy();m.name='V2 canopy chlorophyll '+str(i);nt=m.node_tree;p=principled(m)
        source=p.inputs['Base Color'].links[0].from_socket
        mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=tint
        nt.links.new(source,mix.inputs[1]);nt.links.new(mix.outputs[0],p.inputs['Base Color']);tints.append(m)
    changed=0
    for o in list(scene.objects):
        if not o.name.startswith('Cloud_meadow_Canopy_leaf_'):continue
        mesh=o.data
        if len(mesh.vertices)%27 or len(mesh.polygons)!=len(mesh.vertices)//27*16:raise ValueError('Unexpected canopy topology '+o.name)
        mesh.materials.clear()
        for m in tints:mesh.materials.append(m)
        for k in range(0,len(mesh.vertices),27):
            anchor=mesh.vertices[k].co.copy();scale=random.uniform(.72,1.13);tilt=random.uniform(-.13,.13);idx=random.choices(range(4),[4,3,2,2])[0]
            for v in mesh.vertices[k:k+27]:
                d=(v.co-anchor)*scale;d.z+=d.x*tilt;v.co=anchor+d
            for f in mesh.polygons[k//27*16:k//27*16+16]:f.material_index=idx
            changed+=1
        mesh.update()
    stats['variedCanopyLeaves']=changed
    print('CANOPY_REFINED',changed,flush=True)
    # BVH avoids scattering grass through paths, furniture, stone and cat shelter.
    obstacle_vs=[];obstacle_fs=[]
    prefixes=('Mistwood_Weathered_limestone','Mistwood_Weathered_bench','cat_home_','Conservatory craft','Dressed bridge','Garden_structure')
    for o in scene.objects:
        if o.type!='MESH' or not o.name.startswith(prefixes):continue
        off=len(obstacle_vs);obstacle_vs.extend(o.matrix_world@v.co for v in o.data.vertices)
        obstacle_fs.extend(tuple(off+i for i in f.vertices) for f in o.data.polygons)
    obstacles=BVHTree.FromPolygons(obstacle_vs,obstacle_fs)
    grass_colors=[(.018,.065,.012),(.033,.105,.018),(.065,.15,.028),(.11,.19,.045),(.16,.16,.06)]
    greens=[material('V2 fresh grass '+str(i),c,.75) for i,c in enumerate(grass_colors)]
    # Apply the same botanical range to the inherited extension lawn.
    for i in range(4):replace_material('Fine grass '+str(i),greens[i])
    for i in range(3):replace_material('Meadow_blades_'+str(i),greens[i+1])
    for m in greens:principled(m).inputs['Subsurface Weight'].default_value=.08
    b=Batch();count=0
    for i in range(260000):
        x=random.uniform(-7.35,7.35);y=random.uniform(-7.35,7.35)
        if math.hypot(x,y)>7.3 or -2.5<y<-1.1:continue
        if .55<x<5.5 and 1.4<y<5.4:continue
        if -4.7<x<-1.3 and -6.2<y<-2.7:continue
        if .6<x<2.4 and -6.9<y<-5.65:continue
        if -1.9<x<1.9 and -4.3<y<1.5:continue
        if obstacles.ray_cast(Vector((x,y,.48)),Vector((0,0,-1)),.46)[0] is not None:continue
        density=.60+.27*math.sin(x*1.3+math.cos(y))*math.cos(y*.9)
        if random.random()>density:continue
        h=random.uniform(.045,.14)
        if math.hypot(x,y)>6.4:h*=1.5
        blade(b,random.choices(greens,[3,5,4,2,.4])[0],(x,y,.028),random.random()*math.tau,h,random.uniform(.0015,.0038),random.uniform(.016,.05))
        count+=1
    finish(b,'V2 folded living turf',lawn_col);stats['newCoreGrassBlades']=count
    print('GROUND_REFINED',count,flush=True)
    # Fine crest rail joints, bolted base plates, roof gutters and drain shoes.
    b=Batch()
    # Flush screw heads and washers make the inherited broad bench slats read
    # as assembled wood. Keep all new detail inside each seat's footprint.
    for x,y in [(-3.4,.3),(5.5,-3.5)]:
        for dx in [-.68,.68]:
            for dy in [-.16,.0,.16]:
                lathe(b,brass,(x+dx,y+dy,.567),[(.009,0),(.009,.002),(.006,.003)],16)
    for x in [.9,5.1]:
        for y in [1.75,5.05]:
            b.box(iron,(x,y,.46),(.19,.19,.025))
            for dx in [-.065,.065]:
                for dy in [-.065,.065]:lathe(b,brass,(x+dx,y+dy,.477),[(.012,0),(.012,.009),(.009,.012)],6)
        # Half-round gutter with inner/outer skin and individually modeled brackets.
        vs=[]
        for y in [1.63,5.20]:
            for r in [.063,.056]:
                for j in range(17):
                    a=math.pi+j*math.pi/16;vs.append((x+r*math.cos(a),y,2.66+r*math.sin(a)))
        fs=[]
        for j in range(16):
            fs.extend([(j,j+1,j+35,j+34),(j+17,j+51,j+52,j+18)])
        fs.extend([(0,34,51,17),(16,33,67,50)])
        b.mesh(iron,vs,fs,True)
        for y in [2.0,2.8,3.6,4.4,5.0]:b.tube(brass,[(x+.07*math.cos(t),y,2.66+.07*math.sin(t)) for t in [math.pi+j*math.pi/20 for j in range(21)]],.006,6)
        b.tube(iron,[(x,5.15,2.62),(x+.13,5.20,2.48),(x+.13,5.20,.36),(x+.24,5.20,.18)],.037,16)
        for z in [.55,1.45,2.3]:lathe(b,brass,(x+.13,5.20,z),[(.041,0),(.041,.025)],24)
    finish(b,'V2 bolted rainwater fittings',craft_col,.002)
    # Place specimens beside the greenhouse, outside the walk-through opening.
    petal_mats=[material('V2 lilac corolla '+str(i),c,.57) for i,c in enumerate([(.32,.17,.43),(.48,.30,.58),(.68,.49,.71)])]
    stem=material('V2 fine botanical stem',(.12,.21,.043),.73)
    foliage=[surface('V2 leaf veins '+str(i),[c,tuple(v*1.3 for v in c)],45,.0003,.64) for i,c in enumerate([(.045,.13,.033),(.10,.19,.055),(.14,.24,.09)])]
    for m in foliage:principled(m).inputs['Subsurface Weight'].default_value=.10
    grains=[loam,material('V2 soil ochre grit',(.24,.18,.10),.95),material('V2 soil perlite',(.51,.49,.39),.95)]
    b=Batch();bot=Batch();ground=Batch();pots=[];flowers=0
    for idx,(x,y,r,h) in enumerate([(5.55,1.05,.27,.41),(.22,1.13,.23,.34),(5.62,3.65,.20,.30)]):
        # Wheel-thrown body, slight ellipticity and potter's concentric ridges.
        prof=[(.64*r,0),(.71*r,.025)]+[(r*(.72+.24*t)+.0013*math.sin(t*110),h*t) for t in [j/32 for j in range(2,31)]]+[(r,h*.94),(r*1.04,h*.97),(r*1.04,h),(r*.94,h*1.02),(r*.87,h*.98),(r*.85,h*.91),(.64*r,.04)]
        lathe(b,clay,(x,y,.036),prof,96)
        lathe(b,clay,(x,y,.03),[(.82*r,0),(1.13*r,.015),(1.14*r,.045),(1.07*r,.058),(.82*r,.018)],96)
        ground.ellipsoid(loam,(x,y,h*.88+.036),(.86*r,.86*r,.021),48,8)
        for j in range(1800):
            a=random.random()*math.tau;rr=math.sqrt(random.random())*.82*r;xx=x+rr*math.cos(a);yy=y+rr*math.sin(a);sz=random.uniform(.0015,.0065)
            ground.ellipsoid(random.choices(grains,[24,2,1])[0],(xx,yy,h*.89+.047+.007*math.sin(xx*43)*math.cos(yy*39)),(sz,sz*.73,sz*.56),7,4)
        pots.append([x,y,r,h])
        for j in range(19):
            a=random.random()*math.tau;rr=random.uniform(0,r*.55);px=x+math.cos(a)*rr;py=y+math.sin(a)*rr;z=h*.9+.05
            length=random.uniform(.24,.48);lean=random.uniform(.02,.11)
            pts=[(px+math.cos(a)*lean*t*t,py+math.sin(a)*lean*t*t,z+length*t) for t in [k/10 for k in range(11)]]
            bot.tube(stem,pts,[.0024*(1-k/13) for k in range(11)],6)
            for k in [2,4,6]:
                for sign in [-1,1]:leaf(bot,foliage[j%3],pts[k],a+sign*1.2,.07,.011,.7)
            tip=pts[-1]
            # Whorls of separate curved petals and dark calyx; no blob flowers.
            for tier in range(7):
                for q in range(5):
                    aa=q*math.tau/5+tier*.7;rad=.014*(1-tier/10)
                    p=(tip[0]+rad*math.cos(aa),tip[1]+rad*math.sin(aa),tip[2]-.065+tier*.013)
                    for l in range(4):leaf(bot,petal_mats[(tier+j)%3],p,aa+l*math.tau/4,.011,.005,.3)
                    flowers+=1
    finish(b,'V2 thrown planters and saucers',craft_col)
    finish(bot,'V2 whorled lavender specimens',flora_col)
    # Match the existing four fern vessels; enrich their formerly flat soil too.
    for x,y in [(.42,2.4),(5.56,2.5),(1.3,4.6),(4.7,4.6)]:
        for j in range(1400):
            a=random.random()*math.tau;rr=math.sqrt(random.random())*.25;sz=random.uniform(.0015,.007)
            xx=x+rr*math.cos(a);yy=y+rr*math.sin(a)
            ground.ellipsoid(random.choices(grains,[28,2,1])[0],(xx,yy,.535+.006*math.sin(xx*49)*math.cos(yy*43)),(sz,sz*.72,sz*.57),7,4)
    finish(ground,'V2 raised porous potting soil',soil_col)
    stats.update(newPlanters=pots,modeledFlowerWhorls=flowers)
    # Physical leaf litter gathers at borders and tree bases, not evenly everywhere.
    litter=Batch();dry=[material('V2 fallen leaf '+str(i),c,.95) for i,c in enumerate([(.23,.14,.055),(.32,.22,.09),(.15,.12,.046)])]
    for i in range(400):
        x=random.uniform(-7.3,7.3);y=random.uniform(-7.3,7.3)
        if not 6.4<math.hypot(x,y)<7.25 or -2.6<y<-1.1:continue
        leaf(litter,dry[i%3],(x,y,.04),random.random()*math.tau,.07,.027,.3)
    finish(litter,'V2 gathered leaf litter',soil_col)
    # Keep the inherited layout and scene units, save independently of v1.
    bpy.ops.file.pack_all();scene.render.image_settings.file_format='PNG'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=EXPOSURE
    stats['paletteRevision']=PALETTE_REVISION
    stats['exposureEV']=EXPOSURE
    positions=0
    for o in scene.objects:
        if o.type!='MESH':continue
        coords=np.empty(len(o.data.vertices)*3,dtype=np.float32);o.data.vertices.foreach_get('co',coords)
        if not np.isfinite(coords).all():raise ValueError('Non-finite geometry '+o.name)
        positions+=len(o.data.vertices)
    stats['finitePositionsChecked']=positions
    bpy.ops.wm.save_as_mainfile(filepath=str(master),compress=True)
    report={'version':2,'seed':271026,'sourceMaster':str(args.source),'sourceSha256':hashlib.sha256(args.source.read_bytes()).hexdigest(),'master':master.name,'masterBytes':master.stat().st_size,'masterSha256':hashlib.sha256(master.read_bytes()).hexdigest(),'webSceneChanged':False,'accountDataRead':False,'units':'metres','upAxis':'Z','detailCounts':stats,'objects':len(scene.objects),'baseMeshTriangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in scene.objects if o.type=='MESH'),'runtimeReady':False,'limitations':['Procedural material nodes require UE baking or shader recreation.','Visual geometry is not collision/navigation.','Not yet a runtime LOD/instancing package. No FPS claim.'],'renders':[]}
    (OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('V2_MASTER_SAVED',json.dumps(stats),flush=True)


if args.render_only:
    bpy.ops.wm.open_mainfile(filepath=str(master))
else:build()

if not args.no_render:
    scene=bpy.context.scene;cam=scene.camera
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    devices=[]
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
        if d.use:devices.append(d.name)
    if not devices:raise RuntimeError('OptiX GPU is required')
    scene.render.engine='CYCLES';scene.cycles.device='GPU';scene.cycles.samples=32 if args.preview else 128
    scene.cycles.use_denoising=True;scene.render.resolution_percentage=100
    scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=EXPOSURE
    shots=[('01-island',(30,-44,29),(2,-2.5,.7),42),('02-greenhouse',(10,-9,6),(2.5,2.7,1.9),10),('03-planters',(7.8,-1.9,2.1),(5.48,1.7,.45),2.7),('04-home',(-10,-13,6),(-2.0,-4.7,.7),8)]
    if args.preview:shots=shots[1:]
    report=json.loads((OUT/'build-report.json').read_text(encoding='utf-8'))
    for name,pos,target,scale in shots:
        cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.data.dof.use_dof=False
        scene.render.resolution_x=1200 if args.preview else 2400;scene.render.resolution_y=900 if args.preview else 1800
        path=OUT/(name+('-preview' if args.preview else '')+'.png');scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        report['renders']=[x for x in report['renders'] if x['file']!=path.name]+[{'file':path.name,'resolution':[scene.render.resolution_x,scene.render.resolution_y],'samples':scene.cycles.samples,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
        report['renderer']='Cycles / OptiX';report['devices']=devices
        (OUT/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('V2_RENDER_DONE',path.name,flush=True)
print('V2_COMPLETE',flush=True)
