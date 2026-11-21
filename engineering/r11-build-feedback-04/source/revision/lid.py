"""Eight-piece lift-off lid with two-axis, screw-clamped overlap joints.

The aluminium plate retains R10's outline and eight M5 bolt holes; R11-02
removes its dedicated centre hanging hole. Each M5 screw clamps a corner
frame and a middle frame together.
At the same station, a second, horizontal M5 screw clamps the tall wall lap.
These horizontal screws connect lid pieces only: there is no lid/body lock.

Coordinates are the assembled case datum in mm (floor underside Z=0).
No slicer/printer settings are inferred from the ASA washer reference.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cadquery as cq

from .core import ROOT, P, W, D, H, T, box, fuse, disk, rr, part, hexprism, head, roundwasher, bounds


EPS = 1e-6


def _reference():
    """Use R10's selected t1/groove1.70 interface, not old R9 t1.0 fit0.3."""
    p = ROOT / 'reference' / 'r10-parameters.json'
    old = json.loads(p.read_text())
    b, g, l = old['body'], old['guard'], old['lid']
    ox = b['width'] / 2 + g['wall'] + g['fit_per_face'] + g['adhesive_per_face']
    oy = b['depth'] / 2 + g['wall'] + g['fit_per_face'] + g['adhesive_per_face']
    seat = b['height'] + g['wall']
    pz = seat + l['rise_to_plate_underside']
    inset = l['frame_wall'] + l['plate_edge_gap'] + old['m5']['plate_edge_to_axis']
    assert abs(ox - (W / 2 + P['guard']['wall'] + P['guard']['fit_per_face'])) < EPS
    assert abs(oy - (D / 2 + P['guard']['wall'] + P['guard']['fit_per_face'])) < EPS
    return dict(
        source=str(p.relative_to(ROOT)),
        source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        ox=ox, oy=oy, seat=seat, pz=pz,
        plate_x=2 * (ox - l['frame_wall'] - l['plate_edge_gap']),
        plate_y=2 * (oy - l['frame_wall'] - l['plate_edge_gap']),
        plate_t=l['plate_thickness'], plate_r=l['plate_corner_radius'],
        lip=pz + l['plate_thickness'] + l['top_lip'],
        front_station=ox * l['front_screw_fraction'],
        side_station=oy * l['side_screw_fraction'],
        inset=inset, hole_d=old['m5']['through_hole'],
        old_hanging_xy=old['hanging_holes']['lid'],
    )


def _edge(shape, face, r):
    """Local (s, inward distance, Z) to the assembled lid edge."""
    angle, offset = {
        'front': (0, (0, -r['oy'], 0)),
        'right': (90, (r['ox'], 0, 0)),
        'back': (180, (0, r['oy'], 0)),
        'left': (270, (-r['ox'], 0, 0)),
    }[face]
    return shape.rotate((0, 0, 0), (0, 0, 1), angle).translate(offset)


def _edge_point(s, n, z, face, r):
    if face == 'front': return [s, -r['oy'] + n, z]
    if face == 'right': return [r['ox'] - n, s, z]
    if face == 'back': return [-s, r['oy'] - n, z]
    return [-r['ox'] + n, -s, z]


def _hardware_to_edge(shape, face, r):
    # Hardware coordinates are (s, Z, outward-normal distance).
    return _edge(shape.moved(cq.Plane(origin=(0, 0, 0), xDir=(1, 0, 0), normal=(0, -1, 0)).location), face, r)


def _one(shape, id):
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= EPS:
        raise ValueError(f'{id}: expected one connected valid solid')
    return shape


