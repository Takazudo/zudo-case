"""Regression of the R9 7u40 body plate patterns against the frozen R6 layout."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


PROTOTYPE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROTOTYPE_ROOT.parents[1]
sys.path.insert(0, str(PROTOTYPE_ROOT))

from build import load_params  # noqa: E402
from r9.body import make_plate_solid, plate_specs  # noqa: E402
from r9.common import export_dxf  # noqa: E402
from r9.types import BuildContext  # noqa: E402


class R6BodyRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = json.loads(
            (REPO_ROOT / "engineering/r6-body/engineering/7u40/aluminum/hole-layout.json")
            .read_text(encoding="utf-8")
        )
        context = BuildContext(PROTOTYPE_ROOT, PROTOTYPE_ROOT / "out", load_params())
        cls.specs = plate_specs(context)

    def test_plate_outlines_and_local_hole_centers_match_r6(self) -> None:
        self.assertEqual(sum(spec.quantity for spec in self.specs), 5)
        specs_by_type = {spec.part_type: spec for spec in self.specs}
        self.assertEqual(set(specs_by_type), {record["partType"] for record in self.reference["panels"]})

        for reference in self.reference["panels"]:
            with self.subTest(plate=reference["partType"]):
                spec = specs_by_type[reference["partType"]]
                self.assertEqual(spec.quantity, reference["quantity"])
                self.assertAlmostEqual(spec.width_mm, reference["widthMm"], delta=1e-6)
                self.assertAlmostEqual(spec.height_mm, reference["heightMm"], delta=1e-6)
                self.assertAlmostEqual(spec.thickness_mm, reference["thicknessMm"], delta=1e-6)
                self.assertEqual(len(spec.pattern_holes), reference["holeCount"])
                expected = sorted(tuple(point) for point in reference["holeCentersUV"])
                actual = sorted(hole.center_local_mm for hole in spec.pattern_holes)
                self.assertEqual(len(actual), len(expected))
                for actual_point, expected_point in zip(actual, expected):
                    self.assertAlmostEqual(actual_point[0], expected_point[0], delta=1e-6)
                    self.assertAlmostEqual(actual_point[1], expected_point[1], delta=1e-6)

    def test_46_round_holes_have_stable_ids_and_required_roles(self) -> None:
        holes = [hole for spec in self.specs for hole in spec.holes]
        self.assertEqual(len(holes), 46)
        self.assertEqual(len({hole.id for hole in holes}), 46)
        self.assertEqual(sum(hole.role == "bracket" for hole in holes), 36)
        self.assertEqual(sum(hole.role == "rail-fix" for hole in holes), 10)
        self.assertTrue(all(abs(hole.diameter_mm - 5.5) < 1e-9 for hole in holes))

        for hole in holes:
            with self.subTest(hole=hole.id):
                self.assertTrue(hole.id.startswith("7U40-R9-AL-"))
                self.assertTrue(hole.joint_id.startswith("7U40-R9-JNT-"))
                if hole.role == "bracket":
                    self.assertIsNotNone(hole.bracket_id)
                    self.assertTrue(hole.bracket_id.startswith("7U40-R9-HW-BRACKET-"))
                else:
                    self.assertIsNone(hole.bracket_id)
                    self.assertEqual(hole.face, "inside")

        bracket_ids = {hole.bracket_id for hole in holes if hole.bracket_id is not None}
        self.assertEqual(len(bracket_ids), 18)
        self.assertEqual(len({hole.joint_id for hole in holes}), 28)

    def test_plate_solids_use_assembly_coordinates(self) -> None:
        expected = {
            "bottom": ((-114.7, -167.0, 0.0), (114.7, 167.0, 1.5)),
            "front_back": ((-113.2, -167.0, 1.5), (113.2, -165.5, 91.0)),
            "left_right": ((113.2, -167.0, 1.5), (114.7, 167.0, 91.0)),
        }
        for spec in self.specs:
            with self.subTest(plate=spec.part_type):
                bounds = make_plate_solid(spec).BoundingBox()
                actual = ((bounds.xmin, bounds.ymin, bounds.zmin),
                          (bounds.xmax, bounds.ymax, bounds.zmax))
                for actual_point, expected_point in zip(actual, expected[spec.part_type]):
                    for actual_value, expected_value in zip(actual_point, expected_point):
                        self.assertAlmostEqual(actual_value, expected_value, delta=1e-6)

    def test_repeated_dxf_exports_are_byte_identical(self) -> None:
        outline = ((0.0, 0.0), (80.0, 0.0), (80.0, 40.0), (0.0, 40.0))
        holes = ((12.0, 10.0, 2.75), (68.0, 30.0, 2.75))
        slots = ((40.0, 20.0, 12.0, 5.5, 30.0),)
        with TemporaryDirectory() as directory:
            first = Path(directory) / "first.dxf"
            second = Path(directory) / "second.dxf"
            export_dxf(first, outline, holes, slots)
            export_dxf(second, outline, holes, slots)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
