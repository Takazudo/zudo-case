"""Check the shipped R6 candidate, its package inventories and preserved inputs."""
from pathlib import Path
import hashlib
import base64
import gzip
import io
import json
import re
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
    manifest = json.loads((ROOT / "project/tenbox-v2/r6-review.json").read_text())
    assert manifest["revision"] == "R6" and manifest["production_approved"] is False
    assert manifest["user_confirmation"] == "pending"
    for record in manifest["files"] + manifest["preserved_inputs"]:
        p = ROOT / record["path"]
        raw = p.read_bytes()
        assert len(raw) == record["bytes"], record["path"]
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], record["path"]
    review = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r6-review.zip")
    geometry = json.loads(review["geometry-checks.json"])
    assert len(geometry) == manifest["verification"]["cad_check_count"]
    assert geometry and all(c["passed"] for c in geometry)
    model = json.loads(review["model_data.json"])
    assert model["production_approved"] is False
    assert model["railLayout"]["railBodies"] == 3
    assert model["railSource"]["panelPlaneZ"] == 74
    assert model["mountParameters"]["frame_to_side_inner_face_gap_mm"] == 8
    assert len(model["sideFixingParameters"]["slots"]) == 8
    assert model["bracketParameters"]["total"] == 26
    assert len(model["floorSeatParameters"]["seats"]) == 4
    prints = checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r6-print.zip")
    report = json.loads(prints["h2d-project-report.json"])
    assert (report["project_count"], report["stored_object_count"],
            report["required_physical_part_count"], report["plate_runs_for_assembly"]) == (15, 22, 23, 16)
    assert report["changed_project_count"] == 3 and report["byte_identical_project_count"] == 12
    assert report["global_settings_bytes_unchanged"] and report["object_plate_settings_bytes_unchanged"]
    assert report["sliced"] is False and report["studio_application_loaded"] is False
    for part in report["parts"]:
        name = part["project_file"]
        raw = prints[name]
        assert hashlib.sha256(raw).hexdigest() == part["project_sha256"]
        baseline = ROOT / "engineering/tenbox-v2/r5/source/h2d-r5/projects" / Path(name).name
        with zipfile.ZipFile(io.BytesIO(raw)) as z, zipfile.ZipFile(baseline) as old:
            for member in ["Metadata/project_settings.config", "Metadata/model_settings.config"]:
                assert z.read(member) == old.read(member), (name, member)
        if not part["changed_geometry_in_r6"]:
            assert raw == baseline.read_bytes(), name
    checked_zip(ROOT / "public/downloads/candidate/tenbox-v2-r6-source.zip")
    preview = (ROOT / "public/previews/tenbox-v2-r6.html").read_text()
    assert 'id="tenbox-v2-r6"' in preview
    embedded = re.search(r'<script[^>]*data-id="model"[^>]*>([^<]+)</script>', preview)
    assert embedded, "Missing embedded model"
    view = json.loads(gzip.decompress(base64.b64decode(embedded.group(1))))
    model_sha = hashlib.sha256(review["model_data.json"]).hexdigest()
    assert view["previewMetadata"]["sourceModelSha256"] == model_sha == manifest["model_sha256"]
    print(f"R6 review: {len(geometry)} CAD checks, 15 H2D projects, 3 changed meshes, 12 retained projects; all package hashes verified.")


if __name__ == "__main__":
    main()
