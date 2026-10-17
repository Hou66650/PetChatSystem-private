"""Independent, editable wardrobe assets with real seams, folded cloth and PBR weave.
Run: blender --background --python scripts/blender/build_wardrobe.py
Coordinates below are glTF coordinates; source mesh conversion is explicit.
"""
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'art/wardrobe-v1'
OUT = ROOT / 'static/models/wardrobe-v1'
for path in (ART, OUT): path.mkdir(parents=True, exist_ok=True)
PI = math.pi
report = []


def xyz(p): return (p[0], -p[2], p[1])


def material(name, color, metal=0, cloth=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Roughness'].default_value = .88 if cloth else .38
    node.inputs['Metallic'].default_value = metal
    if cloth:
        n = 256
        yy, xx = np.mgrid[:n, :n]
        weave = .9 + .06*np.sin(xx*PI/2) + .04*np.sin(yy*PI/2)
        rgba = np.ones((n,n,4), dtype=np.float32)
        rgba[:,:,:3] = np.clip(np.array(color)[None,None,:]*weave[:,:,None],0,1)
        image = bpy.data.images.new(name+' woven albedo', width=n, height=n)
        image.pixels.foreach_set(rgba.ravel());image.pack()
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
        mat.node_tree.links.new(tex.outputs['Color'],node.inputs['Base Color'])
        normals = np.ones((n,n,4),dtype=np.float32)
        normals[:,:,0] = .5+.08*np.cos(xx*PI/2)
        normals[:,:,1] = .5+.06*np.cos(yy*PI/2)
        normal = bpy.data.images.new(name+' weave normal',width=n,height=n)
        normal.colorspace_settings.name='Non-Color';normal.pixels.foreach_set(normals.ravel());normal.pack()
        texn=mat.node_tree.nodes.new('ShaderNodeTexImage');texn.image=normal
        mapping=mat.node_tree.nodes.new('ShaderNodeNormalMap')
        mat.node_tree.links.new(texn.outputs['Color'],mapping.inputs['Color'])
        mat.node_tree.links.new(mapping.outputs['Normal'],node.inputs['Normal'])
    return mat


def mesh(name, vertices, faces, mat, uv=None):
    data=bpy.data.meshes.new(name);data.from_pydata([xyz(v) for v in vertices],[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);data.materials.append(mat)
    layer=data.uv_layers.new(name='UVMap')
    for polygon in data.polygons:
        polygon.use_smooth=True
        for loop in polygon.loop_indices:
            i=data.loops[loop].vertex_index
            layer.data[loop].uv=uv[i] if uv else (vertices[i][0]*6+.5, vertices[i][1]*6+.5)
    return obj


def surface(name, fn, mat, nu=32, nv=24, wrap=False):
    verts=[];uv=[];faces=[]
    for i in range(nu+1):
        for j in range(nv+1):
            u,v=i/nu,j/nv;verts.append(fn(u,v));uv.append((u,v))
    for i in range(nu):
        for j in range(nv):
            a=i*(nv+1)+j;faces.append((a,a+1,a+nv+2,a+nv+1))
    return mesh(name,verts,faces,mat,uv)


def cord(name, points, radius, mat, sides=6):
    verts=[];faces=[]
    for i,p in enumerate(points):
        point=Vector(p);tangent=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])
        tangent.normalize();normal=tangent.cross(Vector((0,0,1)))
        if normal.length<.01:normal=tangent.cross(Vector((0,1,0)))
        normal.normalize();other=tangent.cross(normal).normalized()
        for j in range(sides):
            q=point+radius*(normal*math.cos(2*PI*j/sides)+other*math.sin(2*PI*j/sides));verts.append(tuple(q))
    for i in range(len(points)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,b,b+sides,a+sides))
    faces += [tuple(reversed(range(sides))),tuple(range(len(verts)-sides,len(verts)))]
    return mesh(name,verts,faces,mat)


def bead(name, p, scale, mat, segments=16, rings=10):
    return surface(name,lambda u,v:(p[0]+scale[0]*math.sin(PI*u)*math.cos(2*PI*v),p[1]+scale[1]*math.cos(PI*u),p[2]+scale[2]*math.sin(PI*u)*math.sin(2*PI*v)),mat,rings,segments)


def thickness(obj, width):
    modifier=obj.modifiers.new('Sewn fabric thickness','SOLIDIFY');modifier.thickness=width
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def bow(cloth, thread, gold, coral=False):
    for side in (-1,1):
        def loop(u,v):
            angle=v*2*PI;s=math.sin(PI*u)**.7
            return (side*(.014+.112*u),(.004+.044*s)*math.cos(angle),(.003+.020*s)*math.sin(angle)+.0035*math.sin(angle*5)*(1-u))
        surface(('Left' if side<0 else 'Right')+' pleated bow loop',loop,cloth,40,32)
        for v in (0,.5):
            points=[loop(i/50,v) for i in range(51)]
            cord('Rolled loop edge',points,.0018,cloth)
            for i in range(0,48,3):cord('Loop topstitch',[tuple(x+(0 if k!=2 else .0015) for k,x in enumerate(points[t])) for t in (i,i+1)],.00055,thread,5)
        def tail(u,v):
            width=.026*(1-.3*u);tip=u**9*(.015*(1-abs(v*2-1)))
            return (side*(.026+.027*u)+(v-.5)*width*2,-.02-.095*u+tip,.002+.008*math.sin(u*PI*2)+(v-.5)*.009)
        ribbon=surface('Forked folded ribbon tail',tail,cloth,32,12);thickness(ribbon,.0018)
        for v in (.08,.92):
            for i in range(0,27,3):cord('Tail stitching',[tail(t/30,v) for t in (i,i+1)],.0005,thread,5)
    bead('Wrapped center knot',(0,0,.008),(.025,.035,.028),cloth,24,16)
    cord('Gold keeper border',[(.020*math.cos(a),.029*math.sin(a),.031) for a in np.linspace(0,2*PI,49)],.0018,gold)
    bead('Enamel center badge',(0,0,.038),(.012,.014,.004),gold)
    for x,y,r in [(-.005,.006,.0027),(.002,.008,.0027),(.007,.004,.0025),(0,-.003,.005)]:
        bead('Embossed paw on badge',(x,y,.042),(r,r,.0015),thread,10,6)
    if coral:
        cord('Coral ribbon loop trim',[(.029*math.cos(a),.037*math.sin(a),.005) for a in np.linspace(0,2*PI,49)],.001,gold)


