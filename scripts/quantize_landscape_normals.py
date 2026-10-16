"""Pack unit normals without changing positions, UVs, triangles or image pixels.

The bundled Three.js loader supports KHR_mesh_quantization. Normals use signed
normalized bytes, with a four-byte stride; editable Blender data stays float32.
"""
import json,struct

def quantize_normals(path):
    import numpy as np
    data=path.read_bytes();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);binary=data[28+n:]
    ids={p['attributes']['NORMAL'] for m in doc['meshes'] for p in m['primitives'] if 'NORMAL' in p['attributes']}
    ids={i for i in ids if doc['accessors'][i]['componentType']==5126}
    if not ids:return
    if any('sparse' in doc['accessors'][i] for i in ids):
        raise ValueError('Sparse normals must be resolved before quantization')
    occupied={a.get('bufferView') for i,a in enumerate(doc['accessors']) if i not in ids}
    occupied.update(i.get('bufferView') for i in doc.get('images',[]))
    for a in doc['accessors']:
        occupied.update(v['bufferView'] for v in a.get('sparse',{}).values() if isinstance(v,dict) and 'bufferView' in v)
    removed={doc['accessors'][i]['bufferView'] for i in ids}-occupied
    views=[];packed=bytearray();mapping={}
    for i,v in enumerate(doc['bufferViews']):
        if i in removed:continue
        packed.extend(b'\0'*((-len(packed))%4));start=v.get('byteOffset',0);mapping[i]=len(views);views.append(dict(v,byteOffset=len(packed)));packed.extend(binary[start:start+v['byteLength']])
    for i,a in enumerate(doc['accessors']):
        if i in ids:
            v=doc['bufferViews'][a['bufferView']];offset=v.get('byteOffset',0)+a.get('byteOffset',0)
            normals=np.ndarray((a['count'],3),dtype='<f4',buffer=binary,offset=offset,strides=(v.get('byteStride',12),4))
            values=np.zeros((a['count'],4),dtype=np.int8);values[:,:3]=np.rint(np.clip(normals,-1,1)*127).astype(np.int8)
            packed.extend(b'\0'*((-len(packed))%4));a.update(bufferView=len(views),byteOffset=0,componentType=5120,normalized=True)
            a.pop('min',None);a.pop('max',None)
            views.append(dict(buffer=0,byteOffset=len(packed),byteLength=values.nbytes,byteStride=4,target=34962));packed.extend(values.tobytes())
        elif 'bufferView' in a:a['bufferView']=mapping[a['bufferView']]
        for v in a.get('sparse',{}).values():
            if isinstance(v,dict) and 'bufferView' in v:v['bufferView']=mapping[v['bufferView']]
    for i in doc.get('images',[]):
        if 'bufferView' in i:i['bufferView']=mapping[i['bufferView']]
    for key in ['extensionsUsed','extensionsRequired']:
        if 'KHR_mesh_quantization' not in doc.setdefault(key,[]):doc[key].append('KHR_mesh_quantization')
    doc['bufferViews']=views;doc['buffers'][0]['byteLength']=len(packed);packed.extend(b'\0'*((-len(packed))%4))
    raw=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();raw+=b' '*((-len(raw))%4)
    path.write_bytes(struct.pack('<III',0x46546c67,2,28+len(raw)+len(packed))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(packed),0x004e4942)+packed)
