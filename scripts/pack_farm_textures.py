"""Deduplicate public garden GLB images into content-addressed sibling textures.

Geometry remains GLB; all ten stages reuse cached textures instead of downloading
the same maps with every growth transition. No image editing or re-encoding.
"""
import hashlib, json, struct, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'static/models/petchat-farm-v1'

def pack(path):
    data=path.read_bytes();assert data[:4]==b'glTF'
    length,kind=struct.unpack_from('<II',data,12);assert kind==0x4e4f534a
    doc=json.loads(data[20:20+length]);offset=20+length
    if offset>=len(data):return
    size,kind=struct.unpack_from('<II',data,offset);assert kind==0x004e4942
    binary=data[offset+8:offset+8+size];removed=set()
    for im in doc.get('images',[]):
        if 'bufferView' not in im:continue
        idx=im.pop('bufferView');view=doc['bufferViews'][idx];start=view.get('byteOffset',0)
        content=binary[start:start+view['byteLength']];suffix='.png' if im.pop('mimeType')=='image/png' else '.jpg'
        name=hashlib.sha256(content).hexdigest()[:24]+suffix;target=ROOT/'textures'/name
        target.parent.mkdir(exist_ok=True);target.write_bytes(content);im['uri']='textures/'+name;removed.add(idx)
    if not removed:return
    packed=bytearray();views=[];mapping={}
    for idx,view in enumerate(doc['bufferViews']):
        if idx in removed:continue
        while len(packed)%4:packed.append(0)
        start=view.get('byteOffset',0);new=dict(view,byteOffset=len(packed));packed.extend(binary[start:start+view['byteLength']]);mapping[idx]=len(views);views.append(new)
    for accessor in doc.get('accessors',[]):
        if 'bufferView' in accessor:accessor['bufferView']=mapping[accessor['bufferView']]
        for part in accessor.get('sparse',{}).values():
            if isinstance(part,dict) and 'bufferView' in part:part['bufferView']=mapping[part['bufferView']]
    doc['bufferViews']=views;doc['buffers'][0]['byteLength']=len(packed)
    while len(packed)%4:packed.append(0)
    raw=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();raw+=b' '*((-len(raw))%4)
    result=struct.pack('<III',0x46546c67,2,28+len(raw)+len(packed))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(packed),0x004e4942)+packed
    path.write_bytes(result)

if __name__=='__main__':
    before=sum(p.stat().st_size for p in ROOT.glob('*.glb'))
    for path in ROOT.glob('*.glb'):pack(path)
    files=list(ROOT.glob('*.glb'));referenced=set()
    for path in files:
        data=path.read_bytes();doc=json.loads(data[20:20+struct.unpack_from('<I',data,12)[0]])
        referenced.update(im['uri'] for im in doc.get('images',[]) if 'uri' in im)
    texture_root=(ROOT/'textures').resolve()
    for path in texture_root.iterdir():
        if path.is_file() and path.resolve().parent==texture_root and re.fullmatch(r'[0-9a-f]{24}\.(png|jpg)',path.name) and 'textures/'+path.name not in referenced:
            path.unlink() # Only this packer's content-addressed, now-unused material outputs.
    textures=list(texture_root.glob('*'))
    after=sum(p.stat().st_size for p in files+textures)
    print(json.dumps(dict(before=before,after=after,models=len(files),sharedTextures=len(textures))))
