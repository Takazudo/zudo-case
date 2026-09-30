"""Targeted #99/#100/#101 regression tests; no physical approval."""
from pathlib import Path
import json,tempfile,unittest
from dataclasses import replace
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fitfix.geometry import *
from fitfix.validation import overlap,pairs,check_flat_walls,contact_area_z
from fitfix import io
from fitfix.coupons import coupon_families

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'parameters.json').read_text())
B=Body(**DATA['body']);G=Guard(**{k:v for k,v in DATA['guard'].items() if k!='comparison_wall'});L=DATA['lid']

class GeometryTests(unittest.TestCase):
    def test_old_lower_return_negative_control(self):
        # The exact axis-aligned offending R9 return region from #99.
        return_region=box(-2.5,-1.8,0,100,-.3,5)
        floor=box(-10,0,0,100,0,1.5)
        self.assertAlmostEqual(overlap(return_region,floor),105,places=6)
    def test_new_lower_l_section_clears_floor_and_wall(self):
        for t in (1.0,1.2):
            s=guard_section(B,replace(G,wall=t),100,'bottom')
            floor=box(-20,0,0,100,0,1.5);wall=box(-1.5,0,0,100,1.5,20)
            self.assertEqual(overlap(s,floor),0)
            self.assertEqual(overlap(s,wall),0)
    def test_all_guard_instances_against_all_five_plates(self):
        for t in (1.0,1.2):
            gp=guard_instances(guard_parts(B,replace(G,wall=t)))
            self.assertEqual(len(gp),16)
            self.assertTrue(pairs(gp,body_envelopes(B))['passed'])
            self.assertTrue(pairs(gp)['passed'])
    def test_wall_thickness_is_not_consumed_by_fit_or_adhesive(self):
        for t in (1.0,1.2):
            for fit,adh in ((0,0),(.1,.15),(.15,.15),(.25,.15),(.35,.25)):
                values=check_flat_walls(B,replace(G,wall=t,fit_per_face=fit,adhesive_per_face=adh))
                for value in values.values():self.assertAlmostEqual(value,t,places=6)
    def test_seat_is_absolute_z_not_total_height(self):
        i=interface(B,G,L)
        self.assertAlmostEqual(i['guard_top_z_mm'],92.2)
        self.assertAlmostEqual(i['guard_envelope_height_mm'],93.4)
        self.assertEqual(i['guard_top_z_mm'],i['lid_seat_z_mm'])
    def test_lid_has_actual_contact_support(self):
        for t in (1.0,1.2):
            g=replace(G,wall=t);top=guard_perimeter(B,g);parts,_=lid_parts(B,g,L)
            for p in parts:
                if p.group=='lid':self.assertGreater(contact_area_z(p.shape,top,interface(B,g,L)['lid_seat_z_mm']),0)
                self.assertEqual(overlap(p.shape,top),0)
    def test_parameter_changes_follow_seating_and_plate(self):
        for b,g in ((replace(B,height=96),G),(B,replace(G,wall=1)),(B,replace(G,fit_per_face=.25))):
            i=interface(b,g,L);lp,_=lid_parts(b,g,L)
            self.assertEqual(i['lid_seat_z_mm'],b.height+g.wall)
            plate=next(p for p in lp if p.group=='lid-metal')
            self.assertAlmostEqual(io.bounds(plate.shape)['min'][2],i['lid_seat_z_mm']+30)
    def test_new_coupon_pairs_do_not_interpenetrate(self):
        records=coupon_families(B,G,L)
        for name in ('C2-01','C2-02','C2-03','C4-01','C5-01'):
            c=next(x for x in records if x['id']==name)
            self.assertTrue(pairs(c['parts'])['passed'],name)
    def test_c1_07_label_is_manifold(self):
        c=next(x for x in coupon_families(B,G,L) if x['id']=='C1-07')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'label.stl';io.stl(c['parts'][0].shape,p)
            self.assertTrue(io.inspect_stl(p,c['parts'][0].shape)['watertight'])
    def test_exports_repeat_within_same_toolchain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n in (1,2):
                s=guard_section(B,G,40)
                io.step(s,root/f'{n}.step');io.stl(s,root/f'{n}.stl')
            for ext in ('step','stl'):self.assertEqual(io.digest(root/f'1.{ext}'),io.digest(root/f'2.{ext}'))
    def test_negative_guard_parameters_rejected(self):
        for g in (replace(G,wall=0),replace(G,fit_per_face=-.1),replace(G,outer_radius=1.2)):
            with self.assertRaises(ValueError):g.validate()

if __name__=='__main__':unittest.main(verbosity=2)
