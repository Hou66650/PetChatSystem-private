"""Externalize new meadow maps and reuse unchanged farm textures byte-for-byte.

Run after the Blender builder. Leaves geometry and image pixels unchanged.
"""
import hashlib,json,struct
from pathlib import Path
R=Path(__file__).resolve().parents[1]
P=R/'static/models/petchat-meadow-v1/mistwood-meadow.glb'
def main():
    data=P.read_bytes();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);binary=data[28+n:];removed=set()
    source=R/'static/models/petchat-farm-v1/textures'
    for image in doc.get('images',[]):
        if 'bufferView' not in image:continue
        i=image.pop('bufferView');v=doc['bufferViews'][i];raw=binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']];suffix='.png' if image.pop('mimeType')=='image/png' else '.jpg'
        # Imported immutable, content-addressed maps were not changed in Blender.
        name=image.get('name','')+suffix
        if len(image.get('name',''))==24 and all(c in '0123456789abcdef' for c in image['name']) and (source/name).exists():
            image['uri']='../petchat-farm-v1/textures/'+name
        else:
            name=hashlib.sha256(raw).hexdigest()[:24]+suffix;target=P.parent/'textures'/name;target.parent.mkdir(exist_ok=True);target.write_bytes(raw);image['uri']='textures/'+name
        removed.add(i)
    if not removed:return
    packed=bytearray();views=[];mapping={}
    for i,v in enumerate(doc['bufferViews']):
        if i in removed:continue
        packed.extend(b'\0'*((-len(packed))%4));start=v.get('byteOffset',0);mapping[i]=len(views);views.append(dict(v,byteOffset=len(packed)));packed.extend(binary[start:start+v['byteLength']])
    for a in doc['accessors']:
        if 'bufferView' in a:a['bufferView']=mapping[a['bufferView']]
        for v in a.get('sparse',{}).values():
            if isinstance(v,dict) and 'bufferView' in v:v['bufferView']=mapping[v['bufferView']]
    doc['bufferViews']=views;doc['buffers'][0]['byteLength']=len(packed);packed.extend(b'\0'*((-len(packed))%4));raw=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();raw+=b' '*((-len(raw))%4)
    P.write_bytes(struct.pack('<III',0x46546c67,2,28+len(raw)+len(packed))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(packed),0x004e4942)+packed)
    report=R/'art/cloud-meadow-v1/build-report.json';r=json.loads(report.read_text());r.update(bytes=P.stat().st_size,sharedTextures=sum(i['uri'].startswith('../') for i in doc['images']),newTextureBytes=sum(p.stat().st_size for p in (P.parent/'textures').iterdir()));report.write_text(json.dumps(r,indent=2))
    print(json.dumps(r))
if __name__=='__main__':main()
