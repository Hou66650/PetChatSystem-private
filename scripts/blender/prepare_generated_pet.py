"""Preserve geometry and PBR, reduce embedded textures for browser delivery."""
import sys
from pathlib import Path
import bpy

source, output = sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(Path(source).resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes or sum(len(o.data.vertices) for o in meshes)>250000:
    raise ValueError('Model empty or exceeds vertex budget')
for im in bpy.data.images:
    if max(im.size)>2048:
        scale=2048/max(im.size)
        im.scale(round(im.size[0]*scale),round(im.size[1]*scale))
bpy.ops.export_scene.gltf(filepath=str(Path(output).resolve()),export_format='GLB')