def build_lid():
    r = _reference()
    wall = P['lid']['frame_wall']
    seat, pz, lip = r['seat'], r['pz'], r['lip']
    leaf = 1.5
    overlap_half = 10.0
    shoulder = 2.0
    seam = P['guard']['seam_clearance']
    ledge_depth = 8.0
    joint_ledge_depth = 14.0
    ledge_bottom = pz - 2 * leaf
    ledge_split = pz - leaf
    wall_axis_z = P['lid']['wall_joint_axis_z']
    locator_engagement = P['lid']['locator_engagement']
    locator_clearance = P['lid']['locator_clearance']
    locator_thickness = P['lid']['locator_thickness']
    bridge_height = 2.5
    # The body guard's inner return is 2.6 mm in from the metal exterior.
    inner_guard_x = W / 2 - T - P['guard']['fit_per_face'] - P['guard']['wall']
    inner_guard_y = D / 2 - T - P['guard']['fit_per_face'] - P['guard']['wall']
    locator_x = inner_guard_x - locator_clearance
    locator_y = inner_guard_y - locator_clearance
    locator_edges = P['lid']['locator_edges']
    parts = []
    corners = {k: [] for k in ('fl', 'fr', 'br', 'bl')}
    mids = {}
    joints = []
    edge_corner = {
        'front': {-1: 'fl', 1: 'fr'},
        'right': {-1: 'fr', 1: 'br'},
        'back': {-1: 'br', 1: 'bl'},
        'left': {-1: 'bl', 1: 'fl'},
    }

    def full_section(a, b, with_locator, locator_n, span_limit):
        sections = [
            box(a, b, 0, wall, seat, lip),
            box(a, b, 0, ledge_depth, ledge_bottom, pz),
        ]
        if with_locator:
            sections.append(box(a, b, 0, locator_n + locator_thickness, seat, seat + bridge_height))
            la, lb = max(a, -span_limit), min(b, span_limit)
            if lb > la + EPS:
                sections.append(box(la, lb, locator_n, locator_n + locator_thickness,
                                    seat - locator_engagement, seat + bridge_height))
        return fuse(sections)

    def signed_boxes(sign, lo, hi, n0, n1, z0, z1):
        a, b = sorted((sign * lo, sign * hi))
        return box(a, b, n0, n1, z0, z1)

    for face in ('front', 'right', 'back', 'left'):
        front_back = face in ('front', 'back')
        has_locator = face in locator_edges
        a = r['front_station'] if front_back else r['side_station']
        edge_half = r['ox'] if front_back else r['oy']
        locator_n = r['oy'] - locator_y if front_back else r['ox'] - locator_x
        span_limit = locator_x if front_back else locator_y
        middle = [full_section(-a + overlap_half + seam, a - overlap_half - seam,
                               has_locator, locator_n, span_limit)]
        for sign in (-1, 1):
            corner_id = edge_corner[face][sign]
            start, end = sorted((sign * (a + overlap_half), sign * edge_half))
            corner = [full_section(start, end, has_locator, locator_n, span_limit)]
            # Corner owns the outer wall and upper ledge over the 20 mm lap.
            corner.extend([
                signed_boxes(sign, a - overlap_half, a + overlap_half, 0, wall, seat, lip),
                signed_boxes(sign, a - overlap_half, a + overlap_half, 0, joint_ledge_depth, ledge_split, pz),
            ])
            # Middle owns the inner wall and lower ledge.  Its 2 mm shoulder
            # joins each leaf to the middle's main wall with a real shared face.
            middle.extend([
                signed_boxes(sign, a - overlap_half - shoulder, a + overlap_half,
                             wall, 2 * wall, seat, ledge_split),
                signed_boxes(sign, a - overlap_half - shoulder, a + overlap_half,
                             wall, joint_ledge_depth, ledge_bottom, ledge_split),
            ])
            if has_locator:
                # The 12 mm lift-off skirt stays inside the cavity, clear of
                # all four body walls.  Its short seams are held by both laps.
                corner.extend([
                    signed_boxes(sign, a + seam / 2, a + overlap_half,
                                 2 * wall, locator_n + locator_thickness, seat, seat + bridge_height),
                    signed_boxes(sign, a + seam / 2, a + overlap_half,
                                 locator_n, locator_n + locator_thickness,
                                 seat - locator_engagement, seat + bridge_height),
                ])
                middle.extend([
                    signed_boxes(sign, a - overlap_half - shoulder, a - seam / 2,
                                 wall, locator_n + locator_thickness, seat, seat + bridge_height),
                    signed_boxes(sign, a - overlap_half - shoulder, a - seam / 2,
                                 locator_n, locator_n + locator_thickness,
                                 seat - locator_engagement, seat + bridge_height),
                ])
            corners[corner_id].append(_edge(fuse(corner), face, r))
            s = sign * a
            xy = _edge_point(s, r['inset'], pz, face, r)
            outer_point = _edge_point(s, 0, wall_axis_z, face, r)
            inner_point = _edge_point(s, 2 * wall, wall_axis_z, face, r)
            joints.append(dict(
                id=f'lid-joint-{face}-{corner_id}', face=face, station_s=s,
                component_ids=[f'lid-corner-{corner_id}', f'lid-middle-{face}'],
                plate_axis=[xy[0], xy[1], pz], wall_axis=outer_point,
                wall_axis_inward=[inner_point[k] - outer_point[k] for k in range(3)],
                vertical_lap_mm=[2 * overlap_half, joint_ledge_depth, 2 * leaf],
                wall_lap_mm=[2 * overlap_half, 2 * wall, ledge_split - seat],
                plate_screw='M5x12', wall_screw='M5x12',
                plate_nut_side='inside below horizontal lap',
                wall_nut_side='inside lid', wall_washers='OD15 ID5 t1 each side',
            ))
        mids[face] = _edge(fuse(middle), face, r)

    frames = {f'lid-corner-{name}': fuse(shapes) for name, shapes in corners.items()}
    frames.update({f'lid-middle-{name}': shape for name, shape in mids.items()})
    # The body now has inside top ears, washers and nuts.  Their full slot
    # travel reaches Z90; bottom-open reliefs let this lid lift straight off.
    # Cut only the locating skirts.  The outer tall walls, bridge at Z92 and
    # plate ledges are untouched.
    locator_reliefs = []
    for face in locator_edges:
        front_back = face in ('front', 'back')
        locator_n = r['oy'] - locator_y if front_back else r['ox'] - locator_x
        stations = P['joint_stations']['front_back_x' if front_back else 'side_y']
        for station in stations:
            local_cut = box(station - 9.0, station + 9.0,
                            locator_n - .1, locator_n + locator_thickness + .1,
                            seat - locator_engagement - 1.0, 90.5)
            relief = _edge(local_cut, face, r)
            affected, removed = [], 0.0
            for id, shape in frames.items():
                volume = shape.intersect(relief).Volume()
                if volume > EPS:
                    frames[id] = shape.cut(relief).clean()
                    affected.append(id)
                    removed += volume
            center = _edge_point(station, locator_n, 0, face, r)
            locator_reliefs.append(dict(
                face=face, center_x_mm=_edge_point(station, locator_n, 0, face, r)[0],
                center_y_mm=center[1], local_station_mm=station,
                width_mm=18.0, bottom_open=True, bottom_z_mm=seat - locator_engagement,
                top_z_mm=90.5, full_body_washer_travel_top_z_mm=90.0,
                top_clearance_mm=.5, material_below_seat_remaining_mm=seat - 90.5,
                bridge_start_z_mm=seat, bridge_height_mm=bridge_height,
                affected_part_ids=affected, removed_volume_mm3=removed,
                cut_bounds_mm=bounds(relief),
            ))
    # Every matching hole is cut from BOTH overlapping pieces by the same axis.
    for j in joints:
        x, y, _ = j['plate_axis']
        vertical_cut = disk(x, y, ledge_bottom - 1, pz + 1, r['hole_d'] / 2)
        horizontal_cut = _hardware_to_edge(
            disk(j['station_s'], wall_axis_z, -2 * wall - 1, 1, r['hole_d'] / 2), j['face'], r)
        for id in j['component_ids']:
            frames[id] = frames[id].cut(vertical_cut).cut(horizontal_cut).clean()

    for id, shape in frames.items():
        label = id.removeprefix('lid-')
        parts.append(part(id, _one(shape, id), f'蓋枠 {label}', 'lidFrame', role='nylon',
                          note='連続した角／中央材。四辺の内側ガイド。M5板ねじ＋横ねじで重ね継ぎ。',
                          explode=[0, 0, 1], material='PA12-HP black candidate'))

    plate = rr(-r['plate_x'] / 2, r['plate_x'] / 2, -r['plate_y'] / 2, r['plate_y'] / 2,
               pz, pz + r['plate_t'], r['plate_r'])
    for j in joints:
        x, y, _ = j['plate_axis']
        plate = plate.cut(disk(x, y, pz - 1, pz + r['plate_t'] + 1, r['hole_d'] / 2))
    plate = plate.clean()
    parts.append(part('lid-plate', _one(plate, 'lid-plate'), '蓋アルミ板（R10外形・M5 8穴を維持／吊り穴なし）',
                      'lidMetal', role='metal', explode=[0, 0, 1.5],
                      material='A5052 1.5 mm black anodized candidate'))

    for j in joints:
        id, face, s = j['id'], j['face'], j['station_s']
        x, y, _ = j['plate_axis']
        plate_top = pz + r['plate_t']
        # Preserve the old Ø10×5 head envelope. A Ø15 washer here would hit
        # the raised plate lip, so the original no-washer top stack remains.
        vs = fuse([head(x, y, plate_top, plate_top + 5.0, 10.0),
                   disk(x, y, plate_top - 12.0, plate_top, 2.5)])
        angle = 0 if face in ('front', 'back') else 30
        vn = hexprism(x, y, ledge_bottom - 5.0, ledge_bottom, 8.0, angle, 2.5)
        parts.append(part(id + '-plate-screw', _one(vs, id), '蓋板 M5×12 ねじ', 'lidHardware',
                          role='fastener', explode=[0, 0, 1.6], hardware_envelope=True))
        parts.append(part(id + '-plate-nut', _one(vn, id), '蓋板 内側M5ナット', 'lidHardware',
                          role='fastener', explode=[0, 0, .8], hardware_envelope=True))
        hs = fuse([head(s, wall_axis_z, 1, 2.4, 12), disk(s, wall_axis_z, -11, 1, 2.5)])
        hn = hexprism(s, wall_axis_z, -9, -4, 8, 0, 2.5)
        for suffix, shape, label, role in (
            ('wall-screw', hs, '蓋壁 継ぎ目M5×12ねじ', 'fastener'),
            ('wall-nut', hn, '蓋壁 内側M5ナット', 'fastener'),
            ('wall-washer-outer', roundwasher(s, wall_axis_z, 0, 1), '蓋壁 外側丸ワッシャー', 'washer'),
            ('wall-washer-inner', roundwasher(s, wall_axis_z, -4, -3), '蓋壁 内側丸ワッシャー', 'washer'),
        ):
            parts.append(part(id + '-' + suffix, _one(_hardware_to_edge(shape, face, r), id + '-' + suffix),
                              label, 'lidHardware', role=role, explode=[0, 0, 1.0],
                              hardware_envelope=role == 'fastener',
                              material='black ASA reference geometry' if role == 'washer' else 'M5 assumed envelope'))

    metadata = dict(
        source=r['source'], source_sha256=r['source_sha256'],
        preserved_reference='R10-FULLSET-01 selected 7u40-t1-groove1p70-m5',
        plate_dimensions_mm=[r['plate_x'], r['plate_y'], r['plate_t']],
        plate_corner_radius_mm=r['plate_r'], plate_hole_diameter_mm=r['hole_d'],
        plate_holes_xy=[[j['plate_axis'][0], j['plate_axis'][1]] for j in joints],
        hanging_hole=None,
        removed_hanging_hole=dict(xy=r['old_hanging_xy'], diameter_mm=4,
                                  source_revision='R10-FULLSET-01', removed_in='R11-BUILD-FEEDBACK-02'),
        exterior_xy_mm=[2 * r['ox'], 2 * r['oy']], seat_z_mm=seat,
        plate_bottom_z_mm=pz, lip_top_z_mm=lip,
        locator=dict(edges=locator_edges, engagement_mm=locator_engagement,
                     clearance_mm=locator_clearance, thickness_mm=locator_thickness,
                     maximum_abs_x_mm=locator_x, maximum_abs_y_mm=locator_y,
                     bottom_z_mm=seat - locator_engagement,
                     inside_hardware_reliefs=locator_reliefs),
        counts=dict(nylon=8, aluminum=1, vertical_screws=8, horizontal_screws=8, nuts=16, round_washers=16),
        joints=joints,
        assumptions=[
            '20 mm overlap, two 1.5 mm horizontal leaves and two 1.5 mm wall leaves are new design choices.',
            'M5x12 length and the existing Ø10x5 top / Ø12x1.4 wall head envelopes require purchased-hardware confirmation.',
            'Four locating skirts: R11-04 adds left/right guides, keeping 12 mm engagement, 2 mm thickness and 0.7 mm nominal guard clearance.',
            'Eight bottom-open 18 mm skirt reliefs at body joint X±59.5 and Y±95 end at Z90.5, clearing the full inside-washer slot travel by 0.5 mm.',
            'No lid-to-body locks are added; horizontal M5 screws only join lid segments.',
            'R11-02 removes the dedicated central diameter4 hanging hole. Only the original outline and eight M5 bolt holes are preserved; the whole plate is intentionally different.',
        ],
        production_approved=False,
    )
    return parts, metadata


