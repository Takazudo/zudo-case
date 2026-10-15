"""Rebuild only presentation from preserved scene; never regenerate manufacturing data."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fitfix.preview import make_preview
out=ROOT/'out'
manifest=json.loads((out/'outputs-manifest.json').read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Verify all previously recorded non-preview outputs before using retained scene.
for entry in manifest['files']:
    if entry['path']!='preview.html':
        assert digest(out/entry['path'])==entry['sha256'],entry['path']
make_preview(json.loads((out/'scene.json').read_text()),ROOT/'vendor/three-bundle.js',out/'preview.html')
for entry in manifest['inputs']:
    if entry['path']=='fitfix/preview.py':entry['sha256']=digest(ROOT/entry['path'])
for entry in manifest['files']:
    if entry['path']=='preview.html':entry.update(sha256=digest(out/'preview.html'),bytes=(out/'preview.html').stat().st_size)
(out/'outputs-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Refreshed preview only; retained scene and manufacturing output hashes verified')
