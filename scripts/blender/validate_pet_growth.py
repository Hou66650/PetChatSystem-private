"""Create comparable growth review images and measure stage-independent proportions."""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pet_growth import ART, ROOT, bounds, studio_render

ASSETS = {
    'cat': {
        'juvenile': ('static/models/pet-growth-v1/cat/tabby-juvenile.glb', .58),
        'adolescent': ('static/models/pet-growth-v1/cat/tabby-adolescent.glb', .72),
        'adult': ('static/models/petchat-cat-v3/cat.glb', .85),
    },
    'shiba': {
        'juvenile': ('static/models/pet-growth-v1/shiba/default-juvenile.glb', .64),
        'adolescent': ('static/models/pet-growth-v1/shiba/default-adolescent.glb', .82),
        'adult': ('static/models/pet-growth-v1/shiba/default-adult.glb', .95),
    },
    'husky': {
        'juvenile': ('static/models/pet-growth-v1/husky/default-juvenile.glb', .72),
        'adolescent': ('static/models/pet-growth-v1/husky/default-adolescent.glb', .91),
        'adult': ('static/models/petchat-husky-v3/xueqiu.glb', 1.05),
    },
    'shepherd': {
        'juvenile': ('static/models/pet-growth-v1/shepherd/default-juvenile.glb', .76),
        'adolescent': ('static/models/pet-growth-v1/shepherd/default-adolescent.glb', .96),
        'adult': ('static/models/pet-growth-v1/shepherd/default-adult.glb', 1.12),
    },
}


def model_objects():
    rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    meshes = [obj for obj in bpy.context.scene.objects
              if obj.type == 'MESH' and any(modifier.type == 'ARMATURE' for modifier in obj.modifiers)]
    return rig, meshes


def reset_rig(rig):
    if rig.animation_data:
        rig.animation_data.action = None
        for track in rig.animation_data.nla_tracks:
            track.mute = True
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.view_layer.update()


def metrics(rig, meshes):
    low, high = bounds(meshes)
    height = high.z - low.z
    front_upper = rig.data.bones['FL_upper'].head_local
    front_foot = rig.data.bones['FL_foot'].head_local
    head = rig.data.bones['head'].head_local
    neck = rig.data.bones['neck'].head_local
    tail = rig.data.bones['tail'].head_local
    return {
        'height': height,
        'headHeightRatio': (head.z - low.z) / height,
        'frontLegRatio': (front_upper.z - front_foot.z) / height,
        'torsoLengthRatio': abs(tail.y - neck.y) / height,
        'headWidthRatio': abs(rig.data.bones['ear_R'].head_local.x - rig.data.bones['ear_L'].head_local.x) / height,
    }


def adult_views(species):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path, _ = ASSETS[species]['adult']
    bpy.ops.import_scene.gltf(filepath=str(ROOT / path))
    rig, meshes = model_objects()
    reset_rig(rig)
    low, high = bounds(meshes)
    studio_render(meshes, low, high, f'{species}-adult')


def import_stage(species, stage):
    before = set(bpy.context.scene.objects)
    path, target_height = ASSETS[species][stage]
    bpy.ops.import_scene.gltf(filepath=str(ROOT / path))
    created = [obj for obj in bpy.context.scene.objects if obj not in before]
    rig = next(obj for obj in created if obj.type == 'ARMATURE')
    meshes = [obj for obj in created if obj.type == 'MESH' and any(modifier.type == 'ARMATURE' for modifier in obj.modifiers)]
    for obj in created:
        if obj.type == 'MESH' and obj not in meshes:
            obj.hide_render = True
    reset_rig(rig)
    return rig, meshes, target_height


