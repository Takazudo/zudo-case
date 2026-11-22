"""Check the shipped R8 candidate, its package inventories and preserved inputs."""
from pathlib import Path
import hashlib
import base64
import gzip
import io
import json
import re
import math
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def checked_zip(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, str(path)
        names = z.namelist()
        assert len(names) == len(set(names)), "Duplicate archive member"
        receipts = {}
        for line in z.read("MANIFEST.sha256").decode().splitlines():
            sha, name = line.split("  ", 1)
            assert name not in receipts, name
            receipts[name] = sha
            assert hashlib.sha256(z.read(name)).hexdigest() == sha, name
        assert set(receipts) == set(names) - {"MANIFEST.sha256"}
        return {n: z.read(n) for n in names}


def main():
    manifest = json.loads((ROOT / "project/tenbox-v2/r8-review.json").read_text())
    assert manifest["revision"] == "R8" and manifest["production_approved"] is False
    assert manifest["user_confirmation"] == "pending"
    for record in manifest["files"] + manifest["preserved_inputs"] + manifest["preserved_previous_review"]:
        p = ROOT / record["path"]
        raw = p.read_bytes()
        assert len(raw) == record["bytes"], record["path"]
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], record["path"]
    review = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r8-review.zip")
    geometry = json.loads(review["geometry-checks.json"])
    assert len(geometry) == manifest["verification"]["cad_check_count"]
    assert geometry and all(c["passed"] for c in geometry)
    model = json.loads(review["model_data.json"])
    assert model["production_approved"] is False
    assert model["railLayout"]["railBodies"] == 3
    assert math.isclose(model["railSource"]["panelPlaneZ"], 88.131103, abs_tol=1e-9)
    assert model["mountParameters"]["selected_frame_slot"] == "lower"
    assert model["mountParameters"]["frame_hole_index"] == 1
    assert math.isclose(model["mountParameters"]["mount_z_mm"], 66.8205295, abs_tol=1e-8)
    assert math.isclose(model["mountParameters"]["frame_raise_from_r7_mm"], 12.631103, abs_tol=1e-9)
    assert math.isclose(108-model["railSource"]["panelPlaneZ"], 19.868897, abs_tol=1e-9)
    assert math.isclose(model["railSource"]["panelPlaneZ"]+27-108, 7.131103, abs_tol=1e-9)
    assert model["mountParameters"]["frame_to_side_inner_face_gap_mm"] == 8
    assert len(model["sideFixingParameters"]["slots"]) == 8
    assert model["bracketParameters"]["total"] == 26
    fasteners = model["bracketParameters"]["fasteners"]
    assert len(fasteners) == 52, "Every L bracket must have both fastening legs modeled"
    assert all(f["nut_side"] == "inside" for f in fasteners), "L-bracket nut on exterior"
    assert sum(f["nut_height_mm"] == 2.7 for f in fasteners) == 34
    assert sum(f["nut_height_mm"] == 4.0 for f in fasteners) == 18
    assert all(f["thread_engagement_mm"] >= f["nut_height_mm"] - 0.000001 for f in fasteners)
    assert all(f["thread_projection_mm"] > 0 for f in fasteners)
    assert all(l["window_edge_clearance_mm"] == 3.0 for l in model["sideFixingParameters"]["ledges"])
    rail_nuts = [p for p in model["parts"] if p["id"].startswith("rail-nut-")]
    rail_washers = [p for p in model["parts"] if p["id"].startswith("rail-washer-")]
    assert len(rail_nuts) == len(rail_washers) == 8
    assert all(p["nutSide"] == "outside" for p in rail_nuts)
    assert all(abs(p["box"][4] - p["box"][1] - 10) < 0.000001 and
               abs(p["box"][5] - p["box"][2] - 10) < 0.000001 and
               p["box"][5] < 72 for p in rail_washers), "Rail washers contact the lift-off lid"
    schedule = json.loads(review["fastener-schedule.json"])
    assert schedule["bracket_connections"] == 52 and schedule["rail_frame_connections"] == 8
    assert sum(r["quantity"] for r in schedule["rows"] if r["nut_side"] == "inside") == 52
    assert sum(r["quantity"] for r in schedule["rows"] if r["nut_side"] == "outside") == 8
    assert len(model["floorSeatParameters"]["seats"]) == 4
    prints = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r8-print.zip")
    report = json.loads(prints["h2d-project-report.json"])
    assert (report["project_count"], report["stored_object_count"],
            report["required_physical_part_count"], report["plate_runs_for_assembly"]) == (15, 22, 23, 16)
    assert report["based_on"] == "R7"
    assert report["changed_project_count"] == 0 and report["byte_identical_project_count"] == 15
    assert report["printed_geometry"]["part_count"] == 23 and report["printed_geometry"]["all_passed"]
    previous_prints = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r7-print.zip")
    assert report["global_settings_bytes_unchanged"] and report["object_plate_settings_bytes_unchanged"]
    assert report["sliced"] is False and report["studio_application_loaded"] is False
    for part in report["parts"]:
        name = part["project_file"]
        raw = prints[name]
        assert hashlib.sha256(raw).hexdigest() == part["project_sha256"]
        baseline_raw = previous_prints[name]
        with zipfile.ZipFile(io.BytesIO(raw)) as z, zipfile.ZipFile(io.BytesIO(baseline_raw)) as old:
            for member in ["Metadata/project_settings.config", "Metadata/model_settings.config"]:
                assert z.read(member) == old.read(member), (name, member)
        assert not part["changed_geometry_in_r8"]
        assert raw == baseline_raw, name
    source = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r8-source.zip")
    assert source["public/downloads/candidate/tenbox-v2-r7-print.zip"] == (ROOT / "public/downloads/candidate/tenbox-v2-r7-print.zip").read_bytes()
    assert source["engineering/tenbox-v2/r8/reference/r7-model-data.json.gz"] == (ROOT / "engineering/tenbox-v2/r8/reference/r7-model-data.json.gz").read_bytes()
    assert "engineering/tenbox-v2/r8/reference/user-feedback/08-lower-slot-alignment.png" in source
    preview = (ROOT / "public/previews/tenbox-v2-r8.html").read_text()
    assert 'id="tenbox-v2-r8"' in preview
    embedded = re.search(r'<script[^>]*data-id="model"[^>]*>([^<]+)</script>', preview)
    assert embedded, "Missing embedded model"
    view = json.loads(gzip.decompress(base64.b64decode(embedded.group(1))))
    assert view["baselineParts"] and len(view["baselineParts"]) == len(view["parts"])
    assert "lower-slot" in view["jointScenes"] and "lower-slot" in view["baselineJointScenes"]
    model_sha = hashlib.sha256(review["model_data.json"]).hexdigest()
    assert view["previewMetadata"]["sourceModelSha256"] == model_sha == manifest["model_sha256"]
    print(f"R8 review: {len(geometry)} CAD checks, 15 H2D projects, 23 unchanged printed parts, 15 byte-identical R7 projects; all package hashes verified.")


if __name__ == "__main__":
    main()
