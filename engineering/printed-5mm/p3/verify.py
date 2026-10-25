"""Check a clean full-build output against its own manifest and fixed inventory."""
from pathlib import Path
import argparse,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--published-root',type=Path);a=p.parse_args();out=a.out
m=json.loads((out/'outputs-manifest.json').read_text())
assert m['revision']=='P3-PRINTED-5MM-7U-RAILS'
for f in m['files']:
 data=(out/f['path']).read_bytes(); assert len(data)==f['bytes']; assert hashlib.sha256(data).hexdigest()==f['sha256']
model=json.loads((out/'source/model.json').read_text())
assert len(model['parts'])==15
ids=[x['id'] for x in model['parts']]
assert len(ids)==len(set(ids))
assert set(ids)=={'floor-1','floor-2','wall-front','wall-back','wall-right','wall-left','lid-edge-front','lid-edge-back','lid-edge-right','lid-edge-left','lid-top-1','lid-top-2','pad-horizontal','pad-vertical','washer-round'}
assert model['revision']=='P3-PRINTED-5MM-7U-RAILS'
assert model['parameters']['revision']==model['revision']
assert len([x for x in model['parts'] if x['id'] not in ('pad-horizontal','pad-vertical','washer-round')])==12
assert len([x for x in model['scenes']['assembly'] if x.get('existingReference')])==66
assert len(list((out/'stl').glob('*.stl')))==len(list((out/'step').glob('*.step')))==15
for zpath in (out/'printed-5mm-p3-stl.zip',out/'printed-5mm-p3-source.zip'):
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  assert len(z.namelist())==len(set(z.namelist()))
  for name in z.namelist(): assert z.read(name)==(out/name).read_bytes(),name
if a.published_root:
    repo=a.published_root
    mapping={}
    for file in (out/'stl').glob('*.stl'): mapping[file]=repo/'engineering/printed-5mm/p3/out/stl'/file.name
    for file in (out/'step').glob('*.step'): mapping[file]=repo/'engineering/printed-5mm/p3/out/step'/file.name
    for name in ('BOM.json','PRINT-PARTS.csv','PRINT-START-HERE.md','DIMENSIONS.json','accepted-geometry-comparison.json'):
        mapping[out/name]=repo/'engineering/printed-5mm/p3/out'/name
    for name in ('geometry-checks.json','rail-geometry-checks.json','print-bed-checks.json'):
        mapping[out/'evidence'/name]=repo/'engineering/printed-5mm/p3/out'/name
    mapping[out/'reference/RAIL-PLACEMENT.json']=repo/'engineering/printed-5mm/p3/out/RAIL-PLACEMENT.json'
    mapping[out/'zudo-case-printed-5mm-p3.html']=repo/'public/previews/printed-5mm-p3.html'
    for name in ('printed-5mm-p3-stl.zip','printed-5mm-p3-source.zip'):
        mapping[out/name]=repo/'public/downloads/candidate'/name
    for generated,published in mapping.items():
        assert hashlib.sha256(generated.read_bytes()).digest()==hashlib.sha256(published.read_bytes()).digest(),published
print('P3 full output verified')