def _shared_planar_area(a, b):
    """BRep common of opposing faces, since solid common drops contact faces."""
    area = 0.0
    af = [(f, f.normalAt(), f.Center()) for f in a.Faces() if f.geomType() == 'PLANE']
    bf = [(f, f.normalAt(), f.Center()) for f in b.Faces() if f.geomType() == 'PLANE']
    for fa, na, ca in af:
        for fb, nb, cb in bf:
            if na.dot(nb) > -0.999999 or abs(na.dot(cb - ca)) > EPS:
                continue
            if fa.distance(fb) <= EPS:
                area += fa.intersect(fb).Area()
    return area


def _validate_plate_reference(plate, metadata):
    """Compare with R10 after filling only its dedicated centre Ø4 hole."""
    old_step = ROOT / 'reference' / 'r10-lid-plate.step'
    old_plate = cq.importers.importStep(str(old_step)).val()
    old_bounds, new_bounds = bounds(old_plate), bounds(plate)
    # The bundled manufacturing STEP has a translated datum. Align minima
    # without rotation or scale; a changed outline still fails the solid check.
    old_plate = old_plate.translate(tuple(new_bounds[k] - old_bounds[k] for k in range(3)))
    raw_difference = plate.cut(old_plate).Volume() + old_plate.cut(plate).Volume()
    removed = metadata['removed_hanging_hole']
    hx, hy = removed['xy']
    z0, z1 = new_bounds[2], new_bounds[5]
    plug = disk(hx, hy, z0, z1, removed['diameter_mm'] / 2)
    original_hole_occupancy = old_plate.intersect(plug).Volume()
    candidate_hole_occupancy = plate.intersect(plug).Volume()
    filled_reference = old_plate.fuse(plug).clean()
    fill_added = filled_reference.Volume() - old_plate.Volume()
    filled_difference = plate.cut(filled_reference).Volume() + filled_reference.cut(plate).Volume()
    width, depth, thickness = metadata['plate_dimensions_mm']
    outline = rr(-width/2, width/2, -depth/2, depth/2, z0, z1, metadata['plate_corner_radius_mm'])
    void_count = len(outline.cut(plate).Solids())
    bolt_checks = []
    for x, y in metadata['plate_holes_xy']:
        bore = disk(x, y, z0, z1, metadata['plate_hole_diameter_mm'] / 2)
        bolt_checks.append(dict(xy_mm=[x,y],diameter_mm=metadata['plate_hole_diameter_mm'],
                               original_occupied_volume_mm3=old_plate.intersect(bore).Volume(),
                               revised_occupied_volume_mm3=plate.intersect(bore).Volume()))
    checks = dict(
        reference_hanging_hole_is_central_diameter4=abs(hx)<EPS and abs(hy)<EPS and abs(removed['diameter_mm']-4)<EPS,
        reference_hanging_hole_was_empty=original_hole_occupancy<EPS,
        candidate_hanging_hole_is_filled=abs(candidate_hole_occupancy-plug.Volume())<EPS,
        reference_fill_adds_only_central_hole_volume=abs(fill_added-plug.Volume())<EPS,
        plate_matches_filled_r10_reference=filled_difference<EPS,
        exactly_eight_bolt_holes_remain=void_count==8 and len(bolt_checks)==8,
        all_original_bolt_holes_clear=all(c['original_occupied_volume_mm3']<EPS and c['revised_occupied_volume_mm3']<EPS for c in bolt_checks),
    )
    return dict(passed=all(checks.values()),checks=checks,
                raw_r10_symmetric_difference_mm3=raw_difference,
                filled_r10_symmetric_difference_mm3=filled_difference,
                central_hole_fill_volume_mm3=fill_added,remaining_void_count=void_count,
                bolt_hole_checks=bolt_checks,
                old_plate_source=str(old_step.relative_to(ROOT)),
                old_plate_sha256=hashlib.sha256(old_step.read_bytes()).hexdigest(),
                scope='R10 outline and eight bolt holes preserved after filling only the dedicated centre diameter4 hole; the full original plate shape is not claimed unchanged.')


