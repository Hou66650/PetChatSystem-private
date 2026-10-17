"""Blender-only runtime shelter clearance edit; preserve the offline master."""
from pathlib import Path
import bpy,json,hashlib
p=Path(__file__).resolve().parents[1]
src=p/'Saved/Art/P1SakuraV2Chunks/sakura-V2_05-00.glb';out=p/'Saved/Art/P1SakuraV2Care';out.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(src))
changed={}
for obj in bpy.context.scene.objects:
 if obj.type!='MESH':continue
 if not any(t in obj.name for t in ('aged_chestnut','aged chestnut','ink_glazed','ink glazed','woven_cushions','woven cushions')):continue
 count=0;inverse=obj.matrix_world.inverted()
 for v in obj.data.vertices:
  world=obj.matrix_world@v.co
  if -2.91<world.x<-1.09 and -12.21<world.y<-10.79:
   if world.z>.30 and 'cushion' not in obj.name:world.z=.30+(world.z-.30)*1.5
   # Move the complete shelter off the original courtyard stone rails.
   world.x+=1.6;world.y+=5.5;v.co=inverse@world;count+=1
 if count:changed[obj.name]=count
assert changed,'No authored shelter geometry found'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(out/'sakura-care.glb'),export_format='GLB',use_selection=True,export_apply=True,export_cameras=False,export_lights=False)
(out/'clearance.json').write_text(json.dumps({'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'changed_vertices':changed,'edit':'shelter roof/posts raised 1.5x above 0.30m; shelter/bed moved (+1.6,+5.5,0)m to runtime-probed open ground; bowls and other furniture unchanged'},indent=2),encoding='utf-8')
print('CARE_CLEARANCE_EXPORTED',changed)
