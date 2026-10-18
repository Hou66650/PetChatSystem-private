"""Derive cached runtime tiers from the detailed master through Blender MCP.

Keep full plant components instead of collapsing leaves into spikes. Keep
facility silhouettes and UVs; static meshes sharing a material become one draw.
"""
import bpy, bmesh, random, json, hashlib, gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/models/paw-commons-v3'
OUT.mkdir(exist_ok=True)
MASTER=ROOT/'art/paw-commons-v3/paw-commons-quality.blend'
reports={}

def thin_components(mesh,ratio):
    parents=list(range(len(mesh.vertices)))
    def find(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for edge in mesh.edges:
        a,b=(find(int(i)) for i in edge.vertices)
        if a!=b:parents[b]=a
    rng=random.Random(71);keep={}
    for i in range(len(parents)):
        r=find(i)
        if r not in keep:keep[r]=rng.random()<ratio
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not keep[find(v.index)]],context='VERTS')
    bm.to_mesh(mesh);bm.free();mesh.update()

for tier,foliage,flowers,grass,rock in [('preview',.035,.035,.08,.12),('play',.18,.14,.20,.30),('desktop',.36,.30,.38,.50)]:
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    bpy.context.preferences.edit.use_global_undo=False
    objects=[]
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.get('preview_only'):continue
        if tier=='preview' and o.name.startswith('Q04'):continue
        # Evaluate bevels before reducing and batching. Leave the master untouched.
        ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());copy=ev.to_mesh().copy();ev.to_mesh_clear()
        o.modifiers.clear();o.data=copy
        mat=o.data.materials[0].name
        if o.name.startswith('D01') and 'Leaf' in mat:thin_components(o.data,foliage)
        elif o.name.startswith('Q04'):
            # Preserve fern leaves. Floral spheres are simplified below, not randomly removed.
            if 'Leaf' in mat:thin_components(o.data,.22 if tier=='play' else .60)
        elif o.name.startswith('D03'):
            thin_components(o.data,grass if 'Leaf' in mat else flowers)
        elif o.name.startswith('D05') and 'Leaf' in mat:thin_components(o.data,flowers)
        elif o.name.startswith('D02') and 'Leaf' in mat:thin_components(o.data,.3 if tier=='preview' else .65)
        if not o.data.polygons:bpy.data.objects.remove(o,do_unlink=True);continue
        # Decimate rocks and curved props, never flattened leaves/grass blades.
        # Planar lawn/path boundaries must retain their holes and silhouettes.
        if 'Leaf' not in mat and not o.name.startswith(('D03','01 ','02 ')):
            mod=o.modifiers.new('Runtime reduction','DECIMATE');mod.ratio=rock if 'limestone' in mat.lower() else (.22 if tier=='preview' else .60 if tier=='play' else .86)
            if o.name.startswith('Q04'):mod.ratio=.20 if tier=='play' else .65
            ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());copy=ev.to_mesh().copy();ev.to_mesh_clear();o.modifiers.clear();o.data=copy
        objects.append(o)
    # bmesh data-layer merge retains UVs; one object per material.
    buckets={}
    for o in objects:
        # Evaluate and split each material before batching: canopy leaves have three colours.
        for index,mat in enumerate(o.data.materials):
            bm=bmesh.new();bm.from_mesh(o.data)
            bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index!=index],context='FACES')
            bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
            if not bm.faces:bm.free();continue
            mesh=bpy.data.meshes.new(o.name+' material');bm.to_mesh(mesh);bm.free()
            mesh.materials.clear();mesh.materials.append(mat)
            for f in mesh.polygons:f.material_index=0
            part=bpy.data.objects.new(o.name+' material',mesh);part.matrix_world=o.matrix_world.copy()
            bpy.context.collection.objects.link(part);buckets.setdefault(mat,[]).append(part)
        bpy.data.objects.remove(o,do_unlink=True)
    merged=[]
    for mat,parts in buckets.items():
        bm=bmesh.new()
        for o in parts:
            o.data.transform(o.matrix_world);bm.from_mesh(o.data)
        mesh=bpy.data.meshes.new('Paw '+tier+' '+mat.name);bm.to_mesh(mesh);bm.free();mesh.materials.clear();mesh.materials.append(mat)
        for p in mesh.polygons:p.material_index=0
        result=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(result);merged.append(result)
        for o in parts:bpy.data.objects.remove(o,do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in merged:o.select_set(True)
    args=dict(filepath=str(OUT/(tier+'.glb')),export_format='GLB',use_selection=True,export_animations=False,export_extras=False,export_apply=False)
    props=bpy.ops.export_scene.gltf.get_rna_type().properties
    if 'export_image_format' in props:args['export_image_format']='JPEG'
    if 'export_jpeg_quality' in props:args['export_jpeg_quality']=85
    bpy.ops.export_scene.gltf(**args)
    triangles=0
    for o in merged:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
    raw=(OUT/(tier+'.glb')).read_bytes();compressed=gzip.compress(raw,compresslevel=9,mtime=0)
    (OUT/(tier+'.glb.gz')).write_bytes(compressed)
    reports[tier]={'triangles':triangles,'meshes':len(merged),'bytes':len(raw),'gzipBytes':len(compressed),'sha256':hashlib.sha256(raw).hexdigest()}
    print('PAW_RUNTIME '+tier+' '+json.dumps(reports[tier]),flush=True)
(OUT/'runtime-report.json').write_text(json.dumps({'source':str(MASTER.relative_to(ROOT)),'transport':'Blender MCP','tiers':reports},indent=2),encoding='utf-8')
