"""Walk-in botanical conservatory. Coordinates shared with mistwood-layout.js."""
import math, random
from mathutils import Vector
from shepherd_geometry import Batch, material

def build(stone, iron, bronze, glass, wood):
    b=Batch(); objects=[]
    cream=material('Garden_ivory_ceramic',(.68,.65,.50),.3)
    earth=material('Garden_potting_soil',(.09,.065,.035),.98)
    leaf=material('Garden_jade_leaves',(.12,.29,.10),.63)
    young=material('Garden_lime_growth',(.31,.47,.12),.65)
    stem=material('Garden_leaf_veins',(.27,.36,.12),.7)
    flower=material('Garden_catnip_lilac',(.62,.46,.69),.65)
    linen=material('Garden_woven_linen',(.56,.46,.30),.92)
    glow=material('Garden_lamp',(.98,.64,.27),.3,0,1)
    for m in [leaf,young,flower,linen]:m.use_backface_culling=False
    def wall(x,y,w,d):
        b.box(stone,(x,y,.18),(w,d,.30))
        b.box(glass,(x,y,1.50),(w,d,2.25))
        b.box(iron,(x,y,.35),(w+.02,d+.02,.035))
        b.box(iron,(x,y,2.65),(w+.02,d+.02,.045))
    # Wide, step-free front portal; side and rear walls retain old footprint.
    for x in [.9,5.1]:wall(x,3.4,.12,3.3)
    wall(3,5.05,4.2,.12)
    for x in [1.4,4.6]:wall(x,1.75,1.0,.12)
    b.box(stone,(3,3.4,.015),(4.2,3.3,.04))
    for x in [.9,1.9,4.1,5.1]:b.tube(iron,[(x,1.75,.03),(x,1.75,2.65)],.027,8)
    for x in [.9,5.1]:
        for y in [2.55,3.4,4.2,5.05]:b.tube(iron,[(x,y,.3),(x,y,2.65)],.024,8)
    for y in [1.75,5.05]:
        b.mesh(glass,[(.9,y,2.65),(5.1,y,2.65),(3,y,3.95)],[(0,1,2)])
        b.tube(bronze,[(.9,y,2.65),(3,y,3.95),(5.1,y,2.65)],.035,10)
    for j in range(9):
        y=1.75+j*3.3/8
        b.tube(iron,[(.9,y,2.65),(3,y,3.95),(5.1,y,2.65)],.022,8)
        if j<8:
            for x in [.9,5.1]:b.mesh(glass,[(x,y,2.65),(3,y,3.95),(3,y+3.3/8,3.95),(x,y+3.3/8,2.65)],[(0,1,2,3)])
    b.tube(bronze,[(3,1.65,3.95),(3,5.15,3.95)],.04,10)
    # Glass privacy partition with a generously sized, rounded cat passage.
    for x in [1.4,4.6]:wall(x,3.5,1,.07)
    for x in [1.9,4.1]:b.tube(bronze,[(x,3.5,.035),(x,3.5,1.0)],.025,8)
    arch=[(3+1.1*math.cos(i*math.pi/32),3.5,1+1.0*math.sin(i*math.pi/32)) for i in range(33)]
    b.tube(bronze,arch,.025,8)
    for i in range(32):
        p,q=arch[i:i+2];b.mesh(glass,[p,q,(q[0],3.5,2.65),(p[0],3.5,2.65)],[(0,1,2,3)])
    # Low suspended hammock: raised retreat without rebuilding a second floor.
    vs=[];fs=[]
    for j in range(17):
        for i in range(25):
            u=i/24*2-1;v=j/16*2-1
            vs.append((3+u*.86,4.22+v*.51,.51+.16*u*u+.06*v*v))
    for j in range(16):
        for i in range(24):a=j*25+i;fs.append((a,a+1,a+26,a+25))
    b.mesh(linen,vs,fs,True)
    for x in [2.14,3.86]:
        for y in [3.71,4.73]:b.tube(linen,[(x,y,.73),(x,y,2.6)],.012,7)
    for x in [2.14,3.86]:b.tube(wood,[(x,3.68,.72),(x,4.76,.72)],.035,10)
    for j in range(20):
        y0=3.05+j*.70/20;y1=y0+.70/20
        z0=.035+.49*j/20;z1=.035+.49*(j+1)/20
        b.mesh(wood,[(1.9,y0,z0),(4.1,y0,z0),(4.1,y1,z1),(1.9,y1,z1)],[(0,1,2,3)])
        b.tube(linen,[(1.92,y1,z1+.004),(4.08,y1,z1+.004)],.005,5)
    # Woven stitch detail remains geometry, no large texture allocation.
    for i in range(35):
        x=2.18+i*1.64/34;u=(x-3)/.86
        b.tube(linen,[(x,3.73,.51+.16*u*u+.055),(x,4.71,.51+.16*u*u+.055)],.003,4)
    for x in [2,4]:
        b.tube(bronze,[(x,3.1,3.25),(x,3.1,2.35)],.012,8)
        b.ellipsoid(glow,(x,3.1,2.27),(.13,.13,.17),16,10)
        b.tube(bronze,[(x,3.1,2.42),(x,3.1,2.47)],[.16,.07],16)
    def pot(x,y,r=.25):
        b.tube(cream,[(x,y,.035),(x,y,.28),(x,y,.31)],[r*.72,r,r*1.04],24)
        b.tube(earth,[(x,y,.30),(x,y,.315)],[r*.92,r*.92],24)
        for a in range(24):
            t=a*math.tau/24;b.tube(bronze,[(x+math.cos(t)*r*.8,y+math.sin(t)*r*.8,.09),(x+math.cos(t)*r,y+math.sin(t)*r,.27)],.0025,4)
    def blade(batch,p,a,length,width,mat,serrated=False,detail=True):
        p=Vector(p);axis=Vector((math.cos(a),math.sin(a),.45));side=Vector((-math.sin(a),math.cos(a),0));verts=[]
        segments=12 if detail else 4
        for j in range(segments+1):
            t=j/segments;center=p+axis*length*t+Vector((0,0,-length*.35*t*t))
            w=width*math.sin(math.pi*t)**.7*(.82 if serrated and j%2 else 1)
            verts.extend([center-side*w,center+Vector((0,0,width*.15*math.sin(math.pi*t))),center+side*w])
        batch.mesh(mat,verts,[(j*3+k,j*3+k+3,j*3+k+4,j*3+k+1) for j in range(segments) for k in range(2)],True)
        if detail:batch.tube(stem,[verts[j*3+1]+Vector((0,0,.001)) for j in range(0,13,3)],.0018,4)
        if serrated:
            for j in [3,5,7,9]:
                for sideIndex in [0,2]:batch.tube(stem,[verts[(j-1)*3+1],verts[j*3+sideIndex]],.001,3)
    # Three real growth layers per plant, with rooted curved blades and veined leaves.
    for kind,x,y in [('grass',1.34,2.55),('catnip',4.66,2.55)]:
        pot(x,y,.28)
        for level in range(3):
            bb=Batch();random.seed(815+level+(100 if kind=='grass' else 0))
            for k in range(45 if kind=='grass' else 9):
                a=random.random()*math.tau;r=random.random()*.21;px=x+r*math.cos(a);py=y+r*math.sin(a)
                if kind=='grass':blade(bb,(px,py,.32),a,random.uniform(.25,.52),random.uniform(.009,.02),leaf if k%3 else young)
                else:
                    h=random.uniform(.3,.6);bb.tube(stem,[(px,py,.31),(px+.03,py,.31+h)],.005,6)
                    for j in range(4):
                        for side in [-1,1]:blade(bb,(px+.03*j/4,py,.38+j*h/5),a+side*math.pi/2,.16-j*.018,.045-j*.004,leaf if j<3 else young,True)
                    for j in range(4):
                        for q in range(5):
                            aa=q*math.tau/5;bb.ellipsoid(flower,(px+.03+.023*math.cos(aa),py+.023*math.sin(aa),.31+h+j*.016),(.012,.012,.014),6,4)
            for o in bb.objects('Garden_'+kind+'_'+str(level)):
                o['garden_plant']=kind;o['growth_layer']=level;objects.append(o)
    # Permanent baseline planting: dense ferns on shelves, away from cat routes.
    for x in [1.28,4.72]:
        for y in [3.15,4.55]:
            pot(x,y,.21)
            for k in range(9):
                a=k*math.tau/9
                for j in range(7):
                    t=j/7;p=(x+math.cos(a)*t*.36,y+math.sin(a)*t*.36,.34+.22*math.sin(t*math.pi))
                    for side in [-1,1]:blade(b,p,a+side*.9,.13*(1-t*.6),.023,leaf,detail=False)
    # Optional lace side curtains with modeled scallops and openwork threads.
    bb=Batch()
    for x in [1.02,4.98]:
        for j in range(34):
            y=3.65+j*.035
            bb.tube(linen,[(x+.035*math.sin(j),y,.72+i*.045) for i in range(42)],.003,4)
        for i in range(40):
            z=.72+i*.045;bb.tube(linen,[(x+.035*math.sin(j),3.65+j*.035,z+.012*math.sin(j*2)) for j in range(34)],.003,4)
    for o in bb.objects('Garden_lace'):o['garden_cosmetic']='lace';objects.append(o)
    bb=Batch();bb.ellipsoid(linen,(3,4.22,.56),(.72,.44,.075),32,12)
    for o in bb.objects('Garden_plush'):o['garden_cosmetic']='plush';objects.append(o)
    bb=Batch();night=material('Garden_night_blossoms',(.35,.75,.8),.4,0,1.3)
    for x in [1.28,4.72]:
        for k in range(12):
            a=k*2.4;r=.18*math.sqrt(k/12);px=x+r*math.cos(a);py=4.55+r*math.sin(a);h=.65+.06*math.sin(k)
            bb.tube(stem,[(px,py,.34),(px,py,h)],.003,5)
            for q in range(5):blade(bb,(px,py,h),q*math.tau/5,.065,.022,night)
    for o in bb.objects('Garden_night'):o['garden_cosmetic']='night';objects.append(o)
    objects+=b.objects('Garden_structure')
    return objects
