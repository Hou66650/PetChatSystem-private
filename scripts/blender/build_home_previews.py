"""Small, non-interactive island dioramas for the home selector."""
import bpy
import json
import gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/models/home-islands'
OUT.mkdir(parents=True,exist_ok=True)
for theme in ['sakura','snow','camp','room']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    src=ROOT/('static/models/petchat-mistwood-v1/mistwood.glb' if theme=='room' else f'static/models/petchat-realistic-islands-v1/{theme}.glb')
    bpy.ops.import_scene.gltf(filepath=str(src))
    for obj in list(bpy.data.objects):
        if obj.type!='MESH':continue
        bpy.context.view_layer.objects.active=obj
        # Preserve disconnected foliage, roof tiles and cliff facets. Global
        # collapse decimation erased entire components at low ratios.
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
    (OUT/(theme+'.glb.gz')).write_bytes(gzip.compress((OUT/(theme+'.glb')).read_bytes(),compresslevel=9,mtime=0))
    (OUT/(theme+'.json')).write_text(json.dumps({'theme':theme,'triangles':triangles,'surfaceArea':surface_area,'meshes':mesh_count,'geometry':'original topology, no collapse decimation','bytes':(OUT/(theme+'.glb')).stat().st_size},indent=2))
    print('HOME_PREVIEW',theme,(OUT/(theme+'.glb')).stat().st_size,flush=True)
