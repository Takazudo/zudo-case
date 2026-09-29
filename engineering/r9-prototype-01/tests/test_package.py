"""Focused package scope, cost discipline, hash, size, and repeatability checks."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile

from r9.package import (
    CANDIDATE,
    LIMIT_BYTES,
    NEW_COMMITTED_FILES,
    OUT,
    OUTPUT_MANIFEST,
    PACKAGE_NAMES,
    REPO_ROOT,
    SIZE_INVENTORY,
    build,
)


class CandidatePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build()
        cls.initial_bytes = {
            path: (REPO_ROOT / path).read_bytes()
            for path in (
                "engineering/r9-prototype-01/out/bom.json",
                "engineering/r9-prototype-01/out/bom.csv",
                "engineering/r9-prototype-01/out/DIFF-FROM-R6-R8.md",
                "engineering/r9-prototype-01/out/outputs-manifest.json",
                "engineering/r9-prototype-01/out/SIZE-INVENTORY.json",
                *(f"public/downloads/candidate/{name}" for name in PACKAGE_NAMES.values()),
            )
        }

    def _zip(self, category):
        return CANDIDATE / PACKAGE_NAMES[category]

    def test_aluminum_package_contains_only_the_six_plate_set_and_tables(self):
        with zipfile.ZipFile(self._zip("aluminum")) as archive:
            names = archive.namelist()
            cad = [name for name in names if name.endswith((".step", ".dxf", ".stl"))]
            self.assertEqual(len([name for name in cad if name.endswith(".step")]), 4)
            self.assertEqual(len([name for name in cad if name.endswith(".dxf")]), 4)
            self.assertFalse(any(name.endswith(".stl") for name in cad))
            self.assertIn("hole-table.json", names)
            self.assertIn("slot-checks.json", names)
            self.assertIn("plates.json", names)
            plate_table = json.loads(archive.read("plates.json"))
            self.assertEqual(sum(row["quantity"] for row in plate_table["plates"]), 6)
            self.assertEqual({row["quantity"] for row in plate_table["plates"]}, {1, 2})
            self.assertIn("READ-BEFORE-ORDER.txt", names)
            self.assertIn("package-manifest.json", names)

    def test_pa12_and_coupon_packages_have_exact_material_scopes(self):
        with zipfile.ZipFile(self._zip("pa12")) as archive:
            names = archive.namelist()
            cad = [name for name in names if name.endswith((".step", ".stl", ".dxf"))]
            self.assertEqual(len(cad), 32)
            self.assertFalse(any(name.endswith(".dxf") for name in cad))
            self.assertTrue(all(name.endswith((".step", ".stl")) for name in cad))
            self.assertFalse(any("lid-plate" in name for name in names))
            table = json.loads(archive.read("quantities.json"))
            self.assertEqual([item["thicknessMm"] for item in table["guards"]], [1.2, 1.0])
            self.assertEqual([item["quantity"] for item in table["guards"]], [16, 16])
            self.assertEqual(table["lidFrame"]["quantity"], 4)

        with zipfile.ZipFile(self._zip("coupons")) as archive:
            names = archive.namelist()
            geometry = [name for name in names if name.startswith("coupons/")]
            self.assertTrue(geometry)
            self.assertTrue(all(name.split("/")[1] in {"C1", "C2", "C3"} for name in geometry))
            coupon_manifest = json.loads(archive.read("coupon-manifest.json"))
            referenced = {
                item["path"]
                for coupon in coupon_manifest["coupons"]
                for item in coupon.get("fileHashes", [])
            }
            self.assertEqual(referenced, set(geometry))
            self.assertIn("READ-BEFORE-ORDER.txt", names)

        for category in PACKAGE_NAMES:
            with zipfile.ZipFile(self._zip(category)) as archive:
                readme = archive.read("READ-BEFORE-ORDER.txt").decode("utf-8")
                self.assertIn("未承認", readme)
                self.assertIn("G01–G11", readme)
                self.assertIn("発注", readme)

    def test_bom_keeps_unquoted_prices_null_and_bracket_cash_separate(self):
        bom = json.loads((OUT / "bom.json").read_text(encoding="utf-8"))
        rows = [*bom["items"], *bom["coupons"], *bom["excludedFromCost"]]
        for row in rows:
            self.assertIsNone(row.get("unitPriceJpy"))
            self.assertIsNone(row.get("lineTotalJpy"))
        self.assertIsNone(bom["costSummary"]["quotedTotalJpy"])
        bracket = next(row for row in bom["items"] if row["id"] == "existing-stock-bracket-20x20x16")
        self.assertEqual(bracket["incrementalCashJpy"], 0)
        self.assertIsNone(bracket["productCostJpy"])
        csv_rows = list(csv.DictReader(io.StringIO((OUT / "bom.csv").read_text(encoding="utf-8"))))
        bracket_csv = next(row for row in csv_rows if row["id"] == bracket["id"])
        self.assertEqual(bracket_csv["incrementalCashJpy"], "0")
        self.assertEqual(bracket_csv["productCostJpy"], "")
        self.assertEqual(bracket_csv["measuredThicknessMm"], "2")
        strap_csv = next(row for row in csv_rows if row["id"] == "external-transport-strap")
        self.assertEqual(strap_csv["widthMm"], "20.0")
        self.assertEqual(strap_csv["estimatedLoopLengthMm"], "721.2")

    def test_output_manifest_and_sizes_cover_required_bytes_without_self_hash(self):
        manifest = json.loads(OUTPUT_MANIFEST.read_text(encoding="utf-8"))
        output_paths = {entry["path"] for entry in manifest["outputs"]}
        self.assertNotIn("engineering/r9-prototype-01/out/outputs-manifest.json", output_paths)
        self.assertIn("public/previews/r9-prototype-01.html", output_paths)
        for path in OUT.rglob("*"):
            if path.is_file() and path != OUTPUT_MANIFEST:
                self.assertIn(path.relative_to(REPO_ROOT).as_posix(), output_paths)
        for category, name in PACKAGE_NAMES.items():
            path = CANDIDATE / name
            self.assertLess(path.stat().st_size, LIMIT_BYTES)
            self.assertIn(path.relative_to(REPO_ROOT).as_posix(), output_paths)
            with zipfile.ZipFile(path) as archive:
                package_manifest = json.loads(archive.read("package-manifest.json"))
                package_names = set(archive.namelist()) - {"package-manifest.json"}
                self.assertEqual({item["path"] for item in package_manifest["files"]}, package_names)
                for item in package_manifest["files"]:
                    raw = archive.read(item["path"])
                    self.assertEqual(len(raw), item["bytes"], item["path"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["path"])

        for item in manifest["outputs"]:
            path = REPO_ROOT / item["path"]
            raw = path.read_bytes()
            self.assertEqual(len(raw), item["bytes"], item["path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["path"])
        for item in manifest["inputs"]:
            path = REPO_ROOT / item["path"]
            raw = path.read_bytes()
            self.assertEqual(len(raw), item["bytes"], item["path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["path"])
        r7_path = REPO_ROOT / manifest["r7ZipMembers"][0]["archive"]
        with zipfile.ZipFile(r7_path) as archive:
            for item in manifest["r7ZipMembers"]:
                raw = archive.read(item["member"])
                self.assertEqual(len(raw), item["bytes"], item["member"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["member"])

        self.assertTrue(manifest["r6SourceFiles"])
        self.assertTrue(manifest["r7ZipMembers"])
        self.assertTrue(manifest["browserEvidence"]["available"])
        self.assertIn("not CAD validation", manifest["browserEvidence"]["scope"])
        for item in manifest["browserEvidence"]["screenshots"]:
            raw = (REPO_ROOT / item["path"]).read_bytes()
            self.assertEqual(len(raw), item["bytes"], item["path"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["path"])

        inventory = json.loads(SIZE_INVENTORY.read_text(encoding="utf-8"))
        inventory_rows = {item["path"]: item["bytes"] for item in inventory["files"]}
        self.assertEqual(set(inventory_rows), set(NEW_COMMITTED_FILES))
        self.assertEqual(inventory["totalBytes"], sum(inventory_rows.values()))
        self.assertLess(inventory["totalBytes"], 40 * 1024 * 1024)
        for path, size in inventory_rows.items():
            self.assertLess(size, LIMIT_BYTES, path)
            if path.endswith("outputs-manifest.json"):
                self.assertEqual(size, OUTPUT_MANIFEST.stat().st_size)
            else:
                self.assertEqual(size, (REPO_ROOT / path).stat().st_size)

    def test_rebuilding_packages_produces_identical_bytes_and_manifest(self):
        build()
        for path, initial in self.initial_bytes.items():
            self.assertEqual((REPO_ROOT / path).read_bytes(), initial, path)


if __name__ == "__main__":
    unittest.main()
