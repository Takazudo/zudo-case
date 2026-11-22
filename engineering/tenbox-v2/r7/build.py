"""Build the R7 feedback revision without overwriting R5 or R6.

The R5 locked Python environment is reused. Publication here means copying
candidate assets into this checkout; it does not deploy or approve production.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
R5 = ROOT.parent / "r5"
REPOSITORY = ROOT.parents[2]
spec = importlib.util.spec_from_file_location("tenbox_r5_package", R5 / "build.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


def run(script, *args):
    subprocess.run([sys.executable, str(script), *map(str, args)], check=True)


def receipt(path, base):
    return {"path": path.relative_to(base).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def source_payload(cad):
    # R7 is an incremental revision. Include its actual frozen dependencies,
    # rather than a source ZIP which depends on an unseen local checkout.
    result = pack.files_under(R5 / "source", "engineering/tenbox-v2/r5/source/")
    for name in ["build.py", "pyproject.toml", "uv.lock", ".python-version", "README.md"]:
        result["engineering/tenbox-v2/r5/" + name] = (R5 / name).read_bytes()
    for directory in [ROOT / "reference", ROOT / "preview"]:
        result.update(pack.files_under(directory, "engineering/tenbox-v2/r7/" + directory.name + "/"))
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and path.suffix in {".py", ".json", ".md"}:
            result["engineering/tenbox-v2/r7/" + path.name] = path.read_bytes()
    for source in json.loads((cad / "source-receipts.json").read_text()):
        result[source["file"]] = (REPOSITORY / source["file"]).read_bytes()
    result["README.md"] = (ROOT / "README.md").read_bytes()
    return result


def write_fastener_schedule(cad):
    """Keep the modeled hardware choices inspectable outside the large scene JSON."""
    model = json.loads((cad / "model_data.json").read_text())
    counts = Counter()
    for joint in model["bracketParameters"]["fasteners"]:
        side = joint["wall"] in {"body-left", "body-right"}
        location = ("lid " + joint["axis"] if joint["group"] == "lid" else
                    "body " + ("side " if side else "end ") + joint["axis"])
        counts[(location, joint["nominal_screw_length_mm"], joint["nut_height_mm"], joint["nut_side"])] += 1
    rows = [{"location": location, "quantity": count, "thread": "M5",
             "nominal_screw_length_mm": length, "nominal_nut_height_mm": height,
             "nut_side": nut_side}
            for (location, length, height, nut_side), count in sorted(counts.items())]
    rail_count = sum(p["id"].startswith("rail-bolt-") for p in model["parts"])
    rows.append({"location": "rail frame to case side", "quantity": rail_count, "thread": "M5",
                 "nominal_screw_length_mm": 25.0, "nominal_nut_height_mm": 5.0, "nut_side": "outside"})
    record = {"status": "nominal CAD reference; purchased hardware not measured",
              "bracket_connections": len(model["bracketParameters"]["fasteners"]),
              "rail_frame_connections": rail_count, "rows": rows,
              "note": "L-bracket nuts bear directly on metal. L-bracket exterior washers are OD15/ID5/t1. The eight rail exterior washers are OD10/ID5/t1 to clear the lift-off lid; the rail outside washer+nut stack remains6mm. See the design notes for protective washers."}
    (cad / "fastener-schedule.json").write_text(json.dumps(record, indent=2) + "\n")
    with (cad / "fastener-schedule.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--publish-root", type=Path)
    parser.add_argument("--inline-out", type=Path)
    parser.add_argument("--no-packages", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("Choose an absent output directory; existing revisions are not overwritten.")
    out.mkdir(parents=True)
    cad, prints = out / "cad", out / "h2d"
    run(ROOT / "build_geometry.py", "--out", cad)
    write_fastener_schedule(cad)
    run(ROOT / "build_print_projects.py", "--cad", cad, "--out", prints)
    preview_args = ["--model", cad / "model_data.json", "--out", out / "tenbox-v2-r7.html"]
    if args.inline_out:
        preview_args += ["--inline-out", args.inline_out.resolve()]
    run(ROOT / "preview/build_preview.py", *preview_args)
    manifest = {
        "family": "tenbox-v2", "revision": "R7", "status": "review-candidate",
        "based_on": "R6", "geometry_base": "R5", "production_approved": False,
        "user_confirmation": "pending", "source_commit": "7ece63e324a66f1fd77cfe13f205b1e185f6af16",
        "native_studio_load": "not_performed", "native_studio_slice": "not_performed",
        "physical_print_fit_load": "not_performed",
        "files": [receipt(p, out) for p in sorted(out.rglob("*")) if p.is_file()],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if not args.no_packages:
        packages = out / "packages"
        print_payload = pack.files_under(prints)
        print_payload["README.md"] = (ROOT / "README.md").read_bytes()
        pack.atomic_zip(packages / "tenbox-v2-r7-print.zip", print_payload)
        review_payload = pack.files_under(cad)
        review_payload["tenbox-v2-r7.html"] = (out / "tenbox-v2-r7.html").read_bytes()
        review_payload["README.md"] = (ROOT / "README.md").read_bytes()
        pack.atomic_zip(packages / "tenbox-v2-r7-review.zip", review_payload)
        pack.atomic_zip(packages / "tenbox-v2-r7-source.zip", source_payload(cad))
    if args.publish_root:
        repo = args.publish_root.resolve()
        if args.no_packages:
            raise SystemExit("--publish-root requires packages.")
        for package in (out / "packages").glob("*.zip"):
            pack.atomic_copy(package, repo / "public/downloads/candidate" / package.name, "package")
        for name in ["body-left", "body-right", "body-bottom-common"]:
            pack.atomic_copy(prints / "projects" / (name + ".3mf"),
                             repo / "public/downloads/candidate/tenbox-v2-r7" / (name + ".3mf"), "3mf")
        pack.atomic_copy(out / "tenbox-v2-r7.html", repo / "public/previews/tenbox-v2-r7.html", "html")
        old = json.loads((repo / "project/tenbox-v2/manifest.json").read_text())
        previous_review_path = repo / "project/tenbox-v2/r6-review.json"
        previous_review = json.loads(previous_review_path.read_text())
        published = list((repo / "public/downloads/candidate").glob("tenbox-v2-r7-*.zip"))
        published += list((repo / "public/downloads/candidate/tenbox-v2-r7").glob("*.3mf"))
        published += [repo / "public/previews/tenbox-v2-r7.html"]
        sources = [p for p in ROOT.rglob("*") if p.is_file()
                   and not any(x in p.relative_to(ROOT).parts for x in ["__pycache__", "out", "review", "node_modules"])]
        checks = json.loads((cad / "geometry-checks.json").read_text())
        review_record = {
            "family": "tenbox-v2", "revision": "R7", "based_on": "R6", "geometry_base": "R5",
            "previous_review_commit": "7ece63e324a66f1fd77cfe13f205b1e185f6af16",
            "status": "review-candidate", "date": "2026-11-23",
            "production_approved": False, "user_confirmation": "pending",
            "issue": "https://github.com/Takazudo/zudo-case/issues/143",
            "preview": "/previews/tenbox-v2-r7.html",
            "model_sha256": hashlib.sha256((cad / "model_data.json").read_bytes()).hexdigest(),
            "files": [receipt(p, repo) for p in sorted(published + sources)],
            "preserved_inputs": old["inputs"] + old["source_files"] + old["tooling_files"] + old["public_files"],
            "preserved_previous_review": previous_review["files"] + [receipt(previous_review_path, repo)],
            "verification": {"cad_check_count": len(checks), "cad_all_passed": all(c["passed"] for c in checks),
                             "h2d": json.loads((prints / "h2d-project-report.json").read_text()),
                             "native_studio_load": "not_performed", "native_studio_slice": "not_performed",
                             "physical_print_fit_load": "not_performed"},
        }
        (repo / "project/tenbox-v2/r7-review.json").write_text(json.dumps(review_record, indent=2) + "\n")
    print(json.dumps({"out": str(out), "revision": "R7", "production_approved": False,
                      "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
