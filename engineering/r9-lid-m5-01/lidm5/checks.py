"""Nominal M5 checks measured from the generated solids.

Rays use BRep point classification and bisection; walls use BRepExtrema on a thin
horizontal slab. These are CAD geometry checks, not torque, strength or fit tests.
"""
from __future__ import annotations
import math
from .geometry import *
from .geometry import nut_envelope, screw_envelope, hex_prism, lid_parts_m5, lid_quarter_m5, screw_sites, plate_shape
from fitfix.geometry import lid_quarter, lid_parts
from fitfix.validation import overlap, pairs
from fitfix.io import bounds

TOL = 1e-4


def inside(shape, p):
    return shape.isInside(cq.Vector(*p), 1e-7)


def march(shape, origin, direction, want, limit=30., step=.05):
    """Distance along direction until classification becomes `want` (bisection-refined)."""
    d = 0.
    p = lambda t: tuple(o + t * u for o, u in zip(origin, direction))
    while d <= limit:
        if inside(shape, p(d)) == want:
            lo, hi = max(0., d - step), d
            while hi - lo > 1e-5:
                mid = (lo + hi) / 2
                if inside(shape, p(mid)) == want:
                    hi = mid
                else:
                    lo = mid
            return hi
        d += step
    raise AssertionError(f'No classification change from {origin} along {direction}')


def unit(angle_deg):
    a = math.radians(angle_deg)
    return (math.cos(a), math.sin(a), 0.)


def measure_pocket(frame, site, m: M5, pz):
    """Measure one pocket, its roof, depth and walls on the real frame solid."""
    x, y, a = site['x'], site['y'], site['hex_angle']
    zmid = pz - m.nut_roof - m.pocket_effective_depth / 2
    flats, walls_along_flat_normals, corners = [], [], []
    for k in range(6):
        u = unit(a + 30 + 60 * k)
        d = march(frame, (x, y, zmid), u, True)
        flats.append(d)
        start = (x + u[0] * (d + 1e-3), y + u[1] * (d + 1e-3), zmid)
        walls_along_flat_normals.append(1e-3 + march(frame, start, u, False))
        corners.append(march(frame, (x, y, zmid), unit(a + 60 * k), True))
    af = [flats[k] + flats[k + 3] for k in range(3)]
    inward = (-site['normal'][0], -site['normal'][1], 0.)
    walls = {}
    for key, u in (('wall_to_outer_face', (-inward[0], -inward[1], 0.)), ('wall_to_interior', inward)):
        d = march(frame, (x, y, zmid), u, True) + 1e-3
        walls[key] = 1e-3 + march(frame, (x + u[0] * d, y + u[1] * d, zmid), u, False)
    r_roof = (m.through_hole / 2 + m.pocket_af / 2) / 2
    roof_probe = (x + inward[0] * r_roof, y + inward[1] * r_roof, zmid)
    roof_under = zmid + march(frame, roof_probe, (0, 0, 1), True)
    roof_top = roof_under + 1e-3 + march(frame, (roof_probe[0], roof_probe[1], roof_under + 1e-3), (0, 0, 1), False)
    r_wall = m.pocket_af / 2 + m.nut_wall_min / 2
    wall_probe = (x + inward[0] * r_wall, y + inward[1] * r_wall, zmid)
    if not inside(frame, wall_probe):
        raise AssertionError('Wall probe is not inside the boss')
    boss_bottom = zmid - march(frame, wall_probe, (0, 0, -1), False)
    # Bottom entry is open: the pocket centre stays outside the solid to below the boss.
    for z in (zmid, boss_bottom + .5, boss_bottom - .5):
        if inside(frame, (x + inward[0] * r_roof, y + inward[1] * r_roof, z)):
            raise AssertionError('Pocket entry is closed')
    # True minimum wall around the pocket in a mid-height slab (includes hex corners).
    w = 14.
    slab = box(x - w, x + w, y - w, y + w, zmid - .01, zmid + .01)
    section = frame.intersect(slab)
    voids = slab.cut(section).Solids()
    pocket = [v for v in voids if v.isInside(cq.Vector(x + inward[0] * r_roof, y + inward[1] * r_roof, zmid))]
    if len(pocket) != 1:
        raise AssertionError('Pocket void not isolated in slab')
    others = [v for v in voids if not v.isSame(pocket[0])]
    min_wall = min(pocket[0].distance(v) for v in others)
    return dict(
        frame=site['frame'], site=site['site'], axis_xy=[x, y],
        across_flats_measured=af, corner_radius_measured=corners,
        flat_wall_along_normals=walls_along_flat_normals,
        min_wall_true=min_wall, **walls,
        roof_underside_z=roof_under, plate_contact_z=roof_top, roof_thickness=roof_top - roof_under,
        boss_bottom_z=boss_bottom, effective_depth=roof_under - boss_bottom,
        overcut_not_counted=m.pocket_overcut,
    )


