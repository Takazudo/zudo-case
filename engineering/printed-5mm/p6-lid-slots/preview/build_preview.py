"""Build the P6 lid viewer from the exact printable STLs and immutable P5 assembly data."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import struct


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(values):
    length = math.sqrt(sum(v*v for v in values)) or 1
    return [v/length for v in values]


def mesh_edges(points, indices):
    edges = {}
    for n in range(0, len(indices), 3):
        abc = [tuple(points[i*3:i*3+3]) for i in indices[n:n+3]]
        a, b, c = abc
        u = [b[i]-a[i] for i in range(3)]
        v = [c[i]-a[i] for i in range(3)]
        normal = normalize([u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]])
        for i, j in [(0, 1), (1, 2), (2, 0)]:
            edge = tuple(sorted((abc[i], abc[j])))
            edges.setdefault(edge, []).append(normal)
    result = []
    for (a, b), normals in edges.items():
        if len(normals) == 1 or any(sum(u*v for u,v in zip(normals[0], n)) < .87 for n in normals[1:]):
            result.extend(a+b)
    return result


def compact_mesh(points, indices):
    vertices, lookup, remap = [], {}, []
    for n in range(0, len(points), 3):
        vertex = tuple(round(float(v), 5) for v in points[n:n+3])
        if vertex not in lookup:
            lookup[vertex] = len(vertices)//3
            vertices.extend(vertex)
        remap.append(lookup[vertex])
    return vertices, [remap[i] for i in indices]


def read_stl(path, translation):
    content = path.read_bytes()
    count = struct.unpack_from('<I', content, 80)[0]
    assert len(content) == 84 + 50*count, 'Expected binary STL'
    vertices = []
    for n in range(count):
        row = struct.unpack_from('<12fH', content, 84+50*n)
        for k in [3, 6, 9]:
            vertices.extend(row[k+i]+translation[i] for i in range(3))
    return compact_mesh(vertices, list(range(count*3)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--fragment', type=Path)
    parser.add_argument('--standalone', type=Path)
    args = parser.parse_args()
    source = args.repo / 'public/previews/printed-5mm-p5-tab-joints.html'
    p5 = json.loads(re.search(r'<script id="modelData" type="application/json">(.*?)</script>', source.read_text(), re.S).group(1))
    result = {'revision':'P6-LID-SLOTS', 'units':'mm', 'parts':[], 'sources':{'p5_preview_sha256':sha(source)}}
    for part in p5['scenes']['lid']:
        name = part['id']
        if not name.startswith(('lid-edge-', 'lid-bracket-', 'lid-top-')):
            continue
        kind = 'plate' if name.startswith('lid-top-') else 'edge' if name.startswith('lid-edge-') else 'bracket'
        item = {'id':name, 'kind':kind}
        if kind == 'plate':
            path = args.repo / f'engineering/printed-5mm/p6-lid-slots/out/stl/{name}.stl'
            shift = [-112.9, -165.2 if name.endswith('1') else .15, 132.5]
            vertices, indices = read_stl(path, shift)
            item['sha256'] = sha(path)
        else:
            mesh = p5['meshes'][part['mesh']]
            vertices, indices = compact_mesh(mesh['p'], mesh['i'])
            item['p5_mesh_id'] = part['mesh']
        item.update(p=vertices, i=indices, e=mesh_edges(vertices, indices))
        result['parts'].append(item)
    template = Path(__file__).with_name('lid-preview-template.html').read_text()
    fragment = template.replace('__LID_DATA__', json.dumps(result, ensure_ascii=False, separators=(',',':')))
    assert '__LID_DATA__' not in fragment
    assert len(fragment.encode()) < 1_000_000
    if args.fragment:
        args.fragment.parent.mkdir(parents=True, exist_ok=True)
        args.fragment.write_text(fragment)
    if args.standalone:
        wrapper = Path(__file__).with_name('standalone-template.html').read_text()
        args.standalone.parent.mkdir(parents=True, exist_ok=True)
        args.standalone.write_text(wrapper.replace('__FRAGMENT__', fragment))
    print(json.dumps({'bytes':len(fragment.encode()), 'parts':[{k:v for k,v in p.items() if k not in ['p','i','e']} | {'vertices':len(p['p'])//3,'triangles':len(p['i'])//3} for p in result['parts']]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
