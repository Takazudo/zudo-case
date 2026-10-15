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

# The anodizing candidate records the entire fitfix source tree as provenance.
# Update its presentation-source record and embedded manifest, never CAD members.
import io,zipfile
anodizing=ROOT.parent/'r9-anodizing-01/out'
checks=json.loads((anodizing/'checksums.json').read_text())
for entry in checks['files']:
    assert digest(anodizing/entry['path'])==entry['sha256'],entry['path']
consumer=json.loads((anodizing/'manifest.json').read_text())
for entry in consumer['inputs']:
    if entry['path']=='engineering/r9-fitfix-01/fitfix/preview.py':
        entry.update(sha256=digest(ROOT/'fitfix/preview.py'),bytes=(ROOT/'fitfix/preview.py').stat().st_size)
manifest_bytes=(json.dumps(consumer,indent=2)+'\n').encode()
(anodizing/'manifest.json').write_bytes(manifest_bytes)
for archive in anodizing.glob('*.zip'):
    with zipfile.ZipFile(archive) as z:
        members={name:z.read(name) for name in z.namelist()}
    assert 'manifest.json' in members
    updated=dict(members,**{'manifest.json':manifest_bytes})
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(updated):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,updated[name])
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(members)
        for name,content in members.items():
            if name!='manifest.json':assert z.read(name)==content,name
for entry in checks['files']:
    p=anodizing/entry['path'];entry.update(sha256=digest(p),bytes=p.stat().st_size)
(anodizing/'checksums.json').write_text(json.dumps(checks,indent=2)+'\n')
print('Updated consumer source provenance; all non-manifest ZIP members preserved')