def bore_axes(frame, radius):
    found = set()
    for e in frame.Edges():
        if e.geomType() == 'CIRCLE' and abs(e.radius() - radius) < 1e-6:
            c = e.Center()
            found.add((round(c.x, 6), round(c.y, 6)))
    return sorted(found)


def plate_holes(plate):
    found = {}
    for e in plate.Edges():
        if e.geomType() == 'CIRCLE' and abs(e.Length() - 2 * math.pi * e.radius()) < 1e-6:
            c = e.Center()
            found[(round(c.x, 6), round(c.y, 6))] = round(2 * e.radius(), 6)
    return found


def edge_ligament(plate, center, diameter):
    """Hole edge to plate outline, measured against the outline faces only."""
    hole_r = diameter / 2
    holes = plate_holes(plate)
    outline = []
    for f in plate.Faces():
        n = f.normalAt()
        if abs(n.z) > 1e-6:
            continue
        circles = [e for e in f.Edges() if e.geomType() == 'CIRCLE']
        if circles and any(abs(2 * c.radius() - d) < 1e-6 and abs(c.Center().x - x) < 1e-5 and abs(c.Center().y - y) < 1e-5
                           for c in circles for (x, y), d in holes.items()):
            continue
        outline.append(f)
    probe = cq.Solid.makeCylinder(hole_r, 10, cq.Vector(center[0], center[1], bounds(plate)['min'][2] - 5))
    return min(probe.distance(f) for f in outline)


def knob_zones(b, l, rails):
    """Assumed knob envelope: between each rail pair, up to panel+knob height."""
    rs = sorted(rails, key=lambda p: bounds(p.shape)['min'][1])
    zones = []
    top = b.height + l['module_panel'] + l['knob_height']
    for a, c in zip(rs[0::2], rs[1::2]):
        ba, bc = bounds(a.shape), bounds(c.shape)
        zones.append(Part(f'knob-zone-{a.id}-{c.id}',
                          box(min(ba['min'][0], bc['min'][0]), max(ba['max'][0], bc['max'][0]),
                              ba['max'][1], bc['min'][1], max(ba['max'][2], bc['max'][2]), top),
                          group='knob-zone'))
    return zones


def anti_rotation(frame, site, roof_z, nut, m):
    """Seated max nut fits; a min nut turned 30 deg must hit the flats."""
    x, y, a = site['x'], site['y'], site['hex_angle']
    inr = m.pocket_af / 2
    seated = nut_envelope(x, y, roof_z, nut['af_max'], nut['h_max'], a)
    rows = dict(max_nut_seated_overlap_mm3=overlap(seated, frame))
    for label, af, ratio in (('min_sharp', nut['af_min'], None), ('min_truncated', nut['af_min'], nut['corner_ratio']),
                             ('photo_truncated', nut['af_photo'], nut['corner_ratio'])):
        rc = af / math.sqrt(3) if ratio is None else af * ratio / 2
        turned = nut_envelope(x, y, roof_z, af, nut['h_min'], a + 30, ratio)
        hit = overlap(turned, frame)
        rows[label] = dict(across_flats=af, corner_radius=rc, pocket_inscribed_radius=inr,
                           turned_30deg_overlap_mm3=hit, locks=hit > 1e-6,
                           free_rotation_deg=(30 - math.degrees(math.acos(inr / rc))) if rc > inr else None)
    return rows


def insertion_path(frame, site, roof_z, boss_bottom_z, nut, travel):
    """Sampled bottom-entry path: pull the max nut down, then slide it inward."""
    x, y, a = site['x'], site['y'], site['hex_angle']
    seated = nut_envelope(x, y, roof_z, nut['af_max'], nut['h_max'], a)
    down = roof_z - boss_bottom_z + .5
    samples, hits = 0, []
    dz = 0.
    while dz <= down + 1e-9:
        samples += 1
        v = overlap(seated.translate((0, 0, -dz)), frame)
        if v > 1e-6:
            hits.append(dict(down=dz, overlap=v))
        dz += .5
    inward = (-site['normal'][0], -site['normal'][1])
    for s in range(0, int(travel) + 1, 2):
        samples += 1
        v = overlap(seated.translate((inward[0] * s, inward[1] * s, -down)), frame)
        if v > 1e-6:
            hits.append(dict(down=down, inward=s, overlap=v))
    return dict(samples=samples, collisions=hits, passed=not hits,
                path='seated -> straight down past the boss bottom (+0.5) -> inward toward the lid centre',
                continuous_sweep_verified=False)


