"""Build the self-contained preview from build.py's meshes, without network access."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'source/model.json').read_text())
current=json.loads((ROOT/'source/parameters.json').read_text())
if d['revision']!='P5-PRINTED-5MM-TAB-JOINTS-J3' or d['parameters']!=current:
    raise SystemExit('Stale or wrong-variant scene; run the full P3 build')
s=(ROOT/'source/viewer-template.html').read_text()
assert s.count('__MODEL__')==1
s=s.replace('__MODEL__',json.dumps(d,separators=(',',':')))
(ROOT/'zudo-case-printed-5mm-p5-tab-joints.html').write_text(s)
print('Wrote standalone HTML:',len(s.encode()),'bytes')
