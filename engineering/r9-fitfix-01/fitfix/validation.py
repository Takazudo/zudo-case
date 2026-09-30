"""Nominal geometric tests. No load, adhesion or physical-fit certification."""
from dataclasses import replace
import math
import cadquery as cq
from .geometry import *
from .io import bounds

THRESHOLD_MM3=1e-5

def overlap(a,b):
    aa,bb=bounds(a),bounds(b)
    if any(min(aa['max'][i],bb['max'][i])-max(aa['min'][i],bb['min'][i])<1e-8 for i in range(3)):
        return 0.0
    return max(0.0,a.intersect(b).Volume())

def pairs(left,right=None):
    bad=[];tests=0;candidate_tests=0
    for n,a in enumerate(left):
        rr=left[n+1:] if right is None else right
        for b in rr:
            tests+=1
            v=overlap(a.shape,b.shape)
            if v>THRESHOLD_MM3:bad.append(dict(a=a.id,b=b.id,intersection_mm3=v))
    return dict(pair_count=tests,collisions=bad,passed=not bad)

def contact_area_z(a,b,z):
    aa=[f for f in a.Faces() if abs(f.BoundingBox().zmin-z)<1e-6 and abs(f.BoundingBox().zmax-z)<1e-6]
    bb=[f for f in b.Faces() if abs(f.BoundingBox().zmin-z)<1e-6 and abs(f.BoundingBox().zmax-z)<1e-6]
    return sum(max(0.,fa.intersect(fb).Area()) for fa in aa for fb in bb)

def check_flat_walls(b,g):
    """Measure major flat thicknesses by BREP intersection, not parameter names."""
    t,q,m=g.wall,g.gap,b.metal
    s=guard_section(b,g,30)
    probes={
        'outer_wall':box(q-.1,q+t+.1,10,20,-4,-2),
        'inner_return':box(-m-q-t-.1,-m-q+.1,10,20,-4,-2),
        'roof':box(-m+.2,-.2,10,20,-.1,t+.1)}
    areas={'outer_wall':20.,'inner_return':20.,'roof':(m-.4)*10}
    values={name:s.intersect(p).Volume()/areas[name] for name,p in probes.items()}
    bottom=guard_section(b,g,30,'bottom')
    values['bottom_flange']=bottom.intersect(box(-4,-2,10,20,-t-.1,.1)).Volume()/20
    values['bottom_outer_wall']=bottom.intersect(box(q-.1,q+t+.1,10,20,2,4)).Volume()/20
    if any(abs(v-t)>1e-6 for v in values.values()):raise AssertionError(values)
    return values

def validate_variant(b,g,l,guards,lids,hardware,rail_meshes):
    fixed=body_envelopes(b)
    result={'guard_vs_all_5_solid_plate_envelopes':pairs(guards,fixed),
            'guard_vs_guard':pairs(guards),
            'lid_vs_guards_and_plates':pairs(lids,guards+fixed),
            'lid_vs_lid':pairs(lids),
            'guard_vs_reference_hardware':pairs(guards,hardware),
            'lid_vs_reference_hardware':pairs(lids,hardware),
            'flat_wall_measurements_mm':check_flat_walls(b,g)}
    i=interface(b,g,l);top=guard_perimeter(b,g)
    frame=[p for p in lids if p.group=='lid']
    actual_top=[p for p in guards if '-top-' in p.id]
    seating=[dict(part=p.id,area_mm2=sum(contact_area_z(p.shape,q.shape,i['guard_top_z_mm']) for q in actual_top)) for p in frame]
    if any(x['area_mm2']<=0 for x in seating):raise AssertionError(('No lid support',seating))
    # Hard bearing of roof on metal: no gasket or floating body-guard datum.
    roof_support=sum(contact_area_z(q.shape,p.shape,b.height) for q in actual_top for p in fixed if p.id!='body-bottom')
    if roof_support<=0:raise AssertionError('Top guard has no roof support')
    result['seating']={'lid_to_guard_contact_area_mm2':seating,'guard_to_metal_support_area_mm2':roof_support,
                       'lid_seat_z_mm':i['lid_seat_z_mm'],'actual_guard_top_z_mm':bounds(top)['max'][2],
                       'vertical_gap_mm':i['lid_seat_z_mm']-bounds(top)['max'][2]}
    # Sampling plus Z-disjoint proof AFTER 15 mm; not continuous collision detection.
    fixed_all=guards+fixed+hardware+rail_meshes
    lifts=[]
    for rise in [0,.25,.5,.75,*range(1,16)]:
        moving=[Part(p.id,p.shape.translate((0,0,rise)),group=p.group) for p in lids]
        r=pairs(moving,fixed_all);lifts.append(dict(rise_mm=rise,**r))
    min_moving=min(bounds(p.shape)['min'][2] for p in lids)
    max_fixed=max(bounds(p.shape)['max'][2] for p in fixed_all)
    result['lift_path']={'sampled_positions_mm':[r['rise_mm'] for r in lifts],
                         'pair_count':sum(r['pair_count'] for r in lifts),
                         'collisions':[dict(rise_mm=r['rise_mm'],**c) for r in lifts for c in r['collisions']],
                         'after_15mm_z_disjoint':min_moving+15>max_fixed,
                         'continuous_sweep_verified':False,
                         'rail_representation':'source STL world AABB (conservative envelope), not exact solid'}
    if not result['lift_path']['after_15mm_z_disjoint']:raise AssertionError('Lift sampling does not clear stationary Z range')
    bad=[name for name,value in result.items() if isinstance(value,dict) and value.get('passed') is False]
    if result['lift_path']['collisions']:bad.append('lift_path')
    result['passed']=not bad;result['failed_checks']=bad
    return result


def validate_mutations(b,g,l):
    """Allowances and thickness never silently shave the retained walls."""
    results=[]
    for wall in (1.,1.2):
        for fit,adhesive in ((.1,0),(.15,.15),(.25,.15),(.35,.25)):
            gg=replace(g,wall=wall,fit_per_face=fit,adhesive_per_face=adhesive)
            ii=interface(b,gg,l);measure=check_flat_walls(b,gg)
            top=guard_perimeter(b,gg);ll,_=lid_parts(b,gg,l)
            body=body_envelopes(b)
            ints=guard_instances(guard_parts(b,gg))
            check=pairs(ints,body)
            lidcheck=pairs(ll,ints+body)
            ok=check['passed'] and lidcheck['passed'] and abs(bounds(top)['max'][2]-ii['lid_seat_z_mm'])<1e-6
            results.append(dict(wall_mm=wall,fit_mm=fit,adhesive_mm=adhesive,measurements=measure,
                                lid_seat_z_mm=ii['lid_seat_z_mm'],passed=ok))
    if not all(r['passed'] for r in results):raise AssertionError(results)
    # Change metal thickness and case height independently (plate/ref hardware out of scope here).
    for bb in (replace(b,metal=2.0),replace(b,height=96.0)):
        gp=guard_instances(guard_parts(bb,g));lp,_=lid_parts(bb,g,l);ii=interface(bb,g,l)
        ok=pairs(gp,body_envelopes(bb))['passed'] and pairs(lp,gp+body_envelopes(bb))['passed']
        results.append(dict(body=vars(bb),interface=ii,passed=ok))
    if not all(r['passed'] for r in results):raise AssertionError(results)
    return results
