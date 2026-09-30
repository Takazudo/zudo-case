"""Targeted R9 lid geometry and export checks."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cadquery as cq
import ezdxf
from build import export_part, load_params
from r9.common import inspect_binary_stl, sha256_file
from r9.lid import build
from r9.types import BuildContext

ROOT=Path(__file__).resolve().parents[1]

class LidTest(unittest.TestCase):
    def test_lift_off_geometry_exports_and_determinism(self):
        hashes=[]
        with TemporaryDirectory() as temp:
            for run in ('first','second'):
                base=Path(temp)/run
                ctx=BuildContext(base,base/'out',load_params())
                parts=build(ctx)
                self.assertEqual(len(parts),5)
                self.assertEqual(len({p.id for p in parts}),5)
                self.assertFalse(any(word in p.id.lower() for p in parts for word in ('lock','latch','cam','slider','hook','magnet','spacer')))
                self.assertTrue(all(p.qty==1 for p in parts))
                plate=parts[0]
                self.assertEqual(plate.id,'7U40-R9-LID-PLATE')
                self.assertEqual(len(plate.dxf_holes),8)
                self.assertEqual(len(plate.solid.Solids()),1)
                exported=export_part(ctx,plate)
                drawing=ezdxf.readfile(ctx.out/'aluminum'/'7u40-r9-lid-plate-qty1-mm.dxf')
                self.assertFalse(drawing.audit().errors)
                self.assertEqual(drawing.units,ezdxf.units.MM)
                outlines=list(drawing.modelspace().query('LWPOLYLINE'))
                self.assertEqual(len(outlines),1)
                vertices=list(outlines[0].get_points('xyb'))
                self.assertEqual(len(vertices),8)
                self.assertEqual(sum(abs(v[2]-math.tan(math.pi/8))<1e-8 for v in vertices),4)
                self.assertEqual(len(list(drawing.modelspace().query('CIRCLE'))),8)
                reimport=cq.importers.importStep(str(ctx.out/'aluminum'/'7u40-r9-lid-plate-qty1-mm.step')).val()
                self.assertAlmostEqual(reimport.Volume(),plate.solid.Volume(),places=4)
                self.assertTrue(inspect_binary_stl(ctx.out/'aluminum'/'7u40-r9-lid-plate-qty1-mm.stl',plate.solid)['closedManifold'])
                manifest=json.loads((ctx.out/'pa12'/'lid'/'manifest.json').read_text())
                self.assertEqual(len(manifest['deliverables']),8)
                for part in parts[1:]:
                    self.assertEqual(part.export_kinds,())
                    path=ctx.out/'pa12'/'lid'/f'{part.id.lower()}-qty1-mm.stl'
                    self.assertTrue(inspect_binary_stl(path,part.solid)['closedManifold'])
                    step=path.with_suffix('.step')
                    self.assertAlmostEqual(cq.importers.importStep(str(step)).val().Volume(),part.solid.Volume(),places=3)
                paths=[base/entry['path'] for entry in exported+manifest['deliverables']]
                hashes.append({str(path.relative_to(base)):sha256_file(path) for path in paths})
        self.assertEqual(hashes[0],hashes[1])

    def test_frozen_interface_rejects_mismatch(self):
        params=load_params()
        params['lid']['top_edge_guard_opening_x']['value']+=1
        with TemporaryDirectory() as temp:
            ctx=BuildContext(Path(temp),Path(temp)/'out',params)
            with self.assertRaisesRegex(ValueError,'top-edge interface mismatch'):
                build(ctx)

if __name__=='__main__': unittest.main()
