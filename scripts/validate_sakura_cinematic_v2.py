"""Check delivered render hashes, actual PNG sizes and the local editable master."""
import hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/sakura-cinematic-v2'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    r=json.loads((OUT/'build-report.json').read_text(encoding='utf8'))
    assert r['webSceneChanged'] is False and r['accountDataRead'] is False
    assert r['runtimeReady'] is False and r['runtimeLimitations']
    assert r['renderer']=='Cycles / OptiX' and r['devices']
    master=OUT/r['master'];assert master.stat().st_size==r['masterBytes'] and digest(master)==r['masterSha256']
    source=Path(r['source']);assert digest(source)==r['sourceSha256'],'Source master was changed'
    for item in r.get('supportingAssets',[]):assert digest(ROOT/item['file'])==item['sha256']
    assert r['stats']['finiteVerticesChecked']>0
    names=['01-grand-vista.png','02-cherry-promenade.png','03-tea-pavilion.png','04-blossom-detail.png','05-plan.png']
    checked=[]
    for name in names:
        item=next(x for x in r['renders'] if x['file']==name);p=OUT/name;raw=p.read_bytes()
        assert raw[:8]==b'\x89PNG\r\n\x1a\n'
        dims=struct.unpack('>II',raw[16:24]);assert dims==(2400,1800)
        assert item['samples']>=128 and item['sha256']==hashlib.sha256(raw).hexdigest()
        checked.append({'file':name,'size':dims,'sha256':item['sha256']})
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ['src','href'] and not v.startswith(('#','http')):assert (OUT/v).is_file(),v
    Links().feed((OUT/'index.html').read_text(encoding='utf8'))
    result={'passed':True,'masterHashVerified':True,'sourceUnchanged':True,'finiteVertices':r['stats']['finiteVerticesChecked'],'renders':checked,'runtimeQualified':False}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
