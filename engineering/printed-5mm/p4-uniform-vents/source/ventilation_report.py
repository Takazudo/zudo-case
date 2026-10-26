"""Measure conservative hardware projections from the complete generated assembly."""
from pathlib import Path
import json,copy
import cadquery as cq
from ventilation import validate,rounded
ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/'source/parameters.json').read_text());v=validate(p)
m=json.loads((ROOT/'source/model.json').read_text());assembly=m['scenes']['assembly'];reports=m['ventilation']
for r in reports:
    side=r['wall'];long=side in ('left','right');axis=0 if long else 1;tangent=1-axis;sign=1 if side in ('right','back') else -1
    # Local U is reversed on left/back. Use world tangent coordinates for both cutter and rectangles.
    flip=-1 if side in ('left','back') else 1
    cuts=[rounded(flip*u,v) for u in r['centers']]
    keep=[]
    for row in assembly:
        b=row['box'];threshold=90 if long else 140;reach=112 if long else 164.4
        on_side=b[axis]>=threshold if sign>0 else b[axis+3]<=-threshold
        reaches=b[axis+3]>=reach if sign>0 else b[axis]<=-reach
        if row['group']!='lid' and row['cat'] in ('brackets','washers','hardware','railHardware','railSpacers') and on_side and reaches:
            rect=[b[tangent],b[2],b[tangent+3],b[5]]
            solid=cq.Solid.makeBox(rect[2]-rect[0],rect[3]-rect[1],7,cq.Vector(rect[0],rect[1],-6))
            keep.append({'id':row['id'],'world_tangent_z_rectangle':rect,'clearance_mm':min(c.distance(solid) for c in cuts)})
    assert len(keep)>20
    r['minimum_hardware_clearance_mm']=min(k['clearance_mm'] for k in keep)
    assert r['minimum_hardware_clearance_mm']>=v['minimum_hardware_clearance']-1e-7,(side,r)
    r['hardware_projections']=keep
    wall=next(x for x in assembly if x['id']=='wall-'+side)
    wall['ventilation']=r
    wall['note']=f"P4 Uniform: {r['count']} × 3×32mm R0.5. Open area {r['open_area_mm2']/100:.3f} cm². {len(r['holes'])} independent fastening holes. Hardware clearance {r['minimum_hardware_clearance_mm']:.3f}mm; screw-hole clearance {r['minimum_hole_clearance_mm']:.3f}mm. Prototype: thermal/strength/slicer unverified."
    old=copy.deepcopy(wall);old.update(m['unvented'][side]);old.pop('ventilation');old['note']='P3 unvented reference generated from inherited source; dedicated holes unchanged.'
    m['unvented'][side]=old
    local=[x for x in assembly if x['id']==wall['id'] or x['id'] in {k['id'] for k in keep}]
    m['scenes']['panel-'+side]=local
m['scenes']['inside-right']=m['scenes']['panel-right']
report={'revision':m['revision'],'pattern':v['pattern'],'total_vents':sum(r['count'] for r in reports),'total_open_area_mm2':sum(r['open_area_mm2'] for r in reports),'assembly_slots':sum(sum(h[3]!='rail' for h in r['holes']) for r in reports),'rail_holes':sum(sum(h[3]=='rail' for h in r['holes']) for r in reports),'panels':reports,'physical_validation':False}
assert (report['total_vents'],report['assembly_slots'],report['rail_holes'])==(82,28,10)
(ROOT/'VENTILATION.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'source/model.json').write_text(json.dumps(m,separators=(',',':')))
print('P4 ventilation:',[(r['wall'],r['minimum_hardware_clearance_mm'],r['minimum_hole_clearance_mm']) for r in reports])
