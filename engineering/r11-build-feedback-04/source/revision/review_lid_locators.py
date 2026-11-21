"""Independent nominal geometry checks for the R11-04 four-sided lid skirts.

Guide faces are measured on original BRep faces.  The straight lift-off check
uses a continuous vertical swept envelope, not sampled poses: the relevant
lower portion of each frame is combined with +Z extrusions of every upward
horizontal face.  Unsupported inclined/curved faces fail the sweep coverage
check rather than being silently skipped.  Hardware above every obstacle is
excluded by a separating Z plane.  No material, force or physical fit claim.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

from .core import ROOT, P, W, D, T, bounds, box, slot, world
from .reference_check import _load_reference
from .review_inner_ears import _swept_top_nut

EPS = 1e-6
VOLUME_TOL = 1e-5


def _overlap_bounds(a, b):
    return all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > EPS for k in range(3))


def _guide_band(face, x, y, thickness, bottom, top, span=None):
    """Independent case-datum bands, with outer faces toward the body walls."""
    if face in ('front', 'back'):
        lo, hi = (-x, x) if span is None else span
        yy = (-y, -y + thickness) if face == 'front' else (y - thickness, y)
        return box(lo, hi, *yy, bottom, top)
    lo, hi = (-y, y) if span is None else span
    xx = (-x, -x + thickness) if face == 'left' else (x - thickness, x)
    return box(*xx, lo, hi, bottom, top)


def _guide_geometry(parts, metadata):
    loc = metadata['locator']
    seat = metadata['seat_z_mm']
    bottom = seat - P['lid']['locator_engagement']
    thickness = P['lid']['locator_thickness']
    clearance = P['lid']['locator_clearance']
    gx = W/2 - T - P['guard']['fit_per_face'] - P['guard']['wall']
    gy = D/2 - T - P['guard']['fit_per_face'] - P['guard']['wall']
    x, y = gx - clearance, gy - clearance
    frames = [p for p in parts if p['cat'] == 'lidFrame']
    body_guards = [p for p in parts if p['id'].startswith(('body-top-', 'body-corner-'))]
    records = []
    for face in ('front', 'right', 'back', 'left'):
        band = _guide_band(face, x, y, thickness, bottom, seat)
        sections = [(p, p['shape'].intersect(band)) for p in frames]
        sections = [(p, s) for p, s in sections if s.Volume() > VOLUME_TOL]
        axis = 1 if face in ('front', 'back') else 0
        sign = -1 if face in ('front', 'left') else 1
        plane = sign * (y if axis == 1 else x)
        normal = cq.Vector(*[sign if k == axis else 0 for k in range(3)])
        face_area = 0.
        for p, _ in sections:
            for f in p['shape'].Faces():
                if f.geomType() != 'PLANE': continue
                n, c = f.normalAt(), f.Center().toTuple()
                if n.dot(normal) > 1.-EPS and abs(c[axis]-plane) < EPS:
                    face_area += f.intersect(band).Area()
        # Centre and both corner regions must each have the full design depth
        # and thickness. These stations avoid the intentional split seams and
        # body-fastener reliefs; all skirt faces are also measured above.
        span_limit = x if axis == 1 else y
        samples=[]
        for centre in (-span_limit+10., 0., span_limit-10.):
            probe = _guide_band(face, x, y, thickness, bottom, seat,
                                (centre-1., centre+1.))
            occupied = sum(p['shape'].intersect(probe).Volume() for p in frames)
            samples.append(dict(station_mm=centre, expected_volume_mm3=probe.Volume(),
                                occupied_volume_mm3=occupied,
                                passed=abs(occupied-probe.Volume()) < VOLUME_TOL))
        gaps=[]
        for p, s in sections:
            gap=min(s.distance(q['shape']) for q in body_guards)
            gaps.append(dict(part_id=p['id'], clearance_to_body_upper_guards_mm=gap))
        min_gap=min((g['clearance_to_body_upper_guards_mm'] for g in gaps),default=None)
        record=dict(face=face, outer_guide_coordinate_mm=plane,
                    guide_normal=list(normal.toTuple()), guide_face_area_mm2=face_area,
                    engaged_material_volume_mm3=sum(s.Volume() for _,s in sections),
                    part_ids=[p['id'] for p,_ in sections],
                    engagement_z_mm=[bottom,seat], thickness_mm=thickness,
                    minimum_clearance_to_body_upper_guards_mm=min_gap,
                    full_depth_probe_checks=samples, part_clearances=gaps)
        record['passed']=(face_area>100. and len(sections)>=3 and all(s['passed'] for s in samples)
                          and min_gap is not None and min_gap>=clearance-EPS)
        records.append(record)
    checks=dict(
        four_locator_edges_declared=set(loc['edges'])=={'front','right','back','left'},
        physical_guide_faces_present_on_all_four_edges=all(r['passed'] for r in records),
        all_eight_lid_frames_are_single_connected_solids=len(frames)==8 and all(len(p['shape'].Solids())==1 and p['shape'].isValid() for p in frames),
        metadata_matches_independent_nominal_coordinates=abs(loc['maximum_abs_x_mm']-x)<EPS
            and abs(loc['maximum_abs_y_mm']-y)<EPS and abs(loc['bottom_z_mm']-bottom)<EPS
            and abs(loc['thickness_mm']-thickness)<EPS and abs(loc['clearance_mm']-clearance)<EPS,
        eight_bottom_open_fastener_reliefs_present=len(loc['inside_hardware_reliefs'])==8
            and all(r['bottom_open'] and abs(r['width_mm']-18.)<EPS for r in loc['inside_hardware_reliefs'])
            and all(sum(r['face']==face for r in loc['inside_hardware_reliefs'])==2 for face in loc['edges']),
    )
    return dict(passed=all(checks.values()), checks=checks, edges=records,
                body_guard_inner_half_extents_mm=[gx,gy], locator_outer_half_extents_mm=[x,y],
                design_clearance_mm=clearance,
                scope='Original guide faces and exact BRep sections below the seating plane; probe volumes confirm continuous 12 mm engagement away from designed seams and reliefs. Clearance is geometric, not manufacturing fit.')


def _sweep_pieces(shape, lift):
    """Exact vertical sweep union for orthogonal planes/vertical cylinders."""
    pieces=[shape]
    unsupported=[]
    upward=0
    for index, f in enumerate(shape.Faces()):
        kind=f.geomType()
        if kind=='PLANE':
            nz=f.normalAt().z
            if abs(nz)<EPS: continue
            if abs(abs(nz)-1.)>EPS:
                unsupported.append(dict(face=index,kind=kind,normal_z=nz));continue
            if nz>0:
                prism=cq.Solid.extrudeLinear(f.outerWire(),f.innerWires(),cq.Vector(0,0,lift))
                if not prism.isValid(): unsupported.append(dict(face=index,kind=kind,error='Invalid extrusion'))
                else: pieces.append(prism);upward+=1
        elif kind=='CYLINDER':
            surf=BRepAdaptor_Surface(f.wrapped)
            if abs(abs(surf.Cylinder().Axis().Direction().Z())-1.)>EPS:
                unsupported.append(dict(face=index,kind=kind,error='Nonvertical cylinder'))
        else:
            unsupported.append(dict(face=index,kind=kind,error='Unsupported sweep face'))
    return pieces,dict(upward_face_extrusions=upward,unsupported_faces=unsupported,
                       passed=not unsupported and upward>0)


def _straight_lift(parts, body_meta, lid_meta):
    refs, source_receipt=_load_reference()
    body=[dict(id=p['id'],shape=p['shape'],box=bounds(p['shape']),
               method='Exact current body CAD') for p in parts if not p['cat'].startswith('lid')]
    source=[dict(id=r['id'],shape=r['shape'],box=r['box'],method=r['method']) for r in refs]
    travel=[]
    for row in body_meta['hardware_stacks']:
        if row['kind']!='upper':continue
        hole=next(h for h in body_meta['hole_table'] if h['id']==row['id'])
        half=(hole['length']-hole['width'])/2
        nut=_swept_top_nut(row,half)
        u,v=row['bolt_axis_uv']
        washer=world(slot(u,v,15.+2*half,15.,-3.5,-2.5,90),row['face'])
        for kind,shape in (('nut',nut),('washer',washer)):
            travel.append(dict(id='full-upper-travel-'+kind+'-'+row['id'],shape=shape,
                               box=bounds(shape),method='Continuous body fastener adjustment envelope'))
    obstacles=body+source+travel
    max_obstacle_z=max(r['box'][5] for r in obstacles)
    lid=[p for p in parts if p['cat'].startswith('lid')]
    min_lid_z=min(bounds(p['shape'])[2] for p in lid)
    lift=max_obstacle_z-min_lid_z+.5
    frames=[p for p in lid if p['cat']=='lidFrame']
    nonframes=[p for p in lid if p['cat']!='lidFrame']
    higher=[dict(id=p['id'],min_z_mm=bounds(p['shape'])[2],
                 passed=bounds(p['shape'])[2]>=max_obstacle_z-EPS) for p in nonframes]
    # Anything above the highest obstacle can only move farther away. Clip
    # the frames 0.001 mm above that plane, preserving all potentially
    # interfering material while excluding irrelevant horizontal bolt bores.
    cutter=box(-W,W,-D,D,min_lid_z-1,max_obstacle_z+.001)
    sweeps=[];collisions=[];tests=0
    for p in frames:
        lower=p['shape'].intersect(cutter)
        if lower.Volume()<VOLUME_TOL:
            sweeps.append(dict(part=p['id'],pieces=0,passed=True,reason='Entire part above obstacles'));continue
        pieces,coverage=_sweep_pieces(lower,lift)
        local_hits=[]
        for index,piece in enumerate(pieces):
            bb=bounds(piece)
            for obstacle in obstacles:
                if not _overlap_bounds(bb,obstacle['box']):continue
                tests+=1
                volume=piece.intersect(obstacle['shape']).Volume()
                if volume>VOLUME_TOL:
                    hit=dict(part=p['id'],sweep_piece=index,obstacle=obstacle['id'],
                             obstacle_method=obstacle['method'],intersection_mm3=volume)
                    local_hits.append(hit);collisions.append(hit)
        sweeps.append(dict(part=p['id'],pieces=len(pieces),coverage=coverage,
                           overlaps=local_hits,passed=coverage['passed'] and not local_hits))
    checks=dict(all_nonframe_lid_items_above_obstacles=all(x['passed'] for x in higher),
                all_eight_frame_sweeps_covered_and_clear=len(sweeps)==8 and all(x['passed'] for x in sweeps),
                body_upper_adjustment_envelopes_included=len(travel)==16,
                all_source_items_included=len(source)==66,
                end_pose_is_fully_above_obstacles=min_lid_z+lift>max_obstacle_z+EPS)
    return dict(passed=all(checks.values()),checks=checks,translation_axis=[0,0,1],
                translation_range_mm=[0,lift],highest_obstacle_z_mm=max_obstacle_z,
                lowest_closed_lid_z_mm=min_lid_z,clearance_after_full_lift_mm=.5,
                exact_boolean_checks=tests,frame_sweeps=sweeps,collisions=collisions,
                excluded_above_plane_items=higher,body_component_count=len(body),
                source_item_count=len(source),source_exact_cad_count=source_receipt['exact_cad_count'],
                conservative_rail_envelopes=source_receipt['conservative_rail_boxes'],
                continuous_upper_fastener_travel_envelopes=len(travel),
                scope='Continuous straight +Z union sweep, reversible for lowering; lower frame solids plus all upward planar-face extrusions. Exact nominal body and 60 source solids, conservative boxes for six rails, plus full upper nut/washer adjustment envelopes. No tilted removal, tool access, tolerances or physical fit qualification.')


def review_lid_locators(parts, body_meta, lid_meta):
    start=time.time()
    guides=_guide_geometry(parts,lid_meta)
    lift=_straight_lift(parts,body_meta,lid_meta)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        ROOT/'parameters.json',ROOT/'revision/lid.py',ROOT/'revision/body.py',
        ROOT/'revision/review_lid_locators.py',ROOT/'revision/review_inner_ears.py',
        ROOT/'reference/source-frame.json',ROOT/'reference/pcb-contours.json')}
    return dict(revision=P['revision'],passed=guides['passed'] and lift['passed'],
                checks=dict(four_sided_guides=guides['passed'],straight_lift_off=lift['passed']),
                guides=guides,straight_lift_off=lift,input_hashes=hashes,
                elapsed_seconds=time.time()-start,production_approved=False,
                scope='Nominal geometry only; additional lateral guidance does not establish a durability, strength or transport-retention rating.')


if __name__=='__main__':
    from .body import build_body
    from .lid import build_lid
    body,bm=build_body();lid,lm=build_lid()
    result=review_lid_locators(body+lid,bm,lm)
    out=ROOT/'out';out.mkdir(exist_ok=True)
    (out/'lid-locator-review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
    print(json.dumps(dict(passed=result['passed'],checks=result['checks'],
                         guides=result['guides']['checks'],lift=result['straight_lift_off']['checks'],
                         collisions=result['straight_lift_off']['collisions'],
                         elapsed_seconds=result['elapsed_seconds']),indent=2))
    raise SystemExit(0 if result['passed'] else 1)
