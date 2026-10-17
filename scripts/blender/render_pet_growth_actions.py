"""Render every growth-model action at its midpoint for visual contact sheets."""
import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pet_growth import ROOT, bounds
from validate_pet_growth import ASSETS, animation_owners, model_objects, select_action


def setup_studio(low, high):
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Growth_action_world')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.72, .76, .72, 1)
    background.inputs['Strength'].default_value = .6
    center = (low + high) / 2
    size = high - low
    distance = max(size) * 3.2 + 1
    target = center.copy()
    for location, energy, color in [
        ((2, -3, 4), 550, (1, .93, .84)),
        ((-2, -1, 2), 280, (.78, .86, 1)),
        ((0, 3, 2), 220, (1, 1, 1)),
    ]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.size = 3
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.002))
    floor = bpy.context.object
    material = bpy.data.materials.new('Action_warm_paper')
    material.use_nodes = True
    material.diffuse_color = (.80, .76, .67, 1)
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.80, .76, .67, 1)
    floor.data.materials.append(material)
    bpy.ops.object.camera_add(location=(distance * .72, -distance * .72, center.z + size.z * .15))
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max(size.z * 1.25, size.y * 1.15, .5)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 12
    scene.render.resolution_x = 320
    scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'


def render(species, stage, work):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path, _ = ASSETS[species][stage]
    bpy.ops.import_scene.gltf(filepath=str(ROOT / path))
    rig, meshes = model_objects()
    owners = animation_owners(rig, meshes)
    for owner in owners:
        if owner.animation_data:
            owner.animation_data.action = None
            for track in owner.animation_data.nla_tracks:
                track.mute = True
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    low, high = bounds(meshes)
    setup_studio(low, high)
    names = sorted({track.name for owner in owners if owner.animation_data
                    for track in owner.animation_data.nla_tracks})
    for name in names:
        select_action(owners, name)
        tracks = [track for owner in owners if owner.animation_data
                  for track in owner.animation_data.nla_tracks if not track.mute]
        ranges = [strip.action.frame_range for track in tracks for strip in track.strips if strip.action]
        start = min(value[0] for value in ranges)
        end = max(value[1] for value in ranges)
        bpy.context.scene.frame_set(round((start + end) / 2))
        bpy.context.view_layer.update()
        bpy.context.scene.render.filepath = str(work / f'{stage}-{name}.png')
        bpy.ops.render.render(write_still=True)
        print('GROWTH_ACTION_RENDER', species, stage, name)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', choices=sorted(ASSETS), default='cat')
    parser.add_argument('--stages', default='juvenile,adolescent,adult')
    parser.add_argument('--work', required=True)
    args = parser.parse_args(arguments)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    for stage in args.stages.split(','):
        render(args.species, stage, work)


if __name__ == '__main__':
    main()
