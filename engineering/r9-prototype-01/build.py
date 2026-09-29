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


def load_params() -> dict[str, dict]:
    result = {}
    for namespace in ("body", "slots", "guards", "lid", "coupons"):
        data = json.loads((ROOT / "params" / f"{namespace}.json").read_text())
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
    args = parser.parse_args()
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
    (out / "build-log.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"R9 7u40: {len(result['parts'])} parts; {len(result['outputs'])} files; modules: {', '.join(selected)}")


if __name__ == "__main__":
    main()
