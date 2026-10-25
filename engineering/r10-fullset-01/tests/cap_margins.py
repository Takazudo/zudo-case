"""Measure cap margins from exported STEP; keep cap and fixed-bracket scopes separate."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import build
from fullset import geometry as g
import cadquery as cq

def wire(s):
    return max(s.Faces(),key=lambda f:f.Center().z).outerWire()

rows=[]
travel=json.loads((ROOT/'out/validation.json').read_text())['travel']
for kind in ['corner','lower']:
    file=ROOT/f'out/home-print/{kind}-cap-mm.step'
    cap=cq.importers.importStep(str(file)).val()
    # Adopted, unchanged pad outlines are deliberately independent expectations.
    pad=g.rr(-10,10,-7,7,0,1,2) if kind=='corner' else g.rr(-8,8,5,23,0,1,1.5)
    opening=g.slot(0,0 if kind=='corner' else 11.5,10.5,5.5,0,1,0 if kind=='corner' else 90)
    samples=[]
    for r in [r for r in travel if r['kind']==kind]:
        shift=r['offset_mm']
        moved=cap.translate((shift,0,0) if kind=='corner' else (0,11.5+shift,0))
        samples.append(dict(offset_mm=shift,cap_outline_usable_nominal=r['cap_outline_usable_nominal'],fixed_bracket_clear=r['fixed_bracket_clear'],pad_edge_margin_mm=wire(moved).distance(wire(pad)) if r['outside_mm3']<1e-6 else None,slot_outline_coverage_margin_mm=wire(moved).distance(wire(opening)) if r['uncovered_mm3']<1e-6 else None,bearing_area_mm2=r['bearing_area_mm2']))
    nominal=next(r for r in samples if r['offset_mm']==1)
    expected=(1,1.75) if kind=='corner' else (.5,.75)
    assert abs(nominal['pad_edge_margin_mm']-expected[0])<1e-6
    assert abs(nominal['slot_outline_coverage_margin_mm']-expected[1])<1e-6
    rows.append(dict(type=kind,export_step_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),sampled_cap_outline_range_mm=[min(r['offset_mm'] for r in samples if r['cap_outline_usable_nominal']),max(r['offset_mm'] for r in samples if r['cap_outline_usable_nominal'])],samples=samples))
result=dict(scope='CAD measurements from reimported STEP outer wires and adopted pad/slot geometry. 0.25mm samples, not a tolerance rating. Cap projection validity is separate from shaft collision with the fixed nominal bracket.',types=rows)
target=ROOT/'verification/cap-margins.json'
if '--check' in sys.argv:
    assert json.loads(target.read_text())==result,'Cap margin receipt differs'
else:
    target.write_text(json.dumps(result,indent=2)+'\n')
print('Exported cap margins verified:',[(r['type'],r['sampled_cap_outline_range_mm']) for r in rows])
