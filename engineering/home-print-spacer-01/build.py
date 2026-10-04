"""Generate and verify an upright annular spacer STL using only Python stdlib."""
from pathlib import Path
import collections
import hashlib
import json
import math
import struct

ROOT = Path(__file__).resolve().parent
HEIGHT, OD, ID, SEGMENTS = 8.0, 10.0, 5.5, 128


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def generate():
    rings = [[(r*math.cos(2*math.pi*i/SEGMENTS), r*math.sin(2*math.pi*i/SEGMENTS), z)
              for i in range(SEGMENTS)] for r, z in [(OD/2, 0), (OD/2, HEIGHT), (ID/2, 0), (ID/2, HEIGHT)]]
    ob, ot, ib, it = rings
    faces = []
    def quad(a, b, c, d):
        faces.extend([(a, b, c), (a, c, d)])
    for i in range(SEGMENTS):
        j = (i+1) % SEGMENTS
        quad(ob[i], ob[j], ot[j], ot[i])
        quad(ib[j], ib[i], it[i], it[j])
        quad(ot[i], ot[j], it[j], it[i])
        quad(ob[j], ob[i], ib[i], ib[j])
    data = bytearray(b'ZUDO CASE HOME-PRINT-SPACER-01; units mm'.ljust(80, b' '))
    data.extend(struct.pack('<I', len(faces)))
    for a, b, c in faces:
        n = cross(tuple(b[k]-a[k] for k in range(3)), tuple(c[k]-a[k] for k in range(3)))
        length = math.sqrt(sum(x*x for x in n))
        assert length > 0
        data.extend(struct.pack('<12fH', *(x/length for x in n), *a, *b, *c, 0))
    path = ROOT / 'frame-spacer-h8-od10-id5p5-mm.stl'
    path.write_bytes(data)
    # Verify the serialized float32 mesh, rather than just the generator inputs.
    mesh = [struct.unpack_from('<12fH', data, 84+50*i)[3:12] for i in range(len(faces))]
    edges = collections.Counter()
    volume = 0
    vertices = set()
    for face in mesh:
        a, b, c = [tuple(face[i:i+3]) for i in (0, 3, 6)]
        vertices.update((a, b, c))
        for u, v in ((a, b), (b, c), (c, a)):
            edges[u, v] += 1
        volume += sum(a[k]*cross(b, c)[k] for k in range(3))/6
    assert all(count == 1 and edges[v, u] == 1 for (u, v), count in edges.items()), 'non-manifold or inconsistent winding'
    assert len(vertices)-len(edges)//2+len(mesh) == 0, 'expected through-hole topology'
    bounds = [[min(v[k] for v in vertices), max(v[k] for v in vertices)] for k in range(3)]
    assert bounds == [[-5.0, 5.0], [-5.0, 5.0], [0.0, 8.0]]
    bore = min(math.hypot(v[0], v[1]) for v in vertices)*2
    assert abs(bore-ID) < 1e-5
    expected = math.pi*((OD/2)**2-(ID/2)**2)*HEIGHT
    assert abs(volume-expected)/expected < 0.0005
    source = ROOT.parent / 'r6-body/design-parameters.json'
    manifest = dict(revision='HOME-PRINT-SPACER-01', units='mm', status='home-print fit trial; physical fit and clamping unverified',
                    height_mm=HEIGHT, outer_diameter_mm=OD, bore_diameter_mm=ID, segments=SEGMENTS,
                    quantity={'3u60': 4, '7u40': 10, '7u60': 10},
                    input={'path': '../r6-body/design-parameters.json', 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()},
                    output={'path': path.name, 'sha256': hashlib.sha256(data).hexdigest()},
                    verification={'triangles': len(mesh), 'closed_manifold': True, 'consistent_winding': True,
                                  'bounds_mm': bounds, 'volume_mm3': volume, 'bore_vertex_diameter_mm': bore})
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest['verification'], indent=2))


if __name__ == '__main__':
    generate()
