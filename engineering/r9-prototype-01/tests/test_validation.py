"""Integration checks for the R9 aggregate validation outputs."""
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


class ValidationReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((OUT / "validation.json").read_text(encoding="utf-8"))
        cls.build_log = json.loads((OUT / "build-log.json").read_text(encoding="utf-8"))
        cls.coupon_manifest = json.loads(
            (OUT / "coupons" / "coupon-manifest.json").read_text(encoding="utf-8")
        )
        cls.checks = {item["id"]: item for item in cls.report["checks"]}
        cls.outputs = {item["path"]: item for item in cls.build_log["outputs"]}

    def test_report_totals_and_unvalidated_scope_are_explicit(self):
        counts = {
            status: sum(item["status"] == status for item in self.report["checks"])
            for status in ("pass", "flag", "fail")
        }
        self.assertEqual(counts, {
            "pass": self.report["summary"]["passed"],
            "flag": self.report["summary"]["flagged"],
            "fail": self.report["summary"]["failed"],
        })
        self.assertEqual(self.report["summary"]["checkCount"], len(self.report["checks"]))
        self.assertEqual(self.report["status"], "passed_with_flags")
        self.assertEqual(self.report["summary"]["failed"], 0)
        self.assertFalse(self.report["productionApproved"])
        for required in ("FEA", "real materials", "anodizing", "Drop resistance",
                         "fatigue", "Band tension", "(G05)", "(G06)", "(G11)"):
            self.assertTrue(any(required.lower() in item.lower()
                                for item in self.report["not_validated"]), required)

    def test_body_plate_and_hole_table_checks(self):
        self.assertEqual(self.report["plateCounts"], {"body": 5, "lid": 1})
        self.assertEqual(self.report["holeCounts"], {"total": 46, "slots": 36, "round": 10})
        for check_id in ("body-hole-table-counts", "body-dxf-vs-hole-table",
                         "body-step-vs-hole-table-positions",
                         "body-plate-dimensions-and-count", "lid-plate-dimensions-and-count"):
            self.assertEqual(self.checks[check_id]["status"], "pass", check_id)

    def test_every_generated_stl_has_a_status_and_candidate_meshes_pass(self):
        stl_paths = {path for path in self.outputs if path.lower().endswith(".stl")}
        rows = {item["id"].removeprefix("stl:"): item
                for item in self.report["checks"] if item["id"].startswith("stl:")}
        self.assertEqual(set(rows), stl_paths)
        candidates = [item for item in rows.values()
                      if item["details"]["artifactRole"] == "unapproved R9 candidate geometry"]
        self.assertEqual(len(candidates), self.report["meshSummary"]["candidateStlCount"])
        for item in candidates:
            self.assertEqual(item["status"], "pass", item["id"])
            self.assertTrue(item["details"]["closedManifold"], item["id"])
            self.assertTrue(item["details"]["positiveVolume"], item["id"])
            self.assertTrue(item["details"]["volumeMatchesStep"], item["id"])
            self.assertLessEqual(item["details"]["bboxMaxDeltaMm"],
                                 item["details"]["strictBboxToleranceMm"], item["id"])

    def test_reference_mesh_flags_keep_bbox_and_topology_evidence(self):
        flagged = self.report["meshSummary"]["flaggedFiles"]
        bbox_flags = [item for item in flagged if item["artifactRole"] == "provisional reference envelope"]
        self.assertEqual(len(bbox_flags), 6)
        self.assertLessEqual(max(item["bboxMaxDeltaMm"] for item in bbox_flags),
                             self.report["meshSummary"]["bboxTessellationToleranceMm"])
        self.assertGreater(max(item["bboxMaxDeltaMm"] for item in bbox_flags),
                           self.report["meshSummary"]["strictBboxToleranceMm"])

        pcb = next(item for item in flagged if item["path"].endswith("pcb-fixer-qty2-mm.stl"))
        self.assertEqual(pcb["artifactRole"], "source-derived display geometry")
        self.assertFalse(pcb["closedManifold"])
        self.assertEqual(pcb["edgeIncidenceHistogram"], {"1": 20, "2": 18950, "6": 4})
        self.assertEqual(self.checks["hardware-envelope-stl-scope"]["status"], "flag")

    def test_c2_coupon_hashes_are_in_the_combined_ledger_and_preview(self):
        c2_files = [file for coupon in self.coupon_manifest["coupons"]
                    if coupon["id"].startswith("C2-")
                    for file in coupon["fileHashes"]]
        self.assertEqual(len(c2_files), 36)
        for file in c2_files:
            entry = self.outputs[file["path"]]
            self.assertEqual(entry["sha256"], file["sha256"], file["path"])
            self.assertEqual(entry["bytes"], file["bytes"], file["path"])
            actual = (ROOT / file["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(actual).hexdigest(), file["sha256"], file["path"])
        table = json.loads((OUT / "preview" / "file-table.json").read_text(encoding="utf-8"))
        table_paths = {file["path"] for part in table["parts"] for file in part["formats"]}
        html = (ROOT.parents[1] / "public" / "previews" / "r9-prototype-01.html").read_text(
            encoding="utf-8"
        )
        for file in c2_files:
            public_path = "engineering/r9-prototype-01/" + file["path"]
            self.assertIn(public_path, table_paths)
            self.assertIn(public_path, html)
        self.assertEqual(self.checks["preview-c2-file-table"]["status"], "pass")
        self.assertEqual(self.checks["preview-public-html-c2-catalog"]["status"], "pass")

    def test_slot_assembly_and_parameter_checks_are_aggregated(self):
        for check_id in ("s2-slot-profile-counts", "s2-slot-edge", "s2-slot-ligament",
                         "s2-slot-toolAccess", "s2-slot-guardContact",
                         "s4b-tested-static-interference", "s4b-lift-path-nominal-screen",
                         "s4b-slot-guard-contact", "s4b-m5-nominal-tool-envelope"):
            self.assertEqual(self.checks[check_id]["status"], "pass", check_id)
        self.assertEqual(self.checks["s2-slot-bearing-coverage"]["status"], "flag")
        self.assertEqual(self.checks["s4b-band-contact-and-deflection"]["status"], "flag")
        parameter_checks = [item for item in self.report["checks"]
                            if item["id"].startswith("parameter-")]
        self.assertEqual(len(parameter_checks), 8)
        self.assertTrue(all(item["status"] == "pass" for item in parameter_checks))


if __name__ == "__main__":
    unittest.main()