def validate_lid(parts, metadata):
    """Exact BRep checks of the lid, not a physical-fit or load assertion."""
    collisions = []
    for i, a in enumerate(parts):
        ba = bounds(a['shape'])
        for b in parts[i + 1:]:
            bb = bounds(b['shape'])
            if any(ba[k + 3] <= bb[k] + EPS or bb[k + 3] <= ba[k] + EPS for k in range(3)):
                continue
            v = a['shape'].intersect(b['shape']).Volume()
            if v > EPS: collisions.append(dict(a=a['id'], b=b['id'], volume_mm3=v))
    ids = {p['id']: p for p in parts}
    contacts = []
    for j in metadata['joints']:
        a, b = [ids[id]['shape'] for id in j['component_ids']]
        contacts.append(dict(joint=j['id'], shared_contact_area_mm2=_shared_planar_area(a, b),
                             separation_mm=a.distance(b), overlap_volume_mm3=a.intersect(b).Volume()))
    bearing = []
    for j in metadata['joints']:
        c, mid = j['component_ids']
        stem = j['id']
        pairs = [
            (stem + '-plate-screw', 'lid-plate'),
            (stem + '-plate-nut', mid),
            (stem + '-wall-screw', stem + '-wall-washer-outer'),
            (stem + '-wall-washer-outer', c),
            (stem + '-wall-washer-inner', mid),
            (stem + '-wall-nut', stem + '-wall-washer-inner'),
        ]
        for a, b in pairs:
            bearing.append(dict(a=a, b=b, shared_contact_area_mm2=_shared_planar_area(ids[a]['shape'], ids[b]['shape'])))
    plate_reference = _validate_plate_reference(ids['lid-plate']['shape'], metadata)
    relief_checks = []
    for relief in metadata['locator']['inside_hardware_reliefs']:
        x0, y0, z0, x1, y1, z1 = relief['cut_bounds_mm']
        void = box(x0, x1, y0, y1, z0, z1)
        volume = sum(p['shape'].intersect(void).Volume() for p in parts if p['cat'] == 'lidFrame')
        relief_checks.append(dict(face=relief['face'], center_x_mm=relief['center_x_mm'],
                                  center_y_mm=relief['center_y_mm'],
                                  occupied_volume_mm3=volume))
    checks = dict(
        one_valid_solid_each=all(p['shape'].isValid() and len(p['shape'].Solids()) == 1 for p in parts),
        eight_connected_frame_pieces=sum(p['cat'] == 'lidFrame' for p in parts) == 8,
        no_pairwise_positive_overlap=not collisions,
        each_joint_has_shared_bearing_contact=all(j['separation_mm'] < EPS and j['shared_contact_area_mm2'] > 1 for j in contacts),
        every_fastener_has_bearing_contact=all(j['shared_contact_area_mm2'] > 1 for j in bearing),
        plate_outline_and_eight_bolt_holes_preserved_after_hanging_hole_removal=plate_reference['passed'],
        inside_hardware_reliefs_clear=all(r['occupied_volume_mm3'] < EPS for r in relief_checks),
    )
    return dict(passed=all(checks.values()), checks=checks, collisions=collisions, joint_contacts=contacts,
                fastener_bearing=bearing, plate_reference=plate_reference,
                locator_relief_checks=relief_checks,
                scope='Exact lid geometry and local contact only; no body integration, native slicing or physical testing.')


if __name__ == '__main__':
    ps, m = build_lid()
    print(json.dumps(dict(metadata=m, validation=validate_lid(ps, m)), ensure_ascii=False, indent=2))
