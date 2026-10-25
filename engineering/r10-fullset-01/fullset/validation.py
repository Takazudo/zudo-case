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
    static=[i for i in items if i['id'] in shapes and i['role']!='lid-hardware' and not i['id'].startswith(('shaft-','head-','nut-','mount-bolt-','mount-nut-','rail-end-bolt-'))]
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


def hanging(shapes,items,parameters,out):
    rows=[]
    for face in g.FACES:
        u,v=parameters['hanging_holes'][face];id='panel-'+face
        bore=g.world(g.disk(u,v,-3,1,2),face)
        access=g.world(g.disk(u,v,-11,5,2),face)
        hits=[]
        for i in items:
            if i['id']==id or i['id'] not in shapes:continue
            volume=overlaps(access,shapes[i['id']])
            if volume>1e-6:hits.append(dict(id=i['id'],volume_mm3=volume))
        bb=io.bounds(g.panel(face,10.5));lig=min(u-bb['min'][0],bb['max'][0]-u,v-bb['min'][1],bb['max'][1]-v)-2
        assert overlaps(bore,shapes[id])<1e-6 and lig>0
        rows.append(dict(part=id,face_uv=[u,v],diameter=4,edge_ligament_mm=lig,fixture_access_rod_assumption='D4, 11mm inward / 5mm outward from exterior',collisions=hits))
    # Lid central hole is far from the perimeter ledge; assembly access from above.
    lid=shapes['lid-plate'];bb=io.bounds(lid);u,v=parameters['hanging_holes']['lid'];tool=g.disk(u,v,bb['min'][2]-1,bb['max'][2]+5,2)
    hits=[i['id'] for i in items if i['id']!='lid-plate' and i['id'] in shapes and overlaps(tool,shapes[i['id']])>1e-6]
    rows.append(dict(part='lid-plate',face_uv=[u,v],diameter=4,edge_ligament_mm=min(bb['size'][:2])/2-2,collisions=hits,fixture_access_rod_assumption='D4,1mm below plate and5mm above; fixture before assembly'))
    result=dict(passed=all(not r['collisions'] for r in rows),holes=rows,supplier_approved=False)
    io.write_json(out/'hanging-hole-checks.json',result);return result


def joints(shapes,items,out):
    targets=[i for i in items if i['id'] in shapes and i['role'] not in ('fastener','lid-hardware','mountBolt','mountNut','railEndBolt')]
    hits=[]
    for i in items:
        if not i['id'].startswith(('shaft-','head-','nut-')):continue
        for j in targets:
            vol=overlaps(shapes[i['id']],shapes[j['id']])
            if vol>1e-5:hits.append(dict(fastener=i['id'],other=j['id'],volume_mm3=vol))
    # Source rail meshes are represented by conservative envelopes only in collision checks.
    rails=[(i['id'],g.box(*[v for pair in zip(i['box'][:3],i['box'][3:]) for v in pair])) for i in items if i['role']=='rail']
    rail_hits=[]
    for i in items:
        if i['id'] not in shapes or i['role'] not in ('guard','bracket','washer','lid','fastener'):continue
        for id,s in rails:
            vol=overlaps(shapes[i['id']],s)
            if vol>1e-5:rail_hits.append(dict(part=i['id'],rail_envelope=id,volume_mm3=vol))
    feet_min=min(io.bounds(shapes[i['id']])['min'][2] for i in items if i['id'].startswith('foot-'))
    heads_min=min(io.bounds(shapes[i['id']])['min'][2] for i in items if i['id'].startswith('head-floor'))
    tool_hits=[];frame_obstructions=[];bottom_first_obstructions=[]
    for face in g.FACES:
        for k,(u,v,ang,role) in enumerate(g.panel_holes(face)):
            if role=='rail':continue
            if role=='corner':u-=math.copysign(1,u)
            elif role=='lower':v+=1
            elif role=='floor-front':v-=math.copysign(1,v)
            else:u-=math.copysign(1,u)
            lap=face in ('left','right') and role=='lower' and abs(u)<.1
            ranges=[(2.4,22.4),(-31.5,-11.5)] if face=='floor' else [(-25.9,-5.9),(8 if lap else 7,28 if lap else 27)]
            for n0,n1 in ranges:
                tool=g.world(g.disk(u,v,n0,n1,5),face)
                for part in items:
                    id=part['id']
                    if id not in shapes or id.startswith('lid-') or id.endswith(f'{face}-{k}'):continue
                    volume=overlaps(tool,shapes[id])
                    if volume>1e-5:
                        row=dict(joint=f'{face}-{k}',part=id,volume_mm3=volume)
                        (frame_obstructions if part['cat']=='sourceFrame' else bottom_first_obstructions if face!='floor' and role=='lower' and id.startswith(('nut-floor-','shaft-floor-')) else tool_hits).append(row)
    samples=[('top-1-0',g.box(10,11,-169,-166,87,88),1),('top-1-0',g.box(10,11,-166,-164,87,88),1),('top-1-0',g.box(10,11,-166.5,-166,90,93),2)]
    walls=[]
    for id,probe,axis in samples:
        measured=io.bounds(shapes[id].intersect(probe))['size'][axis]
        walls.append(dict(part=id,axis=axis,measured_mm=measured,expected_mm=1))
    r=dict(passed=not hits and not rail_hits and not tool_hits and all(abs(w['measured_mm']-1)<1e-6 for w in walls) and heads_min>feet_min,
           sampled_top_wall_roof=walls,body_tool_assumption='D10 cylinders,20mm straight access; wall-to-bracket fasteners tightened before bottom fasteners; bottom tightened before source frame is installed',body_tool_collisions_in_selected_sequence=tool_hits,wall_tool_obstructions_if_bottom_installed_first=bottom_first_obstructions,tool_obstructions_with_source_frame=frame_obstructions,
fastener_collisions=hits,rail_envelope_collisions=rail_hits,bottom_head_z=heads_min,feet_z=feet_min,uncompressed_clearance_mm=heads_min-feet_min,hardware_envelopes_are_assumptions=True)
    io.write_json(out/'joint-checks.json',r);return r
