"""R11-04 regression audit of inside ears and the immutable R11-03 delta.

This is nominal BRep/contact validation, not strength, print, torque or physical
assembly qualification.  Exact STEP comparisons use the saved rigid transforms;
they never align a reference to the candidate's new bounding box.  Unexported
stock hardware has a separate, explicitly limited scene-envelope comparison.
"""
from __future__ import annotations

import hashlib
import json
import math
import cadquery as cq
from OCP.gp import gp_Trsf

from .core import ROOT, P, T, FACES, bounds, box, disk, slot, world, worldpoint, hexprism


EPS = 1e-6
VOLUME_TOL = 1e-5
BASELINE = ROOT / 'reference' / 'r11-03-baseline'


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _touching(a, b, tol=EPS):
    return all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) >= -tol for k in range(3))


class LocalContacts:
    """Opposing ORIGINAL planar faces, restricted to the current screw footprint.

    Clipping a whole solid can manufacture new contact faces.  Instead, select
    the real BRep faces at an explicitly specified stack interface and clip only
    their common planar area with a 15 mm circular footprint.  Contact at a
    different ear or elsewhere on a continuous corner cannot pass this test.
    """

    def __init__(self, parts):
        self.ids = {p['id']: p for p in parts}
        self.bb = {p['id']: bounds(p['shape']) for p in parts}
        self.faces = {}
        for p in parts:
            self.faces[p['id']] = [(f, f.normalAt(), f.Center())
                                   for f in p['shape'].Faces() if f.geomType() == 'PLANE']

    def at(self, a_ids, b_ids, face, uv, n, site, stage, radius=7.5):
        origin = cq.Vector(*worldpoint(face, uv[0], uv[1], n))
        normal = cq.Vector(*FACES[face][3])
        circle = cq.Wire.makeCircle(radius, origin, normal)
        footprint = cq.Face.makeFromWires(circle)
        window = bounds(footprint)
        mates = []

        def candidates(id):
            if id not in self.ids or not _touching(self.bb[id], window): return []
            return [(f, fn) for f, fn, fc in self.faces[id]
                    if abs(abs(fn.dot(normal)) - 1.0) < EPS
                    and abs(normal.dot(fc - origin)) < EPS]

        for aid in a_ids:
            for bid in b_ids:
                area = 0.0
                for af, an in candidates(aid):
                    for bf, bn in candidates(bid):
                        if an.dot(bn) > -1.0 + EPS: continue
                        common = af.intersect(bf)
                        if common.Area() > EPS:
                            area += common.intersect(footprint).Area()
                if area > EPS: mates.append(dict(a=aid, b=bid, area_mm2=area))
        total = sum(x['area_mm2'] for x in mates)
        return dict(site=site, stage=stage, a=list(a_ids), b=list(b_ids),
                    interface_n_mm=n, footprint_diameter_mm=2 * radius,
                    total_contact_area_mm2=total, mates=mates,
                    passed=total > 1.0)


def _expected_owner(row):
    face, kind = row['face'], row['kind']
    if kind == 'upper': return 'body-top-' + face
    if kind == 'lower': return 'body-bottom-' + face
    if face == 'floor':
        u, v = row['bolt_axis_uv']
        f = ('front' if v > 0 else 'back') if kind == 'floor-front' else ('right' if u > 0 else 'left')
        return 'body-bottom-' + f
    x, y, _ = row['axis_xyz']
    return f'body-corner-{1 if x > 0 else -1}-{1 if y > 0 else -1}'


def _overlaps(shape, candidates, cached_bounds=None):
    bb = bounds(shape)
    result = []
    for p in candidates:
        pb = cached_bounds[p['id']] if cached_bounds is not None else bounds(p['shape'])
        if not _touching(bb, pb): continue
        v = shape.intersect(p['shape']).Volume()
        if v > VOLUME_TOL: result.append(dict(part=p['id'], volume_mm3=v))
    return result


