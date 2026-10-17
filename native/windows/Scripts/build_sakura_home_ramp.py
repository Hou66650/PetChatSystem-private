"""A low wooden access ramp for the raised Sakura bed; no master edits."""
from pathlib import Path
import bpy

out = Path(__file__).resolve().parents[1] / 'Saved/Art/P1SakuraHomeRamp'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
# Coordinates remain in the original Blender island space (metres).
verts = [(-2.57,-10.05,.045),(-1.43,-10.05,.045),
         (-1.43,-11.18,.275),(-2.57,-11.18,.275),
         (-2.57,-10.05,.025),(-1.43,-10.05,.025),
         (-1.43,-11.18,.025),(-2.57,-11.18,.025)]
mesh=bpy.data.meshes.new('Shelter_access_ramp')
mesh.from_pydata(verts, [], [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])
mesh.update()
obj=bpy.data.objects.new('Shelter_access_ramp',mesh)
bpy.context.collection.objects.link(obj)
mat=bpy.data.materials.new('Sakura_ramp_oiled_chestnut');mat.diffuse_color=(.075,.036,.015,1)
mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value=mat.diffuse_color;bsdf.inputs['Roughness'].default_value=.72
mesh.materials.append(mat)
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bevel=obj.modifiers.new('Soft worn edges','BEVEL');bevel.width=.004;bevel.segments=3
bpy.ops.export_scene.gltf(filepath=str(out/'sakura-home-ramp.glb'),export_format='GLB',export_apply=True)
