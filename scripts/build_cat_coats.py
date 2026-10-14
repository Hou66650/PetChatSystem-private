"""Build skinned cosmetic GLBs without changing joints, weights, morphs or clips.
Procedural surface pigments and a fuller longhair silhouette reuse the original rig.
"""
import copy,io,json,struct
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[1];src=(R/'static/models/petchat-cat-v2/cat.glb').read_bytes()
n=struct.unpack_from('<I',src,12)[0];base=json.loads(src[20:20+n]);binary=src[28+n:]
out=R/'static/models/petchat-cat-coats-v1';out.mkdir(exist_ok=True)
def read(j,b,index):
 a=j['accessors'][index];v=j['bufferViews'][a['bufferView']];types={5126:'<f4',5123:'<u2',5121:'u1',5125:'<u4'};width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];dtype=np.dtype(types[a['componentType']]);offset=v.get('byteOffset',0)+a.get('byteOffset',0)
 return np.ndarray((a['count'],width),dtype=dtype,buffer=b,offset=offset,strides=(v.get('byteStride',width*dtype.itemsize),dtype.itemsize)).copy()
v=base['bufferViews'][base['images'][0]['bufferView']];atlas=np.array(Image.open(io.BytesIO(binary[v['byteOffset']:v['byteOffset']+v['byteLength']])).convert('RGB'))/255.
def lin(c):return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
def append(j,b,arr,typ):
 while len(b)%4:b.append(0)
 raw=arr.astype('<f4').tobytes();j['bufferViews'].append(dict(buffer=0,byteOffset=len(b),byteLength=len(raw),target=34962));b.extend(raw)
 a=dict(bufferView=len(j['bufferViews'])-1,componentType=5126,count=len(arr),type=typ)
 if typ=='VEC3':a.update(min=arr.min(axis=0).tolist(),max=arr.max(axis=0).tolist())
 j['accessors'].append(a);return len(j['accessors'])-1
