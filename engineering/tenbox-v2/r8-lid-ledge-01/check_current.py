#!/usr/bin/env python3
"""Verify the published connected-lid replacement using only the standard library.

The immutable R8 archives are the comparison authority. This checks the actual
published bytes, quantities, preserved geometry/settings and rendered meshes;
the CAD builder supplies the separate exact Boolean/fit evidence. --build DIR
checks a complete disposable build before its assets are published.
"""
from pathlib import Path, PurePosixPath
import argparse
import base64
import gzip
import hashlib
import io
import json
import math
import re
import zipfile


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
REVISION = "R8-LID-LEDGE-01"
PREFIX = "tenbox-v2-r8-lid-ledge-01"
PART_STEM = "10box-v2-lid-frontback-connected-r01"
CHANGED = {"lid-front", "lid-back"}
APPROVED_STL = "3426afa3086cdee245bb4dfa63387a8576b7d8551d895a982aa2a4b81f03859a"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_zip(path):
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f"ZIP CRC failed: {path}")
        names = archive.namelist()
        require(len(names) == len(set(names)), f"Duplicate ZIP members: {path}")
        for name in names:
            item = PurePosixPath(name)
            require(not item.is_absolute() and ".." not in item.parts,
                    f"Unsafe ZIP member: {name}")
        receipts = {}
        for line in archive.read("MANIFEST.sha256").decode().splitlines():
            sha, name = line.split("  ", 1)
            require(name not in receipts, f"Duplicate inventory entry: {name}")
            require(re.fullmatch(r"[0-9a-f]{64}", sha), f"Invalid digest: {name}")
            receipts[name] = sha
            require(digest(archive.read(name)) == sha, f"ZIP member digest: {name}")
        require(set(receipts) == set(names) - {"MANIFEST.sha256"},
                f"Incomplete ZIP inventory: {path}")
        return {name: archive.read(name) for name in names}


def json_member(archive, name):
    return json.loads(archive[name])


def check_receipts(records):
    for record in records:
        path = ROOT / record["path"]
        raw = path.read_bytes()
        require(len(raw) == record["bytes"] and digest(raw) == record["sha256"],
                f"Published/preserved receipt mismatch: {record['path']}")


def check_prints(current, previous):
    report = json_member(current, "h2d-project-report.json")
    before = json_member(previous, "h2d-project-report.json")
    require(report["revision"] == REVISION and report["based_on"] == "R8",
            "Wrong print-set revision")
    counts = ("project_count", "stored_object_count", "required_physical_part_count",
              "plate_runs_for_assembly", "changed_project_count", "byte_identical_project_count")
    require(tuple(report[key] for key in counts) == (15, 22, 23, 16, 2, 13),
            "Complete print-set quantities changed")
    require(report["global_settings_bytes_unchanged"] and report["object_plate_settings_bytes_unchanged"],
            "Saved H2D settings preservation not established")
    require(all(report[key] is False for key in ("sliced", "studio_application_loaded", "production_approved")),
            "Unexpected print validation/approval claim")
    parts = {part["part_id"]: part for part in report["parts"]}
    old_parts = {part["part_id"]: part for part in before["parts"]}
    require(len(parts) == len(report["parts"]) == 15 and set(parts) == set(old_parts),
            "Missing, duplicated or unexpected print projects")
    projects = {name for name in current if name.startswith("projects/") and name.endswith(".3mf")}
    require(projects == {p["project_file"] for p in parts.values()}, "Unreported print project")
    require(projects == {p["project_file"] for p in old_parts.values()}, "Project filenames changed")
    changed = set()
    for pid, part in parts.items():
        old = old_parts[pid]
        for key in ("project_file", "assembly_ids", "stored_object_count",
                    "required_physical_quantity", "plate_runs_for_assembly"):
            require(part[key] == old[key], f"Print quantity or assignment changed: {pid}/{key}")
        name = part["project_file"]
        raw, baseline = current[name], previous[name]
        require(digest(raw) == part["project_sha256"], f"Project receipt: {name}")
        require(digest(baseline) == part["source_project_sha256"], f"Wrong baseline project: {name}")
        if raw != baseline:
            changed.add(pid)
        require(part["changed_geometry"] == (pid in CHANGED), f"Incorrect change flag: {pid}")
        require(part["archive_bytes_unchanged"] == (pid not in CHANGED), f"Incorrect byte-identity flag: {pid}")
        if pid not in CHANGED:
            require(raw == baseline, f"Unrelated print project changed: {pid}")
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as new_zip, zipfile.ZipFile(io.BytesIO(baseline)) as old_zip:
            require(new_zip.testzip() is None, f"Changed 3MF CRC: {pid}")
            require(set(new_zip.namelist()) == set(old_zip.namelist()), f"3MF members changed: {pid}")
            members = {name for name in new_zip.namelist() if new_zip.read(name) != old_zip.read(name)}
            require(members == {"3D/3dmodel.model"}, f"3MF settings/metadata changed: {pid}")
            # Mesh replacement must preserve component transforms, build pose,
            # object IDs and every other byte outside the single mesh element.
            stripped = []
            for archive in (new_zip, old_zip):
                xml, count = re.subn(rb"<mesh>.*?</mesh>", b"<mesh/>",
                                     archive.read("3D/3dmodel.model"), flags=re.S)
                require(count == 1, f"Expected one lid mesh in project: {pid}")
                stripped.append(xml)
            require(stripped[0] == stripped[1], f"Saved model metadata or pose changed: {pid}")
        require(part["brim_and_exclusion_check_passed"], f"H2D layout check failed: {pid}")
    require(changed == CHANGED, "Only the two lid projects may change")
    for key, total in (("stored_object_count", 22), ("required_physical_quantity", 23),
                       ("plate_runs_for_assembly", 16)):
        require(sum(part[key] for part in parts.values()) == total, f"Part sums disagree: {key}")
    require(report["common_lid_quantity"] == 2, "The common lid part must be printed twice")
    require(digest(current[report["common_lid_stl"]]) == APPROVED_STL,
            "Complete print set does not contain the user-approved STL")
    return report


