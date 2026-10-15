"""Render the four shipped pets for the island selector; never load unselected GLBs in the browser."""
import bpy
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'static/images/pet-portraits'
OUT.mkdir(parents=True, exist_ok=True)
PETS = [('shiba', 'petchat-shiba-v4/qiuqiu'), ('husky', 'petchat-husky-v3/xueqiu'),
        ('cat', 'petchat-cat-v3/cat'), ('shepherd', 'petchat-shepherd-v2/shepherd')]
for name, asset in PETS:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT / 'static/models' / (asset + '.glb')))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for obj in bpy.context.scene.objects:
        if obj.animation_data:
            obj.animation_data.action = None
            for track in obj.animation_data.nla_tracks:
                track.mute = True
        if obj.type == 'ARMATURE':
            for bone in obj.pose.bones:
                bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in meshes:
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    height = hi.z - lo.z
    rig = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE' and 'head' in o.pose.bones), None)
    head = rig.matrix_world @ rig.pose.bones['head'].head if rig else (lo + hi) / 2
    target = head + Vector((0, -height * .06, height * .02))
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 384
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.world = bpy.data.worlds.new('Portrait daylight')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.74, .81, .86, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .45
    for direction, energy in [((2, -3, 4), 350), ((-3, -1, 2), 180), ((1, 3, 3), 320)]:
        bpy.ops.object.light_add(type='AREA', location=target + Vector(direction) * height)
        light = bpy.context.object
        light.data.energy = energy * height * height
        light.data.size = height * 3
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add(location=target + Vector((.9, -4, .35)) * height)
    camera = bpy.context.object
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = height * .50
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + '.png'))
    bpy.ops.render.render(write_still=True)
    print('PORTRAIT_DONE', name, flush=True)
