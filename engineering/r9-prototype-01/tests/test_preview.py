"""Targeted contracts for the R9 offline preview outputs."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PREVIEW_OUT = ROOT / "out" / "preview"
LIMIT_BYTES = 25 * 1024 * 1024


def load_model() -> dict:
    source = (PREVIEW_OUT / "model-data.js").read_text(encoding="utf-8")
    match = re.fullmatch(r'window\.ZUDO_R9_MODEL_GZIP = "([A-Za-z0-9+/=]+)";\n', source)
    if not match:
        raise AssertionError("invalid R9 model-data.js assignment")
    return json.loads(gzip.decompress(base64.b64decode(match.group(1))))


class PreviewArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_model()
        cls.file_table = json.loads((PREVIEW_OUT / "file-table.json").read_text(encoding="utf-8"))
        cls.section_index = json.loads((PREVIEW_OUT / "sections" / "index.json").read_text(encoding="utf-8"))

    def test_mesh_contract_and_assembly_parts(self):
        model = self.model
        self.assertEqual((model["revision"], model["model"], model["units"]),
                         ("R9-PROTOTYPE-01", "7u40", "mm"))
        self.assertEqual(model["status"], "unapproved_prototype")
        self.assertFalse(model["geometrySources"]["mixesR8Mesh"])
        parts = model["parts"]
        self.assertEqual([(p["partId"], p["instanceId"]) for p in parts],
                         sorted((p["partId"], p["instanceId"]) for p in parts))
        self.assertEqual(sum(p["partId"] == "R6-40HP-RAIL-DISPLAY" for p in parts), 6)
        self.assertTrue(all(abs(p["dimensionsMm"][0] - 204.0) < 1e-5
                            for p in parts if p["partId"] == "R6-40HP-RAIL-DISPLAY"))
        expected_instances = {
            "7U40-R9-AL-BOTTOM": 1,
            "7U40-R9-AL-FRONT-BACK": 2,
            "7U40-R9-AL-LEFT-RIGHT": 2,
            "7U40-R9-LID-PLATE": 1,
            "7U40-R9-PREVIEW-KNOB-ENVELOPE": 1,
        }
        for part_id, quantity in expected_instances.items():
            self.assertEqual(sum(p["partId"] == part_id for p in parts), quantity, part_id)
        self.assertTrue(any(p["partId"] == "7U40-R9-PA12-LID-FRAME-FR" for p in parts))
        self.assertTrue(any(p["partId"] == "7U40-R9-PA12-GUARD-T1P2-TOP-A" for p in parts))
        for part in parts:
            self.assertTrue(part["positions"])
            self.assertEqual(len(part["positions"]) % 3, 0)
            self.assertEqual(len(part["indices"]) % 3, 0)
            self.assertTrue(all(0 <= index < len(part["positions"]) // 3 for index in part["indices"]))
            self.assertEqual(len(part["dimensionsMm"]), 3)
            self.assertTrue(all(value > 0 for value in part["dimensionsMm"]))
            self.assertNotIn("R8", part["partId"])

    def test_file_table_hashes_and_package_names(self):
        self.assertEqual(self.file_table["revision"], "R9-PROTOTYPE-01")
        self.assertEqual(self.file_table["status"], "unapproved_prototype")
        self.assertEqual(self.file_table["packageNames"], {
            "aluminum": "7u40-r9-prototype-01-aluminum-NOT-APPROVED.zip",
            "pa12": "7u40-r9-prototype-01-pa12-NOT-APPROVED.zip",
            "coupons": "7u40-r9-prototype-01-coupons-NOT-APPROVED.zip",
        })
        self.assertTrue(self.file_table["parts"])
        for part in self.file_table["parts"]:
            self.assertTrue(part["partId"].startswith("7U40-R9-"))
            self.assertTrue(part["formats"])
            for file in part["formats"]:
                path = REPO / file["path"]
                raw = path.read_bytes()
                self.assertLess(len(raw), LIMIT_BYTES, file["path"])
                self.assertEqual(len(raw), file["bytes"], file["path"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), file["sha256"], file["path"])

    def test_section_index_covers_candidate_and_unconfirmed_geometry_values(self):
        params = {
            namespace: json.loads((ROOT / "params" / f"{namespace}.json").read_text(encoding="utf-8"))
            for namespace in ("slots", "guards", "lid")
        }
        expected = {(namespace, key) for namespace, records in params.items()
                    for key, record in records.items()
                    if record["status"] in ("candidate", "provisional", "unvalidated")
                    and record["unit"] != "sha256"}
        actual = {(entry["namespace"], entry["key"]) for entry in self.section_index["sections"]}
        self.assertEqual(actual, expected)
        required = {"slots.slot_length", "guards.fitClearancePerSide", "guards.adhesiveLayer",
                    "lid.top_edge_lid_locator_clearance"}
        self.assertTrue(required.issubset({entry["paramId"] for entry in self.section_index["sections"]}))
        for entry in self.section_index["sections"]:
            self.assertIn("old", entry)
            self.assertIn("new", entry)
            self.assertTrue(entry["reason"])
            path = PREVIEW_OUT / entry["image"]
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"), entry["image"])
            self.assertLess(len(raw), LIMIT_BYTES, entry["image"])

    def test_single_file_preview_is_offline_and_below_asset_limit(self):
        html = REPO / "public" / "previews" / "r9-prototype-01.html"
        raw = html.read_bytes()
        self.assertLess(len(raw), LIMIT_BYTES)
        text = raw.decode("utf-8")
        self.assertNotRegex(text, r"<(?:script|link)[^>]+(?:src|href)=['\"](?:https?:)?//")
        for marker in ("R9-PROTOTYPE-01", "未承認", "data-state=\"daily\"",
                       "data-state=\"travel\"", "data-state=\"open\"", "max=\"150\""):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
