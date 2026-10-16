"""Conservative mesh checks; passing these is not semantic anatomy approval."""
import math
import bpy
from mathutils import Vector


def rear_branches(meshes):
    """Count substantial connected branches in three rear cuts, welding seams.

Only applicable after a standing cat is oriented towards -Y. Accessories and
curled tails can be ambiguous: reject the draft, never delete geometry here.
"""
    points = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices]
    lo = min(p.y for p in points); span = max(p.y for p in points)-lo
    tolerance = max(span*1e-5, 1e-8)
    result = []
    for fraction in (.78, .84, .9):
        parents = {}; counts = {}; vertices = {}; next_id = 0
        def root(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]; i = parents[i]
            return i
        for mesh in meshes:
            local = {}
            for vertex in mesh.data.vertices:
                p = mesh.matrix_world @ vertex.co
                if p.y <= lo+span*fraction: continue
                key = tuple(round(x/tolerance) for x in p)
                if key not in vertices:
                    vertices[key] = next_id; parents[next_id] = next_id; next_id += 1
                local[vertex.index] = vertices[key]
            for edge in mesh.data.edges:
                a, b = (local.get(i) for i in edge.vertices)
                if a is not None and b is not None: parents[root(a)] = root(b)
        for i in parents:
            r = root(i); counts[r] = counts.get(r, 0)+1
        substantial = [n for n in counts.values() if n >= max(20, next_id*.1)]
        result.append(len(substantial))
    return result


def binding_support(meshes, rig):
    points = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices]
    span = max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
    result = {}
    for leg in ('FL','FR','HL','HR'):
        name = leg+'_foot'; samples = []
        for mesh in meshes:
            group = mesh.vertex_groups.get(name)
            if group:
                samples.extend(mesh.matrix_world @ v.co for v in mesh.data.vertices
                               if any(g.group == group.index and g.weight >= .25 for g in v.groups))
        head = rig.matrix_world @ rig.data.bones[name].head_local
        distance = (sum(samples, Vector())/len(samples)-head).length/span if samples else None
        result[leg] = {'vertices': len(samples), 'centroidDistanceRatio': distance}
        if len(samples) < 10 or distance is None or distance > .25:
            raise ValueError(name+' 的蒙皮覆盖不足或偏离脚掌，请定位关节并修正权重')
    return result


def mesh_snapshot(meshes):
    result = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for mesh in meshes:
        obj = mesh.evaluated_get(depsgraph); data = obj.to_mesh()
        try:
            points = [obj.matrix_world @ v.co for v in data.vertices]
            if not all(math.isfinite(x) for p in points for x in p):
                raise ValueError('变形后的网格包含无效坐标')
            result.append(points)
        finally:
            obj.to_mesh_clear()
    return result


def deformation_ratio(rest, posed, meshes):
    maximum = 1.0
    points = [p for part in rest for p in part]
    span = max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
    torn = False
    for before, after, mesh in zip(rest, posed, meshes):
        if len(before) != len(after): raise ValueError('动作改变了网格拓扑，需人工检查')
        # Check every edge, including small local tears missed by bone samples.
        for edge in mesh.data.edges:
            a,b = edge.vertices; length = (before[a]-before[b]).length
            if length > 1e-5:
                posed_length = (after[a]-after[b]).length
                maximum = max(maximum, posed_length/length)
                torn |= posed_length/length > 8 and posed_length-length > span*.05
    if torn:
        raise ValueError('动作造成网格边长超过静止长度 8 倍，请修正骨骼与权重')
    return maximum
