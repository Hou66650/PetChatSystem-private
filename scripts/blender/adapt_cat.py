"""Local cat adaptation with explicit compatibility gates and human motion review.

blender -b --factory-startup --python scripts/blender/adapt_cat.py -- INPUT OUTPUT [--mode template-skin] [--forward -Y]
Auto mode accepts compatible standard rigs (or an explicit bone map). Template-skin
is an opt-in draft for standing unrigged cats, not a general animal auto-rigger.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'static/models/petchat-cat-v3/cat.glb'
CLIPS = ['idle_breathe', 'walk', 'run', 'sit_down', 'stand_up', 'lie_down',
         'sleep_loop', 'eat', 'sniff', 'stretch', 'turn_left', 'turn_right']
CORE = ['root', 'spine', 'neck', 'head', 'tail', 'tail_mid', 'tail_tip'] + [
    leg + '_' + joint for leg in ['FL', 'FR', 'HL', 'HR'] for joint in ['upper', 'lower', 'foot']]


def reset(rig):
    if rig.animation_data:
        rig.animation_data.action = None
        for track in rig.animation_data.nla_tracks: track.mute = True
    for bone in rig.pose.bones: bone.matrix_basis.identity()
    bpy.context.view_layer.update()


def bounds(objects):
    points = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    return Vector([min(p[i] for p in points) for i in range(3)]), Vector([max(p[i] for p in points) for i in range(3)])


def action_on(rig, action):
    rig.animation_data_create()
    rig.animation_data.action = action
    if action.slots: rig.animation_data.action_slot = action.slots[0]


def main(args):
    dest = Path(args.output).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if any((dest / f).exists() for f in ['adapted.glb', 'review.blend', 'report.json']):
        raise ValueError('输出目录已存在结果，请使用新目录')
    report = {'schema': 1, 'template': 'pait-cat-v1', 'templateSha256': hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
              'readyForIsland': False, 'warnings': [], 'mode': args.mode}
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(TEMPLATE))
        donor_objects = set(bpy.context.scene.objects)
        donor = next(o for o in donor_objects if o.type == 'ARMATURE')
        reset(donor)
        actions = {}
        for track in donor.animation_data.nla_tracks:
            if track.strips: actions[track.name] = track.strips[0].action
        # Imported GLBs retain the public clip names in NLA tracks.
        for action in bpy.data.actions:
            if action.name in CLIPS: actions.setdefault(action.name, action)
        missing = [c for c in CLIPS if c not in actions]
        if missing: raise ValueError('标准动作库缺少：' + ', '.join(missing))
        manifest = {'id': 'pait-cat-v1', 'coordinates': 'Blender Z up, cat faces -Y',
                    'coreBones': CORE, 'clips': CLIPS,
                    'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else None,
                               'head': list(b.head_local), 'tail': list(b.tail_local)} for b in donor.data.bones]}
        (dest / 'template.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        bpy.ops.import_scene.gltf(filepath=str(Path(args.input).resolve()))
        incoming = set(bpy.context.scene.objects) - donor_objects
        meshes = [o for o in incoming if o.type == 'MESH']
        rigs = [o for o in incoming if o.type == 'ARMATURE']
        if not meshes or sum(len(o.data.vertices) for o in meshes) > 250000:
            raise ValueError('模型为空或超过 25 万顶点，请先在 Blender 中精简')
        if any(o.type not in ('MESH','ARMATURE','EMPTY') for o in incoming):
            raise ValueError('请上传只包含猫咪的模型')
        if rigs:
            if len(rigs) != 1: raise ValueError('当前只支持一套猫咪骨骼')
            rig = rigs[0]
            reset(rig)
            loose = [m for m in meshes if not m.vertex_groups and m.parent_type != 'BONE']
            if loose:
                report['excludedUnboundObjects'] = [m.name for m in loose]
                report['warnings'].append('未绑定的独立物件已从动作模型排除，请核对是否有应保留的配件。')
                for mesh in loose:
                    meshes.remove(mesh); incoming.remove(mesh); bpy.data.objects.remove(mesh, do_unlink=True)
            if args.bone_map:
                mapping = json.loads(Path(args.bone_map).read_text(encoding='utf-8'))
                if not isinstance(mapping, dict) or len(set(mapping.values())) != len(mapping):
                    raise ValueError('关节映射必须一一对应')
                for old, new in mapping.items():
                    if old not in rig.data.bones or new not in donor.data.bones or (new != old and new in rig.data.bones):
                        raise ValueError('关节映射不存在或名称冲突')
                    rig.data.bones[old].name = new
                    for mesh in meshes:
                        if old in mesh.vertex_groups: mesh.vertex_groups[old].name = new
            missing = [b for b in CORE if b not in rig.data.bones]
            if missing: raise ValueError('需要人工对应骨骼：' + ', '.join(missing))
            incompatible = []
            for name in CORE:
                target, source = rig.data.bones[name], donor.data.bones[name]
                if (target.parent.name if target.parent else None) != (source.parent.name if source.parent else None):
                    incompatible.append(name + ':层级')
                delta = target.matrix_local.to_quaternion().rotation_difference(source.matrix_local.to_quaternion())
                if abs(delta.angle) > math.radians(12): incompatible.append(name + ':静止朝向')
            if incompatible: raise ValueError('静止骨架不兼容，需要 Blender 重定向：' + ', '.join(incompatible))
            # Location curves depend on rest-bone lengths. Preserve the original
            # weights and only reuse actions when core rest lengths are compatible.
            ratios = [(rig.data.bones[b].length / donor.data.bones[b].length) for b in CORE if donor.data.bones[b].length > .0001]
            if max(ratios) / min(ratios) > 1.25:
                raise ValueError('骨骼比例差异过大，需要调整步幅与关节位置')
            if rig.animation_data: rig.animation_data_clear()
            for obj in donor_objects: bpy.data.objects.remove(obj, do_unlink=True)
            report['method'] = 'compatible-rig-action-reuse'
        else:
            if args.mode != 'template-skin':
                raise ValueError('未发现骨骼：请确认是站立猫咪，选择模板蒙皮草稿或在 Blender 中绑骨')
            if any(m.data.shape_keys for m in meshes):
                raise ValueError('含表情形变的模型需要人工保留形变后适配')
            angle = {'-Y': 0, '+Y': math.pi, '+X': math.pi/2, '-X': -math.pi/2}[args.forward]
            rotation = Matrix.Rotation(angle, 4, 'Z')
            for mesh in meshes:
                world = rotation @ mesh.matrix_world
                mesh.parent = None
                mesh.matrix_world = world
                bpy.ops.object.select_all(action='DESELECT')
                mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            lo, hi = bounds(meshes); dims = hi-lo
            if min(dims) <= .0001: raise ValueError('模型尺寸无效')
            donor_meshes = [o for o in donor_objects if o.type == 'MESH' and o.vertex_groups]
            dlo, dhi = bounds(donor_meshes); dd = dhi-dlo
            ratios = [dims[i]/dd[i] for i in range(3)]
            if max(ratios)/min(ratios) > 1.8:
                raise ValueError('外形或朝向与站立猫模板差异过大，请检查正面方向或人工定位关节')
            # Fit the donor, never squash the user's appearance to match the template.
            scale = Matrix.Diagonal(Vector((*ratios, 1)))
            fitted = Matrix.Translation(lo) @ scale @ Matrix.Translation(-dlo)
            for obj in donor_objects:
                if obj.parent not in donor_objects: obj.matrix_world = fitted @ obj.matrix_world
            bpy.context.view_layer.update()
            skin = max(donor_meshes, key=lambda o: len(o.data.polygons))
            rig = donor
            for mesh in meshes:
                mesh.vertex_groups.clear()
                for group in skin.vertex_groups: mesh.vertex_groups.new(name=group.name)
                bpy.ops.object.select_all(action='DESELECT')
                mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
                transfer = mesh.modifiers.new('TemplateWeightTransfer', 'DATA_TRANSFER')
                transfer.object = skin; transfer.use_vert_data = True
                transfer.data_types_verts = {'VGROUP_WEIGHTS'}
                transfer.vert_mapping = 'POLYINTERP_NEAREST'
                bpy.ops.object.modifier_apply(modifier=transfer.name)
                world = mesh.matrix_world.copy(); mesh.parent = rig; mesh.matrix_world = world
                modifier = mesh.modifiers.new('CatArmature', 'ARMATURE'); modifier.object = rig
            for obj in donor_objects:
                if obj != rig: bpy.data.objects.remove(obj, do_unlink=True)
            incoming = set(meshes) | {rig}
            report['method'] = 'template-nearest-surface-skin-draft'
            report['warnings'].append('模板蒙皮仅为草稿：请重点检查腋下、腹部、尾根，不能当作通用自动绑骨。')
        unweighted = 0
        for mesh in meshes:
            if mesh.parent_type == 'BONE' and mesh.parent == rig and mesh.parent_bone in rig.data.bones:
                continue
            if not any(m.type == 'ARMATURE' and m.object == rig for m in mesh.modifiers):
                raise ValueError('网格未连接到目标骨骼，需要修正绑定关系')
            valid = {g.index for g in mesh.vertex_groups if g.name in rig.data.bones and rig.data.bones[g.name].use_deform}
            unweighted += sum(1 for v in mesh.data.vertices if sum(g.weight for g in v.groups if g.group in valid) < .001)
        report['unweightedVertices'] = unweighted
        if unweighted: raise ValueError('存在未绑定顶点，需要修正蒙皮后重试')
        reset(rig);rig.animation_data_clear();rig.animation_data_create()
        for name in CLIPS:
            action = actions[name].copy(); action.name = 'pait_' + name
            track = rig.animation_data.nla_tracks.new(); track.name = name
            strip = track.strips.new(name, int(action.frame_range[0]), action)
            if action.slots: strip.action_slot = action.slots[0]
            track.mute = True
        report['clips'] = CLIPS
        report['bones'] = [b.name for b in rig.data.bones]
        report['warnings'] += ['动作已复用；脚掌滑动、穿地及脸部变形仍需逐项验收。',
                               '没有制作眼球或眼睑结构的模型，不保证眨眼与眼神效果。']
        samples = {}
        for track in rig.animation_data.nla_tracks:
            action = track.strips[0].action; action_on(rig, action)
            frames = []
            for fraction in (0, .25, .5, .75, 1):
                start, end = action.frame_range; bpy.context.scene.frame_set(int(start + (end-start)*fraction))
                feet = {leg: list(rig.matrix_world @ rig.pose.bones[leg+'_foot'].head) for leg in ['FL','FR','HL','HR']}
                if not all(math.isfinite(x) for p in feet.values() for x in p): raise ValueError('动作包含无效坐标')
                frames.append(feet)
            samples[track.name] = frames
        report['footSamples'] = samples
        reset(rig)
        bpy.context.scene.frame_set(1)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in incoming: obj.select_set(True)
        rig.select_set(True);bpy.context.view_layer.objects.active = rig
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(dest/'review.blend'))
        bpy.ops.export_scene.gltf(filepath=str(dest/'adapted.glb'), export_format='GLB', use_selection=True,
            export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_frame_range=False,
            export_def_bones=True, export_extras=True)
        report['status'] = 'review_motion'
    except Exception as exc:
        report['status'] = 'needs_manual';report['error'] = str(exc)[:500]
    (dest/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CAT_ADAPTATION ' + json.dumps({k:v for k,v in report.items() if k not in ('footSamples','bones')}, ensure_ascii=False))
    return 0 if report['status'] == 'review_motion' else 2


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('input');p.add_argument('output')
    p.add_argument('--mode', choices=['auto','template-skin'], default='auto')
    p.add_argument('--forward', choices=['-Y','+Y','+X','-X'], default='-Y')
    p.add_argument('--bone-map')
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    sys.exit(main(args))
