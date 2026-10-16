"""Small, non-interactive island dioramas for the home selector."""
import bpy
import bmesh
import json
import gzip
import sys
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/models/home-islands'
OUT.mkdir(parents=True,exist_ok=True)
for theme in (sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['sakura','snow','camp','room']):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src=ROOT/('static/models/petchat-meadow-v1/mistwood-meadow.glb' if theme=='room' else f'static/models/petchat-realistic-islands-v1/{theme}.glb')
    bpy.ops.import_scene.gltf(filepath=str(src))
    for obj in list(bpy.data.objects):
        if obj.type!='MESH':continue
        bpy.context.view_layer.objects.active=obj
        if theme=='room' and obj.data.users>1:obj.data=obj.data.copy()
        # Preserve disconnected foliage, roof tiles and cliff facets. Global
        # collapse decimation erased entire components at low ratios.
        if theme=='room' and obj.name.startswith('Cloud_meadow_Meadow_blades_'):
            bpy.data.objects.remove(obj,do_unlink=True)
            continue
        if theme=='room' and 'Garden_friable_soil' in obj.name:
            # Soil clods are below a pixel in the selector. Keep the bed surface
            # and box topology intact; remove only tiny disconnected clods.
            bm=bmesh.new();bm.from_mesh(obj.data);remaining=set(bm.verts);remove=[]
            while remaining:
                seed=remaining.pop();component={seed};pending=[seed]
                while pending:
                    v=pending.pop()
                    for e in v.link_edges:
                        other=e.other_vert(v)
                        if other in remaining:
                            remaining.remove(other);component.add(other);pending.append(other)
                span=max(max(v.co[i] for v in component)-min(v.co[i] for v in component) for i in range(3))
                if span<.12:remove.extend(component)
            bmesh.ops.delete(bm,geom=remove,context='VERTS');bm.to_mesh(obj.data);bm.free()
        if theme=='room' and obj.name in ['Mistwood_Birch_leaves','Mistwood_Young_leaves','Mistwood_Cedar_sprays']:
            # Four-triangle leaves become two triangles, keeping every leaf's
            # full outer contour. Never randomly delete foliage components.
            bm=bmesh.new();bm.from_mesh(obj.data)
            centers=[v for v in bm.verts if len(v.link_edges)==4 and len(v.link_faces)==4 and all(len(f.verts)==3 for f in v.link_faces)]
            bmesh.ops.dissolve_verts(bm,verts=centers,use_face_split=False,use_boundary_tear=False)
            bm.to_mesh(obj.data);bm.free()
        if theme=='room' and ('Garden_terracotta' in obj.name or obj.name=='Garden_lace_Garden_woven_linen' or obj.name.endswith('_Cedar_bark')):
            # These are continuous pottery, cloth and branch surfaces. Moderate
            # local decimation is safe; ground, masonry and foliage stay intact.
            ratio=.18 if 'Garden_terracotta' in obj.name else .15 if 'Garden_woven_linen' in obj.name else .45
            modifier=obj.modifiers.new('Selector surface LOD','DECIMATE');modifier.ratio=ratio
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        for key in list(obj.keys()):del obj[key]
    for img in bpy.data.images:
        if img.size[0]>128 or img.size[1]>128:
            img.scale(128,128)
            img.pack()
    triangles=0;surface_area=0.;mesh_count=0
    for obj in bpy.data.objects:
        if obj.type!='MESH':continue
        mesh_count+=1;obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            a,b,c=[obj.matrix_world@obj.data.vertices[i].co for i in tri.vertices]
            surface_area+=(b-a).cross(c-a).length*.5;triangles+=1
    bpy.ops.export_scene.gltf(filepath=str(OUT/(theme+'.glb')),export_format='GLB',export_animations=False,export_extras=False)
    # The exporter removes degenerate triangles left by surface simplification.
    raw=(OUT/(theme+'.glb')).read_bytes();doc=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    triangles=sum(doc['accessors'][p['indices']]['count']//3 for n in doc['nodes'] if 'mesh' in n for p in doc['meshes'][n['mesh']]['primitives'])
    (OUT/(theme+'.glb.gz')).write_bytes(gzip.compress((OUT/(theme+'.glb')).read_bytes(),compresslevel=9,mtime=0))
    (OUT/(theme+'.json')).write_text(json.dumps({'theme':theme,'triangles':triangles,'surfaceArea':surface_area,'meshes':mesh_count,'geometry':'room: ground/masonry preserved, all leaf contours retained, pottery/cloth/branch LOD, subpixel clods and short grass omitted' if theme=='room' else 'original topology, no collapse decimation','bytes':(OUT/(theme+'.glb')).stat().st_size},indent=2))
    print('HOME_PREVIEW',theme,(OUT/(theme+'.glb')).stat().st_size,flush=True)
