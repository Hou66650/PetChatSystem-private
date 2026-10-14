"""Small, non-interactive island dioramas for the home selector."""
import bpy
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
        if len(obj.data.polygons)>600:
            mod=obj.modifiers.new('Homepage silhouette','DECIMATE');mod.ratio=.04
            bpy.ops.object.modifier_apply(modifier=mod.name)
        for key in list(obj.keys()):del obj[key]
    for img in bpy.data.images:
        if img.size[0]>128 or img.size[1]>128:
            img.scale(128,128)
            img.pack()
    bpy.ops.export_scene.gltf(filepath=str(OUT/(theme+'.glb')),export_format='GLB',export_animations=False,export_extras=False)
    print('HOME_PREVIEW',theme,(OUT/(theme+'.glb')).stat().st_size,flush=True)
