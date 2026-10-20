"""C2-M5 and N1 coupons, cut from the same M5 definition as the full lid.

C2-M5-01/02/03 keep the C2 locator comparison (0.7/0.5/0.9 mm) with the new M5
boss. Their wall and top guard are the unchanged R9-FITFIX-01 C2 pieces and are
reused, not reordered. N1 is a three-pocket nut ladder for physical AF tuning.
"""
from __future__ import annotations
from .geometry import *
from .geometry import m5_cutters, lid_parts_m5
from fitfix.geometry import body_envelopes, guard_instances, guard_parts, clip
from fitfix.coupons import GLYPHS as BASE_GLYPHS

GLYPHS = {**BASE_GLYPHS, 'M': ('101', '111', '111', '101', '101'), 'N': ('101', '111', '111', '111', '101')}
C2_CLEARANCES = (.7, .5, .9)


def label_on_x(shape, text, x, y, z, direction=1, pixel=.4, rise=.3):
    """fitfix.coupons.label_on_x with an M/N glyph; 2 mm raised glyphs on an X face."""
    marks = []
    for idx, char in enumerate(text):
        for row, bits in enumerate(GLYPHS[char]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    x0, x1 = sorted([x, x + direction * rise])
                    marks.append(box(x0, x1, y + (4 * idx + col) * pixel, y + (4 * idx + col + 1) * pixel,
                                     z + (4 - row) * pixel, z + (5 - row) * pixel))
    return union([shape, *marks], text + ' label')


def c2_window(b):
    """The R9-FITFIX-01 C2 clip window, unchanged."""
    return lambda s: clip(s, 20, 50, -b.depth / 2 - 5, -b.depth / 2 + 27, 60, 150)


def hang_hole_world(plate, uv, diameter):
    from fitfix.io import bounds
    bb = bounds(plate)
    return (bb['min'][0] + uv[0], bb['min'][1] + uv[1]), diameter


def c2_m5(b: Body, g: Guard, l: dict, m: M5, hang: dict):
    body = {p.id: p for p in body_envelopes(b)}
    topfront = next(p for p in guard_instances(guard_parts(b, g)) if p.id == 't1p2-top-a-b')
    cut = c2_window(b)
    wall = Part('c2-01-wall', cut(body['body-front'].shape), 1, 'A5052 t1.5 candidate (reuse R9-FITFIX-01/R9-ANODIZING-01)', 'coupon-reuse')
    guard = Part('c2-01-guard', cut(topfront.shape), 1, 'PA12-HP black candidate (reuse R9-FITFIX-01)', 'coupon-reuse')
    records, plate = [], None
    for num, c in enumerate(C2_CLEARANCES, 1):
        ll = {**l, 'locator_clearance': c}
        name = f'C2-M5-{num:02d}'
        parts, holes, sites = lid_parts_m5(b, g, ll, m)
        mp = {p.id: p for p in parts}
        frame = cut(mp['lid-frame-fr'].shape)
        rotated = frame.rotate((0, 0, 0), (0, 0, 1), 90)
        rotated = label_on_x(rotated, f'M5-{num:02d}', b.depth / 2 + g.gap + g.wall, 24, 99)
        frame = solid(rotated.rotate((0, 0, 0), (0, 0, 1), -90))
        if plate is None:
            raw = cut(mp['lid-plate'].shape)
            (hx, hy), hd = hang_hole_world(raw, hang['uv'], hang['diameter'])
            from fitfix.io import bounds
            z0 = bounds(raw)['min'][2]
            plate = solid(raw.cut(cq.Solid.makeCylinder(hd / 2, 3.5, cq.Vector(hx, hy, z0 - 1))), 'C2-M5 plate')
            plate_hang = dict(x=hx, y=hy, diameter=hd, uv=hang['uv'], source=hang['revision'])
        site = next(s for s in sites if s['frame'] == 'lid-frame-fr' and s['site'] == 'front')
        selected = [Part(f'c2-m5-{num:02d}-frame', frame, 1, group='coupon')]
        if num == 1:
            selected.append(Part('c2-m5-plate', plate, 1, 'A5052 t1.5 black anodized candidate', 'coupon-metal'))
        records.append(dict(id=name, parts=selected, reuse_parts=[wall, guard], locator_clearance_mm=c,
                            interface=interface(b, g, ll), m5_axis_xy=[site['x'], site['y']], site=site,
                            hang_hole=plate_hang, plate=plate,
                            purpose='前辺のフタ着座・位置決めとM5ネジ＋ロックナット締結',
                            reuse='Plate is shared by C2-M5-01/02/03. Wall and guard are the unchanged R9-FITFIX-01 C2 pieces.',
                            physical_results=None))
    return records


def n1_ladder(m: M5, ladder):
    """Small PA12 block: same boss section/roof/bore, pocket AF from the ladder.

    Z=top is the plate contact face; pockets open on the bottom like the lid.
    """
    pitch, half = 16.0, m.pocket_af / 2 + m.nut_wall_min + 1.15
    top = m.boss_depth
    width = pitch * len(ladder)
    s = box(0, width, -half, half, 0, top)
    centers = []
    for n, af in enumerate(ladder):
        x = pitch / 2 + n * pitch
        bore, pocket = m5_cutters(x, 0, top, m, 0.0, af)
        s = solid(s.cut(bore).cut(pocket), 'N1 pocket')
        centers.append(dict(x=x, y=0.0, af=af))
    # Raised AF labels (83/84/85) on the -Y face, rotated through the X-face tool.
    for c in centers:
        text = f"{round(c['af'] * 10):02d}"
        rot = s.rotate((0, 0, 0), (0, 0, 1), 90)
        rot = label_on_x(rot, text, half, c['x'] - 1.4, 2.5, 1)
        s = solid(rot.rotate((0, 0, 0), (0, 0, 1), -90))
    s = label_on_x(s, 'N1', width, -1.4, 2.5, 1)
    return Part('n1-m5-nut-ladder', s, 1, group='coupon'), centers, top
