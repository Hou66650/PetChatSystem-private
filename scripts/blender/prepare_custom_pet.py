"""Inspect a generated pet in Blender without pretending it is animation-ready.

blender --background --factory-startup --python scripts/blender/prepare_custom_pet.py -- input.glb output-directory
Creates an editable .blend and an inspection report; never overwrites source files.
"""
import argparse
import json
from pathlib import Path
import sys
import bpy

parser = argparse.ArgumentParser()
parser.add_argument('input')
parser.add_argument('output')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = Path(args.input).resolve()
target = Path(args.output).resolve()
if not source.is_file() or source.suffix.lower() != '.glb':
    raise ValueError('Input must be an existing GLB')
target.mkdir(parents=True, exist_ok=True)
blend = target / 'pet-review.blend'
report = target / 'inspection.json'
if blend.exists() or report.exists():
    raise FileExistsError('Use a new output directory to preserve previous work')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
result = {
    'source': source.name,
    'meshes': len(meshes),
    'vertices': sum(len(o.data.vertices) for o in meshes),
    'polygons': sum(len(o.data.polygons) for o in meshes),
    'materials': [m.name for m in bpy.data.materials],
    'armatures': [{'name': o.name, 'bones': [b.name for b in o.data.bones]} for o in rigs],
    'actions': [a.name for a in bpy.data.actions],
    'readyForIsland': False,
    'nextChecks': ['appearance approval', 'cat skeleton mapping', 'weight deformation',
                   'walk/run/jump/meal/sleep tests', 'head/eyes/ears/tail controls', 'browser resource budget'],
}
if not meshes:
    raise ValueError('Model has no meshes')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('CUSTOM_PET_INSPECTION ' + json.dumps(result, ensure_ascii=False))