def unchanged_outside_boss(b, g, l, m):
    """Old R9-FITFIX-01 quarter == new quarter outside the new boss boxes."""
    old, _ = lid_quarter(b, g, l)
    new, _, boxes = lid_quarter_m5(b, g, l, m)
    region = cq.Compound.makeCompound(boxes)
    diff = [new.cut(old), old.cut(new)]
    outside = sum(d.cut(region).Volume() for d in diff)
    old_plate = next(p for p in lid_parts(b, g, l)[0] if p.group == 'lid-metal').shape
    parts, holes, _ = lid_parts_m5(b, g, l, m)
    new_plate = next(p for p in parts if p.group == 'lid-metal').shape
    i = interface(b, g, l)
    t = i['lid_plate_mm'][2]
    blank_old = old_plate.Volume() + 8 * math.pi * (l['assembly_hole'] / 2) ** 2 * t
    blank_new = new_plate.Volume() + 8 * math.pi * (m.through_hole / 2) ** 2 * t
    bo, bn = bounds(old_plate), bounds(new_plate)
    return dict(changed_volume_outside_boss_boxes_mm3=outside,
                frame_volume_old_mm3=old.Volume(), frame_volume_new_mm3=new.Volume(),
                plate_blank_volume_difference_mm3=blank_new - blank_old,
                plate_bounds_max_difference_mm=max(abs(x - y) for k in ('min', 'max') for x, y in zip(bo[k], bn[k])),
                passed=outside < 1e-6 and abs(blank_new - blank_old) < 1e-4 and
                max(abs(x - y) for k in ('min', 'max') for x, y in zip(bo[k], bn[k])) < 1e-6)


def fastener_checks(b, g, l, m, frames, plate, sites, stationary, knobs, nut, asm):
    """Per-site pocket, nut, screw, head, tool and insertion checks on assembled frames."""
    i = interface(b, g, l)
    pz, ptop = i['plate_bottom_z_mm'], i['plate_top_z_mm']
    by_id = {p.id: p.shape for p in frames}
    others = stationary + knobs
    holes = plate_holes(plate)
    sites_out = []
    for s in sites:
        frame = by_id[s['frame']]
        pocket = measure_pocket(frame, s, m, pz)
        roof_z = pocket['roof_underside_z']
        ligament = edge_ligament(plate, (s['x'], s['y']), m.through_hole)
        edge_to_axis = ligament + m.through_hole / 2
        rows = []
        for washer in (False, True):
            for length in asm['candidate_lengths']:
                env = screw_envelope(s['x'], s['y'], ptop, length, asm['head_diameter_max'], asm['head_height_max'],
                                     asm['screw_major_diameter'], asm['washer_thickness'] if washer else 0.,
                                     asm['washer_outer_diameter'])
                protrusion = {h: (roof_z - h) - env['tip_z'] for h in (nut['h_min'], nut['h_max'])}
                tip_hits = [o.id for o in others if overlap(env['shank'], o.shape) > 1e-6]
                own_hits = [f.id for f in frames if overlap(env['shank'], f.shape) > 1e-6]
                plate_hit = overlap(env['shank'], plate) > 1e-6
                engaged = min(protrusion.values()) >= asm['min_protrusion_pitches'] * nut['pitch']
                rows.append(dict(length=length, washer=washer, tip_z=env['tip_z'],
                                 protrusion_beyond_nut_min_max={str(k): v for k, v in protrusion.items()},
                                 tip_below_boss_bottom=pocket['boss_bottom_z'] - env['tip_z'],
                                 nylon_engaged=engaged, tip_collisions=tip_hits,
                                 shank_frame_collisions=own_hits, shank_plate_collision=plate_hit,
                                 passed=engaged and not tip_hits and not own_hits and not plate_hit))
        env = screw_envelope(s['x'], s['y'], ptop, 10, asm['head_diameter_max'], asm['head_height_max'], asm['screw_major_diameter'])
        head_frame = min(env['head'].distance(f.shape) for f in frames)
        head_hits = [f.id for f in frames if overlap(env['head'], f.shape) > 1e-6]
        column = cq.Solid.makeCylinder(asm['driver_column_diameter'] / 2, 80, cq.Vector(s['x'], s['y'], ptop + asm['head_height_max']))
        column_hits = [f.id for f in frames if overlap(column, f.shape) > 1e-6]
        nut_seated = nut_envelope(s['x'], s['y'], roof_z, nut['af_max'], nut['h_max'], s['hex_angle'])
        nut_hits = [o.id for o in frames + stationary + knobs if overlap(nut_seated, o.shape) > 1e-6]
        sites_out.append(dict(
            **pocket, plate_hole_present=(round(s['x'], 6), round(s['y'], 6)) in holes,
            plate_edge_ligament=ligament, plate_edge_to_axis=edge_to_axis,
            head_margin_on_plate=edge_to_axis - asm['head_diameter_max'] / 2,
            head_clearance_to_frames=head_frame, head_collisions=head_hits,
            driver_column_collisions=column_hits,
            nut_envelope_collisions=nut_hits,
            anti_rotation=anti_rotation(frame, s, roof_z, nut, m),
            insertion=insertion_path(frame, s, roof_z, pocket['boss_bottom_z'], nut, asm['insertion_inward_travel']),
            screws=rows))
    return sites_out
