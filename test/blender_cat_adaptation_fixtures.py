"""Synthetic proportion fixtures, not evidence of arbitrary reconstructed-cat quality."""
import bpy
from pathlib import Path
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
out = ROOT/'uploads/cat-adapter-fixtures'
out.mkdir(exist_ok=True)
for name, scale, bare in [('tall',(1,1,1.15),False),('long',(1,1.18,1),False),('bare',(1.12,1.08,.95),True)]:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'static/models/petchat-cat-v3/cat.glb'))
    rig = next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    rig.animation_data_clear()
    for bone in rig.pose.bones: bone.matrix_basis.identity()
    meshes = [o for o in bpy.context.scene.objects if o.type=='MESH' and o.vertex_groups]
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    if bare:
        for mesh in meshes:
            if mesh.data.shape_keys: mesh.shape_key_clear()
            world = mesh.matrix_world.copy();mesh.parent=None;mesh.matrix_world=world
            mesh.modifiers.clear();mesh.vertex_groups.clear()
            mesh.matrix_world=Matrix.Diagonal((*scale,1)) @ mesh.matrix_world
            mesh.select_set(True)
    else:
        rig.scale=scale;rig.select_set(True)
        for mesh in meshes: mesh.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
