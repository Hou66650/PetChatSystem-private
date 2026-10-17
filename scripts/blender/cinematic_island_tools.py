"""Reusable offline scene authoring; importing this module does not build a scene."""
import math
import random
import bpy
import numpy as np
from mathutils import Vector
from shepherd_geometry import Batch, material


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def set_input(m, name, value):
    p=principled(m)
    for link in list(p.inputs[name].links):m.node_tree.links.remove(link)
    p.inputs[name].default_value=value


def collection(name):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c);return c


def move(obj,c):
    for old in list(obj.users_collection):old.objects.unlink(obj)
    c.objects.link(obj)


def finish(batch,name,c,bevel=0):
    obs=batch.objects(name)
    for o in obs:
        move(o,c);o['role']='offline_visual_not_collision'
        if bevel:
            b=o.modifiers.new('Crafted edge radius','BEVEL');b.width=bevel;b.segments=3;b.limit_method='ANGLE'
        uv=o.data.uv_layers.new(name='MetricUV')
        for face in o.data.polygons:
            axis=max(range(3),key=lambda i:abs(face.normal[i]));axes=[i for i in range(3) if i!=axis]
            for li in face.loop_indices:
                v=o.data.vertices[o.data.loops[li].vertex_index].co
                uv.data[li].uv=(v[axes[0]]*.8,v[axes[1]]*.8)
    return obs


def tile(name,color,kind='stone',seed=17):
    """Exportable albedo and tangent normals, not baked scene lighting."""
    m=material(name,color,.82);p=principled(m);nt=m.node_tree
    n=512;y,x=np.mgrid[0:n,0:n]/n;rng=np.random.default_rng(seed)
    field=np.zeros((n,n))
    for f,amp in [(2,.24),(7,.13),(19,.09),(63,.04),(151,.02)]:
        for i in range(3):
            a=rng.uniform(0,math.tau)
            field+=amp/3*np.sin(math.tau*f*(x*np.cos(a)+y*np.sin(a))+rng.uniform(0,7))
    if kind=='stone':field-=.10*np.exp(-(np.sin(y*37+field*7)/.13)**2)
    if kind=='wood':field+=.065*np.sin(x*350+field*21)+.03*np.sin(x*970)
    if kind=='snow':field+=rng.normal(0,.025,(n,n))
    rgb=np.clip(np.array(color)[None,None,:]*(1+field[:,:,None]),.004,.95)
    dy,dx=np.gradient(field);normal=np.dstack((-dx*7,-dy*7,np.ones_like(x)));normal/=np.linalg.norm(normal,axis=2)[:,:,None]
    for suffix,values in [('albedo',rgb),('normal',normal*.5+.5)]:
        im=bpy.data.images.new(name+'_'+suffix,width=n,height=n)
        if suffix=='normal':im.colorspace_settings.name='Non-Color'
        im.pixels.foreach_set(np.dstack((values,np.ones_like(x))).astype(np.float32).ravel());im.pack()
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=im
        if suffix=='albedo':nt.links.new(tex.outputs['Color'],p.inputs['Base Color'])
        else:
            nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.38
            nt.links.new(tex.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],p.inputs['Normal'])
    return m


def micro(m,scale,distance):
    nt=m.node_tree;p=principled(m);co=nt.nodes.new('ShaderNodeTexCoord');noise=nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=4
    nt.links.new(co.outputs['Object'],noise.inputs['Vector'])
    bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.35;bump.inputs['Distance'].default_value=distance
    nt.links.new(noise.outputs['Fac'],bump.inputs['Height'])
    if p.inputs['Normal'].is_linked:nt.links.new(p.inputs['Normal'].links[0].from_socket,bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])


def leaf(batch,m,p,a,length,width,rise=.3):
    p=Vector(p);axis=Vector((math.cos(a),math.sin(a),0));side=Vector((-math.sin(a),math.cos(a),0));vs=[]
    for j in range(7):
        t=j/6;mid=p+axis*(length*t)+Vector((0,0,length*(rise*t-.23*t*t)))
        for q in [-1,0,1]:vs.append(mid+side*q*width*math.sin(math.pi*t)**.7+Vector((0,0,.004*math.sin(t*math.pi) if q==0 else 0)))
    batch.mesh(m,vs,[(j*3+q,j*3+q+3,j*3+q+4,j*3+q+1) for j in range(6) for q in range(2)],True)


def lathe(b,m,p,profile,n=48):
    vs=[(p[0]+r*math.cos(i*math.tau/n),p[1]+r*math.sin(i*math.tau/n),p[2]+h) for r,h in profile for i in range(n)]
    b.mesh(m,vs,[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(profile)-1) for i in range(n)],True)


