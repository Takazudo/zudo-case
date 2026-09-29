"""Exported R9 slot profiles re-import with the intended centers and axes."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import cadquery as cq
import ezdxf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build import load_params  # noqa: E402
from r9.body import plate_specs  # noqa: E402
from r9.slots import angle, records  # noqa: E402
from r9.types import BuildContext  # noqa: E402


class SlotExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = BuildContext(ROOT, ROOT / "out", load_params())
        cls.specs = plate_specs(cls.ctx)
        cls.rows, cls.checks = records(cls.ctx)

    def test_counts_and_candidate_checks(self):
        self.assertEqual(self.checks["counts"], {"slots": 36, "roundRailFix": 10})
        self.assertEqual(len(self.rows), 46)
        for kind in ("edge", "ligament", "toolAccess", "guardContact"):
            self.assertEqual(self.checks["failures"][kind], [])
        self.assertEqual(len(self.checks["failures"]["bearingCoverage"]), 26)
        self.assertEqual({row["bearing_od"] for row in self.rows if row["coverage_ok"] is False}, {10.0})
        for row in self.rows:
            if row["profile"] != "slot":
                self.assertEqual((row["width"], row["length"], row["travel"]), (5.5, 5.5, 0))
                continue
            self.assertEqual((row["width"], row["length"], row["travel"]), (5.5, 7.5, 1.0))
            bottom_joint = "-BOTTOM-" in row["joint"]
            if row["plate"].endswith("-BOTTOM"):
                expected = [0, 1, 0] if "-FRONT-" in row["joint"] or "-BACK-" in row["joint"] else [1, 0, 0]
            elif row["plate"].endswith("-FRONT-BACK"):
                expected = [0, 0, 1] if bottom_joint else [1, 0, 0]
            else:
                expected = [0, 0, 1] if bottom_joint else [0, 1, 0]
            self.assertEqual(row["axis"], expected, row["id"])

    def test_dxf_reimport(self):
        for spec in self.specs:
            with self.subTest(plate=spec.id):
                stem = f"{spec.id.lower()}-qty{spec.quantity}-mm"
                doc = ezdxf.readfile(ROOT / "out/aluminum" / f"{stem}.dxf")
                msp = doc.modelspace()
                arcs = list(msp.query('ARC[layer=="SLOTS"]'))
                lines = list(msp.query('LINE[layer=="SLOTS"]'))
                circles = list(msp.query('CIRCLE[layer=="HOLES"]'))
                expected_slots = [h for h in spec.pattern_holes if h.role == "bracket"]
                expected_rounds = [h for h in spec.pattern_holes if h.role == "rail-fix"]
                self.assertEqual(len(arcs), 2 * len(expected_slots))
                self.assertEqual(len(lines), 2 * len(expected_slots))
                self.assertEqual(len(circles), len(expected_rounds))
                for hole in expected_slots:
                    x, y = hole.center_local_mm
                    d = 1.0
                    centers = [(x, y - d), (x, y + d)] if angle(hole) == 90 else [(x - d, y), (x + d, y)]
                    for cx, cy in centers:
                        matches = [a for a in arcs if abs(a.dxf.center.x - cx) < 1e-5 and abs(a.dxf.center.y - cy) < 1e-5]
                        self.assertEqual(len(matches), 1, hole.id)
                        self.assertAlmostEqual(matches[0].dxf.radius, 2.75, delta=1e-6)
                for hole in expected_rounds:
                    x, y = hole.center_local_mm
                    matches = [c for c in circles if abs(c.dxf.center.x - x) < 1e-5 and abs(c.dxf.center.y - y) < 1e-5]
                    self.assertEqual(len(matches), 1, hole.id)
                    self.assertAlmostEqual(matches[0].dxf.radius, 2.75, delta=1e-6)

    def test_step_reimport(self):
        for spec in self.specs:
            with self.subTest(plate=spec.id):
                stem = f"{spec.id.lower()}-qty{spec.quantity}-mm"
                shape = cq.importers.importStep(str(ROOT / "out/aluminum" / f"{stem}.step")).val()
                self.assertTrue(shape.isValid())
                arcs = [e for e in shape.Edges() if e.geomType() == "CIRCLE" and abs(e.radius() - 2.75) < 1e-5]
                def local(point):
                    x, y, z = point
                    if spec.part_type == "bottom":
                        return x + spec.width_mm / 2, y + spec.height_mm / 2
                    if spec.part_type == "front_back":
                        return x + spec.width_mm / 2, z - spec.thickness_mm
                    return y + spec.width_mm / 2, z - spec.thickness_mm
                centers = [local(e.arcCenter().toTuple()) for e in arcs]
                for hole in spec.pattern_holes:
                    x, y = hole.center_local_mm
                    targets = ([(x, y - 1), (x, y + 1)] if angle(hole) == 90 else
                               [(x - 1, y), (x + 1, y)]) if hole.role == "bracket" else [(x, y)]
                    for tx, ty in targets:
                        self.assertTrue(any(abs(cx - tx) < 1e-4 and abs(cy - ty) < 1e-4
                                            for cx, cy in centers), f"{hole.id}: {(tx, ty)}")

    def test_table_matches_export_profiles(self):
        exported = json.loads((ROOT / "out/aluminum/hole-table.json").read_text())
        self.assertEqual(exported["holes"], self.rows)


if __name__ == "__main__":
    unittest.main()
