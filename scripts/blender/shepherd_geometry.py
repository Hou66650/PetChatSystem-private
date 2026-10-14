"""Material-batched mesh authoring shared by the alpine stage and its companion."""
import bpy, math
from mathutils import Vector

def material(name, color, rough=.75, metal=0, glow=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=glow
    return m

class Batch:
    def __init__(self): self.data={}
    def mesh(self,mat,vs,fs,smooth=False):
        v,f,s=self.data.setdefault(mat,([],[],[]));offset=len(v);v.extend(vs)
        f.extend(tuple(i+offset for i in p) for p in fs);s.extend([smooth]*len(fs))
    def box(self,m,p,size,angle=0):
        c,s=math.cos(angle),math.sin(angle);vs=[]
        for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
            x*=size[0]/2;y*=size[1]/2;z*=size[2]/2;vs.append((p[0]+x*c-y*s,p[1]+x*s+y*c,p[2]+z))
        self.mesh(m,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    def ellipsoid(self,m,p,scale,n=16,rings=10):
        vs=[];fs=[]
        for j in range(rings+1):
            a=math.pi*j/rings
            for i in range(n):
                b=math.tau*i/n;vs.append((p[0]+scale[0]*math.sin(a)*math.cos(b),p[1]+scale[1]*math.sin(a)*math.sin(b),p[2]+scale[2]*math.cos(a)))
        for j in range(rings):
            for i in range(n):a=j*n+i;b=j*n+(i+1)%n;fs.append((a,a+n,b+n,b))
        self.mesh(m,vs,fs,True)
    def tube(self,m,points,radii,n=10):
        vs=[];fs=[]
        for j,point in enumerate(points):
            p=Vector(point);d=Vector(points[min(j+1,len(points)-1)])-Vector(points[max(0,j-1)])
            q=d.to_track_quat('Z','Y');r=radii[j] if isinstance(radii,(tuple,list)) else radii
            for i in range(n):vs.append(p+q@Vector((r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),0)))
        for j in range(len(points)-1):
            for i in range(n):a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
        fs.extend([tuple(reversed(range(n))),tuple((len(points)-1)*n+i for i in range(n))]);self.mesh(m,vs,fs,True)
    def objects(self,prefix):
        result=[]
        for m,(vs,fs,smooth) in self.data.items():
            mesh=bpy.data.meshes.new(prefix+'_'+m.name);mesh.from_pydata(vs,[],fs);mesh.update()
            o=bpy.data.objects.new(mesh.name,mesh);bpy.context.collection.objects.link(o);mesh.materials.append(m)
            for p,s in zip(mesh.polygons,smooth):p.use_smooth=s
            result.append(o)
        return result

def studio(folder, target, camera, scale, name, resolution=(1200,1000)):
    scene=bpy.context.scene
    bpy.ops.object.camera_add(location=camera);cam=bpy.context.object;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=scale;scene.camera=cam
    for pos,power,size in [((2,-5,8),1200,6),((-5,-1,4),850,5),((2,5,7),1500,5)]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    scene.world=bpy.data.worlds.new('Alpine studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.30,.39,.48,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=resolution;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.filepath=str(folder/(name+'.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/(name+'.blend')))
    bpy.ops.render.render(write_still=True)
