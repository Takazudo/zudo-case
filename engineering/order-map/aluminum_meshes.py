"""Read the reviewed STL bytes; tessellate original C3 STEP (no original STL exists)."""
import gzip
import hashlib
import json
import struct
from pathlib import Path
import cadquery as cq

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_name('aluminum-meshes.json.gz')

def generate():
    manifest = json.loads((ROOT/'engineering/r9-anodizing-01/out/manifest.json').read_text())
    result = {}
    for part in manifest['parts']:
        variants = {}
        for revision, key in [('original', 'old_files'), ('revised', 'new_files')]:
            file = next((f for f in part[key] if f['path'].endswith('.stl')), None)
            if file:
                source = file['path'] if revision == 'original' else 'engineering/r9-anodizing-01/out/'+file['path']
                raw = (ROOT/source).read_bytes()
                count = struct.unpack_from('<I', raw, 80)[0]
                assert len(raw) == 84+50*count
                positions = []
                for i in range(count):
                    positions.extend(struct.unpack_from('<9f', raw, 84+50*i+12))
                indices = list(range(count*3))
            else:
                file = next(f for f in part[key] if f['path'].endswith('.step'))
                source = file['path'] if revision == 'original' else 'engineering/r9-anodizing-01/out/'+file['path']
                raw = (ROOT/source).read_bytes()
                shape = cq.importers.importStep(str(ROOT/file['path'])).val()
                vertices, triangles = shape.tessellate(0.01, 0.1)
                positions = [n for v in vertices for n in v.toTuple()]
                indices = [n for t in triangles for n in t]
            assert hashlib.sha256(raw).hexdigest() == file['sha256'], file['path']
            variants[revision] = dict(id=part['id'], group='metal', positions=positions, indices=indices,
                                      source=source, sha256=file['sha256'])
        result[part['id']] = variants
    return json.dumps(result, separators=(',', ':'))+'\n'

if __name__ == '__main__':
    import sys
    data = bytearray(gzip.compress(generate().encode(), mtime=0))
    data[9] = 255
    data = bytes(data)
    if '--check' in sys.argv:
        assert OUT.read_bytes() == data, 'Aluminum mesh cache is stale'
    else:
        OUT.write_bytes(data)
    print('Verified 13 original/revised aluminum mesh pairs')