def validate_inner_ear_load_paths(parts, body_meta):
    """Check each of the 40 actual clamping paths, not visual pad overlays."""
    ids = {p['id']: p for p in parts}
    nylon = [p for p in parts if p['cat'] in ('corner', 'span')]
    brackets = [p for p in parts if p['cat'] == 'brackets']
    contacts = LocalContacts(parts)
    nylon_ids, bracket_ids = [p['id'] for p in nylon], [p['id'] for p in brackets]
    holes = {r['id']: r for r in body_meta['hole_table']}
    bearing, sites = [], []
    for row in body_meta['hardware_stacks']:
        site, face, uv = row['id'], row['face'], row['bolt_axis_uv']
        owner = row.get('inner_ear_owner')
        upper = row['kind'] == 'upper'
        expected_n = [-2.5, -1.5]
        panel, nut = 'panel-' + face, 'nut-' + site
        local_contacts = [
            contacts.at(['head-' + site], ['washer-out-' + site], face, uv, 3., site, 'head_to_outer_washer'),
            contacts.at(['washer-out-' + site], nylon_ids, face, uv, 2., site, 'outer_washer_to_outer_ear'),
            contacts.at(nylon_ids, [panel], face, uv, 0., site, 'outer_ear_to_sheet'),
            contacts.at([panel], [owner] if owner else [], face, uv, -1.5, site, 'sheet_to_integral_inner_ear'),
            contacts.at([owner] if owner else [], ['washer-in-' + site] if upper else bracket_ids,
                        face, uv, -2.5, site,
                        'integral_inner_ear_to_retained_washer' if upper else 'integral_inner_ear_to_bracket'),
        ]
        if upper:
            local_contacts.append(contacts.at(['washer-in-' + site], [nut], face, uv, -3.5, site,
                                              'retained_inside_washer_to_nut'))
        else:
            local_contacts.append(contacts.at(bracket_ids, [nut], face, uv, -4.5, site, 'bracket_to_nut'))
        bearing.extend(local_contacts)
        r = holes[site]
        slot_probe = world(slot(r['uc'], r['vc'], r['length'], r['width'],
                                expected_n[0], expected_n[1], r['angle']), face)
        pad_window = world(box(uv[0]-12, uv[0]+12, uv[1]-14, uv[1]+14,
                               expected_n[0], expected_n[1]), face)
        owner_part = ids.get(owner)
        slot_occupied = owner_part['shape'].intersect(slot_probe).Volume() if owner_part else None
        local_pad_volume = owner_part['shape'].intersect(pad_window).Volume() if owner_part else 0.0
        # The metal bracket fixes each lower/corner axis.  The shaft test uses
        # its actual current location and every crossed nylon/metal component.
        bore = world(disk(uv[0], uv[1], -4.5 if not upper else -3.5, 2., 2.5), face)
        crossed = nylon + brackets + [ids[panel]]
        axis_obstructions = _overlaps(bore, crossed, contacts.bb)
        checks = dict(
            owner_matches_expected_connector=owner == _expected_owner(row),
            owner_is_one_valid_nylon_solid=bool(owner_part and owner_part['cat'] in ('corner', 'span')
                                               and owner_part['shape'].isValid()
                                               and len(owner_part['shape'].Solids()) == 1),
            layer_metadata_matches_expected=bool(row.get('inner_ear_n') == expected_n
                                                 and row.get('inner_washer_replaced') is (not upper)),
            inside_washer_matches_joint_type=('washer-in-' + site in ids) == upper,
            actual_integral_material_present=local_pad_volume > 1.,
            full_slot_open_through_inside_pad=slot_occupied is not None and slot_occupied < VOLUME_TOL,
            actual_m5_axis_clear=not axis_obstructions,
            all_local_bearing_interfaces_present=all(c['passed'] for c in local_contacts),
        )
        sites.append(dict(id=site, face=face, kind=row['kind'], inside_owner=owner,
                          inside_layer_n_mm=expected_n, local_pad_volume_mm3=local_pad_volume,
                          full_slot_occupied_volume_mm3=slot_occupied,
                          m5_axis_obstructions=axis_obstructions,
                          bearing_check_count=len(local_contacts), checks=checks, passed=all(checks.values())))
    upper_count = sum(r['kind'] == 'upper' for r in body_meta['hardware_stacks'])
    bracketed_count = len(sites) - upper_count
    expected_bearings = 6 * (upper_count + bracketed_count)
    inside_washers = {p['id'] for p in parts if p['id'].startswith('washer-in-')}
    expected_inside_washers = {'washer-in-' + r['id'] for r in body_meta['hardware_stacks'] if r['kind'] == 'upper'}
    checks = dict(
        forty_sites_with_integral_inside_ears=len(sites) == 40 and body_meta.get('inner_ear_sites') == 40,
        eight_top_and_32_bracketed_sites=upper_count == 8 and bracketed_count == 32,
        every_local_load_path_passes=all(r['passed'] for r in sites),
        all_expected_bearing_checks_present=len(bearing) == expected_bearings == 240,
        only_eight_upper_inside_loose_washers_retained=inside_washers == expected_inside_washers and len(inside_washers) == 8,
        exactly_32_inside_washers_integrated=body_meta.get('integrated_inner_washer_replacements') == 32,
        twelve_connected_body_nylon_parts=len(nylon) == 12 and all(p['shape'].isValid() and len(p['shape'].Solids()) == 1 for p in nylon),
    )
    return dict(passed=all(checks.values()), checks=checks, site_count=len(sites),
                expected_bearing_contacts=expected_bearings, bearing_contacts=bearing, sites=sites,
                contact_method='Opposing original BRep faces on each specified stack plane, clipped to the local diameter15 screw footprint.',
                scope='Positive contact area proves a nominal continuous clamp path only. It does not establish nylon bearing strength, creep resistance or tightening torque.')