def check_geometry(current, previous):
    model = json_member(current, "model_data.json")
    old = json_member(previous, "model_data.json")
    require(model["revision"] == REVISION and model["production_approved"] is False,
            "Wrong review revision or approval state")
    parts = {part["id"]: part for part in model["parts"]}
    old_parts = {part["id"]: part for part in old["parts"]}
    require(len(parts) == len(model["parts"]) and set(parts) == set(old_parts), "Assembly part inventory changed")
    require({pid for pid in parts if parts[pid] != old_parts[pid]} == CHANGED,
            "Unexpected current assembly change or unchanged lid")
    for key in ("baselineParts", "baselineJointScenes", "dimensions", "mountParameters", "ventParameters",
                "sideFixingParameters", "floorSeatParameters", "bracketParameters", "railLayout", "railSource"):
        require(model[key] == old[key], f"Unrelated assembly/reference data changed: {key}")
    for key, mesh in old["meshes"].items():
        require(model["meshes"].get(key) == mesh, f"Frozen/baseline mesh changed: {key}")
    new_meshes = set(model["meshes"]) - set(old["meshes"])
    require(new_meshes == {parts[pid]["mesh"] for pid in CHANGED}, "Unexpected added meshes")
    for pid in CHANGED:
        require(all(math.isclose(a, b, abs_tol=1e-6, rel_tol=0)
                    for a, b in zip(parts[pid]["box"], old_parts[pid]["box"])), f"Part bounds changed: {pid}")
    changed_exports = {name for name in previous if name.startswith(("step/", "stl-review/"))
                       and current.get(name) != previous[name]}
    require(changed_exports == {f"{folder}/{pid}.{extension}" for pid in CHANGED
                                for folder, extension in (("step", "step"), ("stl-review", "stl"))},
            "Unexpected STEP/STL assembly export change")
    require(current["inherited-r8-geometry-checks.json"] == previous["geometry-checks.json"],
            "Inherited R8 checks were rewritten")
    checks = json_member(current, "geometry-checks.json")
    require(checks and all(c["passed"] for c in checks) and model["checks"] == checks,
            "Current geometry checks failed or disagree with the model")
    proof = json_member(current, "lid-ledge-validation.json")
    require(proof["revision"] == REVISION and proof["stl"]["sha256"] == APPROVED_STL,
            "CAD proof does not describe the approved revision")
    require({p["part"] for p in proof["parts"]} == CHANGED and len(proof["parts"]) == 2,
            "CAD proof missing one lid panel")
    for part in proof["parts"]:
        require(part["cad_valid"] and part["solid_count"] == 1, "Invalid revised CAD solid")
        require(part["removed_volume_mm3"] < 1e-6 and part["added_outside_target_regions_mm3"] < 1e-6,
                "Lid change is not confined to the two additive bridges")
        require(math.isclose(part["added_volume_mm3"], 672.377322, abs_tol=1e-6, rel_tol=0),
                "Accepted bridge volume changed")
        require((part["ledge_sections_before"], part["ledge_sections_after"]) == (5, 3),
                "Center ledges are not connected or outer bracket windows changed")
        require(abs(part["roof_overlap_after_mm3"] - part["roof_overlap_before_mm3"]) < 1e-6,
                "Roof interference changed")
        require(digest(current[f"step/{part['part']}.step"]) == part["step_sha256"], "STEP proof digest mismatch")
    require(all(proof[key] is False for key in ("sliced", "studio_application_loaded", "physically_tested", "production_approved")),
            "Unexpected native/physical validation claim")
    return model, checks


