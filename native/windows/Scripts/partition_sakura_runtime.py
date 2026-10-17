"""Lossless glTF runtime mesh partitioning. No geometry reduction or master edits.
Large offline blossom meshes are divided at triangle boundaries for bounded UE imports.
"""
import struct,json,hashlib,copy
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]
src=root/'Saved/Art/P1SakuraV2';out=root/'Saved/Art/P1SakuraV2Chunks';out.mkdir(exist_ok=True)
manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8'));result=copy.deepcopy(manifest);result['modules']=[]
dtypes={5121:np.uint8,5123:np.uint16,5125:np.uint32,5126:np.float32};width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
for mod in manifest['modules']:
    file=src/mod['file']
    if mod['base_triangles']<=600000:
        import shutil
        shutil.copyfile(file,out/file.name);result['modules'].append(mod);continue
    data=file.read_bytes();size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);blob=data[28+size:]
    if len(doc['meshes'])>1:
        import shutil
        shutil.copyfile(file,out/file.name);result['modules'].append(mod);continue
    assert len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1,'Expected single material batch'
    prim=doc['meshes'][0]['primitives'][0]
    def read(i):
        acc=doc['accessors'][i];view=doc['bufferViews'][acc['bufferView']];dt=np.dtype(dtypes[acc['componentType']]);cols=width[acc['type']]
        return np.ndarray((acc['count'],cols),dt,buffer=blob,offset=view.get('byteOffset',0)+acc.get('byteOffset',0),strides=(view.get('byteStride',dt.itemsize*cols),dt.itemsize))
    indices=read(prim['indices']).reshape(-1,3)
    attrs={k:read(v) for k,v in prim['attributes'].items()}
    for part,start in enumerate(range(0,len(indices),400000)):
        tri=indices[start:start+400000];unique,inverse=np.unique(tri,return_inverse=True)
        d=copy.deepcopy(doc);d['bufferViews']=[];d['accessors']=[];buf=bytearray()
        def add_view(raw,target=None):
            while len(buf)%4:buf.append(0)
            view={'buffer':0,'byteOffset':len(buf),'byteLength':len(raw)}
            if target:view['target']=target
            d['bufferViews'].append(view);buf.extend(raw);return len(d['bufferViews'])-1
        def add_accessor(arr,original,target):
            a=copy.deepcopy(original);a['bufferView']=add_view(arr.tobytes(),target);a.pop('byteOffset',None)
            a['count']=len(arr);a.pop('min',None);a.pop('max',None)
            if a['type']=='VEC3':a['min']=arr.min(axis=0).tolist();a['max']=arr.max(axis=0).tolist()
            d['accessors'].append(a);return len(d['accessors'])-1
        newprim=copy.deepcopy(prim);newprim['attributes']={}
        for key,array in attrs.items():newprim['attributes'][key]=add_accessor(array[unique],doc['accessors'][prim['attributes'][key]],34962)
        idx=inverse.astype(np.uint32).reshape(-1,1)
        newprim['indices']=add_accessor(idx,{'componentType':5125,'type':'SCALAR'},34963)
        d['meshes'][0]['primitives']=[newprim]
        for im in d.get('images',[]):
            if 'bufferView' in im:
                v=doc['bufferViews'][im['bufferView']];im['bufferView']=add_view(blob[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])
        d['buffers']=[{'byteLength':len(buf)}]
        js=json.dumps(d,separators=(',',':')).encode();js+=b' '*((-len(js))%4);buf.extend(b'\x00'*((-len(buf))%4))
        body=struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(buf),0x004e4942)+buf
        name=file.stem+f'-part{part:02d}.glb';payload=struct.pack('<III',0x46546c67,2,12+len(body))+body
        (out/name).write_bytes(payload)
        result['modules'].append({'file':name,'base_triangles':len(tri),'objects':mod['objects'],'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
    print('PARTITIONED',file.name,len(indices),flush=True)
assert sum(x['base_triangles'] for x in result['modules'])==sum(x['base_triangles'] for x in manifest['modules'])
result['partition']='lossless indexed triangle groups, maximum 400000 triangles for split meshes'
(out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('SAKURA_PARTITIONS_READY',len(result['modules']))