def localized_outer_lap_contacts(parts, body_meta):
    """Keep outer lap checks independent of new contacts on the inside."""
    from .body import corner_key
    lc = LocalContacts(parts)
    result = []
    for row in body_meta['hardware_stacks']:
        if row['kind'] not in ('lower', 'upper'): continue
        face, uv = row['face'], row['bolt_axis_uv']
        sx, sy = corner_key(face, -1 if uv[0] < 0 else 1)
        a = f'body-corner-{sx}-{sy}'
        b = 'body-' + ('top-' if row['kind'] == 'upper' else 'bottom-') + face
        rec = lc.at([a], [b], face, uv, 1., row['id'], 'outer_t1_to_t1_lap')
        result.append(dict(a=a, b=b, site=row['id'], interface_n_mm=1.,
                           contact_area_mm2=rec['total_contact_area_mm2'],
                           gap_mm=lc.ids[a]['shape'].distance(lc.ids[b]['shape']),
                           contact_method=rec['stage'], passed=rec['passed']))
    return result


def _baseline():
    receipt_path = BASELINE / 'copy-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    hashes = []
    for record in receipt['files']:
        p = BASELINE / record['path']
        actual = _digest(p) if p.is_file() else None
        hashes.append(dict(path=record['path'], sha256=actual, expected_sha256=record['sha256'],
                           passed=actual == record['sha256']))
    scene = json.loads((BASELINE / 'scene.json').read_text())
    manifest = json.loads((BASELINE / 'parts-manifest.json').read_text())
    shapes = {}
    step_hashes = []
    for rec in manifest['parts']:
        p = BASELINE / rec['files']['step']['path']
        actual = _digest(p)
        step_hashes.append(dict(id=rec['id'], sha256=actual, passed=actual == rec['files']['step']['sha256']))
        shape = cq.importers.importStep(str(p)).val()
        matrix = rec['transform']['export_to_assembly_4x4']
        # A gp_Trsf retains exact circles/planes.  CadQuery's generic matrix
        # wrapper can leave a rigid matrix tagged as gp_Other and reject it.
        axes = [cq.Vector(*(matrix[i][j] for i in range(3))) for j in range(3)]
        if any(abs(axes[i].dot(axes[j]) - (1. if i == j else 0.)) > 1e-8
               for i in range(3) for j in range(3)) or axes[0].cross(axes[1]).dot(axes[2]) < 1.-1e-8:
            raise ValueError('Baseline export transform is not a rigid rotation: ' + rec['id'])
        tr = gp_Trsf()
        tr.SetValues(*(matrix[i][j] for i in range(3) for j in range(4)))
        shapes[rec['id']] = shape.moved(cq.Location(tr))
    return scene, manifest, shapes, dict(
        root=str(BASELINE.relative_to(ROOT)), receipt_sha256=_digest(receipt_path),
        checks=hashes, step_manifest_hash_checks=step_hashes,
        passed=all(r['passed'] for r in hashes + step_hashes))