def comparison(species, equal_height):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {}
    center_x = [-1.05, 0, 1.05]
    for x, stage in zip(center_x, ['juvenile', 'adolescent', 'adult']):
        rig, meshes, target_height = import_stage(species, stage)
        values = metrics(rig, meshes)
        report[stage] = values
        scale = (.85 if equal_height else target_height) / values['height']
        rig.scale = (scale, scale, scale)
        low, high = bounds(meshes)
        rig.location.x = x - (low.x + high.x) * scale / 2
        rig.location.y = -(low.y + high.y) * scale / 2
        rig.location.z = -low.z * scale
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Growth_comparison_world')
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.72, .76, .72, 1)
    background.inputs['Strength'].default_value = .65
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.003))
    floor = bpy.context.object
    material = bpy.data.materials.new('Comparison_warm_paper')
    material.use_nodes = True
    material.diffuse_color = (.80, .76, .67, 1)
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.80, .76, .67, 1)
    material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
    floor.data.materials.append(material)
    target = Vector((0, 0, .43))
    for location, energy, color in [
        ((2, -3, 4), 650, (1, .93, .84)),
        ((-2, -1, 2), 350, (.78, .86, 1)),
        ((0, 3, 2), 220, (1, 1, 1)),
    ]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.size = 3
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=(3.8, -6.8, 2.5))
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 3.55
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 16
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    suffix = 'equal-height' if equal_height else 'stages'
    scene.render.filepath = str(ART / 'review' / f'{species}-{suffix}.png')
    bpy.ops.render.render(write_still=True)
    return report


def animation_owners(rig, meshes):
    return [rig] + [mesh.data.shape_keys for mesh in meshes if mesh.data.shape_keys]


def select_action(owners, name):
    found = False
    for owner in owners:
        if not owner.animation_data:
            continue
        owner.animation_data.action = None
        for track in owner.animation_data.nla_tracks:
            matched = track.name == name or any(strip.action and strip.action.name == name for strip in track.strips)
            track.mute = not matched
            found |= matched
    if not found:
        raise ValueError('missing action ' + name)
    for owner in owners:
        if hasattr(owner, 'pose'):
            for bone in owner.pose.bones:
                bone.matrix_basis.identity()


def motion_validation(species, stages):
    from pet_mesh_checks import binding_support, deformation_ratio, mesh_snapshot
    report = {}
    for stage in stages:
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
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        rest = mesh_snapshot(meshes)
        stage_report = {'binding': binding_support(meshes, rig), 'actions': {}}
        names = sorted({track.name for owner in owners if owner.animation_data
                        for track in owner.animation_data.nla_tracks})
        if len(names) != 35:
            raise ValueError(f'{stage}: expected 35 actions, got {len(names)}')
        for name in names:
            select_action(owners, name)
            tracks = [track for owner in owners if owner.animation_data
                      for track in owner.animation_data.nla_tracks if not track.mute]
            frames = sorted({int(strip.action.frame_range[0] + (strip.action.frame_range[1] - strip.action.frame_range[0]) * fraction)
                             for track in tracks for strip in track.strips if strip.action
                             for fraction in (0, .5, 1)})
            maximum = 1.0
            minimum_z = float('inf')
            error = None
            for frame in frames:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()
                posed = mesh_snapshot(meshes)
                try:
                    maximum = max(maximum, deformation_ratio(rest, posed, meshes))
                except ValueError as failure:
                    error = str(failure)
                minimum_z = min(minimum_z, min(point.z for part in posed for point in part))
            stage_report['actions'][name] = {'frames': frames, 'maxEdgeRatio': maximum, 'minZ': minimum_z, 'error': error}
            print('GROWTH_MOTION', species, stage, name, maximum, minimum_z, error or '')
        report[stage] = stage_report
    suffix = '-'.join(stages)
    path = ART / f'{species}-motion-{suffix}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTH_MOTION_COMPLETE', json.dumps(report, ensure_ascii=False))


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', choices=sorted(ASSETS), default='cat')
    parser.add_argument('--views', action='store_true')
    parser.add_argument('--motion', action='store_true')
    parser.add_argument('--stages', default='juvenile,adolescent')
    args = parser.parse_args(arguments)
    if args.motion:
        motion_validation(args.species, args.stages.split(','))
        return
    if args.views:
        adult_views(args.species)
    natural = comparison(args.species, False)
    equal = comparison(args.species, True)
    report = {'species': args.species, 'natural': natural, 'equalHeightSourceMetrics': equal}
    path = ART / f'{args.species}-validation.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTH_COMPARISON', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