def snow_lobe(b,m,p,sc,seed,angle=0):
    vs=[];fs=[];n=16;rings=9
    for j in range(rings+1):
        a=math.pi*j/rings
        for k in range(n):
            t=k*math.tau/n;f=1+.09*math.sin(t*3+a*4+seed)+.035*math.sin(t*7+seed)
            x=sc[0]*math.sin(a)*math.cos(t)*f;y=sc[1]*math.sin(a)*math.sin(t)*f
            vs.append((p[0]+x*math.cos(angle)-y*math.sin(angle),p[1]+x*math.sin(angle)+y*math.cos(angle),p[2]+sc[2]*math.cos(a)*f))
    for j in range(rings):
        for k in range(n):a=j*n+k;c=j*n+(k+1)%n;fs.append((a,c,c+n,a+n))
    b.mesh(m,vs,fs,True)


def camera(scene,location,target,scale):
    o=scene.camera;o.location=location;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o.data.type='ORTHO';o.data.ortho_scale=scale


def lighting(theme,out,preview):
    scene=bpy.context.scene;c=collection('90 Presentation only')
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    world=bpy.data.worlds.new('Open sky');world.use_nodes=True;scene.world=world
    nt=world.node_tree;sky=nt.nodes.new('ShaderNodeTexSky')
    types=sky.bl_rna.properties['sky_type'].enum_items.keys();sky.sky_type='MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in types else 'NISHITA'
    sky.sun_elevation=math.radians(18 if theme=='snow' else 28);sky.sun_rotation=math.radians(135);sky.sun_size=math.radians(3)
    sky.altitude=1;sky.air_density=.9;setattr(sky,'aerosol_density' if hasattr(sky,'aerosol_density') else 'dust_density',.65)
    nt.links.new(sky.outputs['Color'],nt.nodes['Background'].inputs['Color']);nt.nodes['Background'].inputs['Strength'].default_value=.10
    for pos,power,size,color in [((-6,-5,12),1600,9,(1,.87,.72)),((7,-9,7),1000,10,(.65,.80,1))]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.data.color=color;o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler();move(o,c)
    # Cloud layer stays below the island; no volumetric mesh enters exports.
    cloud=bpy.data.materials.new('Cloud bank');cloud.use_nodes=True;n=cloud.node_tree.nodes;n.clear()
    output=n.new('ShaderNodeOutputMaterial');v=n.new('ShaderNodeVolumePrincipled');v.inputs['Color'].default_value=(.9,.96,1,1);v.inputs['Anisotropy'].default_value=.15
    co=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.18;noise.inputs['Detail'].default_value=3
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.4;ramp.color_ramp.elements[1].position=.7;ramp.color_ramp.elements[1].color=(.16,.16,.16,1)
    links=cloud.node_tree.links;links.new(co.outputs['Object'],noise.inputs['Vector']);links.new(noise.outputs['Fac'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],v.inputs['Density'])
    glow=n.new('ShaderNodeMath');glow.operation='MULTIPLY';glow.inputs[1].default_value=.22;links.new(ramp.outputs['Color'],glow.inputs[0]);links.new(glow.outputs[0],v.inputs['Emission Strength']);v.inputs['Emission Color'].default_value=(.65,.8,1,1);links.new(v.outputs['Volume'],output.inputs['Volume'])
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-10));cloudobj=bpy.context.object;cloudobj.name='Cloud sea';cloudobj.scale=(140,140,12);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);cloudobj.data.materials.append(cloud);move(cloudobj,c)
    bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-6.6));plane=bpy.context.object;plane.name='Plan paper';plane.data.materials.append(material('Plan sage',(.38,.43,.42),1));plane.hide_render=True;move(plane,c)
    bpy.ops.object.camera_add();scene.camera=bpy.context.object;move(scene.camera,c)
    scene.render.engine='CYCLES';prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    devices=[]
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
        if d.use:devices.append(d.name)
    if not devices:raise RuntimeError('OptiX GPU required; no CPU fallback')
    scene.cycles.device='GPU';scene.cycles.samples=24 if preview else 96;scene.cycles.use_denoising=True;scene.cycles.max_bounces=10;scene.cycles.transmission_bounces=8;scene.cycles.volume_bounces=1
    scene.render.resolution_x=1200 if preview else 2400;scene.render.resolution_y=1000 if preview else 2000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=-.65 if theme=='snow' else -.45
    return scene,cloudobj,plane,devices
