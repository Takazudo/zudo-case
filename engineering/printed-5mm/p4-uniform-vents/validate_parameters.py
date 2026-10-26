"""Negative schema and actual geometric rejection tests (independent of hash lock)."""
from pathlib import Path
import copy,json,sys
sys.path.insert(0,str(Path(__file__).parent/'source'))
from ventilation import validate,cut_wall,holes_expected
import cadquery as cq
p=json.loads((Path(__file__).parent/'source/parameters.json').read_text())
def reject(label,mutate):
    q=copy.deepcopy(p);mutate(q)
    try: validate(q)
    except (ValueError,KeyError,TypeError): print('rejected',label);return
    raise AssertionError(label)
reject('revision',lambda q:q.update(revision='P3-PRINTED-5MM-7U-RAILS'))
reject('pattern',lambda q:q['ventilation'].update(pattern='02'))
reject('missing vent',lambda q:q['ventilation']['centers']['left'].pop())
reject('duplicate vent',lambda q:q['ventilation']['centers']['left'].__setitem__(1,-132))
reject('outside wall',lambda q:q['ventilation']['centers']['front'].__setitem__(0,-200))
reject('floor vents',lambda q:q['ventilation']['centers'].update(floor=[0]))
reject('lid vents',lambda q:q['ventilation']['centers'].update(lid=[0]))
for key,value in [('width',4),('width',-1),('radius',float('nan')),('height',100),('minimum_hardware_clearance',0),('minimum_web',7)]:
    reject(f'{key}={value}',lambda q,k=key,v=value:q['ventilation'].__setitem__(k,v))
def check(name,passed,**kw):
    if not passed:raise ValueError(name)
wall=cq.Solid.makeBox(226.4,89.5,5,cq.Vector(-113.2,5,-5))
rows=holes_expected('front');rows[0]=(0,46,90,'lower')
try:cut_wall(wall,'front',rows,p,check)
except ValueError:print('rejected changed fastening coordinates')
else:raise AssertionError('changed fastening coordinates')
