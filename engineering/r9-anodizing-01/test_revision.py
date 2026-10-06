"""Geometry, file-readback, traceability and negative regression checks."""
import json
from pathlib import Path
import tempfile
import unittest
import ezdxf
import cadquery as cq
import build


class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)
        cls.manifest = build.build(cls.out)
        cls.parts, _, cls.params = build.source_parts()
        cls.parts = {p['id']:p for p in cls.parts}
        cls.config = json.loads((build.ROOT/'parameters.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_13_source_generated_and_exports_repeatable(self):
        self.assertEqual(len(self.manifest['parts']),13)
        expected = build.ROOT/'out'
        checked=0
        for row in self.manifest['parts']:
            for f in row['new_files']:
                self.assertEqual((self.out/f['path']).read_bytes(), (expected/f['path']).read_bytes(),f['path'])
                checked+=1
            self.assertEqual((self.out/'review'/f"{row['id']}.svg").read_bytes(),
                             (expected/'review'/f"{row['id']}.svg").read_bytes())
        self.assertEqual(checked,39)

    def test_committed_manifest_and_hashes(self):
        expected=build.ROOT/'out'
        checks=json.loads((expected/'checksums.json').read_text())
        for row in checks['files']:
            self.assertEqual(build.io.digest(expected/row['path']),row['sha256'])
        manifest=json.loads((expected/'manifest.json').read_text())
        for row in manifest['inputs']+manifest['original_inputs_verified_against_pinned_commit']:
            self.assertEqual(build.io.digest(build.REPO/row['path']),row['sha256'],row['path'])

    def validate(self, name, revised, center=None, diameter=4):
        p=self.parts[name]
        return build.validate_change(p['shape'],revised,center or self.config['centers_uv_mm'][name],diameter,
                                     build.keepouts(p,self.params))

    def test_missing_hole_rejected(self):
        with self.assertRaisesRegex(ValueError,'functional geometry|full through'):
            self.validate('c1-metal-edge',self.parts['c1-metal-edge']['shape'])

    def test_extra_hole_rejected(self):
        p=self.parts['c1-metal-edge'];s=p['shape']
        revised=s.cut(build.hole_tool(s,[5,5],4)).cut(build.hole_tool(s,[20,5],4))
        with self.assertRaisesRegex(ValueError,'functional geometry|full through'):
            self.validate(p['id'],revised)

    def test_wrong_diameter_rejected(self):
        p=self.parts['c1-metal-edge'];s=p['shape']
        with self.assertRaises(ValueError):
            self.validate(p['id'],s.cut(build.hole_tool(s,[5,5],5)))
        with self.assertRaisesRegex(ValueError,'supplier range'):
            self.validate(p['id'],s,diameter=3)

    def test_original_mount_hole_cannot_be_filled(self):
        name='c3-03-bottom';p=self.parts[name];s=p['shape']
        filled=cq.Solid.makeBox(32,20,1.5).cut(build.hole_tool(s,[4,16],4))
        with self.assertRaisesRegex(ValueError,'material added'):
            self.validate(name,filled)

    def test_edge_and_guard_conflicts_rejected(self):
        for name,center in [('c1-metal-edge',[2.5,5]),('c1-metal-edge',[5,17]),
                            ('c5-01-front',[5.25,7]),('c5-01-left',[8.5,5]),
                            ('c3-02-wall',[10,16])]:
            with self.subTest(name=name,center=center),self.assertRaises(ValueError):
                s=self.parts[name]['shape']
                self.validate(name,s.cut(build.hole_tool(s,center,4)),center=center)

    def test_c3_case_coordinates_distinguish_wall_and_bottom(self):
        rows={p['id']:p for p in self.manifest['parts']}
        for n in ('01','02','03'):
            for face, xyz in [('bottom',[-71.5,-151,0.75]),('wall',[-71.5,-166.25,17.5])]:
                row=rows[f'c3-{n}-{face}']
                self.assertEqual(row['hole_center_exported_step_mm'],[4,16,0.75])
                for actual, expected in zip(row['hole_center_case_mm'],xyz):
                    self.assertAlmostEqual(actual,expected)

    def test_changed_dxf_detected_geometrically(self):
        row=self.manifest['parts'][0]
        path=self.out/next(f['path'] for f in row['new_files'] if f['path'].endswith('.dxf'))
        doc=ezdxf.readfile(path)
        doc.modelspace().query('CIRCLE[layer=="HANGING"]')[0].dxf.radius=2.2
        changed=self.out/'wrong.dxf';doc.saveas(changed)
        shape=self.parts[row['id']]['shape'];b,_,uv=build.frame(shape)
        expected=shape.cut(build.hole_tool(shape,row['hole_center_uv_mm'],4))
        self.assertGreater(build.symmetric_difference(expected,build.local_to_world(build.dxf_shape(changed),b,uv)),1)


if __name__=='__main__':
    unittest.main()
