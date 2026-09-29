"""Focused geometry and export checks for the R9 prototype guards."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import load_params
from r9.common import inspect_binary_stl, sha256_file
from r9.guards import build, guard_section
from r9.types import BuildContext


ROOT = Path(__file__).resolve().parents[1]


class GuardTests(unittest.TestCase):
    def test_section_clearance_changes_solid_and_rejects_contact_fit(self):
        p = {"t": 1.2, "metalThickness": 1.5, "cover": 5,
             "innerOverhang": 1, "fitClearancePerSide": .15,
             "adhesiveLayer": .15, "length": 20, "edgeRounding": .4}
        baseline = guard_section(p)
        wider = guard_section({**p, "fitClearancePerSide": .25})
        self.assertTrue(baseline.isValid())
        self.assertLess(wider.Volume(), baseline.Volume())
        self.assertGreater(baseline.cut(wider).Volume(), 0)
        metal = cq.Solid.makeBox(1.5, 20, 5, cq.Vector(-1.5, 0, -5))
        self.assertLess(baseline.intersect(metal).Volume(), 1e-7)
        with self.assertRaises(ValueError):
            guard_section({**p, "fitClearancePerSide": 0, "adhesiveLayer": 0})

    def test_all_exports_are_watertight_and_deterministic(self):
        params = load_params()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            ctx = BuildContext(root, root / "out", params)
            first = build(ctx)
            self.assertEqual(len(first), 12)
            for variant in ("t1p2", "t1p0"):
                manifest_path = ctx.out / "pa12" / "guards" / variant / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                self.assertEqual(sum(p["quantity"] for p in manifest["parts"]), 16)
                self.assertEqual(len(manifest["parts"]), 6)
                self.assertEqual(manifest["exportStatus"], "prototype candidate; not approved for manufacture")
                for record in manifest["parts"]:
                    shape = next(p.solid for p in first if p.id == record["id"])
                    self.assertLess(max(record["mesh"]["dimensionsMm"]), 180)
                    self.assertLess(abs(record["mesh"]["volumeMm3"] - shape.Volume()) / shape.Volume(), .0005)
                    stl_path = ctx.root / record["files"][1]["path"]
                    self.assertTrue(inspect_binary_stl(stl_path, shape)["closedManifold"])
                    step_path = ctx.root / record["files"][0]["path"]
                    imported = cq.importers.importStep(str(step_path)).val()
                    self.assertTrue(imported.isValid())
                    self.assertLess(abs(imported.Volume()-shape.Volume()), 1e-4)
                    for file in record["files"]:
                        path = ctx.root / file["path"]
                        self.assertEqual(path.stat().st_size, file["bytes"])
                        self.assertEqual(sha256_file(path), file["sha256"])
                lower_width = next(p.solid for p in first if p.id.endswith(f"{variant.upper()}-LOWER-WIDTH-HALF"))
                lower_depth = next(p.solid for p in first if p.id.endswith(f"{variant.upper()}-LOWER-DEPTH-A"))
                self.assertLess(lower_width.intersect(lower_depth).Volume(), 1e-7)
                before = {path.relative_to(ctx.out): sha256_file(path)
                          for path in (ctx.out / "pa12" / "guards" / variant).iterdir()}
                build(ctx)
                after = {path.relative_to(ctx.out): sha256_file(path)
                         for path in (ctx.out / "pa12" / "guards" / variant).iterdir()}
                self.assertEqual(before, after)

    def test_top_edge_interface_is_required(self):
        params = copy.deepcopy(load_params())
        params["guards"]["top_edge_guard_opening_x"]["value"] += .1
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "top_edge_guard_opening_x"):
                build(BuildContext(ROOT, Path(temp), params))


if __name__ == "__main__":
    unittest.main()
