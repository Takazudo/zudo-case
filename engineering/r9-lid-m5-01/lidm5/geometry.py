"""M5 plate/frame fastener for the R9-FITFIX-01 lid.

One M5 definition drives the four lid frames, the aluminium plates and the
C2-M5/N1 coupons. Every non-fastener lid surface is the unchanged R9-FITFIX-01
lid_quarter(): the new boss boxes contain the old M3 bosses and bores, so the
old geometry outside those boxes is preserved exactly (checked in checks.py).
No lid-to-body lock is added; the screws join plate and frame only.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT.parent / 'r9-fitfix-01'
if str(FIT) not in sys.path:
    sys.path.insert(0, str(FIT))

import cadquery as cq
from fitfix.geometry import Body, Guard, Part, box, solid, union, interface, lid_quarter, EPS


@dataclass(frozen=True)
class M5:
    through_hole: float
    pocket_af: float
    pocket_effective_depth: float
    nut_roof: float
    nut_wall_min: float
    boss_half_length: float
    plate_edge_to_axis: float
    pocket_overcut: float = .2

    @property
    def boss_depth(self) -> float:
        return self.pocket_effective_depth + self.nut_roof

    @property
    def pocket_corner_radius(self) -> float:
        return self.pocket_af / math.sqrt(3)

    def validate(self, nut_af_max: float, nut_h_max: float) -> None:
        values = vars(self).values()
        if not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in values):
            raise ValueError('M5 values must be positive finite numbers')
        if self.pocket_af <= nut_af_max:
            raise ValueError('Nut pocket must clear the across-flats envelope')
        if self.pocket_effective_depth <= nut_h_max:
            raise ValueError('Nut pocket must hold the full nut height envelope')
        if self.through_hole >= self.pocket_af:
            raise ValueError('Through hole must stay inside the hex roof')
        if self.boss_half_length < self.pocket_corner_radius + self.nut_wall_min:
            raise ValueError('Boss too short for the hex corner wall')


def load(root: Path = ROOT) -> dict:
    """Read the M5 definition plus the unchanged R9-FITFIX-01 inputs."""
    data = json.loads((root / 'parameters.json').read_text())
    fit = json.loads((root / data['inherits']['body_guard_lid']).read_text())
    anod = json.loads((root / data['inherits']['c2_plate_hang_hole']).read_text())
    m = {k: v for k, v in data['m5'].items() if k != 'af_ladder'}
    result = dict(
        data=data, fit=fit,
        body=Body(**fit['body']),
        guard=Guard(**{k: v for k, v in fit['guard'].items() if k != 'comparison_wall'}),
        comparison_wall=fit['guard']['comparison_wall'],
        lid=fit['lid'], m5=M5(**m), ladder=data['m5']['af_ladder'],
        hang_hole=dict(diameter=anod['diameter_mm'], uv=anod['centers_uv_mm']['c2-01-plate'],
                       revision=anod['revision']),
    )
    result['m5'].validate(data['design_envelope']['nut_across_flats'], data['design_envelope']['nut_height'])
    return result


def hex_prism(x, y, z0, z1, af, angle_deg=0.0):
    """Hex with a vertex at angle_deg; flats face angle_deg+30 + k*60."""
    r = af / math.sqrt(3)
    a0 = math.radians(angle_deg)
    wire = cq.Wire.makePolygon([cq.Vector(x + r * math.cos(a0 + i * math.pi / 3), y + r * math.sin(a0 + i * math.pi / 3), z0)
                                for i in range(6)], close=True)
    return solid(cq.Solid.extrudeLinear(wire, [], cq.Vector(0, 0, z1 - z0)), 'hex prism')


def screw_sites(b: Body, g: Guard, l: dict, m: M5):
    """Quarter-frame screw axes. Each site names its outward edge normal."""
    i = interface(b, g, l)
    ox, oy = (x / 2 for x in i['guard_exterior_mm'])
    inset = l['frame_wall'] + l['plate_edge_gap'] + m.plate_edge_to_axis
    # Front edge (outward -Y): vertices along X, flats face the wall and the interior.
    front = dict(name='front', x=ox * l['front_screw_fraction'], y=-oy + inset, normal=(0, -1), hex_angle=0.0)
    # Side edge (outward +X): rotate so the flats face the wall again.
    side = dict(name='side', x=ox - inset, y=-oy * l['side_screw_fraction'], normal=(1, 0), hex_angle=30.0)
    return [front, side], inset


def boss_box(site, b, g, l, m):
    """Boss envelope measured from the frame outer face; contains the M3 boss."""
    i = interface(b, g, l)
    ox, oy = (x / 2 for x in i['guard_exterior_mm'])
    _, inset = screw_sites(b, g, l, m)
    reach = inset + m.pocket_af / 2 + m.nut_wall_min
    pz = i['plate_bottom_z_mm']
    h = m.boss_half_length
    if site['name'] == 'front':
        return box(site['x'] - h, site['x'] + h, -oy, -oy + reach, pz - m.boss_depth, pz)
    return box(ox - reach, ox, site['y'] - h, site['y'] + h, pz - m.boss_depth, pz)


def m5_cutters(x, y, top, m: M5, angle, af=None):
    """Bore and bottom-entry hex pocket under a plate contact face at Z=top."""
    af = m.pocket_af if af is None else af
    bore = cq.Solid.makeCylinder(m.through_hole / 2, m.boss_depth + 2, cq.Vector(x, y, top - m.boss_depth - 1))
    pocket = hex_prism(x, y, top - m.boss_depth - m.pocket_overcut, top - m.nut_roof, af, angle)
    return bore, pocket


def lid_quarter_m5(b: Body, g: Guard, l: dict, m: M5):
    i = interface(b, g, l)
    pz = i['plate_bottom_z_mm']
    old, _ = lid_quarter(b, g, l)
    sites, _ = screw_sites(b, g, l, m)
    boxes = [boss_box(s, b, g, l, m) for s in sites]
    q = union([old, *boxes], 'M5 lid quarter')
    for s in sites:
        bore, pocket = m5_cutters(s['x'], s['y'], pz, m, s['hex_angle'])
        q = solid(q.cut(bore).cut(pocket), 'M5 nut boss')
    return q, sites, boxes


QUARTERS = [('fr', lambda s: s, lambda p: p),
            ('fl', lambda s: s.mirror('YZ'), lambda p: (-p[0], p[1])),
            ('bl', lambda s: s.rotate((0, 0, 0), (0, 0, 1), 180), lambda p: (-p[0], -p[1])),
            ('br', lambda s: s.mirror('XZ'), lambda p: (p[0], -p[1]))]


def plate_shape(b, g, l, holes, diameter):
    """Same blank as R9-FITFIX-01 lid_parts(); only the hole list differs."""
    i = interface(b, g, l)
    px, py, t = i['lid_plate_mm']
    plate = (cq.Workplane('XY').box(px, py, t, centered=(True, True, False)).edges('|Z')
             .fillet(l['plate_corner_radius']).val().translate((0, 0, i['plate_bottom_z_mm'])))
    for x, y in holes:
        plate = plate.cut(cq.Solid.makeCylinder(diameter / 2, t + 2, cq.Vector(x, y, i['plate_bottom_z_mm'] - 1)))
    return solid(plate, 'lid plate')


def lid_parts_m5(b: Body, g: Guard, l: dict, m: M5):
    """Four frames + matching plate; returns parts, eight hole XY and site records."""
    q, sites, _ = lid_quarter_m5(b, g, l, m)
    parts, holes, records = [], [], []
    for name, fn, pt in QUARTERS:
        parts.append(Part('lid-frame-' + name, solid(fn(q)), 1, 'PA12-HP black candidate', 'lid'))
        for s in sites:
            x, y = pt((s['x'], s['y']))
            nx, ny = pt(s['normal'])
            holes.append((x, y))
            records.append(dict(frame='lid-frame-' + name, site=s['name'], x=x, y=y, normal=(nx, ny),
                                hex_angle=s['hex_angle']))  # both hexes are mirror-symmetric
    parts.append(Part('lid-plate', plate_shape(b, g, l, holes, m.through_hole), 1,
                      'A5052 t1.5 black anodized candidate', 'lid-metal'))
    return parts, holes, records


# Fastener envelopes: assumptions for checks and preview, never order items.
def nut_envelope(x, y, top, af, height, angle, corner_ratio=None):
    nut = hex_prism(x, y, top - height, top, af, angle)
    if corner_ratio:
        nut = solid(nut.intersect(cq.Solid.makeCylinder(af * corner_ratio / 2, height + 2, cq.Vector(x, y, top - height - 1))), 'nut corners')
    return nut


def screw_envelope(x, y, plate_top, length, head_d, head_h, major, washer_t=0., washer_od=0.):
    parts = []
    z = plate_top
    if washer_t:
        parts.append(cq.Solid.makeCylinder(washer_od / 2, washer_t, cq.Vector(x, y, z)))
        z += washer_t
    head = cq.Solid.makeCylinder(head_d / 2, head_h, cq.Vector(x, y, z))
    shank = cq.Solid.makeCylinder(major / 2, length, cq.Vector(x, y, z - length))
    return dict(head=head, shank=shank, washer=parts[0] if parts else None, tip_z=z - length, bearing_z=z)
