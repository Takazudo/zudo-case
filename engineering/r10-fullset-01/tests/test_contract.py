"""Package and manifest mutation tests; no CAD dependency for documentation CI."""
import unittest,json,zipfile,copy,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def contract(m):
    assert m['profile']=='7u40-t1-groove1p70-m5' and m['production_approved'] is False
    p=m['parts'];assert len({r['id'] for r in p})==len(p)
    for d,n in [('aluminum',6),('pa12',20)]:assert sum(r['quantity'] for r in p if r['procurement']==d)==n
    assert sum(r.get('selected_print_quantity',0) for r in p)==72
    assert m['interface']['lid_plate_mm']==[227.4,332.0,1.5]
    for r in p:
        if r['procurement']=='pa12':assert 'PA12' in r['material'] and not any(x in r['id'].lower() for x in ['coupon','washer','cap-','c1-','n1'])
        assert r['quantity']>0

def files_ok(names,dest):
    assert len(names)==len(set(names))
    assert not any('coupon' in n.lower() or re.search(r'(^|[-/])(c[1-5]|n1)([-./]|$)',n.lower()) for n in names)
    assert not any(n.startswith('home-print/') for n in names) if dest!='home-print' else True
    geometry=[n for n in names if n.endswith('.stl' if dest=='pa12' else '.dxf')]
    if dest in ['pa12','aluminum']:assert len(geometry)==(20 if dest=='pa12' else 6)

class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.m=json.loads((ROOT/'out/selected-order.json').read_text())
    def test_selected(self):contract(self.m)
    def test_missing_part(self):
        m=copy.deepcopy(self.m);m['parts'].pop(0)
        with self.assertRaises(AssertionError):contract(m)
    def test_duplicate_quantity(self):
        m=copy.deepcopy(self.m);m['parts'][0]['quantity']=2
        with self.assertRaises(AssertionError):contract(m)
    def test_duplicate_part(self):
        m=copy.deepcopy(self.m);m['parts'].append(m['parts'][0])
        with self.assertRaises(AssertionError):contract(m)
    def test_wrong_profile(self):
        m=copy.deepcopy(self.m);m['profile']='old'
        with self.assertRaises(AssertionError):contract(m)
    def test_stale_dimensions(self):
        m=copy.deepcopy(self.m);m['interface']['lid_plate_mm'][0]+=1
        with self.assertRaises(AssertionError):contract(m)
    def test_packages(self):
        for d in ['pa12','aluminum','home-print']:
            with zipfile.ZipFile(ROOT/f'out/R10-FULLSET-01-{d}.zip') as z:
                self.assertIsNone(z.testzip());files_ok(z.namelist(),d)
                self.assertEqual(json.loads(z.read('selected-order.json')),self.m)
                for name in z.namelist():self.assertEqual(z.read(name),(ROOT/'out'/name).read_bytes())
    def test_forbidden_package_members(self):
        good=[f'pa12/guard-{n}.stl' for n in range(20)]
        for extra in ['home-print/washer.stl','pa12/coupon-N1.step','N1.stl','pa12/C2-M5.step']:
            with self.assertRaises(AssertionError):files_ok(good+[extra],'pa12')
    def test_travel_invalid(self):
        v=json.loads((ROOT/'out/validation.json').read_text())
        for k in ['corner','lower']:
            rows=[r for r in v['travel'] if r['kind']==k]
            self.assertTrue(next(r for r in rows if r['offset_mm']==1)['usable_nominal'])
            self.assertFalse(next(r for r in rows if r['offset_mm']==-2.5)['usable_nominal'])
    def test_preserved_old_bytes(self):
        m=json.loads((ROOT/'reference/preserved-bytes.json').read_text())
        for f in m['files']:self.assertEqual(hashlib.sha256((ROOT.parent.parent/f['path']).read_bytes()).hexdigest(),f['sha256'],f['path'])
    def test_fixed_bracket_collision_is_not_a_washer_success(self):
        v=json.loads((ROOT/'out/validation.json').read_text())
        for kind in ['corner','lower']:
            r=next(r for r in v['travel'] if r['kind']==kind and r['offset_mm']==1.75)
            self.assertTrue(r['cap_outline_usable_nominal'])
            self.assertFalse(r['fixed_bracket_clear'])
            self.assertFalse(r['usable_nominal'])
            self.assertGreater(r['fixed_bracket_overlap_mm3'],0)
    def test_validation_and_ligaments(self):
        for name in ['validation','joint-checks','hanging-hole-checks','lid-checks']:
            self.assertTrue(json.loads((ROOT/f'out/{name}.json').read_text())['passed'],name)
        holes=json.loads((ROOT/'out/hole-table.json').read_text());self.assertEqual(len(holes),54)
        slots=[r for r in holes if r.get('slot_length')];self.assertEqual(len(slots),36)
        parts={p['id']:p for p in self.m['parts']};margins=[]
        for r in slots:
            w,h,_=parts[r['part']]['dimensions_mm'];x,y=r['local_uv']
            rx,ry=(5.25,2.75) if r['angle']==0 else (2.75,5.25)
            margin=min(x-rx,w-x-rx,y-ry,h-y-ry);self.assertGreaterEqual(margin,4.75-1e-6);margins.append(margin)
        self.assertAlmostEqual(min(margins),4.75)
    def test_hashes(self):
        m=json.loads((ROOT/'out/outputs-manifest.json').read_text())
        for f in m['files']:self.assertEqual(hashlib.sha256((ROOT/'out'/f['path']).read_bytes()).hexdigest(),f['sha256'])
if __name__=='__main__':unittest.main()