def _numeric_delta(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return max((_numeric_delta(x, y) for x, y in zip(a, b)), default=0.)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b)
    return 0. if a == b else float('inf')


def validate_baseline_delta(parts, body_meta, lid_meta, baseline=None):
    old, manifest, old_shapes, integrity = baseline or _baseline()
    ids = {p['id']: p for p in parts}
    old_scene = {p['id']: p for p in old['scenes']['assembly'] if p['cat'] != 'sourceFrame'}
    removed, added = set(old_scene) - set(ids), set(ids) - set(old_scene)
    revised_lid_ids = {f'lid-corner-{corner}' for corner in ('fl', 'fr', 'br', 'bl')} | {'lid-middle-left', 'lid-middle-right'}
    exact = []
    for rec in manifest['parts']:
        if rec['id'] == 'round-washer': continue
        id = rec['id']
        current = ids.get(id)
        old_shape = old_shapes[id]
        added_v = current['shape'].cut(old_shape).Volume() if current else None
        removed_v = old_shape.cut(current['shape']).Volume() if current else None
        difference = added_v + removed_v if current else None
        intended_change = id in revised_lid_ids
        passed = difference is not None and (added_v > 100. and current['shape'].Volume() > old_shape.Volume()
                                              if intended_change else difference < VOLUME_TOL)
        exact.append(dict(id=id, category=rec['category'], expectation='revised' if intended_change else 'unchanged',
                          added_volume_mm3=added_v, removed_volume_mm3=removed_v,
                          symmetric_difference_mm3=difference, passed=passed))
    # Stock hardware was not exported as manufacturing STEP in R11-03.  Match
    # every retained item, exact analytic bounds and rounded saved volume; keep
    # this result visibly separate from the 26 exact solid comparisons above.
    exported_ids = {r['id'] for r in manifest['parts']}
    envelopes = []
    for id, p in ids.items():
        if id in exported_ids: continue
        prior = old_scene.get(id)
        bbox_error = _numeric_delta(bounds(p['shape']), prior['box']) if prior else None
        volume_error = abs(p['shape'].Volume() - prior['volume_mm3']) if prior else None
        passed = bool(prior and p['cat'] == prior['cat'] and p.get('role') == prior.get('role')
                      and bbox_error < 1e-5 and volume_error < 1e-4
                      and len(p['shape'].Solids()) == prior['solids'] == 1)
        envelopes.append(dict(id=id, category=p['cat'], bbox_error_mm=bbox_error,
                              saved_volume_error_mm3=volume_error, passed=passed))
    old_stacks = {r['id']: r for r in old['body_metadata']['hardware_stacks']}
    stack_deltas = []
    for r in body_meta['hardware_stacks']:
        previous = old_stacks.get(r['id'], {})
        changed = [k for k, v in previous.items() if _numeric_delta(r.get(k), v) > 1e-8]
        stack_deltas.append(dict(id=r['id'], changed_original_fields=changed, passed=not changed and bool(previous)))
    old_holes = {r['id']: r for r in old['body_metadata']['hole_table']}
    hole_deltas = []
    for row in body_meta['hole_table']:
        previous = old_holes.get(row['id'])
        equal = previous == row
        slot_ok = row['angle'] is None or (abs(row['length']-15.5) < EPS and abs(row['width']-5.5) < EPS
                                            and abs(row['length']-row['old_length']-5.) < EPS)
        hole_deltas.append(dict(id=row['id'], unchanged=equal, slot_dimensions_preserved=slot_ok, passed=equal and slot_ok))
    loose = [p for p in parts if p.get('role') == 'washer']
    washer_reference = old_shapes['round-washer']
    # The recorded inverse transform for this reusable part returns it to its
    # centred modelling datum, so compare the centred primitive directly.
    from .core import roundwasher
    canonical = roundwasher(0, 0, 0, 1)
    washer_delta = canonical.cut(washer_reference).Volume() + washer_reference.cut(canonical).Volume()
    unchanged = [r for r in exact if r['expectation'] == 'unchanged']
    changed = [r for r in exact if r['expectation'] == 'revised']
    checks = dict(
        bundled_baseline_hashes_match=integrity['passed'],
        all_component_ids_retained=not removed and not added,
        six_sheets_exactly_unchanged=sum(r['category'] == 'aluminum' for r in unchanged) == 6
                                    and all(r['passed'] for r in unchanged if r['category'] == 'aluminum'),
        twelve_body_nylon_solids_exactly_unchanged=sum(r['id'].startswith('body-') for r in unchanged) == 12
                                                 and all(r['passed'] for r in unchanged if r['id'].startswith('body-')),
        front_back_lid_middle_spans_exactly_unchanged={r['id'] for r in unchanged if r['id'].startswith('lid-middle-')} == {'lid-middle-front', 'lid-middle-back'}
                                                   and all(r['passed'] for r in unchanged if r['id'].startswith('lid-middle-')),
        six_intended_lid_pieces_gain_material={r['id'] for r in changed} == revised_lid_ids and all(r['passed'] for r in changed),
        all_236_retained_stock_component_envelopes_unchanged=len(envelopes) == 236 and all(r['passed'] for r in envelopes),
        all_40_fastener_stack_coordinates_unchanged=len(stack_deltas) == 40 and all(r['passed'] for r in stack_deltas),
        all_50_body_sheet_holes_and_slot_extensions_unchanged=len(hole_deltas) == 50 and all(r['passed'] for r in hole_deltas),
        lid_joint_coordinates_unchanged=lid_meta['joints'] == old['lid_metadata']['joints'],
        reusable_loose_washer_exactly_unchanged=washer_delta < VOLUME_TOL,
        all_262_components_and_64_washers_retained=len(old_scene) == len(parts) == 262
                                                 and len(loose) == sum(p.get('role') == 'washer' for p in old_scene.values()) == 64,
    )
    return dict(passed=all(checks.values()), checks=checks, baseline_integrity=integrity,
                removed_ids=sorted(removed), added_ids=sorted(added), exact_solid_comparisons=exact,
                retained_stock_component_envelope_checks=envelopes, fastener_stack_checks=stack_deltas,
                sheet_hole_checks=hole_deltas, canonical_washer_symmetric_difference_mm3=washer_delta,
                old_new_counts=dict(old_components=len(old_scene), new_components=len(parts),
                                    old_loose_washers=sum(p.get('role') == 'washer' for p in old_scene.values()),
                                    new_loose_washers=len(loose)),
                scope='Six sheets, twelve body nylon parts, two front/back lid middle spans and six revised lid nylon parts: exact STEP/BRep differences in the saved assembly datum. Sixteen stock brackets, 216 retained fastener/washer items and four feet: exact candidate bounds versus saved R11-03 bounds plus rounded volume/one-solid checks; this is an envelope invariant, not a baseline BRep equality claim.')


