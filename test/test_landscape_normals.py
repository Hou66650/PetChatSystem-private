"""GLB packing preserves shared/interleaved positions, indices and embedded images."""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from quantize_landscape_normals import quantize_normals


def read(path):
    data = path.read_bytes()
    size = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20 + size]), data[28 + size:]


def view(doc, binary, index):
    entry = doc['bufferViews'][index]
    start = entry.get('byteOffset', 0)
    return binary[start:start + entry['byteLength']]


class LandscapeNormalsTests(unittest.TestCase):
    def fixture(self, path, shared):
        normals = [(1, 0, 0), (-.6, .8, 0), tuple(v / math.sqrt(14) for v in (1, 2, 3))]
        positions = [(0.123456, 2, 3), (-40, 7, 0), (100, 3, 4)]
        if shared:
            binary = struct.pack('<18f', *[v for p, n in zip(positions, normals) for v in (*p, *n)])
            views = [dict(buffer=0, byteOffset=0, byteLength=72, byteStride=24)]
            ni, offset = 0, 12
        else:
            binary = struct.pack('<18f', *[v for row in positions + normals for v in row])
            views = [dict(buffer=0, byteOffset=0, byteLength=36), dict(buffer=0, byteOffset=36, byteLength=36)]
            ni, offset = 1, 0
        views += [dict(buffer=0, byteOffset=72, byteLength=6), dict(buffer=0, byteOffset=80, byteLength=8)]
        binary += struct.pack('<3H', 0, 1, 2) + b'\0\0' + b'PNG-test'
        doc = dict(asset={'version': '2.0'}, buffers=[{'byteLength': len(binary)}], bufferViews=views,
                   accessors=[dict(bufferView=0, componentType=5126, count=3, type='VEC3'),
                              dict(bufferView=ni, byteOffset=offset, componentType=5126, count=3, type='VEC3'),
                              dict(bufferView=len(views)-2, componentType=5123, count=3, type='SCALAR')],
                   meshes=[{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1}, 'indices': 2}]}],
                   images=[{'bufferView': len(views)-1, 'mimeType': 'image/png'}])
        raw = json.dumps(doc).encode(); raw += b' ' * (-len(raw) % 4)
        path.write_bytes(struct.pack('<III', 0x46546c67, 2, 28+len(raw)+len(binary)) +
                         struct.pack('<II', len(raw), 0x4e4f534a) + raw +
                         struct.pack('<II', len(binary), 0x004e4942) + binary)
        return normals

    def test_shared_and_separate_views_preserve_geometry_and_images(self):
        for shared in (False, True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'fixture.glb'
                normals = self.fixture(path, shared)
                old, original = read(path)
                quantize_normals(path)
                doc, binary = read(path)
                self.assertEqual(view(old, original, 0), view(doc, binary, doc['accessors'][0]['bufferView']))
                self.assertEqual(struct.pack('<3H', 0, 1, 2), view(doc, binary, doc['accessors'][2]['bufferView']))
                self.assertEqual(b'PNG-test', view(doc, binary, doc['images'][0]['bufferView']))
                self.assertIn('KHR_mesh_quantization', doc['extensionsRequired'])
                self.assertTrue(all(v.get('byteOffset', 0) % 4 == 0 for v in doc['bufferViews']))
                accessor = doc['accessors'][1]
                self.assertEqual(accessor['componentType'], 5120)
                self.assertTrue(accessor['normalized'])
                packed = view(doc, binary, accessor['bufferView'])
                for index, expected in enumerate(normals):
                    actual = struct.unpack_from('<3b', packed, index * 4)
                    length = math.sqrt(sum(v*v for v in actual))
                    cosine = sum(a*b/length for a, b in zip(actual, expected))
                    self.assertLess(math.degrees(math.acos(min(1, cosine))), .5)
                once = path.read_bytes(); quantize_normals(path)
                self.assertEqual(once, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
