"""Nominal geometry checks, not physical qualification."""
import math
import cadquery as cq
from fitfix import io
from . import geometry as g

def overlaps(a,b):
    aa=io.bounds(a);bb=io.bounds(b)
    if any(min(aa['max'][k],bb['max'][k])-max(aa['min'][k],bb['min'][k])<1e-6 for k in range(3)):return 0.
    return a.intersect(b).Volume()

def check(shapes,items,out):
    checks=list(g.audits);collisions=[]
    # All guards and lid against panels, shimmed brackets, washers and unchanged
    # source PCB/spacers. Threads intentionally share nut envelopes and are
    # checked by bore/stack tests rather than treated as fused-material collisions.
    static=[i for i in items if i['id'] in shapes and not i['id'].startswith(('shaft-','head-','nut-','mount-bolt-','mount-nut-','rail-end-bolt-'))]
    for n,a in enumerate(static):
        for b in static[n+1:]:
            v=overlaps(shapes[a['id']],shapes[b['id']])
            if v>1e-5:collisions.append(dict(a=a['id'],b=b['id'],volume_mm3=v))
    checks.append(dict(check='all static solids pairwise positive overlap',passed=not collisions,collisions=collisions))
    travel=[]
    for kind in ['corner','lower']:
        pad=g.rr(-10,10,-7,7,0,1,2) if kind=='corner' else g.rr(-8,8,5,23,0,1,1.5)
        hole=(0,0) if kind=='corner' else (0,11.5)
        slot=g.slot(*hole,10.5,5.5,0,1,0 if kind=='corner' else 90)
        for n in range(-10,11):
            shift=n/4;u,v=(shift,0) if kind=='corner' else (0,11.5+shift)
            outline=g.outer_cap(u,v,0,1,kind,True);cap=g.outer_cap(u,v,0,1,kind)
            outside=outline.cut(pad).Volume();uncovered=slot.cut(outline).Volume();bearing=cap.intersect(pad.cut(slot)).Volume()
            travel.append(dict(kind=kind,offset_mm=shift,outside_mm3=outside,uncovered_mm3=uncovered,bearing_area_mm2=bearing,usable_nominal=outside<1e-6 and uncovered<1e-6))
        nominal=next(r for r in travel if r['kind']==kind and r['offset_mm']==1)
        checks.append(dict(check='nominal cap support '+kind,passed=nominal['usable_nominal']))
    checks.append(dict(check='local stepped web and ears',passed=all(len(shapes[f'lower-{f}-1'].Solids())==1 and overlaps(shapes[f'lower-{f}-0'],shapes[f'lower-{f}-1'])<1e-6 for f in ('left','right')),thin_ears_mm=1,local_web_mm=2))
    result=dict(scope='Nominal CAD; pairwise BRep checks exclude threaded hardware and source rail meshes; no physical result',passed=all(c.get('passed',True) for c in checks),checks=checks,travel_sample_step_mm=.25,travel=travel)
    io.write_json(out/'validation.json',result)
    return result
