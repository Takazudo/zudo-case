"""Clearance against the unchanged 66-item R10 rail unit.

PCB solids are the exact R6 polygon extrusions, reconstructed from bundled,
unchanged KiCad contour points. The 52 source hardware items are the original
nominal cylinders/tubes/hexagons, including their bores. The six imported rails
retain their source meshes in the viewer; this validator uses their conservative
bounding boxes because those original meshes are not valid closed BReps.

No reference-to-reference pairs are requalified here. The check covers every
new body/lid component against every reference item. Zero-volume bearing-face
contacts and bores are not positive-volume collisions. An overlap with a rail
box is reported as an unresolved conservative-envelope overlap, never as an
exact mesh collision. All dimensions here remain design/source envelopes, not
physical inspection results or a structural/torque qualification.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import math

import cadquery as cq

from .core import ROOT, P, FACES, box, bounds

VOLUME_TOLERANCE = 1e-6
DISTANCE_TOLERANCE = 1e-6
NEAR_LIMIT = 1.0


def _cylinder(axis, a, b, center, radius, bore=0):
    a,b=sorted((a,b));c=list(center);c[axis]=a
    direction=cq.Vector(*[int(k==axis) for k in range(3)])
    s=cq.Solid.makeCylinder(radius,b-a,cq.Vector(*c),direction)
    if bore:
        c[axis]=a-1
        s=s.cut(cq.Solid.makeCylinder(bore,b-a+2,cq.Vector(*c),direction))
    return s.clean()


def _source_hex(a,b,y,z,af,height):
    assert abs((b-a)-height)<1e-5
    r=af/math.sqrt(3)
    wire=cq.Wire.makePolygon([cq.Vector(a,y+r*math.cos(k*math.pi/3),z+r*math.sin(k*math.pi/3)) for k in range(6)],close=True)
    s=cq.Solid.extrudeLinear(wire,[],cq.Vector(b-a,0,0))
    return s.cut(_cylinder(0,a-1,b+1,(0,y,z),2.5)).clean()


def _gap(a,b):
    return math.sqrt(sum(max(0,b[k]-a[k+3],a[k]-b[k+3])**2 for k in range(3)))


def _box_overlap(a,b):
    return all(min(a[k+3],b[k+3])-max(a[k],b[k])>DISTANCE_TOLERANCE for k in range(3))


@lru_cache(maxsize=1)
def _load_reference():
    source_file=ROOT/'reference/source-frame.json'
    contour_file=ROOT/'reference/pcb-contours.json'
    source=json.loads(source_file.read_text())
    bundle=json.loads(contour_file.read_text())
    reg=bundle['registration'];spec=bundle['source_hardware_parameters']
    def value(k):return spec[k]['value']
    refs=[];deviations=[]
    for item in source['items']:
        ident=item['id'];role=item['role'];bb=item['box']
        yc=(bb[1]+bb[4])/2;zc=(bb[2]+bb[5])/2
        method='exact original nominal CAD';basis='original R6 hardware primitive'
        if role=='rail':
            shape=box(bb[0],bb[3],bb[1],bb[4],bb[2],bb[5])
            method='conservative bounding box';basis='unchanged source mesh bounds; mesh not a closed valid BRep'
        elif role in ('fixer','padder'):
            if role=='fixer':kind='fixer7u';offset_u=offset_v=0.0
            else:
                row=int(ident.rsplit('row',1)[1]);placement=reg['padder_placements'][row]
                kind=placement['kind'];offset_u=placement['u'];offset_v=placement['v']
            contour=bundle['pcb_contours'][kind]
            def wire(points):
                uv=[(v,u) for u,v in points] if kind=='fixer7u' else points
                return cq.Wire.makePolygon([cq.Vector(bb[0],u+offset_u-reg['board_y0'],reg['pcb_top_z']-v-offset_v) for u,v in uv],close=True)
            shape=cq.Solid.extrudeLinear(wire(contour['outer']),[wire(p) for p in contour['cutouts']],cq.Vector(reg['pcb_thickness'],0,0))
            expected=contour['materialAreaMm2']*reg['pcb_thickness']
            if abs(shape.Volume()-expected)>1e-4:raise ValueError('Original PCB area mismatch: '+ident)
            basis='unchanged source KiCad polygon extrusion, all bores retained'
        elif role in ('innerSpacer','outerWasher'):
            shape=_cylinder(0,bb[0],bb[3],(0,yc,zc),value('nylonOuterDiameterMm')/2,value('nylonInnerDiameterMm')/2)
        elif role=='mountNut':
            shape=_source_hex(bb[0],bb[3],yc,zc,value('lockNutAcrossFlatsMm'),value('lockNutHeightMm'))
        elif role=='mountBolt':
            side=1 if (bb[0]+bb[3])>0 else -1
            seat=side*reg['mount_head_seat_x']
            shape=_cylinder(0,seat-side*value('mountHeadHeightMm'),seat,(0,yc,zc),value('mountHeadDiameterMm')/2).fuse(
                _cylinder(0,seat,seat+side*value('mountBoltLengthMm'),(0,yc,zc),2.5)).clean()
        elif role=='railEndBolt':
            side=1 if (bb[0]+bb[3])>0 else -1
            seat=side*reg['fixer_outside_x']
            shape=_cylinder(0,seat,seat+side*value('railEndHeadHeightMm'),(0,yc,zc),value('railEndHeadDiameterMm')/2).fuse(
                _cylinder(0,seat-side*value('railEndBoltLengthMm'),seat,(0,yc,zc),2.5)).clean()
        else:raise ValueError('Unhandled source role: '+role)
        if not shape.isValid():raise ValueError('Invalid reference shape: '+ident)
        actual=bounds(shape);delta=max(abs(a-b) for a,b in zip(bb,actual))
        if delta>1e-5:raise ValueError(f'Source placement changed: {ident}: {delta:g}mm')
        deviations.append(dict(id=ident,bounds_difference_mm=delta,
                               volume_difference_from_rounded_source_mm3=None if role=='rail' else abs(shape.Volume()-item['volume'])))
        refs.append(dict(id=ident,role=role,shape=shape,box=actual,method=method,basis=basis))
    if len(refs)!=66:raise ValueError(f'Expected 66 source items, got {len(refs)}')
    receipt=dict(source_count=len(refs),exact_cad_count=sum(r['role']!='rail' for r in refs),
                 conservative_rail_boxes=6,roles=dict(Counter(r['role'] for r in refs)),
                 source_provenance=source['provenance'],contour_provenance=bundle['sources'],
                 bundled_input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source_file,contour_file)},
                 maximum_placement_difference_mm=max(d['bounds_difference_mm'] for d in deviations),
                 source_reconstruction_checks=deviations,
                 source_hardware_is_nominal=True)
    return refs,receipt


def _nut_geometry(p,extra=0,radius=None):
    bb=bounds(p['shape']);center=[(bb[k]+bb[k+3])/2 for k in range(3)]
    normal=FACES[p['face']][3];axis=next(k for k,n in enumerate(normal) if n)
    transverse=[k for k in range(3) if k!=axis]
    if radius is None:
        radius=max(math.sqrt(sum((vertex.toTuple()[k]-center[k])**2 for k in transverse)) for vertex in p['shape'].Vertices())
    a,b=bb[axis],bb[axis+3]
    if normal[axis]>0:a-=extra
    else:b+=extra
    return _cylinder(axis,a,b,center,radius),center,radius


def _perpendicular_nut_pairs(parts):
    nuts=[p for p in parts if p['id'].startswith('nut-')]
    corners={};pairs=[]
    for p in nuts:
        if p.get('kind')!='corner':continue
        bb=bounds(p['shape']);c=[(bb[k]+bb[k+3])/2 for k in range(3)]
        key=(1 if c[0]>0 else -1,1 if c[1]>0 else -1,round(c[2],6))
        corners.setdefault(key,[]).append(p)
    for key,items in sorted(corners.items()):
        if len(items)!=2:raise ValueError('Expected two perpendicular corner nuts: '+str(key))
        items.sort(key=lambda p:p['face'] not in ('front','back'))
        pairs.append(('vertical-corner',items[0],items[1]))
    floor=[p for p in nuts if p.get('face')=='floor']
    used=set()
    for p in nuts:
        if p.get('kind')!='lower':continue
        _,c,_=_nut_geometry(p)
        def xy_gap(q):
            bb=bounds(q['shape']);d=[(bb[k]+bb[k+3])/2 for k in range(2)]
            return math.hypot(c[0]-d[0],c[1]-d[1])
        q=min(floor,key=xy_gap)
        if xy_gap(q)>12 or q['id'] in used:raise ValueError('Ambiguous bottom nut pair: '+p['id'])
        used.add(q['id']);pairs.append(('wall-floor',p,q))
    result=[];examples={}
    for kind,a,b in pairs:
        ar,_,_=_nut_geometry(a);br,_,_=_nut_geometry(b)
        record=dict(kind=kind,a=a['id'],b=b['id'],nut_intersection_mm3=a['shape'].intersect(b['shape']).Volume(),
                    nut_clearance_mm=a['shape'].distance(b['shape']),
                    full_rotation_envelope_intersection_mm3=ar.intersect(br).Volume(),
                    full_rotation_envelope_clearance_mm=ar.distance(br))
        result.append(record);examples.setdefault(kind,(a,b))
    tool_checks=[]
    for kind,(a,b) in examples.items():
        for diameter in (10,12):
            for inward in (1,2,5):
                for tool,target in ((a,b),(b,a)):
                    envelope,_,_=_nut_geometry(tool,extra=inward,radius=diameter/2)
                    tool_checks.append(dict(pair_kind=kind,tool_at=tool['id'],other_nut=target['id'],
                        hypothetical_tool_diameter_mm=diameter,inward_extension_beyond_nut_mm=inward,
                        intersection_mm3=envelope.intersect(target['shape']).Volume(),clearance_mm=envelope.distance(target['shape'])))
    return dict(pair_count=len(result),pairs=result,
                all_nut_pairs_have_positive_clearance=all(r['nut_clearance_mm']>DISTANCE_TOLERANCE for r in result),
                all_full_rotation_envelopes_have_positive_clearance=all(r['full_rotation_envelope_clearance_mm']>DISTANCE_TOLERANCE for r in result),
                minimum_nut_clearance_mm=min((r['nut_clearance_mm'] for r in result),default=None),
                minimum_full_rotation_clearance_mm=min((r['full_rotation_envelope_clearance_mm'] for r in result),default=None),
                hypothetical_tool_checks=tool_checks,
                tool_access_note='Nut rotation is checked separately from tool access. These hypothetical D10/D12 coaxial tool noses are not actual tool models. Generic sockets are not cleared. Hold nuts with a suitable slim wrench or pliers while tightening the exterior screw; wall nuts before floor nuts, rail unit last. Later inner-nut service may require removal of the rail unit.')


def validate_reference(parts):
    """Return JSON-safe validation data for a list of new body/lid CAD parts."""
    refs,receipt=_load_reference()
    reference_ids={r['id'] for r in refs}
    new=[p for p in parts if p.get('cat')!='sourceFrame' and p['id'] not in reference_ids]
    exact_overlaps=[];envelope_overlaps=[];contacts=[];near=[];unexpected_contacts=[]
    boolean_count=distance_count=0
    for p in new:
        pb=bounds(p['shape'])
        for r in refs:
            bb_gap=_gap(pb,r['box'])
            if bb_gap>NEAR_LIMIT:continue
            row=dict(part=p['id'],reference=r['id'],reference_method=r['method'])
            # Disjoint enclosing boxes prove separation without walking the
            # original fixer's thousands of contour edges. Record that distance
            # as a conservative bound, never as an exact closest-surface claim.
            if bb_gap>DISTANCE_TOLERANCE:
                near.append(dict(row,clearance_lower_bound_mm=bb_gap,clearance_method='distance between disjoint enclosing boxes'))
                continue
            volume=0.0
            if _box_overlap(pb,r['box']):
                volume=p['shape'].intersect(r['shape']).Volume();boolean_count+=1
                if volume>VOLUME_TOLERANCE:
                    issue=dict(row,intersection_mm3=volume)
                    (envelope_overlaps if r['role']=='rail' else exact_overlaps).append(issue)
                    continue
            distance=p['shape'].distance(r['shape']);distance_count+=1
            if distance<=DISTANCE_TOLERANCE:
                expected_panel='panel-right' if (r['box'][0]+r['box'][3])>0 else 'panel-left'
                expected=p['id']==expected_panel and r['role'] in ('innerSpacer','outerWasher')
                contact=dict(row,intersection_mm3=volume,intentional_original_mount_bearing_contact=expected)
                contacts.append(contact)
                if not expected:unexpected_contacts.append(contact)
            elif distance<=NEAR_LIMIT:near.append(dict(row,clearance_mm=distance,clearance_method='exact CAD distance'))
    nut_pairs=_perpendicular_nut_pairs(new)
    by_id={r['id']:r for r in refs};pad_clearances=[]
    for p in new:
        if not p['id'].startswith('body-corner-'):continue
        sx,sy=p['sx'],p['sy'];number=1 if sy<0 else 5
        for prefix in ('outer-washer','mount-nut'):
            ident=f'{prefix}-{sx}-{number}';r=by_id[ident]
            pad_clearances.append(dict(part=p['id'],reference=ident,clearance_mm=p['shape'].distance(r['shape']),method='exact nominal CAD distance'))
    expected_pairs=P['expected_counts']['perpendicular_nut_pairs']
    return dict(pass_=not exact_overlaps and not envelope_overlaps and not unexpected_contacts and nut_pairs['pair_count']==expected_pairs and nut_pairs['all_full_rotation_envelopes_have_positive_clearance'],
                scope='Every new body/lid solid versus all66 unchanged source-frame items. Exact nominal source CAD for60, conservative source mesh bounding boxes for6 rails. Original source-to-source pairs and physical properties are outside this check.',
                source_receipt=receipt,new_component_count=len(new),pair_count=len(new)*len(refs),
                broad_phase_pruned=True,exact_boolean_pair_count=boolean_count,near_distance_pair_count=distance_count,
                positive_volume_tolerance_mm3=VOLUME_TOLERANCE,distance_tolerance_mm=DISTANCE_TOLERANCE,
                exact_source_collisions=exact_overlaps,unresolved_conservative_rail_envelope_overlaps=envelope_overlaps,
                nominal_surface_contacts=contacts,unexpected_surface_contacts=unexpected_contacts,
                positive_clearances_or_bounds_at_most_1mm=near,
                corner_pad_to_original_rail_mount_clearances=pad_clearances,
                minimum_corner_pad_to_original_rail_mount_clearance_mm=min((r['clearance_mm'] for r in pad_clearances),default=None),
                perpendicular_nut_pairs=nut_pairs,
                expected_perpendicular_nut_pairs=expected_pairs,
                limitations=['Source hardware dimensions remain the original nominal/display envelopes, with their original uncertainty.',
                             'Rail box separation proves separation from that mesh; box overlap would require a separate mesh-level review.',
                             'No actual tool, printed-part tolerances, nylon strength, tightening torque, or assembled prototype is qualified.'])
