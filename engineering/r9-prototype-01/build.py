"""R9-PROTOTYPE-01 7U40 generator. Geometry hooks are populated in later issues."""
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
import re

from r9.common import export_dxf, export_step, export_stl, sha256_file
from r9.types import BuildContext, Part

ROOT = Path(__file__).resolve().parent
MODULES = ("body", "slots", "guards", "lid", "coupons", "preview_data", "checks")
OUT_DIRS = ("aluminum", "pa12", "hardware-envelopes", "coupons", "assembly", "preview")
VALID_STATUSES = {"user_confirmed", "adopted", "provisional", "candidate", "unvalidated"}


def load_params(params_dir: Path | None = None) -> dict[str, dict]:
    params_dir = params_dir or ROOT / "params"
    result = {}
    for namespace in ("body", "slots", "guards", "lid", "coupons"):
        data = json.loads((params_dir / f"{namespace}.json").read_text())
        for key, item in data.items():
            if set(item) != {"value", "unit", "status", "source", "note"} or item["status"] not in VALID_STATUSES:
                raise ValueError(f"invalid parameter {namespace}.{key}")
        result[namespace] = data
    shared = ("top_edge_guard_opening_x", "top_edge_guard_opening_y",
              "top_edge_guard_exterior_x", "top_edge_guard_exterior_y",
              "top_edge_seated_guard_z", "top_edge_adhesive_allowance")
    for key in shared:
        if result["guards"][key]["value"] != result["lid"][key]["value"]:
            raise ValueError(f"top-edge interface mismatch: {key}")
    return result


