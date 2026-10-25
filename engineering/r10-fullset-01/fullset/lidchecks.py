"""Reuse the merged M5 geometric checks against the R10 combined interface."""
import json
from pathlib import Path
from fitfix.geometry import Part,box
from fitfix import io
from lidm5.checks import fastener_checks,knob_zones
from .validation import overlaps

def validate(b,g,l,m,parts,sites,shapes,items,out):
    base=json.loads((Path(__file__).resolve().parents[2]/'r9-lid-m5-01/parameters.json').read_text())
    n=base['nut_source'];asm=base['assumptions']
    nut=dict(af_max=n['across_flats_max'],af_min=n['across_flats_min'],af_photo=n['product_photo_across_flats'],h_min=n['height_min'],h_max=n['height_max'],pitch=n['pitch'],corner_ratio=asm['nut_corner_ratio_e_over_s'])
    frames=[p for p in parts if p.group=='lid'];plate=shapes['lid-plate']
    stationary=[Part(i['id'],shapes[i['id']]) for i in items if i['id'] in shapes and not i['id'].startswith('lid-')]
    rails=[Part(i['id'],box(*[v for pair in zip(i['box'][:3],i['box'][3:]) for v in pair])) for i in items if i['role']=='rail']
    knobs=knob_zones(b,l,rails)
    result=fastener_checks(b,g,l,m,frames,plate,sites,stationary+rails,knobs,nut,asm)
    failed=[]
    for s in result:
        screw=next(r for r in s['screws'] if r['length']==10 and not r['washer'])
        ok=screw['passed'] and not s['head_collisions'] and not s['driver_column_collisions'] and not s['nut_envelope_collisions'] and s['insertion']['passed'] and s['min_wall_true']>=1.6-1e-4 and s['roof_thickness']>=1.5-1e-4 and s['effective_depth']>=5.5-1e-4 and s['anti_rotation']['min_truncated']['locks']
        if not ok:failed.append(s['frame']+'-'+s['site'])
    lift=[]
    for dz in (0,.25,.5,1,2,4,8,12,15,30,60):
        hits=[]
        for a in frames:
            for c in stationary+rails+knobs:
                v=overlaps(a.shape.translate((0,0,dz)),c.shape)
                if v>1e-5:hits.append(dict(frame=a.id,other=c.id,volume_mm3=v))
        lift.append(dict(dz=dz,collisions=hits))
    report=dict(passed=not failed and all(not s['collisions'] for s in lift),failed=failed,sites=result,lift_path_samples=lift,continuous_sweep_verified=False,rail_check='Conservative bounding envelopes of original mesh; original mesh rendered unchanged',knob_envelope='module panel2 + knob25, cables removed; provisional')
    io.write_json(out/'lid-checks.json',report);return report
