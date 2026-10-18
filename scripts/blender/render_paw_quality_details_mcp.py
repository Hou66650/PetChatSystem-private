"""Unobstructed facility studies; foliage is hidden only for these labelled renders."""
import bpy,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'art/paw-commons-v3'
sys.path.insert(0,str(HERE))
from cinematic_island_tools import camera
bpy.ops.wm.open_mainfile(filepath=str(OUT/'paw-commons-quality.blend'))
scene=bpy.context.scene
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
except Exception:scene.cycles.device='CPU'
for c in bpy.data.collections:
    if c.name.startswith('D01'):c.hide_render=True
for name,loc,target,scale in [('03-treehouse',(-11,0,7),(-6,7.5,1.9),8.5),('04-canopy-toys',(13,-1,7),(6.5,7.3,1.3),8),('05-toy-shelf',(14,-12,5),(10,-5.1,.8),4.2)]:
    camera(scene,loc,target,scale);scene.render.filepath=str(OUT/'review'/f'{name}.png');bpy.ops.render.render(write_still=True)
print('PAW_FACILITY_STUDIES_COMPLETE',flush=True)
