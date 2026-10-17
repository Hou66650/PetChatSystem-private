"""Render every standard cat coat at each newly modeled growth stage."""
import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pet_growth import ROOT, bounds, studio_render
from validate_pet_growth import model_objects, reset_rig


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--stages', default='juvenile,adolescent')
    args = parser.parse_args(arguments)
    for stage in args.stages.split(','):
        for coat in ['tabby', 'ginger', 'tuxedo', 'calico', 'ragdoll']:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            path = ROOT / 'static/models/pet-growth-v1/cat' / f'{coat}-{stage}.glb'
            bpy.ops.import_scene.gltf(filepath=str(path))
            rig, meshes = model_objects()
            reset_rig(rig)
            low, high = bounds(meshes)
            studio_render(meshes, low, high, f'cat-{coat}-{stage}')


if __name__ == '__main__':
    main()
