#!/usr/bin/env python3
"""Publish the complete current R8 case with the accepted connected lid part.

The previous R8 packages are immutable inputs. Only the two lid edge solids,
their print projects and the current preview change. Use --publish-root to
write the new versioned repository assets; this command does not deploy.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import zipfile

import cadquery as cq
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
REVISION = "R8-LID-LEDGE-01"
PREFIX = "tenbox-v2-r8-lid-ledge-01"
PART_STEM = "10box-v2-lid-frontback-connected-r01"
ISSUE = "https://github.com/Takazudo/zudo-case/issues/149"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


part_builder = load("lid_ledge_part", ROOT / "build.py")
pack = load("lid_ledge_pack", ROOT.parent / "r5/build.py")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def receipt(path, base):
    return {"path": path.relative_to(base).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run(path, *args):
    subprocess.run([sys.executable, str(path), *map(str, args)], check=True)


def extract(archive, target, excluded=()):
    pack.verify_zip(archive)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name in {"MANIFEST.sha256", "README.md", *excluded}:
                continue
            path = target / name
            require(path.resolve().is_relative_to(target.resolve()), "Unsafe ZIP member")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--publish-root", type=Path)
    parser.add_argument("--no-packages", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    require(not out.exists(), "Choose an absent output directory")
    require(not (args.publish_root and args.no_packages), "Publication requires complete packages")
    previous_record_path = REPO / "project/tenbox-v2/r8-review.json"
    previous_record = json.loads(previous_record_path.read_text())
    inputs = {}
    for kind in ["review", "print"]:
        path = REPO / f"public/downloads/candidate/tenbox-v2-r8-{kind}.zip"
        expected = next(x for x in previous_record["files"] if x["path"] == path.relative_to(REPO).as_posix())
        require(sha(path) == expected["sha256"] and path.stat().st_size == expected["bytes"], "R8 baseline archive changed")
        inputs[kind] = path
    out.mkdir(parents=True)
    part, cad, prints = out / "lid", out / "cad", out / "h2d"
    run(ROOT / "build.py", "--out", part)
    part_report = json.loads((part / "validation.json").read_text())
    require(sha(part / (PART_STEM + ".stl")) == part_builder.CFG["approved_stl_sha256"], "Approved STL bytes changed")
    extract(inputs["review"], cad, {"tenbox-v2-r8.html"})
    extract(inputs["print"], prints)
    previous_model = json.loads((cad / "model_data.json").read_text())
    model = copy.deepcopy(previous_model)
    model.update(revision=REVISION, schema="10box-v2-review/8-lid-ledge-01", previousRevision="R8", production_approved=False)
    changes = {"based_on": "R8", "changed_printed_parts": ["lid-front", "lid-back"],
               "common_part_quantity": 2, "gap_x_intervals_front_mm": part_builder.CFG["gap_x_intervals"],
               "bridge_z_mm": [103, 108], "bridge_inward_projection_mm": 3,
               "outer_bracket_windows_retained": True, "roof_geometry_unchanged": True,
               "approved_stl_sha256": part_builder.CFG["approved_stl_sha256"],
               "assembly_placements_changed": [], "all_other_parts_unchanged": True}
    model["lidLedgeChanges"] = changes
    model["lidClearance"].update(lid_geometry_changed=True, roof_geometry_changed=False)
    model["previewMetadata"]["lidLedgeRevision"] = REVISION
    model["previousR8Checks"] = model.pop("checks")
    current_checks = []
    new_parts = {}
    for entry in part_report["parts"]:
        pid = entry["part"]
        shape = cq.importers.importStep(str(part / "step" / (pid + ".step"))).val()
        points, triangles, checked = part_builder.shape_mesh(shape)
        key = "r8-lid-ledge-01-" + pid
        model["meshes"][key] = {"p": [round(float(v), 6) for row in points for v in row],
                                "i": [int(i) for row in triangles for i in row]}
        record = next(p for p in model["parts"] if p["id"] == pid)
        record.update(mesh=key, box=part_builder.bounds(shape).tolist(), volume=shape.Volume(),
                      material="10BOX-v2 R8-LID-LEDGE-01 / printed lid edge",
                      note="Two obsolete central support-ledge gaps connected; outer bracket windows and all mounting features retained.",
                      sourceId=pid, source_file="step/" + pid + ".step")
        new_parts[pid] = record
        shutil.copy2(part / "step" / (pid + ".step"), cad / "step" / (pid + ".step"))
        cq.exporters.export(shape, str(cad / "stl-review" / (pid + ".stl")), tolerance=.06, angularTolerance=.20)
        current_checks.append({"check": "accepted connected lid " + pid, "passed": True,
                               "single_valid_solid": entry["cad_valid"] and entry["solid_count"] == 1,
                               "added_volume_mm3": entry["added_volume_mm3"],
                               "removed_volume_mm3": entry["removed_volume_mm3"],
                               "added_outside_target_regions_mm3": entry["added_outside_target_regions_mm3"],
                               "roof_overlap_increase_mm3": entry["roof_overlap_increase_mm3"], "mesh": checked})
    # Detail scenes, if they include these panels, use the same revised source
    # mesh. baselineParts and baselineJointScenes remain the exact R7 reference.
    for scene in model.get("jointScenes", {}).values():
        for record in scene:
            pid = record.get("sourceId", record["id"])
            if pid in new_parts:
                for key in ["mesh", "box", "volume", "material", "note", "source_file"]:
                    record[key] = copy.deepcopy(new_parts[pid][key])
    unchanged = []
    previous_parts = {p["id"]: p for p in previous_model["parts"]}
    for p in model["parts"]:
        if p["id"] not in new_parts:
            before = previous_parts[p["id"]]
            require(p == before and model["meshes"][p["mesh"]] == previous_model["meshes"][before["mesh"]],
                    "Unrelated geometry or placement changed: " + p["id"])
            unchanged.append(p["id"])
    require(model["baselineParts"] == previous_model["baselineParts"], "Historical R7 comparison changed")
    current_checks += [{"check": "all other R8 parts and placements unchanged", "passed": True, "part_count": len(unchanged)},
                       {"check": "approved common STL byte identity", "passed": True, "sha256": sha(part/(PART_STEM+".stl"))}]
    # A conservative separation proof for every existing lid hardware envelope.
    minimum_gap = float("inf")
    hardware = [p for p in model["parts"] if p.get("group") == "lid" and p["id"] not in
                {"lid-front", "lid-back", "lid-left", "lid-right", "lid-top-single"}]
    for pid in ["lid-front", "lid-back"]:
        sign = 1 if pid == "lid-front" else -1
        for a, b in part_builder.CFG["gap_x_intervals"]:
            lo = np.array([a-.05, -145.05, 103.]); hi = np.array([b+.05, -142., 108.])
            if sign == -1:
                lo, hi = np.r_[-hi[:2], lo[2]], np.r_[-lo[:2], hi[2]]
            for p in hardware:
                bb = np.array(p["box"]); offset = np.array(p.get("staticOffset", [0,0,0]))
                separation = np.maximum(0, np.maximum(lo-(bb[3:]+offset), (bb[:3]+offset)-hi))
                distance = float(np.linalg.norm(separation))
                require(distance > 0, "Bridge envelope intersects lid hardware " + p["id"])
                minimum_gap = min(minimum_gap, distance)
    current_checks.append({"check": "bridge envelopes clear existing lid hardware", "passed": True,
                           "hardware_count": len(hardware), "minimum_aabb_distance_mm": minimum_gap})
    model["checks"] = current_checks
    model["lidLedgeChanges"]["unchanged_current_part_count"] = len(unchanged)
    (cad / "geometry-checks.json").rename(cad / "inherited-r8-geometry-checks.json")
    write_json(cad / "model_data.json", model)
    write_json(cad / "geometry-checks.json", current_checks)
    params = json.loads((cad / "parameters.json").read_text())
    params.update(revision=REVISION, lidLedgeChanges=changes, lidClearance=model["lidClearance"])
    write_json(cad / "parameters.json", params)
    shutil.copy2(part / "validation.json", cad / "lid-ledge-validation.json")
    previous_print = json.loads((prints / "h2d-project-report.json").read_text())
    (prints / "baseline-r8").mkdir()
    for name in ["h2d-project-report.json", "printed-geometry-comparison.json", "print-poses.json"]:
        if (prints/name).exists():
            (prints/name).rename(prints/"baseline-r8"/name)
    results = []
    for old in previous_print["parts"]:
        pid = old["part_id"]
        target = prints / old["project_file"]
        original = target.read_bytes()
        result = {key: copy.deepcopy(old[key]) for key in ["part_id", "project_file", "assembly_ids",
                  "stored_object_count", "required_physical_quantity", "plate_runs_for_assembly"]}
        result.update(source_revision="R8", source_project_sha256=old["project_sha256"],
                      changed_geometry=pid in new_parts, archive_bytes_unchanged=pid not in new_parts,
                      global_settings_bytes_unchanged=True, object_plate_settings_bytes_unchanged=True)
        if pid in new_parts:
            source = part / "projects" / (pid + "-connected-r01.3mf")
            shutil.copy2(source, target)
            proof = next(e["project"] for e in part_report["parts"] if e["part"] == pid)
            result.update(changed_archive_members=proof["changed_archive_members"],
                          structural_validation=proof["structural_validation"], pose=proof["rotation"],
                          pose_recovery_error_mm=proof["pose_recovery_error_mm"],
                          brim_and_exclusion_check_passed=proof["brim_and_exclusion_check_passed"])
            write_json(prints / "validation" / (pid + ".json"), proof)
        else:
            require(target.read_bytes() == original and sha(target) == old["project_sha256"], "Unrelated project changed")
            result["changed_archive_members"] = []
        result["project_sha256"] = sha(target)
        results.append(result)
    require((len(results), sum(p["stored_object_count"] for p in results), sum(p["required_physical_quantity"] for p in results),
             sum(p["plate_runs_for_assembly"] for p in results)) == (15,22,23,16), "Print inventory changed")
    for extension in ["stl", "3mf"]:
        shutil.copy2(part/(PART_STEM+"."+extension), out/(PART_STEM+"."+extension))
    shutil.copy2(part/(PART_STEM+".stl"), prints/"meshes"/(PART_STEM+".stl"))
    report = {"revision": REVISION, "based_on": "R8", "project_count": 15, "stored_object_count": 22,
              "required_physical_part_count": 23, "plate_runs_for_assembly": 16,
              "changed_project_count": 2, "byte_identical_project_count": 13,
              "global_settings_bytes_unchanged": True, "object_plate_settings_bytes_unchanged": True,
              "sliced": False, "studio_application_loaded": False, "production_approved": False,
              "common_lid_stl": "meshes/"+PART_STEM+".stl", "common_lid_quantity": 2, "parts": results}
    write_json(prints/"h2d-project-report.json", report)
    preview = out/(PREFIX+".html")
    run(ROOT/"preview/build_preview.py", "--model", cad/"model_data.json", "--out", preview)
    if not args.no_packages:
        packages = out/"packages"
        readme = (ROOT/"README.md").read_bytes()
        payload = pack.files_under(prints); payload["README.md"] = readme
        pack.atomic_zip(packages/(PREFIX+"-print.zip"), payload)
        payload = pack.files_under(cad); payload[preview.name] = preview.read_bytes(); payload["README.md"] = readme
        pack.atomic_zip(packages/(PREFIX+"-review.zip"), payload)
        # This revision consumes the exact R8 assembly and print archives, not
        # every historical R5-R8 generator/output. Ship the complete inputs
        # actually used here; repeating the old source tree and nested review
        # archives would duplicate large meshes and unrelated historical files.
        payload = pack.files_under(ROOT, "engineering/tenbox-v2/r8-lid-ledge-01/")
        dependency_paths = [
            "engineering/tenbox-v2/r5/build.py",
            "engineering/tenbox-v2/r5/pyproject.toml",
            "engineering/tenbox-v2/r5/uv.lock",
            "engineering/tenbox-v2/r5/.python-version",
            "engineering/tenbox-v2/r5/source/h2d-r5/tools/bambu_3mf.py",
            "engineering/tenbox-v2/r5/source/research/zudo-case/viewer-template.html",
            *["engineering/tenbox-v2/r5/source/10box-v2-r5/step/"+name+".step"
              for name in ["lid-front", "lid-back", "lid-top-single"]],
            *["engineering/tenbox-v2/r5/source/h2d-r5/projects/"+name+".3mf"
              for name in ["lid-front", "lid-back"]],
        ]
        for name in dependency_paths:
            payload[name] = (REPO/name).read_bytes()
        for path in [*inputs.values(), previous_record_path]:
            payload[path.relative_to(REPO).as_posix()] = path.read_bytes()
        payload["README.md"] = readme
        pack.atomic_zip(packages/(PREFIX+"-source.zip"), payload)
    if args.publish_root:
        repo = args.publish_root.resolve()
        published = []
        for path in sorted((out/"packages").glob("*.zip")):
            dest = repo/"public/downloads/candidate"/path.name
            pack.atomic_copy(path, dest, "package"); published.append(dest)
        for ext in ["stl", "3mf"]:
            path = out/(PART_STEM+"."+ext); dest = repo/"public/downloads/candidate"/path.name
            pack.atomic_copy(path, dest, "3mf" if ext == "3mf" else "stl"); published.append(dest)
        dest = repo/"public/previews"/preview.name
        pack.atomic_copy(preview, dest, "html"); published.append(dest)
        sources = [p for p in ROOT.rglob("*") if p.is_file() and not any(x in p.parts for x in ["__pycache__", ".venv", "node_modules"])]
        record = {"family": "tenbox-v2", "revision": REVISION, "based_on": "R8", "status": "current",
                  "date": "2026-11-24", "production_approved": False, "user_confirmation": "accepted", "issue": ISSUE,
                  "preview": "/previews/"+preview.name, "model_sha256": sha(cad/"model_data.json"),
                  "source_commit": part_builder.CFG["source_commit"], "changes": changes,
                  "files": [receipt(p, repo) for p in sorted(published+sources)],
                  "preserved_previous_review": previous_record["files"] + [receipt(previous_record_path, REPO)],
                  "verification": {"cad_check_count": len(current_checks), "cad_all_passed": all(c["passed"] for c in current_checks),
                                   "h2d": report, "approved_stl_sha256": sha(out/(PART_STEM+".stl")),
                                   "native_studio_load": "not_performed", "native_studio_slice": "not_performed",
                                   "physical_print_fit_load": "not_performed"}}
        write_json(repo/"project/tenbox-v2/r8-lid-ledge-01.json", record)
    print(json.dumps({"revision": REVISION, "out": str(out), "changed_projects": 2, "unchanged_projects": 13,
                      "unchanged_other_parts": len(unchanged), "approved_stl_sha256": sha(out/(PART_STEM+".stl"))}))


if __name__ == "__main__":
    main()