def export_part(ctx: BuildContext, part: Part) -> list[dict]:
    if not re.fullmatch(r"7U40-R9-[A-Z0-9-]+", part.id) or part.qty < 1:
        raise ValueError(f"invalid part ID/quantity: {part.id}")
    if part.category not in OUT_DIRS:
        raise ValueError(f"unknown category: {part.category}")
    outputs = []
    stem = f"{part.id.lower()}-qty{part.qty}-mm"
    for kind in part.export_kinds:
        path = ctx.out / part.category / f"{stem}.{kind}"
        if kind == "step":
            export_step(part.solid, path)
            if part.category == "coupons":
                # OCC writes insignificant trailing spaces in DATA records.
                # Keep the committed coupon STEP exports diff-clean, matching
                # the guard and lid candidate exporters.
                path.write_bytes(b"\n".join(
                    line.rstrip(b" \t") for line in path.read_bytes().split(b"\n")
                ))
        elif kind == "stl":
            export_stl(part.solid, path)
        elif kind == "dxf":
            if part.dxf_outline is None:
                raise ValueError(f"DXF outline missing: {part.id}")
            export_dxf(path, part.dxf_outline, part.dxf_holes, part.dxf_slots)
        else:
            raise ValueError(f"unsupported export kind: {kind}")
        outputs.append({"path": str(path.relative_to(ctx.root)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return outputs


def parse_modules(value: str | None) -> tuple[str, ...]:
    if value is None:
        return MODULES
    names = tuple(value.split(","))
    if any(name not in MODULES for name in names):
        raise argparse.ArgumentTypeError(
            f"--only expects comma-separated modules from: {', '.join(MODULES)}"
        )
    if len(set(names)) != len(names):
        raise argparse.ArgumentTypeError("--only contains duplicate modules")
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=parse_modules, metavar="MODULE[,MODULE...]")
    parser.add_argument("--validate", action="store_true",
                        help="run the full build, then aggregate CAD and parameter-change checks")
    args = parser.parse_args()
    if args.validate and args.only is not None:
        parser.error("--validate requires the complete build; omit --only")
    out = ROOT / "out"
    for directory in OUT_DIRS:
        (out / directory).mkdir(parents=True, exist_ok=True)
    ctx = BuildContext(ROOT, out, load_params())
    selected = args.only if args.only is not None else MODULES
    result = {"revision": ctx.revision, "model": ctx.model, "modules": list(selected),
              "geometryStatus": "unapproved prototype candidate", "parts": [], "outputs": []}
    seen_ids = set()
    for name in selected:
        parts = importlib.import_module(f"r9.{name}").build(ctx)
        if not isinstance(parts, list) or any(not isinstance(part, Part) for part in parts):
            raise TypeError(f"{name}.build must return list[Part]")
        for part in parts:
            if part.id in seen_ids:
                raise ValueError(f"duplicate part ID: {part.id}")
            seen_ids.add(part.id)
            result["parts"].append({"id": part.id, "category": part.category,
                                    "material": part.material, "qty": part.qty})
            result["outputs"].extend(export_part(ctx, part))
    # Guard/lid exporters write their own nested candidate files. Include the
    # manifest-listed delivered bytes in the shared ledger without exporting
    # them again to the category root.
    for name, manifests in (("guards", ("pa12/guards/t1p2/manifest.json", "pa12/guards/t1p0/manifest.json")),
                            ("lid", ("pa12/lid/manifest.json",))):
        if name not in selected:
            continue
        for manifest_name in manifests:
            manifest_path = out / manifest_name
            manifest = json.loads(manifest_path.read_text())
            files = (manifest.get("deliverables", []) if name == "lid" else
                     [file for part in manifest["parts"] for file in part["files"]])
            for file in files:
                path = ROOT / file["path"]
                if sha256_file(path) != file["sha256"] or path.stat().st_size != file["bytes"]:
                    raise ValueError(f"module manifest digest mismatch: {path}")
                result["outputs"].append({"path": file["path"], "sha256": file["sha256"], "bytes": file["bytes"]})
            result["outputs"].append({"path": str(manifest_path.relative_to(ROOT)),
                                      "sha256": sha256_file(manifest_path), "bytes": manifest_path.stat().st_size})
    if "checks" in selected:
        for path in sorted((out / "assembly").iterdir()):
            if path.is_file():
                result["outputs"].append({"path": str(path.relative_to(ROOT)),
                                          "sha256": sha256_file(path), "bytes": path.stat().st_size})
    if "coupons" in selected:
        coupon_manifest = importlib.import_module("r9.coupons").finalize(ctx)
        manifest_path = ROOT / coupon_manifest["path"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # C2 files are emitted into nested per-coupon folders by coupons.py,
        # outside the generic Part exporter. Add every manifest-listed byte
        # to the shared ledger, checking the manifest digest before recording.
        recorded = {entry["path"]: entry for entry in result["outputs"]}
        for coupon in manifest["coupons"]:
            for file in coupon.get("fileHashes", []):
                path = ROOT / file["path"]
                actual = {"path": file["path"], "sha256": sha256_file(path),
                          "bytes": path.stat().st_size}
                if actual["sha256"] != file["sha256"] or actual["bytes"] != file["bytes"]:
                    raise ValueError(f"coupon manifest digest mismatch: {path}")
                previous = recorded.get(actual["path"])
                if previous is not None and previous != actual:
                    raise ValueError(f"conflicting coupon ledger entry: {path}")
                if previous is None:
                    result["outputs"].append(actual)
                    recorded[actual["path"]] = actual
        result["outputs"].append(coupon_manifest)

    validation_report = None
    if args.validate:
        # Refresh the checked-in single-file preview after preview_data has
        # updated its file table, so nested C2 outputs are represented there.
        preview_html = importlib.import_module("preview.build").build()
        print(f"Preview HTML updated: {preview_html.relative_to(ROOT.parents[1])}")
        validation_report = importlib.import_module("r9.checks").validate(ctx, result["outputs"])
        validation_path = out / "validation.json"
        validation_output = {"path": str(validation_path.relative_to(ROOT)),
                             "sha256": sha256_file(validation_path),
                             "bytes": validation_path.stat().st_size}
        result["outputs"].append(validation_output)
        markdown_path = ROOT / "VALIDATION.md"
        result["outputs"].append({"path": str(markdown_path.relative_to(ROOT)),
                                  "sha256": sha256_file(markdown_path),
                                  "bytes": markdown_path.stat().st_size})
        summary = validation_report["summary"]
        print(f"Validation: {summary['passed']} pass; {summary['flagged']} flag; "
              f"{summary['failed']} fail")

    result["outputs"].sort(key=lambda entry: entry["path"])
    (out / "build-log.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"R9 7u40: {len(result['parts'])} parts; {len(result['outputs'])} files; modules: {', '.join(selected)}")
    if validation_report is not None and validation_report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