def check_preview(html, model, model_hash):
    require(f'id="{PREFIX}"' in html, "Wrong current preview root")
    embedded = re.search(r'<script[^>]*data-id="model"[^>]*>([^<]+)</script>', html)
    require(embedded, "Missing embedded preview model")
    view = json.loads(gzip.decompress(base64.b64decode(embedded.group(1))))
    require(view["revision"] == REVISION and view["previewMetadata"]["sourceModelSha256"] == model_hash,
            "Preview is based on a stale model")
    if view.get("meshEncoding", {}).get("indices") == "delta-v1":
        for mesh in view["meshes"].values():
            total, indices = 0, []
            for delta in mesh["i"]:
                total += delta
                indices.append(total)
            mesh["i"] = indices
    # Preview meshes are rounded to 0.001 mm and may share translated aliases.
    # Compare world-space vertices and topology so the hash alone cannot hide a
    # stale lid mesh or an incorrect static offset in the actual visible scene.
    for collection in ("parts", "baselineParts"):
        expected = {p["id"]: p for p in model[collection]}
        visible = {p["id"]: p for p in view[collection]}
        require(set(visible) == set(expected), f"Preview inventory mismatch: {collection}")
        for pid, part in visible.items():
            source = expected[pid]
            mesh, original = view["meshes"][part["mesh"]], model["meshes"][source["mesh"]]
            require(mesh["i"] == original["i"] and len(mesh["p"]) == len(original["p"]),
                    f"Preview topology changed: {collection}/{pid}")
            offset, old_offset = part.get("staticOffset", [0, 0, 0]), source.get("staticOffset", [0, 0, 0])
            error = max(abs(a + offset[i % 3] - b - old_offset[i % 3])
                        for i, (a, b) in enumerate(zip(mesh["p"], original["p"])))
            require(error <= .0005001, f"Preview geometry or placement differs: {collection}/{pid}/{error}")


def check_source(archive):
    for kind in ("review", "print"):
        name = f"public/downloads/candidate/tenbox-v2-r8-{kind}.zip"
        require(archive[name] == (ROOT / name).read_bytes(), f"Source ZIP changed its R8 input: {name}")
    for path in SOURCE.rglob("*"):
        if not path.is_file() or any(p in path.parts for p in ("__pycache__", ".venv", "node_modules")):
            continue
        name = path.relative_to(ROOT).as_posix()
        require(archive.get(name) == path.read_bytes(), f"Current source ZIP is missing/stale: {name}")
    for name in ("engineering/tenbox-v2/r5/pyproject.toml", "engineering/tenbox-v2/r5/uv.lock",
                 "project/tenbox-v2/r8-review.json"):
        require(archive[name] == (ROOT / name).read_bytes(), f"Source dependency changed: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, help="Check complete output before publication")
    args = parser.parse_args()
    published = ROOT / "public/downloads/candidate"
    output = args.build.resolve() if args.build else None
    package_dir = output / "packages" if output else published
    old_print = checked_zip(published / "tenbox-v2-r8-print.zip")
    old_review = checked_zip(published / "tenbox-v2-r8-review.zip")
    prints = checked_zip(package_dir / (PREFIX + "-print.zip"))
    review = checked_zip(package_dir / (PREFIX + "-review.zip"))
    source = checked_zip(package_dir / (PREFIX + "-source.zip"))
    report = check_prints(prints, old_print)
    model, checks = check_geometry(review, old_review)
    model_hash = digest(review["model_data.json"])
    html_path = output / (PREFIX + ".html") if output else ROOT / "public/previews" / (PREFIX + ".html")
    html = html_path.read_text()
    require(review[PREFIX + ".html"] == html_path.read_bytes(), "Review ZIP preview differs from the primary preview")
    check_preview(html, model, model_hash)
    check_source(source)
    direct = output if output else published
    require(digest((direct / (PART_STEM + ".stl")).read_bytes()) == APPROVED_STL, "Direct STL changed from approved bytes")
    require((direct / (PART_STEM + ".3mf")).read_bytes() == prints["projects/lid-front.3mf"],
            "Direct common 3MF differs from the current lid project")
    if not output:
        registry = json.loads((ROOT / "project/tenbox-v2/r8-lid-ledge-01.json").read_text())
        require(registry["revision"] == REVISION and registry["status"] == "current" and
                registry["user_confirmation"] == "accepted" and registry["production_approved"] is False,
                "Wrong current artifact registry state")
        check_receipts(registry["files"] + registry["preserved_previous_review"])
        require(registry["model_sha256"] == model_hash, "Registry model digest mismatch")
        require(registry["verification"]["h2d"] == report and
                registry["verification"]["cad_check_count"] == len(checks) and
                registry["verification"]["cad_all_passed"], "Registry verification differs from published packages")
        selection = json.loads((ROOT / "project/tenbox-v2/current.json").read_text())
        require(selection["current_revision"] == REVISION and selection["artifact_registry"] ==
                "project/tenbox-v2/r8-lid-ledge-01.json", "Primary selection still points to an older revision")
    print(f"{REVISION}: approved STL; 2 updated + 13 byte-identical H2D projects; "
          f"22 stored / 23 physical parts / 16 plate runs; {len(checks)} geometry checks; "
          "all inventories, source bytes, preserved R8 data and preview meshes verified.")


if __name__ == "__main__":
    main()
