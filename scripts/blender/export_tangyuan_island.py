"""Export the real Sakura island and check it against every matched pose.

The island is translated around the actor, so the approved camera and character
animation remain unchanged. Collision samples are a shot check, not physics QA.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser()
p.add_argument('--island',required=True);p.add_argument('--character',required=True)
p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=a.character)
scene=bpy.context.scene
body=bpy.data.objects['Tangyuan | reconstructed surface, original UV retained']
rig=next(o for o in scene.objects if o.type=='ARMATURE')
before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=a.island)
new=set(bpy.data.objects)-before;meshes=[o for o in new if o.type=='MESH']
points=[o.matrix_world@Vector(p) for o in meshes for p in o.bound_box]
lo=Vector([min(p[i] for p in points) for i in range(3)])
hi=Vector([max(p[i] for p in points) for i in range(3)])
scale=13/max(hi.x-lo.x,hi.y-lo.y);center=(lo+hi)*.5;center.z=lo.z
for obj in meshes:
    matrix=obj.matrix_world.copy();obj.parent=None
    for v in obj.data.vertices:v.co=(matrix@v.co-center)*scale
    obj.matrix_world.identity()

def tree(soil):
    vertices=[];faces=[]
    for obj in meshes:
        offset=len(vertices);vertices.extend(v.co.copy() for v in obj.data.vertices)
        faces.extend(tuple(offset+i for i in p.vertices) for p in obj.data.polygons
                     if obj.data.materials[p.material_index].name.startswith('Natural_moss_and_soil')==soil)
    return BVHTree.FromPolygons(vertices,faces)

ground=tree(True);obstacles=tree(False)
poses=[]
for frame in range(scene.frame_start,scene.frame_end+1):
    scene.frame_set(frame);bpy.context.view_layer.update()
    evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());data=evaluated.to_mesh()
    try:
        # Full surface grounding; sampled obstacle distance plus named joints.
        pts=[evaluated.matrix_world@v.co for v in data.vertices]
        lowest=min(pts,key=lambda v:v.z)
        poses.append((frame,lowest,pts[::20],scene.camera.matrix_world.translation.copy(),
                      [rig.matrix_world@rig.pose.bones[n].head for n in ('head','spine','FL_foot','FR_foot')]+pts[::200]))
    finally:evaluated.to_mesh_clear()

def check_patch(origin):
    checks=[]
    for frame,lowest,samples,eye,targets in poses:
        low=lowest+origin
        soil,_,_,_=ground.ray_cast(Vector((low.x,low.y,30)),Vector((0,0,-1)),60)
        if soil is None:return None
        clearance=low.z-soil.z
        for point in samples:
            if point.z>.16:continue
            v=point+origin
            soil,_,_,_=ground.ray_cast(Vector((v.x,v.y,30)),Vector((0,0,-1)),60)
            if soil is None:return None
            clearance=min(clearance,v.z-soil.z)
        collisions=sum(obstacles.find_nearest(v+origin,.012)[0] is not None for v in samples)
        occluded=0
        for target in targets:
            delta=target-eye
            occluded+=obstacles.ray_cast(eye+origin,delta.normalized(),max(0,delta.length-.005))[0] is not None
        checks.append({'frame':frame,'lowest_ground_clearance':clearance,
                       'near_obstacle_samples':collisions,'occluded_surface_rays':occluded})
        if clearance<-.01 or collisions or occluded:return None
    return checks

candidates=sorted([(x*.25,y*.25) for x in range(-14,-5) for y in range(-4,5)],
                  key=lambda p:(p[0]+2.5)**2+p[1]**2)
checks=None
for attempt,(x,y) in enumerate(candidates,1):
    hit,normal,_,_=ground.ray_cast(Vector((x,y,30)),Vector((0,0,-1)),60)
    if hit is None or normal.z<.8:continue
    origin=hit+Vector((0,0,.005));checks=check_patch(origin)
    if checks:break
if not checks:raise ValueError('No unobstructed placement supports all matched poses')
report={'source_asset_sha256':hashlib.sha256(Path(a.island).read_bytes()).hexdigest(),
        'island_width':13,'actor_origin_in_island':list(origin),'frames':checks,'candidate_attempts':attempt,
        'scope':'full mesh lowest point plus low surface samples; every twentieth vertex obstacle proximity; camera rays to four joints and every two hundredth surface vertex'}
(out/'placement-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if any(c['lowest_ground_clearance']<-.01 or c['near_obstacle_samples'] or c['occluded_surface_rays'] for c in checks):
    raise ValueError('Island shot placement failed; inspect placement-validation.json')

materials={}
for obj in meshes:
    for v in obj.data.vertices:v.co-=origin
    for m in obj.data.materials:
        if m.name in materials:continue
        bsdf=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        item={'color':list(bsdf.inputs['Base Color'].default_value)[:3],
              'roughness':float(bsdf.inputs['Roughness'].default_value),
              'metallic':float(bsdf.inputs['Metallic'].default_value),
              'two_sided':not m.use_backface_culling}
        for socket,key in [('Base Color','albedo'),('Normal','normal')]:
            links=bsdf.inputs[socket].links
            if not links:continue
            node=links[0].from_node
            if node.type=='NORMAL_MAP':
                item['normal_strength']=node.inputs['Strength'].default_value
                node=node.inputs['Color'].links[0].from_node
            if node.type=='TEX_IMAGE' and node.image:
                file=out/(m.name+'-'+key+'.png');node.image.save(filepath=str(file));item[key]=str(file)
        materials[m.name]=item
    obj.select_set(False)
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
bpy.ops.export_scene.fbx(filepath=str(out/'Sakura.fbx'),use_selection=True,object_types={'MESH'},
    axis_forward='-Y',axis_up='Z',bake_anim=False,mesh_smooth_type='FACE',path_mode='COPY',embed_textures=True)
(out/'materials.json').write_text(json.dumps(materials,indent=2),encoding='utf-8')
print('ISLAND_CHECKED_AND_EXPORTED',len(meshes),len(checks),list(origin),flush=True)
