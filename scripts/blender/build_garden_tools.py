"""Blender-authored interactive garden tools, metre scale, reusable GLB + source."""
import bpy, math, random, sys
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent))
from shepherd_geometry import Batch,material,studio
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/models/petchat-garden-tools-v1';ART=ROOT/'art/garden-tools-v1'
OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
random.seed(216)
enamel=material('Sage vitreous enamel',(.115,.23,.19),.28,.48)
brass=material('Brushed warm brass',(.50,.34,.13),.34,.78)
steel=material('Rolled steel edges',(.29,.34,.31),.26,.82)
wood=material('Oiled ash grip',(.42,.24,.10),.65)
dark=material('Interior shadow',(.035,.048,.037),.88)
cream=material('Ivory ceramic fertilizer tin',(.72,.68,.52),.37,.12)
earth=material('Slow release granules',(.28,.17,.07),.92)

def lathe(batch,mat,profile,n=72):
    vs=[(r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n),z) for r,z in profile for i in range(n)]
    faces=[]
    for j in range(len(profile)-1):
        for i in range(n):a=j*n+i;b=j*n+(i+1)%n;faces.append((a,b,b+n,a+n))
    batch.mesh(mat,vs,faces,True)

def ring(batch,mat,r,z,thick=.006):
    batch.tube(mat,[(r*math.cos(i*math.tau/72),r*math.sin(i*math.tau/72),z) for i in range(73)],thick,10)

def export(obs,name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_animations=False,export_extras=True)

b=Batch()
lathe(b,enamel,[(.001,.025),(.185,.025),(.216,.06),(.225,.12),(.21,.39),(.172,.445),(.16,.455),(.152,.445),(.162,.433),(.20,.38),(.215,.12),(.205,.066),(.001,.045)])
for z,r in [(.047,.209),(.075,.217),(.395,.209),(.452,.161)]:ring(b,steel,r,z)
for i in range(24):
    a=i*math.tau/24;b.tube(enamel,[(r*math.cos(a),r*math.sin(a),z) for r,z in [(.221,.12),(.216,.24),(.212,.36)]],.0018,6)
# True curved rear handle, top carry arch and wooden sleeve.
b.tube(steel,[(-.18-.18*math.sin(t*math.pi),0,.09+t*.29) for t in [i/30 for i in range(31)]],.016,14)
b.tube(steel,[(0,.22*math.cos(t),.44+.19*math.sin(t)) for t in [i*math.pi/36 for i in range(37)]],.014,14)
b.tube(wood,[(0,.22*math.cos(t),.44+.19*math.sin(t)) for t in [math.pi*.34+i*math.pi*.32/20 for i in range(21)]],.023,18)
for side in [-1,1]:
    b.ellipsoid(brass,(0,side*.205,.405),(.032,.014,.045),20,12)
    b.ellipsoid(steel,(0,side*.218,.405),(.008,.004,.008),12,8)
# Rising spout with braced joint, flared rose and individually recessed jet apertures.
b.tube(enamel,[(.18,0,.14),(.28,0,.20),(.42,0,.36),(.53,0,.45)],[.068,.053,.032,.024],24)
b.tube(steel,[(.17,0,.36),(.33,0,.31)],.008,12)
b.tube(brass,[(.50,0,.425),(.56,0,.48)],[.027,.095],40)
axis=Vector((1,0,1)).normalized();u=Vector((0,1,0));v=axis.cross(u);center=Vector((.563,0,.483))
for j in range(-4,5):
    for i in range(-4,5):
        if i*i+j*j>18:continue
        p=center+u*(i*.018)+v*(j*.018)
        b.tube(dark,[p,p+axis*.0015],.0038,12)
        b.tube(brass,[p+u*(.0045*math.cos(t))+v*(.0045*math.sin(t)) for t in [k*math.tau/12 for k in range(13)]],.001,6)
b.tube(brass,[center+u*(.094*math.cos(t))+v*(.094*math.sin(t)) for t in [k*math.tau/72 for k in range(73)]],.006,12)
can=b.objects('Watering_can')
for o in can:o['garden_tool']='water'
export(can,'watering-can')

b=Batch();lathe(b,cream,[(.001,.02),(.13,.02),(.147,.045),(.147,.28),(.128,.305),(.126,.316),(.118,.316),(.118,.304),(.137,.275),(.137,.05),(.001,.035)])
for z in [.04,.07,.26,.315]:ring(b,brass,.145 if z<.3 else .125,z,.004)
for i in range(28):
    a=i*math.tau/28;b.tube(cream,[(.148*math.cos(a),.148*math.sin(a),z) for z in [.10,.22]],.002,8)
for i in range(140):
    a=random.random()*math.tau;r=math.sqrt(random.random())*.115
    b.ellipsoid(earth,(r*math.cos(a),r*math.sin(a),.265+random.random()*.018),(.006,.008,.005),8,5)
# Brass spoon bowl and grained ash handle resting diagonally in the tin.
b.ellipsoid(brass,(.10,0,.30),(.064,.04,.012),24,12)
b.tube(brass,[(.12,0,.31),(.24,0,.39)],.007,12)
b.tube(wood,[(.23,0,.385),(.38,0,.49)],[.017,.012],18)
tin=b.objects('Fertilizer_tin')
for o in tin:o['garden_tool']='fertilize'
export(tin,'fertilizer-tin')
for o in tin:o.location=(.9,0,0)
studio(ART,(.38,0,.26),(2.2,-3.5,2.1),1.8,'garden-tools',(1280,900))
