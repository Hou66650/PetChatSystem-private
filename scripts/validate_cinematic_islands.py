"""Offline art integrity checks; no application, database or network access."""
import hashlib
import json
from pathlib import Path
import struct
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/cinematic-islands-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    results = {}
    for theme in ['sakura', 'snow', 'camp']:
        folder = OUT / theme
        report = json.loads((folder / 'build-report.json').read_text(encoding='utf-8'))
        assert report['theme'] == theme
        assert report['webSceneChanged'] is False and report['accountDataRead'] is False
        assert report['devices'] and report['renderer'] == 'Cycles / OptiX'
        assert report['packedImages'] > 0
        assert sha(OUT / report['source']) == report['sourceSha256']
        assert sha(OUT / 'source/layouts.json') == report['layoutSha256']
        master = folder / 'island-master.blend'
        assert master.stat().st_size == report['masterBytes']
        assert sha(master) == report['masterSha256']
        assert len(report['modules']) == 4
        vertices = triangles = byte_count = 0
        mesh_names = set()
        for module in report['modules']:
            path = folder / module['file']
            assert path.resolve().is_relative_to(folder.resolve())
            raw = path.read_bytes()
            assert len(raw) == module['bytes'] and sha(path) == module['sha256']
            assert struct.unpack_from('<4sII', raw) == (b'glTF', 2, len(raw))
            size, kind = struct.unpack_from('<I4s', raw, 12)
            assert kind == b'JSON'
            doc = json.loads(raw[20:20+size])
            length, kind = struct.unpack_from('<I4s', raw, 20+size)
            assert kind == b'BIN\0' and 28+size+length == len(raw)
            binary = memoryview(raw)[28+size:]
            assert doc.get('meshes') and not doc.get('cameras')
            for im in doc.get('images', []):
                assert 'bufferView' in im and 'uri' not in im
            for mesh in doc['meshes']:
                assert mesh['name'] not in mesh_names
                mesh_names.add(mesh['name'])
                for primitive in mesh['primitives']:
                    acc = doc['accessors'][primitive['attributes']['POSITION']]
                    assert acc['componentType'] == 5126 and acc['type'] == 'VEC3'
                    view = doc['bufferViews'][acc['bufferView']]
                    start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
                    stride = view.get('byteStride', 12)
                    assert start + (acc['count']-1)*stride + 12 <= len(binary)
                    xyz = np.ndarray((acc['count'], 3), '<f4', binary, start, (stride, 4))
                    assert np.isfinite(xyz).all() and (np.abs(xyz) < 100).all()
                    assert np.allclose(xyz.min(axis=0), acc['min'], atol=1e-4)
                    assert np.allclose(xyz.max(axis=0), acc['max'], atol=1e-4)
                    vertices += acc['count']
                    if 'indices' in primitive:
                        indices = doc['accessors'][primitive['indices']]
                        assert indices['count'] % 3 == 0
                        iv = doc['bufferViews'][indices['bufferView']]
                        dtype = {5121:'u1',5123:'<u2',5125:'<u4'}[indices['componentType']]
                        values = np.frombuffer(binary, dtype, indices['count'], iv.get('byteOffset',0)+indices.get('byteOffset',0))
                        assert values.max() < acc['count']
                        triangles += indices['count']//3
            byte_count += len(raw)
        renders = {}
        for name in ['01-panorama', '02-architecture', '03-plan']:
            raw = (folder / (name+'.png')).read_bytes()
            assert raw[:8] == b'\x89PNG\r\n\x1a\n' and len(raw) > 100000
            dimensions = struct.unpack_from('>II', raw, 16)
            assert dimensions == (2400, 2000)
            renders[name] = dimensions
        results[theme] = {'status':'passed', 'modules':4, 'moduleBytes':byte_count,
                          'positionsChecked':vertices, 'triangles':triangles, 'renders':renders}
    unchanged = json.loads((OUT/'web-unchanged.json').read_text(encoding='utf-8'))
    assert unchanged['unchanged'] is True
    for relative, expected in unchanged['sha256'].items():
        assert sha(ROOT/relative) == expected, f'Production changed: {relative}'
    result = {'status':'passed', 'islands':results, 'productionInputsUnchanged':True,
              'scope':'Integrity, embedded textures, all vertex bounds and indices, render dimensions. Visual review is separate; no runtime performance claim.'}
    (OUT/'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
