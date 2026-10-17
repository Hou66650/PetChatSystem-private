"""Build distinct juvenile and adolescent pet geometry from each species' adult asset."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'art' / 'pet-growth-v1'
MODELS = ROOT / 'static' / 'models' / 'pet-growth-v1'
SPECIES = {
    'cat': {
        'source': 'static/models/petchat-cat-v3/cat.glb',
        'prefix': 'cat',
        'appearance': 'tabby',
    },
    'shiba': {
        'source': 'static/models/petchat-shiba-v4/qiuqiu.glb',
        'prefix': 'shiba',
        'appearance': 'default',
    },
    'husky': {
        'source': 'static/models/petchat-husky-v3/xueqiu.glb',
        'prefix': 'husky',
        'appearance': 'default',
    },
    'shepherd': {
        'source': 'static/models/petchat-shepherd-v2/shepherd.glb',
        'prefix': 'shepherd',
        'appearance': 'default',
    },
}
STAGES = {
    'juvenile': {
        'label': '幼年', 'body': (1.06, .80, .90), 'head': (1.20, .95, 1.20),
        'leg': .75, 'paw': .95, 'tail': .85,
    },
    'adolescent': {
        'label': '少年', 'body': (1.03, .90, .95), 'head': (1.10, 1.00, 1.10),
        'leg': .88, 'paw': .98, 'tail': .93,
    },
    'adult': {
        'label': '成年', 'body': (1, 1, 1), 'head': (1, 1, 1),
        'leg': 1, 'paw': 1, 'tail': 1,
    },
}
BODY_BONES = {'root', 'spine', 'spine_front', 'spine_rear', 'neck', 'neck_flex', 'SOCKET_neck'}
HEAD_BONES = {
    'head', 'brow_L', 'brow_R', 'cheek_L', 'cheek_R', 'ear_L', 'ear_R', 'eye_L', 'eye_R',
    'jaw', 'SOCKET_mouth', 'tongue', 'lid_L', 'lid_R', 'SOCKET_head',
}
TAIL_BONES = {'tail', 'tail_mid', 'tail_tip'}
LEGS = ['FL', 'FR', 'HL', 'HR']


def scale_about(pivot, scale):
    if isinstance(scale, (int, float)):
        matrix = Matrix.Scale(scale, 4)
    else:
        matrix = Matrix.Diagonal((*scale, 1.0))
    return Matrix.Translation(pivot) @ matrix @ Matrix.Translation(-pivot)


def bone_transform(bone, target_head, target_tail):
    source_head = bone.head_local.copy()
    source_tail = bone.tail_local.copy()
    source_direction = source_tail - source_head
    target_direction = target_tail - target_head
    if source_direction.length < 1e-6 or target_direction.length < 1e-6:
        return Matrix.Translation(target_head) @ Matrix.Translation(-source_head)
    scale = target_direction.length / source_direction.length
    rotation = source_direction.normalized().rotation_difference(target_direction.normalized())
    return (Matrix.Translation(target_head) @ rotation.to_matrix().to_4x4() @
            Matrix.Scale(scale, 4) @ Matrix.Translation(-source_head))


def stage_transforms(rig, stage):
    bones = rig.data.bones
    body_scale = stage['body']
    body = scale_about(Vector((0, -.1, 0)), body_scale)
    front = bones['FL_upper']
    upper = front.head_local
    foot = bones['FL_foot'].head_local
    target_upper_z = foot.z + (upper.z - foot.z) * stage['leg']
    body = Matrix.Translation((0, 0, target_upper_z - (body @ upper).z)) @ body
    transforms = {}
    for bone in bones:
        transforms[bone.name] = body.copy()
    head = bones['head'].head_local.copy()
    head_transform = body @ scale_about(head, stage['head'])
    for name in HEAD_BONES:
        if name in bones:
            transforms[name] = head_transform.copy()
    tail = bones['tail'].head_local.copy()
    tail_transform = body @ scale_about(tail, stage['tail'])
    for name in TAIL_BONES:
        transforms[name] = tail_transform.copy()
    for name in BODY_BONES:
        if name.startswith('SOCKET_') and name in bones:
            transforms[name] = head_transform.copy()
    for leg in LEGS:
        upper_bone = bones[leg + '_upper']
        lower_bone = bones[leg + '_lower']
        foot_bone = bones[leg + '_foot']
        upper_target = body @ upper_bone.head_local
        foot_target = body @ foot_bone.head_local
        foot_target.z = foot_bone.head_local.z
        knee_target = foot_target + (lower_bone.head_local - foot_bone.head_local) * stage['leg']
        transforms[upper_bone.name] = bone_transform(upper_bone, upper_target, knee_target)
        transforms[lower_bone.name] = bone_transform(lower_bone, knee_target, foot_target)
        for name in [foot_bone.name, 'toe_' + leg]:
            bone = bones[name]
            direction = (bone.tail_local - bone.head_local) * stage['paw']
            transforms[name] = bone_transform(bone, foot_target, foot_target + direction)
        attachment = ('shoulder_' if leg[0] == 'F' else 'hip_') + leg[1]
        transforms[attachment] = body.copy()
    return transforms


def apply_stage(rig, meshes, transforms):
    original = {bone.name: (bone.head_local.copy(), bone.tail_local.copy(), bone.matrix_local.copy())
                for bone in rig.data.bones}
    groups = []
    for mesh in meshes:
        lookup = {group.index: group.name for group in mesh.vertex_groups}
        weights = []
        for vertex in mesh.data.vertices:
            values = []
            for item in vertex.groups:
                name = lookup.get(item.group)
                if name in transforms and item.weight > 1e-6:
                    values.append((name, item.weight))
            weights.append(values)
        groups.append(weights)
    for mesh, weights in zip(meshes, groups):
        deltas = []
        for vertex, values in zip(mesh.data.vertices, weights):
            point = vertex.co.copy()
            if not values:
                deltas.append(Vector())
                continue
            total = sum(weight for _, weight in values)
            deformed = Vector()
            for name, weight in values:
                deformed += (transforms[name] @ point) * (weight / total)
            delta = deformed - point
            vertex.co = deformed
            deltas.append(delta)
        if mesh.data.shape_keys:
            for key in mesh.data.shape_keys.key_blocks:
                if key.name == 'Basis':
                    continue
                for point, delta in zip(key.data, deltas):
                    point.co += delta
        mesh.data.update()
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in rig.data.edit_bones:
        head, tail, matrix = original[bone.name]
        transform = transforms[bone.name]
        target_head = transform @ head
        target_tail = transform @ tail
        rotation = transform.to_3x3().to_quaternion() if bone.name.startswith(('FL_', 'FR_', 'HL_', 'HR_', 'toe_')) else matrix.to_3x3().to_quaternion()
        bone.matrix = Matrix.Translation(target_head) @ rotation.to_matrix().to_4x4()
        bone.head = target_head
        bone.tail = target_tail
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()


def action_curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def retarget_action_locations(stage):
    factors = {}
    for name in BODY_BONES | {'root'}:
        factors[name] = stage['leg']
    for leg in LEGS:
        for suffix in ['upper', 'lower', 'foot']:
            factors[leg + '_' + suffix] = stage['leg']
        factors['toe_' + leg] = stage['leg']
        factors[('shoulder_' if leg[0] == 'F' else 'hip_') + leg[1]] = stage['leg']
    for name in TAIL_BONES:
        factors[name] = stage['tail']
    for action in bpy.data.actions:
        for curve in action_curves(action):
            if not curve.data_path.startswith('pose.bones[') or not curve.data_path.endswith('].location'):
                continue
            bone = curve.data_path.split('"')[1]
            factor = factors.get(bone)
            if factor is None:
                continue
            for point in curve.keyframe_points:
                point.co.y *= factor
                point.handle_left.y *= factor
                point.handle_right.y *= factor
            curve.update()


def ground_action_roots(rig, meshes):
    import numpy as np
    body = next((mesh for mesh in meshes if mesh.data.shape_keys), max(meshes, key=lambda mesh: len(mesh.data.vertices)))
    points = np.array([[*vertex.co, 1] for vertex in body.data.vertices])
    lookup = {group.index: group.name for group in body.vertex_groups}
    groups = {}
    for index, vertex in enumerate(body.data.vertices):
        for item in vertex.groups:
            name = lookup.get(item.group)
            if name and item.weight > 1e-6:
                groups.setdefault(name, []).append((index, item.weight))
    groups = {name: (np.array([index for index, _ in values]), np.array([weight for _, weight in values]))
              for name, values in groups.items()}
    inverses = {name: rig.data.bones[name].matrix_local.inverted() for name in groups}
    root = rig.pose.bones['root']
    scene = bpy.context.scene
    for track in rig.animation_data.nla_tracks:
        action = track.strips[0].action
        rig.animation_data.action = action
        if action.slots:
            rig.animation_data.action_slot = action.slots[0]
        frames = range(int(action.frame_range[0]), int(action.frame_range[1]) + 1)
        values = []
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            heights = np.zeros(len(points))
            for name, (indices, weights) in groups.items():
                matrix = np.array(rig.pose.bones[name].matrix @ inverses[name])
                heights[indices] += (points[indices] @ matrix[2]) * weights
            lift = max(0, .003 - float(heights.min()))
            matrix = root.matrix.copy()
            matrix.translation.z += lift
            values.append(root.bone.convert_local_to_pose(matrix, root.bone.matrix_local, invert=True).to_translation())
        for curve in action_curves(action):
            if curve.data_path == 'pose.bones["root"].location':
                curve.keyframe_points.clear()
        for frame, value in zip(frames, values):
            root.location = value
            root.keyframe_insert(data_path='location', frame=frame, group='root')
    rig.animation_data.action = None
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    scene.frame_set(1)


def bounds(meshes):
    low = Vector((float('inf'),) * 3)
    high = Vector((float('-inf'),) * 3)
    for mesh in meshes:
        for vertex in mesh.data.vertices:
            point = mesh.matrix_world @ vertex.co
            for index in range(3):
                low[index] = min(low[index], point[index])
                high[index] = max(high[index], point[index])
    return low, high


def weight_coverage(meshes):
    result = {}
    for leg in LEGS:
        names = {leg + '_foot', leg + '_lower'}
        count = 0
        for mesh in meshes:
            lookup = {group.index: group.name for group in mesh.vertex_groups}
            for vertex in mesh.data.vertices:
                weight = sum(item.weight for item in vertex.groups if lookup.get(item.group) in names)
                if weight >= .25:
                    count += 1
        result[leg] = count
    return result


def studio_render(meshes, low, high, prefix):
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Growth_review_world')
    center = (low + high) / 2
    size = high - low
    distance = max(size) * 3.2 + 1
    cameras = {
        'front': Vector((center.x, -distance, center.z)),
        'side': Vector((distance, center.y, center.z)),
        'back': Vector((center.x, distance, center.z)),
        'three-quarter': Vector((distance * .72, -distance * .72, center.z + size.z * .15)),
    }
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max(size.z * 1.22, size.y * 1.12, .5)
    scene.camera = camera
    for location, energy, color in [
        ((2, -3, 4), 500, (1, .93, .84)),
        ((-2, -1, 2), 240, (.78, .86, 1)),
    ]:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.color = color
        light.data.shape = 'DISK'
        light.data.size = 3
        light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.72, .76, .72, 1)
    background.inputs['Strength'].default_value = .55
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, low.z - .002))
    floor = bpy.context.object
    material = bpy.data.materials.new('Review_warm_paper')
    material.diffuse_color = (.80, .76, .67, 1)
    material.use_nodes = True
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.80, .76, .67, 1)
    material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .85
    floor.data.materials.append(material)
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 16
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    for name, location in cameras.items():
        camera.location = location
        camera.rotation_euler = (center - location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(ART / 'review' / f'{prefix}-{name}.png')
        bpy.ops.render.render(write_still=True)


def build(species, stage_name, render=True):
    config = SPECIES[species]
    stage = STAGES[stage_name]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT / config['source']))
    rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    meshes = [obj for obj in bpy.context.scene.objects
              if obj.type == 'MESH' and any(modifier.type == 'ARMATURE' for modifier in obj.modifiers)]
    if rig.animation_data:
        rig.animation_data.action = None
        for track in rig.animation_data.nla_tracks:
            track.mute = True
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    transforms = stage_transforms(rig, stage)
    apply_stage(rig, meshes, transforms)
    retarget_action_locations(stage)
    ground_action_roots(rig, meshes)
    rig['growth_stage'] = stage['label']
    rig['growth_geometry'] = 'Species-specific rest mesh, shape keys and joints rebuilt; not an object-scale variant.'
    rig['growth_source'] = config['source']
    bpy.context.view_layer.update()
    low, high = bounds(meshes)
    prefix = f"{config['prefix']}-{stage_name}"
    ART.mkdir(parents=True, exist_ok=True)
    (ART / 'review').mkdir(parents=True, exist_ok=True)
    destination = MODELS / config['prefix']
    destination.mkdir(parents=True, exist_ok=True)
    glb = destination / f"{config['appearance']}-{stage_name}.glb"
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=str(ART / f'{prefix}.blend'), compress=True)
    bpy.ops.export_scene.gltf(
        filepath=str(glb), export_format='GLB', use_selection=True,
        export_animation_mode='NLA_TRACKS', export_force_sampling=True,
        export_frame_range=False, export_def_bones=True, export_extras=True,
        export_morph_normal=False,
    )
    report = {
        'species': species,
        'stage': stage_name,
        'label': stage['label'],
        'source': config['source'],
        'parameters': stage,
        'bounds': {'min': list(low), 'max': list(high)},
        'weightCoverage': weight_coverage(meshes),
        'bones': len(rig.data.bones),
        'actions': len(bpy.data.actions),
        'glb': str(glb.relative_to(ROOT)),
        'bytes': glb.stat().st_size,
        'sha256': hashlib.sha256(glb.read_bytes()).hexdigest(),
    }
    (ART / f'{prefix}-build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GROWTH_BUILD', json.dumps(report, ensure_ascii=False))
    if render:
        studio_render(meshes, low, high, prefix)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', choices=sorted(SPECIES), default='cat')
    parser.add_argument('--stages', default='juvenile,adolescent')
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args(arguments)
    for stage in args.stages.split(','):
        if stage not in STAGES:
            parser.error('unknown stage: ' + stage)
        build(args.species, stage, not args.no_render)


if __name__ == '__main__':
    main()
