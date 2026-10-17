"""Verify v2 offline art deliverables, not runtime performance or visual quality."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/cloud-meadow-cinematic-v2'


def verify():
    report=json.loads((OUT/'build-report.json').read_text(encoding='utf-8'))
    assert report['webSceneChanged'] is False and report['accountDataRead'] is False
    assert report['runtimeReady'] is False
    assert report['renderer']=='Cycles / OptiX' and report['devices']
    source=Path(report['sourceMaster'])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['sourceSha256']
    master=OUT/report['master']
    assert master.resolve().is_relative_to(OUT.resolve())
    assert master.stat().st_size==report['masterBytes']
    assert hashlib.sha256(master.read_bytes()).hexdigest()==report['masterSha256']
    counts=report['detailCounts']
    assert counts['newCoreGrassBlades']>50000
    assert counts['removedLegacyGroundFaces']>40000
    assert counts['finitePositionsChecked']>0
    required={n+'.png' for n in ['01-island','02-greenhouse','03-planters','04-home']}
    renders={r['file']:r for r in report['renders'] if r['file'] in required}
    assert renders.keys()==required
    for name,r in renders.items():
        raw=(OUT/name).read_bytes()
        assert raw[:8]==b'\x89PNG\r\n\x1a\n'
        assert struct.unpack_from('>II',raw,16)==(2400,1800)
        assert r['samples']>=128
        assert hashlib.sha256(raw).hexdigest()==r['sha256']
    result={'status':'passed','masterBytes':master.stat().st_size,'renders':sorted(required),'scope':'source/master/render hashes, PNG dimensions and recorded geometry validation; UE runtime remains unqualified'}
    (OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':verify()
