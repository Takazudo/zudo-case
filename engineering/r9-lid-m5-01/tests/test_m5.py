"""R9-LID-M5-01 regression tests (#123). Nominal geometry only; no physical approval."""
from dataclasses import replace
from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lidm5.geometry import *
from lidm5.geometry import lid_parts_m5, nut_envelope, screw_sites
from lidm5.checks import measure_pocket, anti_rotation, unchanged_outside_boss, plate_holes, bore_axes, edge_ligament
from lidm5.coupons import c2_m5, n1_ladder
from fitfix.geometry import lid_quarter, guard_instances, guard_parts, body_envelopes
from fitfix.validation import overlap, pairs
from fitfix import io

P = load()
B, G, L, M = P['body'], P['guard'], P['lid'], P['m5']
SRC = P['data']['nut_source']
NUT = dict(af_min=SRC['across_flats_min'], af_max=8.0, af_photo=SRC['product_photo_across_flats'], h_min=SRC['height_min'],
           h_max=5.0, pitch=SRC['pitch'], corner_ratio=P['data']['assumptions']['nut_corner_ratio_e_over_s'])
PARTS, HOLES, SITES = lid_parts_m5(B, G, L, M)
FRAMES = {p.id: p.shape for p in PARTS if p.group == 'lid'}
PLATE = next(p.shape for p in PARTS if p.group == 'lid-metal')
PZ = interface(B, G, L)['plate_bottom_z_mm']


class M5Tests(unittest.TestCase):
    def test_old_m3_pocket_cannot_hold_m5_nut(self):
        old, (front, _) = lid_quarter(B, G, L)
        nut = nut_envelope(front[0], front[1], PZ - L['nut_roof'], 8.0, 5.0, 0.0)
        self.assertGreater(overlap(nut, old), 1.0)

    def test_every_site_holds_envelope_and_measures_adopted_values(self):
        for s in SITES:
            m = measure_pocket(FRAMES[s['frame']], s, M, PZ)
            for af in m['across_flats_measured']:
                self.assertAlmostEqual(af, M.pocket_af, places=3)
            self.assertAlmostEqual(m['effective_depth'], M.pocket_effective_depth, places=3)
            self.assertAlmostEqual(m['roof_thickness'], M.nut_roof, places=3)
            self.assertGreaterEqual(m['min_wall_true'], 1.5)
            nut = nut_envelope(s['x'], s['y'], m['roof_underside_z'], 8.0, 5.0, s['hex_angle'])
            self.assertLess(overlap(nut, FRAMES[s['frame']]), 1e-6)

    def test_overcut_is_not_counted_as_depth(self):
        mm = replace(M, pocket_overcut=1.0)
        parts, _, sites = lid_parts_m5(B, G, L, mm)
        s = sites[0]
        m = measure_pocket(next(p.shape for p in parts if p.id == s['frame']), s, mm, PZ)
        self.assertAlmostEqual(m['effective_depth'], M.pocket_effective_depth, places=3)

    def test_anti_rotation_locks_min_nut_and_documents_85_choice(self):
        s = SITES[0]
        roof = PZ - M.nut_roof
        r = anti_rotation(FRAMES[s['frame']], s, roof, NUT, M)
        self.assertTrue(r['min_sharp']['locks'] and r['min_truncated']['locks'])
        wide = replace(M, pocket_af=8.5)
        parts, _, sites = lid_parts_m5(B, G, L, wide)
        r85 = anti_rotation(next(p.shape for p in parts if p.id == sites[0]['frame']), sites[0], roof, NUT, wide)
        self.assertFalse(r85['min_truncated']['locks'])

    def test_eight_frame_bores_match_eight_plate_holes(self):
        for g in (G, replace(G, wall=1.0)):
            parts, holes, _ = lid_parts_m5(B, g, L, M)
            axes = sorted(a for p in parts if p.group == 'lid' for a in bore_axes(p.shape, M.through_hole / 2))
            plate = next(p.shape for p in parts if p.group == 'lid-metal')
            ph = sorted(k for k, v in plate_holes(plate).items() if abs(v - M.through_hole) < 1e-6)
            self.assertEqual(len(axes), 8)
            self.assertEqual(axes, ph)

    def test_old_edge_distance_would_overhang_head(self):
        self.assertAlmostEqual(edge_ligament(PLATE, HOLES[0], M.through_hole), M.plate_edge_to_axis - M.through_hole / 2, places=4)
        head = P['data']['assumptions']['head_diameter_max'] / 2
        self.assertGreaterEqual(M.plate_edge_to_axis - head, 0)
        self.assertLess(3.9 - head, 0)  # the M3 axis position cannot carry the assumed M5 head

    def test_side_boss_stays_outside_40hp_rail_x_range(self):
        # Rail AABB x=+-102, inner edge of the front rail y=-144.6, rail top z=89.4 (R6 reference).
        knob_band = box(-102, 102, -144.6, 144.6, 89.4, PZ)
        for q in FRAMES.values():
            self.assertLess(overlap(q, knob_band), 1e-6)

    def test_seat_locator_and_plate_blank_unchanged(self):
        for g in (G, replace(G, wall=1.0), replace(G, fit_per_face=.25)):
            self.assertTrue(unchanged_outside_boss(B, g, L, M)['passed'])

    def test_lid_clears_guards_and_body_for_parameter_changes(self):
        for b, g in ((B, G), (B, replace(G, wall=1.0)), (replace(B, height=96.0), G)):
            parts, _, _ = lid_parts_m5(b, g, L, M)
            guards = guard_instances(guard_parts(b, g))
            self.assertTrue(pairs(parts, guards + body_envelopes(b))['passed'])

    def test_invalid_definitions_rejected(self):
        for bad in (replace(M, pocket_af=7.9), replace(M, pocket_effective_depth=4.9), replace(M, boss_half_length=6.0)):
            with self.assertRaises(ValueError):
                bad.validate(8.0, 5.0)

    def test_coupons_share_the_definition_and_keep_hang_hole_separate(self):
        recs = c2_m5(B, G, L, M, P['hang_hole'])
        self.assertEqual([r['locator_clearance_mm'] for r in recs], [.7, .5, .9])
        holes = plate_holes(recs[0]['plate'])
        self.assertEqual(sorted(holes.values()), [P['hang_hole']['diameter'], M.through_hole])
        front = next(s for s in SITES if s['frame'] == 'lid-frame-fr' and s['site'] == 'front')
        for r in recs:
            frame = r['parts'][0].shape
            self.assertEqual(bore_axes(frame, M.through_hole / 2), [(round(front['x'], 6), round(front['y'], 6))])
            m = measure_pocket(frame, dict(front, frame='c2'), M, PZ)
            self.assertAlmostEqual(m['effective_depth'], M.pocket_effective_depth, places=3)
            self.assertTrue(pairs([r['parts'][0], Part('plate', recs[0]['plate']), *r['reuse_parts']])['passed'])
        part, centers, _ = n1_ladder(M, P['ladder'])
        self.assertEqual([c['af'] for c in centers], [8.3, 8.4, 8.5])

    def test_exports_repeat_within_same_toolchain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in (1, 2):
                io.step(FRAMES['lid-frame-fr'], root / f'{n}.step'); io.stl(FRAMES['lid-frame-fr'], root / f'{n}.stl')
            for ext in ('step', 'stl'):
                self.assertEqual(io.digest(root / f'1.{ext}'), io.digest(root / f'2.{ext}'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
