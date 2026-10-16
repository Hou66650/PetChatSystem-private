"""Concept-matched landscape detail, authored as real Blender geometry in metres.

The lawn remains playable and the saved placement/navigation footprint is unchanged.
Tall ground details live on outward-facing cliffs, not inside the planting area.
"""
import math,random,json,re
from mathutils import Vector
from shepherd_geometry import material

def enrich(b,layout,old,stone,cliff,bark,lawn,added,path_distance,inside,root):
    rng=random.Random(16842);tau=math.tau
    greens=[material('Canopy_leaf_'+str(i),c,.82) for i,c in enumerate([
        (.11,.19,.038),(.17,.25,.055),(.24,.32,.075),(.30,.36,.105),(.37,.40,.14)])]
    blades=[material('Meadow_blades_'+str(i),c,.92) for i,c in enumerate([
        (.17,.22,.058),(.24,.29,.075),(.32,.35,.12),(.38,.39,.16)])]
    trailing=[material('Cliff_ivy_'+str(i),c,.9) for i,c in enumerate([(.12,.20,.035),(.24,.29,.06),(.35,.36,.10)])]
    cream=material('Rim_flower_ivory',(.86,.82,.55),.75)
    gold=material('Rim_flower_gold',(.77,.54,.15),.8)
    stem=material('Rim_stem',(.13,.20,.045),.94)
    earth=material('Meadow_walk_earth',(.28,.255,.17),.96)
    moss=material('Cliff_moss',(.21,.25,.075),.97)
    for m in greens+blades+trailing+[cream,gold]:m.use_backface_culling=False
    stats=dict(leaves=0,grassBlades=0,rockOutcrops=0,vineStrands=0,flowers=0)

    def leaf(p,angle,length,width,mat,drop=0):
        p=Vector(p);axis=Vector((math.cos(angle),math.sin(angle),drop));side=Vector((-math.sin(angle)*width,math.cos(angle)*width,0))
        b.mesh(mat,[p,p+axis*length*.48+side,p+axis*length+Vector((0,0,-length*.12)),p+axis*length*.48-side,p+axis*length*.48+Vector((0,0,length*.13))],[(0,1,4),(1,2,4),(2,3,4),(3,0,4)],True)
        stats['leaves']+=1

    def rock(p,scale,seed,mat=stone):
        # Fractured blocks, with shared vertices at every ring; no separate strips
        # that leave the sawtooth seams visible in the first island version.
        phase=seed*2.399;vs=[];fs=[];n=11;rings=7
        for j in range(rings+1):
            a=math.pi*j/rings
            for k in range(n):
                u=tau*k/n;rough=1+.13*math.sin(u*3+a*4+phase)+.065*math.cos(u*7-a*5+phase)
                vs.append((p[0]+scale[0]*math.sin(a)*math.cos(u)*rough,p[1]+scale[1]*math.sin(a)*math.sin(u)*rough,p[2]+scale[2]*math.cos(a)*(1+.07*math.sin(u*4+phase))))
        for j in range(rings):
            for k in range(n):v=j*n+k;w=j*n+(k+1)%n;fs.append((v,w,w+n,v+n))
        b.mesh(mat,vs,fs,False);stats['rockOutcrops']+=1

    # A narrow earthen trail with individually weathered, irregular inset stones.
    # Keep the exact existing centreline: user planting corridors stay valid.
    for a,c in zip(layout['loop'],layout['loop'][1:]):
        dx,dz=c[0]-a[0],c[1]-a[1];length=math.hypot(dx,dz);nx,nz=-dz/length,dx/length
        if added((a[0]+c[0])/2,(a[1]+c[1])/2):
            w=.31+rng.random()*.045
            b.mesh(earth,[(a[0]+nx*w,-a[1]-nz*w,.027),(a[0]-nx*w,-a[1]+nz*w,.027),(c[0]-nx*w,-c[1]+nz*w,.027),(c[0]+nx*w,-c[1]-nz*w,.027)],[(0,1,2,3)])
        for j in range(max(1,math.ceil(length/.33))):
            t=(j+.5)/max(1,math.ceil(length/.33));px=a[0]+dx*t;pz=a[1]+dz*t
            if not added(px,pz):continue
            for side in [-1,1]:
                if rng.random()<.17:continue
                off=side*rng.uniform(.09,.15);xx,yy=px+nx*off,-pz-nz*off
                vs=[(xx,yy,.036)];n=7;rx=rng.uniform(.12,.18);ry=rng.uniform(.09,.14)
                for k in range(n):
                    ang=tau*k/n;f=rng.uniform(.82,1.13);vs.append((xx+rx*f*math.cos(ang),yy+ry*f*math.sin(ang),rng.uniform(.031,.036)))
                b.mesh(stone,vs,[(0,k+1,(k+1)%n+1) for k in range(n)])

    # Individually bent short blades. Height stays below the existing paw-clearance
    # envelope; colour is patchy and seed placement is aperiodic, not a lawn grid.
    for k in range(270000):
        px=rng.uniform(1,19);pz=rng.uniform(-2.8,13.5)
        if not added(px,pz) or path_distance(px,pz)<.37:continue
        angle=rng.random()*tau;h=rng.uniform(.025,.068);w=rng.uniform(.003,.007);bend=rng.uniform(.008,.025)
        p=Vector((px,-pz,.026));side=Vector((math.cos(angle)*w,math.sin(angle)*w,0));tip=p+Vector((math.sin(angle)*bend,-math.cos(angle)*bend,h))
        patch=math.sin(px*.73+math.sin(pz*.47)*2)+math.cos(pz*1.19+px*.21)
        shade=max(0,min(3,int(1.5+patch*.72+rng.uniform(-.5,.5))))
        b.mesh(blades[shade],[p-side,p+side,(p+tip)/2+side*.45,tip,(p+tip)/2-side*.45],[(0,1,2,4),(4,2,3)],True)
        stats['grassBlades']+=1

    def crown(x,z,h,index,new=True,birch=True):
        lean=Vector((.15*math.sin(index),.14*math.cos(index),0));base=Vector((x,-z,0))
        if new:
            b.tube(bark,[base+Vector((0,0,h*j/12))+lean*(j/12)**2 for j in range(13)],[.16*(1-j/14) for j in range(13)],14)
        # Rounded, overlapping crown lobes; branch hierarchy remains visible at
        # the lower crown rather than becoming a solid green sphere.
        for j in range(23 if new else 26):
            u=rng.uniform(.46,.94);angle=j*2.399+index+rng.uniform(-.25,.25)
            reach=(1.45 if new else 1.65)*math.sqrt(max(.12,1-((u-.70)/.29)**2))
            centre=base+Vector((math.cos(angle)*reach,math.sin(angle)*reach,h*u))
            centre+=Vector((rng.uniform(-.18,.18),rng.uniform(-.18,.18),rng.uniform(-.15,.25)))
            branch=base+Vector((0,0,h*max(.3,u-.12)))
            b.tube(bark,[branch,branch.lerp(centre,.6)+Vector((0,0,-.12)),centre],[.04,.023,.0035],9)
            rx,ry,rz=(.68,.62,.46) if new else ((.86,.75,.58) if birch else (.74,.65,.48))
            for q in range(260 if new else 280):
                az=rng.random()*tau;vertical=rng.uniform(-1,1);r=rng.random()**.30
                p=centre+Vector((rx*r*math.sqrt(1-vertical*vertical)*math.cos(az),ry*r*math.sqrt(1-vertical*vertical)*math.sin(az),rz*r*vertical))
                size=rng.uniform(.13,.21) if new else rng.uniform(.11,.18)
                leaf(p,rng.random()*tau,size,size*rng.uniform(.28,.40),greens[(q+j+index)%5],rng.uniform(-.4,.45))
    for i,t in enumerate(layout['trees']):crown(t['x'],t['z'],t['h'],i)
    native=json.loads(re.search(r'const layout = (\{[\s\S]+?\});',(root/'static/js/den/mistwood-layout.js').read_text()).group(1))
    for i,t in enumerate(native['trees']):crown(t['x'],t['z'],t['h'],i+10,False,t.get('birch',False))

    # Dress the complete visible coastline, respecting the old river outlets.
    # Everything tall is outside the playable/plantable polygon, or below it.
    farm=json.loads((root/'static/data/farm-layout.json').read_text())
    domains=[old,farm['terrace']]+layout['domains'];rim=[]
    for di,d in enumerate(domains):
        count=math.ceil(tau*max(d['rx'],d['rz'])/.42)
        for k in range(count):
            angle=tau*k/count;xx=d['x']+d['rx']*math.cos(angle);zz=d['z']+d['rz']*math.sin(angle)
            if any(inside(xx,zz,o,.08) for o in domains if o is not d):continue
            if abs(zz-1.8)<.85 and abs(abs(xx)-7.7)<1.1:continue
            # Do not decorate the existing western farm connector as an exposed rim.
            e=farm['entry']
            if abs(xx-e['x'])<e['w']/2 and abs(zz-e['z'])<e['d']/2:continue
            normal=Vector((math.cos(angle)/d['rx'],-math.sin(angle)/d['rz'],0)).normalized()
            top=Vector((xx,-zz,.025));rim.append((top,normal))
            for row in range(5):
                depth=.42+row*.75+rng.uniform(-.13,.13);f=1-depth*.105
                stagger=angle+(row%2)*tau/count*.48+rng.uniform(-.22,.22)*tau/count
                p=Vector((d['x']+d['rx']*f*math.cos(stagger),-d['z']-d['rz']*f*math.sin(stagger),-depth))
                rock(p,(rng.uniform(.36,.66),rng.uniform(.32,.58),min(rng.uniform(.27,.54),depth-.04)),k+row*43+di*99,stone if row%3 else cliff)
            if k%3==0:
                p=top+normal*.08+Vector((0,0,-.06))
                rock(p,(.19,.19,.07),k,moss)
            if rng.random()<.40:
                for v in range(rng.randint(2,4)):
                    start=top+normal*.11+Vector((rng.uniform(-.12,.12),rng.uniform(-.12,.12),.08))
                    drop=rng.uniform(.65,2.8);points=[]
                    for j in range(16):
                        t=j/15;p=start+normal*(.08+math.sin(t*math.pi)*.11)+Vector((math.sin(t*9+v)*.055,math.cos(t*8+v)*.05,-drop*t));points.append(p)
                        if j:
                            for side in [-1,1]:leaf(p,rng.random()*tau,rng.uniform(.09,.16),.045,trailing[j%3],-.4)
                    b.tube(stem,points,.006,5);stats['vineStrands']+=1
            # Small bankside flower tufts sit outwards, leaving all central lawn empty.
            if rng.random()<.55:
                for q in range(42):
                    p=top+normal*.06+Vector((rng.uniform(-.07,.07),rng.uniform(-.07,.07),rng.uniform(.05,.24)))
                    leaf(p,rng.random()*tau,rng.uniform(.06,.12),.025,trailing[q%3],.15)
                for flower in range(rng.randint(7,12)):
                    p=top+normal*rng.uniform(.02,.18)+Vector((rng.uniform(-.09,.09),rng.uniform(-.09,.09),0))
                    h=rng.uniform(.16,.33);end=p+Vector((rng.uniform(-.04,.04),rng.uniform(-.04,.04),h))
                    b.tube(stem,[p,end],.0035,5)
                    for side in [-1,1]:leaf(p+Vector((0,0,h*.4)),angle+side,rng.uniform(.06,.11),.022,trailing[k%3],.1)
                    for petal in range(6):
                        a=petal*tau/6;leaf(end,a,.035,.015,cream,.12)
                    b.ellipsoid(gold,end+Vector((0,0,.004)),(.014,.014,.012),7,4);stats['flowers']+=1
    stats['coastSamples']=len(rim)
    return stats