def _convex_hull(points):
    pts = sorted(set(points))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) > 1 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) > 1 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _swept_top_nut(row, half_travel):
    u, v = row['bolt_axis_uv']
    n0, n1 = row['inner_nut_n']
    radius = 8 / math.sqrt(3)
    hull = _convex_hull([(u + radius*math.cos(k*math.pi/3),
                          v + end + radius*math.sin(k*math.pi/3))
                         for k in range(6) for end in (-half_travel, half_travel)])
    wire = cq.Wire.makePolygon([cq.Vector(x,y,n0) for x,y in hull], close=True)
    return world(cq.Solid.extrudeLinear(wire, [], cq.Vector(0,0,n1-n0)), row['face'])


def validate_access_and_top_travel(parts, body_meta, baseline=None):
    old, manifest, old_shapes, _ = baseline or _baseline()
    ids = {p['id']: p for p in parts}
    nylon = [p for p in parts if p['cat'] in ('corner', 'span')]
    old_nylon = [dict(id=p['id'], shape=old_shapes[p['id']]) for p in nylon]
    pads_and_lid = nylon + [p for p in parts if p['cat'] == 'lidFrame']
    cached_bounds = {p['id']: bounds(p['shape']) for p in parts}
    old_bounds = {p['id']: bounds(p['shape']) for p in old_nylon}
    rotational, tool_probes, top_sweeps = [], [], []
    for row in body_meta['hardware_stacks']:
        u, v = row['bolt_axis_uv']; n0,n1 = row['inner_nut_n']; face=row['face']
        # Circumscribed cylinder covers every hex orientation. Contact at its
        # bearing plane is intentional; any positive nylon volume is not.
        rotation = world(disk(u,v,n0,n1,8/math.sqrt(3)),face)
        clashes = _overlaps(rotation,nylon,cached_bounds)
        rotational.append(dict(site=row['id'], overlaps=clashes, passed=not clashes))
        for diameter in (10., 12.):
            # A deliberately simple *solid* access envelope; own nut/shaft are
            # not checked. This only probes nylon beside a hypothetical socket.
            tool = world(disk(u,v,n0-15,n1-1e-5,diameter/2),face)
            current = _overlaps(tool,nylon,cached_bounds)
            previous = _overlaps(tool,old_nylon,old_bounds)
            tool_probes.append(dict(site=row['id'], probe_diameter_mm=diameter,
                                    approach_extension_inward_mm=15.,
                                    current_nylon_obstructions=current, previous_nylon_obstructions=previous,
                                    current_obstructed=bool(current), previously_obstructed=bool(previous)))
        if row['kind'] != 'upper': continue
        hole = next(r for r in body_meta['hole_table'] if r['id'] == row['id'])
        travel = (hole['length']-hole['width'])/2
        sweep = _swept_top_nut(row,travel)
        sweep_clashes = _overlaps(sweep,pads_and_lid,cached_bounds)
        washer_sweep = world(slot(u,v,15.+2*travel,15.,-3.5,-2.5,90),face)
        washer_sweep_clashes = _overlaps(washer_sweep,pads_and_lid,cached_bounds)
        samples=[]
        for shift in (-travel,0.,travel):
            shifted_nut = world(hexprism(u,v+shift,n0,n1,8,0,2.5),face)
            shifted_washer = world(disk(u,v+shift,-3.5,-2.5,7.5,2.5),face)
            temporary = [ids[row['inner_ear_owner']], dict(id='sample-nut',shape=shifted_nut),
                         dict(id='sample-washer',shape=shifted_washer)]
            lc = LocalContacts(temporary)
            c = lc.at([row['inner_ear_owner']],['sample-washer'],face,[u,v+shift],-2.5,
                      row['id'],'top_integral_seat_to_retained_washer')
            w = lc.at(['sample-washer'],['sample-nut'],face,[u,v+shift],-3.5,
                      row['id'],'retained_top_washer_to_nut')
            samples.append(dict(bolt_center_v_mm=v+shift,ear_to_washer_bearing_area_mm2=c['total_contact_area_mm2'],
                                washer_to_nut_bearing_area_mm2=w['total_contact_area_mm2'],
                                passed=c['passed'] and w['passed']))
        # Independent area comparison explaining why the eight original top
        # washers remain. Move only a hypothetical nut to the original pad's
        # bearing face; it is never included in the deliverable assembly.
        hypothetical = world(hexprism(u,v,n0+1.,n1+1.,8,0,2.5),face)
        lc = LocalContacts([ids[row['inner_ear_owner']],dict(id='hypothetical-nut',shape=hypothetical)])
        direct = lc.at([row['inner_ear_owner']],['hypothetical-nut'],face,[u,v],-2.5,
                       row['id'],'hypothetical_direct_nut_on_slot')
        retained_area = samples[1]['washer_to_nut_bearing_area_mm2']
        top_sweeps.append(dict(site=row['id'],bolt_center_v_range_mm=[v-travel,v+travel],
                               continuous_nut_sweep_obstructions=sweep_clashes,
                               continuous_inside_washer_sweep_obstructions=washer_sweep_clashes,
                               top_washer_design_comparison=dict(
                                   retained_washer_to_nut_area_mm2=retained_area,
                                   hypothetical_direct_nut_to_slot_area_mm2=direct['total_contact_area_mm2'],
                                   direct_fraction_of_retained_area=direct['total_contact_area_mm2']/retained_area,
                                   note='Nominal AF8 nut geometry only; area comparison is not a material strength calculation.'),
                               bearing_samples=samples,passed=not sweep_clashes and not washer_sweep_clashes and all(x['passed'] for x in samples)))
    lid_collisions=[]
    lid=[p for p in parts if p['cat'] in ('lidFrame','lidMetal','lidHardware')]
    for p in nylon:
        for hit in _overlaps(p['shape'],lid,cached_bounds):
            lid_collisions.append(dict(body_part=p['id'],**hit))
    checks=dict(all_40_nut_rotation_envelopes_clear_of_body_nylon=len(rotational)==40 and all(r['passed'] for r in rotational),
                all_eight_top_nut_travel_sweeps_clear=len(top_sweeps)==8 and all(r['passed'] for r in top_sweeps),
                no_body_nylon_lid_overlap=not lid_collisions)
    newly_obstructed=[dict(site=r['site'],probe_diameter_mm=r['probe_diameter_mm']) for r in tool_probes
                      if r['current_obstructed'] and not r['previously_obstructed']]
    return dict(passed=all(checks.values()),checks=checks,nut_rotation_checks=rotational,
                top_slot_travel_checks=top_sweeps,lid_collisions=lid_collisions,
                hypothetical_axial_tool_probes=tool_probes,newly_obstructed_axial_tool_probes=newly_obstructed,
                assembly_note='Omit the 32 old inside washers at metal-bracketed sites; retain all eight top inside washers. Integral wall/floor L cheeks and corner returns must be offered to the sheets before clamping; fit wall nuts before the perpendicular floor nuts and install the independent rail unit last. Start all shared-joint screws loosely before final tightening. This sequence is a CAD-based proposal, not a physically demonstrated assembly.',
                tool_scope='D10/D12 cylinders are hypothetical axial tool-clearance probes against nylon only. The actual socket/wrench geometry and access with modules installed are unknown. Obstructed probes are reported, not disguised as a generic tool-fit pass; original-frame clearance and perpendicular-nut checks remain in reference_check.py.',
                top_bearing_scope='The eight top nuts retain their round inside washers. Ear-to-washer and washer-to-nut areas at both travel endpoints and the nominal centre are reported; positive area alone is not a bearing-strength or torque approval.')


def review_inner_ears(parts, body_meta, lid_meta):
    baseline = _baseline()
    paths = validate_inner_ear_load_paths(parts,body_meta)
    delta = validate_baseline_delta(parts,body_meta,lid_meta,baseline)
    access = validate_access_and_top_travel(parts,body_meta,baseline)
    checks=dict(local_load_paths=paths['passed'],r11_03_delta=delta['passed'],
                nut_and_lid_geometry=access['passed'])
    return dict(passed=all(checks.values()),checks=checks,load_paths=paths,baseline_delta=delta,access=access,
                production_approved=False,
                scope='Focused nominal CAD evidence for integral inside ears. Full component collisions, lid checks and original rail-frame clearances are separate checks in the same build. No physical assembly, material-strength or manufacturing approval is claimed.')


if __name__ == '__main__':
    from .body import build_body
    from .lid import build_lid
    body,bm=build_body();lid,lm=build_lid()
    result=review_inner_ears(body+lid,bm,lm)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
