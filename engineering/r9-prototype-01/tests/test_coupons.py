"""Focused exports and parameter coupling for R9 C1/C3 test coupons."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

import cadquery as cq
import ezdxf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build import export_part, load_params  # noqa: E402
from r9.common import inspect_binary_stl, sha256_file  # noqa: E402
from r9.coupons import (  # noqa: E402
    _build_c1, _build_c2,
    build as build_coupons,
    finalize as finalize_coupons,
)
from r9.guards import build as build_guards  # noqa: E402
from r9.types import BuildContext  # noqa: E402


def _context(temp: str, params: dict) -> BuildContext:
    return BuildContext(ROOT, Path(temp) / "out", params)


class CouponTests(unittest.TestCase):
    def test_c1_and_c3_exports_are_valid_deterministic_and_described(self):
        params = load_params()
        with TemporaryDirectory(dir=ROOT) as temp:
            ctx = _context(temp, params)
            parts = build_coupons(ctx)
            self.assertEqual(len(parts), 31)
            self.assertEqual(len({part.id for part in parts}), len(parts))
            for part in parts:
                outputs = export_part(ctx, part)
                for output in outputs:
                    self.assertLess(output["bytes"], 25 * 1024 * 1024, output["path"])
                if "step" in part.export_kinds:
                    step_path = ctx.out / "coupons" / f"{part.id.lower()}-qty{part.qty}-mm.step"
                    imported = cq.importers.importStep(str(step_path)).val()
                    self.assertTrue(imported.isValid(), part.id)
                    self.assertAlmostEqual(imported.Volume(), part.solid.Volume(), places=4)
                if "stl" in part.export_kinds:
                    path = ctx.out / "coupons" / f"{part.id.lower()}-qty{part.qty}-mm.stl"
                    mesh = inspect_binary_stl(path, part.solid)
                    self.assertTrue(mesh["closedManifold"], part.id)
                    if part.id.endswith("C1-01"):
                        self.assertGreater(mesh["bboxMaxMm"][0], 1.2)

            finalize_coupons(ctx)
            manifest_path = ctx.out / "coupons" / "coupon-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["status"], "unapproved_prototype")
            self.assertFalse(manifest["manufacturingApproval"])
            self.assertTrue(manifest["inputs"])
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["inputs"]))
            for item in manifest["inputs"]:
                target = ROOT.parents[1] / item["path"]
                self.assertEqual(item["bytes"], target.stat().st_size)
                self.assertEqual(item["sha256"], sha256_file(target))
            records = {record["id"]: record for record in manifest["coupons"]}
            self.assertEqual(set(records), {
                "C1-01", "C1-02", "C1-03", "C1-04", "C1-05", "C1-06", "C1-07",
                "C1-AL-EDGE", "C2-01", "C2-02", "C2-03", "C3-01", "C3-02", "C3-03",
            })
            self.assertEqual(records["C1-02"]["changedParameter"], {
                "name": "fitClearancePerSideMm", "baselineValue": 0.15, "couponValue": 0.1,
            })
            self.assertEqual(records["C1-03"]["changedParameter"]["couponValue"], 0.25)
            self.assertEqual(records["C1-04"]["changedParameter"]["name"], "adhesiveLayerMm")
            self.assertEqual(records["C1-05"]["changedParameter"]["couponValue"], 1.0)
            self.assertEqual(records["C1-07"]["changedParameter"]["name"], "splitEndReliefMm")
            self.assertEqual(records["C1-07"]["details"]["centerGapMm"], 0.0)
            self.assertEqual(records["C1-06"]["details"]["centerGapMm"], 0.5)
            self.assertEqual(records["C1-06"]["quantity"], 2)
            self.assertEqual(len(records["C1-06"]["files"]), 4)
            guard = next(part for part in parts if part.id.endswith("CPN-C1-01"))
            edge = next(part for part in parts if part.id.endswith("CPN-C1-AL-EDGE"))
            self.assertLess(guard.solid.intersect(edge.solid).Volume(), 1e-7)
            self.assertTrue(all(value is None for record in records.values()
                                for value in record["results"].values()))
            for record in records.values():
                for relative_path in record["files"]:
                    self.assertTrue((ROOT / relative_path).is_file(), relative_path)
                self.assertEqual([file["path"] for file in record["fileHashes"]], record["files"])
                for file in record["fileHashes"]:
                    target = ROOT / file["path"]
                    self.assertEqual(file["bytes"], target.stat().st_size)
                    self.assertEqual(file["sha256"], sha256_file(target))
            self.assertEqual(len(records["C3-01"]["files"]), 4)
            self.assertEqual(len(records["C3-02"]["files"]), 4)
            self.assertEqual(len(records["C3-03"]["files"]), 4)
            self.assertEqual({plate["sourceEdgeOffsetMm"]
                              for plate in records["C3-01"]["details"]["plates"]}, {10.0, 11.5})

            c2_records = [records[f"C2-{index:02d}"] for index in range(1, 4)]
            self.assertEqual([record["details"]["locatorClearanceMm"] for record in c2_records],
                             [0.7, 0.5, 0.9])
            self.assertEqual([record["changedParameter"] for record in c2_records], [
                None,
                {"name": "top_edge_lid_locator_clearance", "baselineValue": 0.7, "couponValue": 0.5},
                {"name": "top_edge_lid_locator_clearance", "baselineValue": 0.7, "couponValue": 0.9},
            ])
            for record in c2_records:
                details = record["details"]
                self.assertEqual(len(record["files"]), 12)
                self.assertAlmostEqual(details["frontWallToRailEnvelopeGapMm"], 8.32318, places=5)
                self.assertFalse(details["verticalRemovalPathCheck"]["candidateBrepIntersectionFound"])
                self.assertIsNone(details["verticalRemovalPathCheck"]["physicalLiftOffResult"])
                self.assertEqual(details["verticalRemovalPathCheck"]["sampleStepMm"], 1)
                self.assertEqual(len(details["components"]), 5)
                self.assertTrue(all(value is None for value in record["results"].values()))
            c2_parts = {part.id: part for part in parts if "-CPN-C2-" in part.id}
            frame_volumes = []
            for record in c2_records:
                roles = {component["partId"].rsplit("-", 1)[-1]: component
                         for component in record["details"]["components"]}
                self.assertEqual(set(roles), {"WALL", "ENVELOPE", "GUARD", "FRAME", "PLATE"})
                frame = c2_parts[roles["FRAME"]["partId"]]
                frame_volumes.append(frame.solid.Volume())
                for component in record["details"]["components"]:
                    part = c2_parts[component["partId"]]
                    for relative in component["files"]:
                        path = ROOT / relative
                        self.assertLess(path.stat().st_size, 25 * 1024 * 1024, relative)
                        if path.suffix == ".step":
                            imported = cq.importers.importStep(str(path)).val()
                            self.assertTrue(imported.isValid(), relative)
                            self.assertAlmostEqual(imported.Volume(), part.solid.Volume(), places=4)
                        elif path.suffix == ".stl":
                            self.assertTrue(inspect_binary_stl(path, part.solid)["closedManifold"])
                        elif path.suffix == ".dxf":
                            modelspace = ezdxf.readfile(path).modelspace()
                            circles = list(modelspace.query('CIRCLE[layer=="HOLES"]'))
                            if component["partId"].endswith("-LID-PLATE"):
                                self.assertEqual(len(circles), 1)
                                self.assertAlmostEqual(circles[0].dxf.radius, 1.7, places=6)
                            if component["partId"].endswith("-BODY-WALL"):
                                self.assertEqual(circles, [])
            self.assertEqual(len(set(round(volume, 5) for volume in frame_volumes)), 3)
            baseline_components = {
                component["partId"].rsplit("-", 1)[-1]: c2_parts[component["partId"]]
                for component in c2_records[0]["details"]["components"]
            }
            for record in c2_records[1:]:
                variant_components = {
                    component["partId"].rsplit("-", 1)[-1]: c2_parts[component["partId"]]
                    for component in record["details"]["components"]
                }
                for role in ("WALL", "ENVELOPE", "GUARD", "PLATE"):
                    self.assertAlmostEqual(
                        baseline_components[role].solid.Volume(),
                        variant_components[role].solid.Volume(), places=6,
                    )
            self.assertAlmostEqual(
                c2_parts["7U40-R9-CPN-C2-01-BODY-WALL"].solid.intersect(
                    c2_parts["7U40-R9-CPN-C2-01-GUARD"].solid).Volume(), 0.0, places=7,
            )
            self.assertAlmostEqual(
                c2_parts["7U40-R9-CPN-C2-01-GUARD"].solid.intersect(
                    c2_parts["7U40-R9-CPN-C2-01-LID-FRAME"].solid).Volume(), 0.0, places=7,
            )
            self.assertAlmostEqual(
                c2_parts["7U40-R9-CPN-C2-01-LID-FRAME"].solid.intersect(
                    c2_parts["7U40-R9-CPN-C2-01-LID-PLATE"].solid).Volume(), 0.0, places=7,
            )

            c3_parts = {part.id: part for part in parts if "-C3-" in part.id}
            for coupon, expected_slots, expected_rounds, arc_center_spacing in (
                    ("C3-01", 1, 0, 2.0), ("C3-02", 1, 0, 3.0), ("C3-03", 0, 1, None)):
                plate_parts = [part for part in c3_parts.values() if f"-CPN-{coupon}-" in part.id]
                self.assertEqual(len(plate_parts), 2)
                for part in plate_parts:
                    bounds = part.solid.BoundingBox()
                    self.assertAlmostEqual(bounds.xlen, 32.0, places=6)
                    self.assertAlmostEqual(bounds.ylen, 20.0, places=6)
                    self.assertAlmostEqual(bounds.zlen, 1.5, places=6)
                    step_path = ctx.out / "coupons" / f"{part.id.lower()}-qty1-mm.step"
                    self.assertTrue(cq.importers.importStep(str(step_path)).val().isValid())
                    dxf_path = ctx.out / "coupons" / f"{part.id.lower()}-qty1-mm.dxf"
                    modelspace = ezdxf.readfile(dxf_path).modelspace()
                    arcs = list(modelspace.query('ARC[layer=="SLOTS"]'))
                    self.assertEqual(len(list(modelspace.query('LINE[layer=="SLOTS"]'))), 2 * expected_slots)
                    self.assertEqual(len(arcs), 2 * expected_slots)
                    circles = list(modelspace.query('CIRCLE[layer=="HOLES"]'))
                    self.assertEqual(len(circles), expected_rounds)
                    if expected_slots:
                        self.assertTrue(all(abs(arc.dxf.radius - 2.75) < 1e-6 for arc in arcs))
                        centers = sorted({(round(arc.dxf.center.x, 6), round(arc.dxf.center.y, 6))
                                          for arc in arcs})
                        self.assertEqual(len(centers), 2)
                        self.assertAlmostEqual(abs(centers[1][1] - centers[0][1]), arc_center_spacing)
                    if expected_rounds:
                        self.assertAlmostEqual(circles[0].dxf.radius, 2.75, places=6)

            first_hashes = {path.relative_to(ctx.out): sha256_file(path)
                            for path in (ctx.out / "coupons").rglob("*") if path.is_file()}
            rebuilt = build_coupons(ctx)
            for part in rebuilt:
                export_part(ctx, part)
            finalize_coupons(ctx)
            second_hashes = {path.relative_to(ctx.out): sha256_file(path)
                             for path in (ctx.out / "coupons").rglob("*") if path.is_file()}
            self.assertEqual(first_hashes, second_hashes)

    def test_lid_clearance_parameter_changes_baseline_c2_coupon(self):
        baseline = load_params()
        changed = copy.deepcopy(baseline)
        changed["lid"]["top_edge_lid_locator_clearance"]["value"] = 0.8
        with TemporaryDirectory(dir=ROOT) as temp:
            baseline_ctx = _context(str(Path(temp) / "baseline"), baseline)
            changed_ctx = _context(str(Path(temp) / "changed"), changed)
            baseline_parts, baseline_records = _build_c2(baseline_ctx)
            changed_parts, changed_records = _build_c2(changed_ctx)
            baseline_frame = next(part for part in baseline_parts
                                  if part.id.endswith("CPN-C2-01-LID-FRAME"))
            changed_frame = next(part for part in changed_parts
                                 if part.id.endswith("CPN-C2-01-LID-FRAME"))
            self.assertNotAlmostEqual(
                baseline_frame.solid.Volume(), changed_frame.solid.Volume(), places=5,
            )
            self.assertEqual(baseline_records[0]["details"]["locatorClearanceMm"], 0.7)
            self.assertEqual(changed_records[0]["details"]["locatorClearanceMm"], 0.8)

    def test_guard_parameter_changes_body_guard_and_c1_coupon(self):
        baseline = load_params()
        changed = copy.deepcopy(baseline)
        changed["guards"]["fitClearancePerSide"]["value"] = 0.25
        with TemporaryDirectory(dir=ROOT) as temp:
            baseline_ctx = _context(str(Path(temp) / "baseline"), baseline)
            changed_ctx = _context(str(Path(temp) / "changed"), changed)
            baseline_guard = next(part for part in build_guards(baseline_ctx)
                                  if part.id.endswith("T1P2-TOP-A"))
            changed_guard = next(part for part in build_guards(changed_ctx)
                                 if part.id.endswith("T1P2-TOP-A"))
            baseline_coupon = next(part for part in _build_c1(baseline_ctx)[0]
                                   if part.id.endswith("CPN-C1-01"))
            changed_coupon = next(part for part in _build_c1(changed_ctx)[0]
                                  if part.id.endswith("CPN-C1-01"))
            self.assertNotAlmostEqual(baseline_guard.solid.Volume(), changed_guard.solid.Volume(), places=5)
            self.assertNotAlmostEqual(baseline_coupon.solid.Volume(), changed_coupon.solid.Volume(), places=5)


if __name__ == "__main__":
    unittest.main()
