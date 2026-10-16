"""Validate delivered meadow staging modules and rendered evidence (no bpy)."""
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/cloud-meadow-cinematic-v1'


def verify():
    report = json.loads((OUT / 'build-report.json').read_text(encoding='utf-8'))
    assert report['webSceneChanged'] is False
    assert report['accountDataRead'] is False
    assert report['renderer'] == 'Cycles / OptiX'
    assert report['devices'], 'Missing verified GPU'
    source = ROOT / report['source']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report['sourceSha256']
    assert report['newFineGrassBlades'] > 50000
    assert report['refinedCanopyLeaves'] > 100000
    master = (OUT / 'cloud-meadow-master.blend').read_bytes()
    assert len(master) == report['masterBytes'] and len(master) > 10_000_000
    assert hashlib.sha256(master).hexdigest() == report['masterSha256']
    assert report['packedImages'] > 0
    del master
    modules = report['runtimeModules']
    assert len(modules) == 10
    names = set()
    position_count = triangle_count = total_bytes = 0
    for entry in modules:
        path = OUT / entry['file']
        assert path.resolve().is_relative_to(OUT.resolve())
        raw = path.read_bytes()
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
        assert struct.unpack_from('<4sII', raw) == (b'glTF', 2, len(raw))
        size, kind = struct.unpack_from('<I4s', raw, 12)
        assert kind == b'JSON'
        doc = json.loads(raw[20:20+size])
        binary_size, binary_kind = struct.unpack_from('<I4s', raw, 20+size)
        assert binary_kind == b'BIN\0'
        binary = memoryview(raw)[28+size:28+size+binary_size]
        assert len(binary) == binary_size
        assert doc.get('meshes'), path.name
        assert not doc.get('cameras'), path.name
        for image in doc.get('images', []):
            assert 'bufferView' in image, f'External texture: {path.name}'
        for mesh in doc['meshes']:
            name = mesh.get('name', '')
            assert name not in names, f'Duplicate geometry across modules: {name}'
            names.add(name)
            for primitive in mesh['primitives']:
                acc = doc['accessors'][primitive['attributes']['POSITION']]
                assert acc['componentType'] == 5126 and acc['type'] == 'VEC3'
                view = doc['bufferViews'][acc['bufferView']]
                start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
                stride = view.get('byteStride', 12)
                assert start + (acc['count'] - 1) * stride + 12 <= len(binary)
                for i in range(acc['count']):
                    xyz = struct.unpack_from('<3f', binary, start+i*stride)
                    assert all(math.isfinite(v) and abs(v) < 100 for v in xyz), (path.name, xyz)
                position_count += acc['count']
                if 'indices' in primitive:
                    triangle_count += doc['accessors'][primitive['indices']]['count']//3
        total_bytes += len(raw)
    dimensions = {}
    for name in ['01-meadow-panorama', '02-conservatory-detail', '03-grass-and-bridge', '04-plan']:
        data = (OUT / (name + '.png')).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        w, h = struct.unpack_from('>II', data, 16)
        assert w == 2400 and h == 1688, (name, w, h)
        assert len(data) > 100000, name
        dimensions[name] = [w, h]
    result = {'status': 'passed', 'modules': len(modules), 'moduleBytes': total_bytes,
              'uniqueMeshTriangles': triangle_count, 'positionsChecked': position_count,
              'renders': dimensions, 'scope': 'file integrity, embedded textures, finite positions, dimensions; visual review is separate'}
    (OUT / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