for coat in ['ginger','tuxedo','calico','ragdoll']:
 j=copy.deepcopy(base);b=bytearray(binary)
 for mesh in j['meshes']:
  for prim in mesh['primitives']:
   attrs=prim['attributes'];p=read(j,b,attrs['POSITION']);x,y,z=p.T;fur=mesh['name']=='Reference_fur'
   if 'TEXCOORD_0' in attrs:
    uv=read(j,b,attrs['TEXCOORD_0']);original=atlas[np.clip((uv[:,1]*(atlas.shape[0]-1)).astype(int),0,atlas.shape[0]-1),np.clip((uv[:,0]*(atlas.shape[1]-1)).astype(int),0,atlas.shape[1]-1)]
   else:original=np.clip(read(j,b,attrs['COLOR_0'])[:,:3],0,1)**(1/2.2)
   noise=.5+.22*np.sin(x*21+z*13+np.sin(y*16))+.18*np.sin(z*31-y*17+x*8)
   rgb=np.tile([.94,.91,.82],(len(p),1))
   if coat=='ginger':
    stripe=(np.sin(z*43+y*17+np.sin(x*30)*1.5)>.54)&(y>.24)
    rgb[:]=[.84,.52,.22];rgb[stripe]=[.49,.25,.09];rgb[(y<.13)|((z>.44)&(y<.79))]=[.96,.87,.67]
   elif coat=='tuxedo':
    mask=(noise>.51)&(y>.20);mask|=(y>.83)&(z>.30);rgb[mask]=[.055,.066,.075];rgb[(abs(x)<.042)&(z>.46)&(y<.94)]=[.95,.93,.86]
   elif coat=='calico':
    rgb[(noise>.51)&(y>.18)]=[.78,.39,.13];rgb[(noise<.33)&(y>.20)]=[.06,.065,.07]
   else:
    mask=((z>.40)&(y>.73))|((y<.17))|((z<-.30)&(y>.55));rgb[mask]=[.32,.25,.23]
    rgb[(abs(x)<.06)&(z>.46)&(y<.9)]=[.94,.90,.80]
   # Keep fine shading from the source surface and the actual eyes/nose pigments.
   detail=np.clip(.87+.17*original.mean(axis=1),.84,1.0);rgb*=detail[:,None]
   face=(z>.46)&(y>.76)&(y<.90)&(abs(x)>.045)&(abs(x)<.17)
   feature=face&(original.mean(axis=1)<.26)
   nose=(z>.52)&(y>.70)&(y<.79)&(abs(x)<.08)
   rgb[feature|nose]=original[feature|nose]
   face_all=(z>.32)&(y>.70)
   face_color=original.copy()
   if coat=='ginger':face_color*=np.array([1.08,.84,.58])
   if coat in ('tuxedo','calico','ragdoll'):
    u=(x-.07)*.65-(z-.49)*.76
    face_color[:]=[.92,.89,.81]
    if coat=='ragdoll':face_color[(abs(u)>.035+( .84-y)*.4)|(y>.88)]=[.34,.27,.24]
    if coat=='tuxedo':face_color[(u>.025)|(y>.89)]=[.075,.08,.085]
    if coat=='calico':
     face_color[(u>.01)&(y>.81)]=[.77,.43,.18];face_color[(u<-.025)&(y>.86)]=[.075,.08,.085]
    keep=np.zeros(len(p),dtype=bool);blend=np.zeros(len(p))
    for center,radius in [([.03186,.82568,.53827],.033),([.10877,.82275,.44764],.033),([.10377,.74472,.53307],.029)]:
     distance=np.linalg.norm(p-np.array(center),axis=1);keep|=distance<radius;blend=np.maximum(blend,np.clip((radius-distance)/.014,0,1))
    face_color=face_color*(1-blend[:,None])+original*blend[:,None]
    if coat=='ragdoll':
     iris=keep&(original[:,1]>original[:,0]*.97)&(original[:,1]>original[:,2]*1.15)&(y>.80)
     face_color[iris]=np.clip(original[iris].mean(axis=1)[:,None]*np.array([.55,1.10,1.5]),0,1)
    if fur:face_color=original.copy()
   rgb[face_all]=np.clip(face_color[face_all],0,1)
   if fur:rgb=np.clip(rgb*(.92+.12*np.sin(x*711+y*327+z*519)[:,None]),0,1)
   attrs['COLOR_0']=append(j,b,np.column_stack([lin(np.clip(rgb,0,1)),np.ones(len(p))]),'VEC4')
   mat=j['materials'][prim['material']];mat['pbrMetallicRoughness'].pop('baseColorTexture',None);mat['name']='Coat_'+coat+('_fibres' if fur else '_skin')
   if coat=='ragdoll':
    normal=read(j,b,attrs['NORMAL']);amount=np.clip((y-.25)/.35,0,1)*(.018 if fur else .006);amount[(z>.30)&(y>.70)]=0
    p+=normal*amount[:,None];cheeks=(y>.60)&(y<.72)&(z>.3);p[cheeks,0]*=1.13
    attrs['POSITION']=append(j,b,p,'VEC3')
 # Remove source textures and superseded accessors from each standalone asset.
 j.pop('images',None);j.pop('textures',None);j.pop('samplers',None)
 refs=[]
 for mesh in j['meshes']:
  for prim in mesh['primitives']:
   refs.extend((prim['attributes'],k) for k in prim['attributes'])
   if 'indices' in prim:refs.append((prim,'indices'))
   for target in prim.get('targets',[]):refs.extend((target,k) for k in target)
 for skin in j.get('skins',[]):
  if 'inverseBindMatrices' in skin:refs.append((skin,'inverseBindMatrices'))
 for animation in j.get('animations',[]):
  for sampler in animation['samplers']:refs.extend([(sampler,'input'),(sampler,'output')])
 used=sorted({obj[key] for obj,key in refs});mapping={old:new for new,old in enumerate(used)}
 j['accessors']=[j['accessors'][i] for i in used]
 for obj,key in refs:obj[key]=mapping[obj[key]]
 vrefs=[]
 for accessor in j['accessors']:
  if 'bufferView' in accessor:vrefs.append((accessor,'bufferView'))
  for part in accessor.get('sparse',{}).values():
   if isinstance(part,dict) and 'bufferView' in part:vrefs.append((part,'bufferView'))
 views=sorted({obj[key] for obj,key in vrefs});mapping={old:new for new,old in enumerate(views)};compact=bytearray();newviews=[]
 for i in views:
  v=dict(j['bufferViews'][i]);offset=v.get('byteOffset',0)
  while len(compact)%4:compact.append(0)
  v['byteOffset']=len(compact);compact.extend(b[offset:offset+v['byteLength']]);newviews.append(v)
 for obj,key in vrefs:obj[key]=mapping[obj[key]]
 j['bufferViews']=newviews;b=compact
 while len(b)%4:b.append(0)
 j['buffers'][0]['byteLength']=len(b);j.setdefault('extras',{})['catCoat']=coat
 raw=json.dumps(j,separators=(',',':')).encode();raw+=b' '*((-len(raw))%4)
 data=struct.pack('<III',0x46546c67,2,28+len(raw)+len(b))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(b),0x004e4942)+b
 (out/(coat+'.glb')).write_bytes(data);print(coat,len(data),'bytes',len(j['animations']),'shared animations')
