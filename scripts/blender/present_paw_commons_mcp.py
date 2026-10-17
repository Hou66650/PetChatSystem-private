"""MCP presentation pass; clouds stay in Blender, never in the runtime GLB."""
import bpy,sys,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'art/paw-commons-v2'
sys.path.insert(0,str(HERE))
from shepherd_geometry import Batch
from cinematic_island_tools import collection,finish,camera
bpy.ops.wm.open_mainfile(filepath=str(OUT/'paw-commons-detailed.blend'))
scene=bpy.context.scene
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
for c in list(bpy.data.collections):
    if c.name.startswith('P Cloud'):
        for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(c)
nt=scene.world.node_tree
sky=nt.nodes.new('ShaderNodeTexSky')
sky.sky_type='MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in sky.bl_rna.properties['sky_type'].enum_items.keys() else 'NISHITA'
sky.sun_elevation=math.radians(22);sky.sun_rotation=math.radians(135);sky.sun_size=math.radians(2)
nt.links.new(sky.outputs['Color'],nt.nodes['Background'].inputs['Color']);nt.nodes['Background'].inputs['Strength'].default_value=.15
mat=bpy.data.materials.new('Presentation cloud sea');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
out=nodes.new('ShaderNodeOutputMaterial');vol=nodes.new('ShaderNodeVolumePrincipled');vol.inputs['Color'].default_value=(.9,.95,1,1);vol.inputs['Anisotropy'].default_value=.2
vol.inputs['Emission Color'].default_value=(.80,.87,1,1);vol.inputs['Emission Strength'].default_value=.025
coords=nodes.new('ShaderNodeTexCoord');noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.17;noise.inputs['Detail'].default_value=3
ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.38;ramp.color_ramp.elements[1].position=.72;ramp.color_ramp.elements[1].color=(.21,.21,.21,1)
links.new(coords.outputs['Object'],noise.inputs['Vector']);links.new(noise.outputs['Fac'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],vol.inputs['Density']);links.new(vol.outputs['Volume'],out.inputs['Volume'])
b=Batch();b.box(mat,(0,0,-11),(120,120,8));obs=finish(b,'Cloud sea',collection('P Cloud presentation only'))
for o in obs:o['preview_only']=True
scene.view_settings.exposure=-.35
camera(scene,(12,-37,25),(0,0,-.1),34)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'paw-commons-detailed.blend'),compress=True)
scene.cycles.samples=64
trees=next(c for c in bpy.data.collections if c.name.startswith('D01'))
for name,loc,target,scale in [('06-detailed-overview',(12,-37,25),(0,0,-.1),34),('07-detailed-tunnels',(-18,-13,10),(-8.5,1,1),13),('08-detailed-treehouse',(-11,0,7),(-6,7.5,1.9),8.5),('09-detailed-canopy',(13,-1,7),(6.5,7.3,1.3),8)]:
    # Hide tree crowns in isolated facility studies, not the overall/model export.
    trees.hide_render=name in ['08-detailed-treehouse','09-detailed-canopy']
    camera(scene,loc,target,scale);scene.render.filepath=str(OUT/'review'/f'{name}.png');bpy.ops.render.render(write_still=True)
trees.hide_render=False
print('PAW_PRESENTATION_COMPLETE',flush=True)