def flower(petal, thread, gold):
    for row,count,length in [(0,10,.061),(1,8,.048)]:
        for i in range(count):
            angle=i*2*PI/count+row*.21
            def point(u,v):
                width=.016*math.sin(PI*u)**.65*(v*2-1)
                radial=.009+length*u
                y=.008+row*.005+.012*math.sin(PI*u)-.009*u+.004*(v*2-1)**2+.0015*math.sin(u*PI*5)
                return (radial*math.cos(angle)-width*math.sin(angle),y,radial*math.sin(angle)+width*math.cos(angle))
            obj=surface('Layer %s petal %02d'%(row+1,i+1),point,petal,20,8);thickness(obj,.0015)
            cord('Petal raised midrib',[point(u,.5) for u in np.linspace(.15,.9,14)],.00065,thread,5)
    bead('Domed flower center',(0,.018,0),(.023,.013,.023),gold,24,12)
    for i in range(55):
        a=i*2.39996;r=.021*math.sqrt((i+.5)/55)
        bead('Pollen bead %02d'%i,(r*math.cos(a),.02+.012*math.sqrt(1-(r/.024)**2),r*math.sin(a)),(.0022,.0025,.0022),gold,8,6)
    for x in (-.018,.018):cord('Underside brass hair clip',[(x,-.003,z) for z in np.linspace(-.025,.025,12)],.0025,gold)


def beret(cloth, thread, gold):
    def crown(u,v):
        a=v*2*PI;r=.114*u
        return (r*math.cos(a),.012+.055*(1-u*u)**.7+.006*math.sin(a)*u,r*.87*math.sin(a))
    obj=surface('Six-panel wool crown',crown,cloth,30,96);thickness(obj,.003)
    surface('Inner fitted sweatband',lambda u,v:(.103*math.cos(v*2*PI),-.008+.025*u,.087*math.sin(v*2*PI)),cloth,4,96)
    for n in range(6):
        v=n/6
        cord('Panel raised seam %d'%n,[crown(u,v) for u in np.linspace(.06,.98,40)],.0012,cloth)
        for i in range(3,36,3):
            points=[crown(t/40,v+.006) for t in (i,i+1)]
            cord('Panel hand stitching',[(x,y+.0015,z) for x,y,z in points],.0005,thread,5)
    for i in range(96):
        cord('Sweatband running stitch',[(.104*math.cos(a),.004,.088*math.sin(a)) for a in (i*2*PI/96,(i+.55)*2*PI/96)],.0006,thread,5)
    cord('Wool top stem',[(0,.067,0),(.003,.073,0),(.009,.078,.002)],.004,cloth,10)
    bead('Side brass maker button',(.106,.019,.01),(.003,.008,.008),gold)


for item,color,design in [('moss-bow',(.24,.37,.25),'bow'),('coral-bow',(.57,.25,.20),'bow'),('daisy',(.84,.78,.61),'flower'),('blue-beret',(.23,.34,.42),'beret')]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    cloth=material('Woven '+item,color,cloth=True)
    thread=material('Ivory cotton stitching',(.76,.69,.53),cloth=True)
    gold=material('Brushed warm brass',(.65,.43,.14),metal=.72)
    if design=='bow':bow(cloth,thread,gold,item=='coral-bow')
    elif design=='flower':flower(cloth,thread,gold)
    else:beret(cloth,thread,gold)
    bpy.context.scene['asset_id']=item
    bpy.context.scene['coordinate_contract']='glTF Y-up, forward +Z, dimensions relative to pet height; head origin surface contact, neck origin bow center.'
    bpy.context.scene['materials']='Own woven color and normal textures, packed into blend and GLB; no external references.'
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/(item+'.blend')),compress=True)
    # Merge by material for runtime; editable source retains individually named parts.
    for mat in list(bpy.data.materials):
        objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.data.materials and o.data.materials[0]==mat]
        if not objects:continue
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:obj.select_set(True)
        bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
        obj=bpy.context.object;obj.name=item+' / '+mat.name
        modifier=obj.modifiers.new('Runtime triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=modifier.name)
    target=OUT/(item+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',export_yup=True,export_animations=False)
    triangles=sum(len(o.data.polygons) for o in bpy.context.scene.objects if o.type=='MESH')
    report.append(dict(id=item,triangles=triangles,bytes=target.stat().st_size,source=str((ART/(item+'.blend')).relative_to(ROOT)),model=str(target.relative_to(ROOT))))
(ART/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
