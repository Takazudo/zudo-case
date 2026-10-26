"""Check a clean full-build output against its own manifest and fixed inventory."""
from pathlib import Path
import argparse,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--published-root',type=Path);a=p.parse_args();out=a.out
m=json.loads((out/'outputs-manifest.json').read_text())
assert m['revision']=='P4-PRINTED-5MM-UNIFORM-VENTS'
for f in m['files']:
 data=(out/f['path']).read_bytes(); assert len(data)==f['bytes']; assert hashlib.sha256(data).hexdigest()==f['sha256']
model=json.loads((out/'source/model.json').read_text())
assert all(x.get('passed',True) for x in model['checks'])
assert len(model['parts'])==15
ids=[x['id'] for x in model['parts']]
assert len(ids)==len(set(ids))
assert set(ids)=={'floor-1','floor-2','wall-front','wall-back','wall-right','wall-left','lid-edge-front','lid-edge-back','lid-edge-right','lid-edge-left','lid-top-1','lid-top-2','pad-horizontal','pad-vertical','washer-round'}
assert model['revision']=='P4-PRINTED-5MM-UNIFORM-VENTS'
assert model['parameters']['revision']==model['revision']
assert len([x for x in model['parts'] if x['id'] not in ('pad-horizontal','pad-vertical','washer-round')])==12
assert len([x for x in model['scenes']['assembly'] if x.get('existingReference')])==66
assert len(list((out/'stl').glob('*.stl')))==len(list((out/'step').glob('*.step')))==15
for zpath in (out/'printed-5mm-p4-uniform-vents-stl.zip',out/'printed-5mm-p4-uniform-vents-source.zip'):
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  assert len(z.namelist())==len(set(z.namelist()))
  for name in z.namelist(): assert z.read(name)==(out/name).read_bytes(),name
if a.published_root:
    repo=a.published_root
    mapping={}
    for file in (out/'stl').glob('*.stl'): mapping[file]=repo/'engineering/printed-5mm/p4-uniform-vents/out/stl'/file.name
    for file in (out/'step').glob('*.step'): mapping[file]=repo/'engineering/printed-5mm/p4-uniform-vents/out/step'/file.name
    for name in ('BOM.json','PRINT-PARTS.csv','PRINT-START-HERE.md','DIMENSIONS.json','accepted-geometry-comparison.json','VENTILATION.json','PRINT-MAPPING.json'):
        mapping[out/name]=repo/'engineering/printed-5mm/p4-uniform-vents/out'/name
    for name in ('geometry-checks.json','rail-geometry-checks.json','print-bed-checks.json'):
        mapping[out/'evidence'/name]=repo/'engineering/printed-5mm/p4-uniform-vents/out'/name
    mapping[out/'reference/RAIL-PLACEMENT.json']=repo/'engineering/printed-5mm/p4-uniform-vents/out/RAIL-PLACEMENT.json'
    mapping[out/'zudo-case-printed-5mm-p4-uniform-vents.html']=repo/'public/previews/printed-5mm-p4-uniform-vents.html'
    for name in ('printed-5mm-p4-uniform-vents-stl.zip','printed-5mm-p4-uniform-vents-source.zip'):
        mapping[out/name]=repo/'public/downloads/candidate'/name
    for generated,published in mapping.items():
        assert hashlib.sha256(generated.read_bytes()).digest()==hashlib.sha256(published.read_bytes()).digest(),published
print('P4 full output verified')

r=json.loads((out/'VENTILATION.json').read_text())
assert r['revision']==m['revision'] and r['pattern']=='uniform-four-walls'
assert (r['total_vents'],r['assembly_slots'],r['rail_holes'])==(82,28,10)
assert model['ventilation']==r['panels']
for panel in r['panels']:
    assert panel['minimum_hardware_clearance_mm']>=4-1e-7
    assert panel['minimum_hole_clearance_mm']>=6.9
    assert panel['minimum_web_mm']>=8-1e-7 and panel['minimum_edge_mm']>=25
    row=next(x for x in model['scenes']['assembly'] if x['id']=='wall-'+panel['wall'])
    assert row['mesh']!=model['unvented'][panel['wall']]['mesh']
if a.published_root:
    assert (out/'reference/RAIL-PLACEMENT.json').read_bytes()==(repo/'engineering/printed-5mm/p3/out/RAIL-PLACEMENT.json').read_bytes()
    preserved=json.loads((out/'reference/PRESERVATION.json').read_text())
    for f in preserved['files']:
        assert hashlib.sha256((repo/f['path']).read_bytes()).hexdigest()==f['sha256'],f['path']
    assert json.loads((repo/'project/release-state.json').read_text())['current_fullset_candidate']==preserved['current_fullset_candidate']
    for pid in ids:
        if not pid.startswith('wall-'):
            for ext in ('step','stl'):
                assert (out/ext/(pid+'.'+ext)).read_bytes()==(repo/'engineering/printed-5mm/p3/out'/ext/(pid+'.'+ext)).read_bytes(),pid
print('P4 vents and P3/R10 preservation verified')
