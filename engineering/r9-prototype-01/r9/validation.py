"""Aggregate validation for generated R9 7U40 prototype outputs."""
from __future__ import annotations

import base64
import gzip
import importlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path

import cadquery as cq
import ezdxf

from .common import (
    STL_BBOX_TOLERANCE_MM,
    STL_TESSELLATION_TOLERANCE_MM,
    STL_VOLUME_ABSOLUTE_TOLERANCE_MM3,
    STL_VOLUME_RELATIVE_TOLERANCE,
    export_dxf,
    export_step,
    export_stl,
    inspect_binary_stl,
    sha256_file,
)
from .types import BuildContext, Part

LIMIT_BYTES = 25 * 1024 * 1024
TOLERANCE_MM = 1e-4
NOT_VALIDATED = [
    "FEA, load capacity, or strength under service loads.",
    "Fit with real materials and manufacturing tolerances.",
    "Guard adhesion, retention, and pull-off strength.",
    "The effect of anodizing thickness on fit.",
    "Drop resistance and fatigue life.",
    "Band tension, strap load strength, and lid deflection during transport.",
    "Actual module knob heights and cable clearance (G05).",
    "Actual hardware, fastener, washer, and driver fit (G06).",
    "Physical assembly and transport trial (G11).",
]


def _relative(ctx: BuildContext, path: Path) -> str:
    return path.resolve().relative_to(ctx.root.resolve()).as_posix()


def _append(checks: list[dict], check_id: str, status: str,
            summary: str, **details) -> None:
    if status not in ("pass", "fail", "flag"):
        raise ValueError(f"unknown validation status: {status}")
    checks.append({"id": check_id, "status": status, "summary": summary,
                   "details": details})


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _import_step(path: Path) -> cq.Shape:
    imported = cq.importers.importStep(str(path))
    shape = imported.val()
    if shape is None:
        raise ValueError("STEP import returned no shape")
    return shape


def _bbox(shape: cq.Shape) -> dict:
    box = shape.BoundingBox()
    low = [float(box.xmin), float(box.ymin), float(box.zmin)]
    high = [float(box.xmax), float(box.ymax), float(box.zmax)]
    return {"minMm": low, "maxMm": high,
            "dimensionsMm": [high[index] - low[index] for index in range(3)]}


def _dxf_audit(path: Path) -> tuple[ezdxf.document.Drawing, dict]:
    document = ezdxf.readfile(path)
    auditor = document.audit()
    entities = list(document.modelspace())
    return document, {
        "units": document.units,
        "entityCount": len(entities),
        "errorCount": len(auditor.errors),
        "fixCount": len(auditor.fixes),
        "entityTypes": {kind: sum(entity.dxftype() == kind for entity in entities)
                        for kind in sorted({entity.dxftype() for entity in entities})},
    }


def _dxf_features(path: Path) -> list[dict]:
    document, audit = _dxf_audit(path)
    if audit["units"] != ezdxf.units.MM:
        raise ValueError(f"DXF units are not millimetres: {path}")
    if audit["errorCount"] or audit["fixCount"]:
        raise ValueError(f"DXF audit reported errors/fixes: {path}: {audit}")
    modelspace = document.modelspace()
    features = []
    for entity in modelspace.query("CIRCLE[layer=='HOLES']"):
        features.append({"profile": "round",
                         "center": [float(entity.dxf.center.x), float(entity.dxf.center.y)],
                         "diameter": 2 * float(entity.dxf.radius)})

    slot_lines = []
    for entity in modelspace.query("LINE[layer=='SLOTS']"):
        start = entity.dxf.start
        end = entity.dxf.end
        start_xy = (float(start.x), float(start.y))
        end_xy = (float(end.x), float(end.y))
        dx, dy = end_xy[0] - start_xy[0], end_xy[1] - start_xy[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError(f"zero-length DXF slot edge: {path}")
        slot_lines.append({
            "start": start_xy,
            "end": end_xy,
            "midpoint": ((start_xy[0] + end_xy[0]) / 2,
                         (start_xy[1] + end_xy[1]) / 2),
            "direction": (dx / length, dy / length),
            "length": length,
        })

    arcs_by_center: dict[tuple[float, float], list] = {}
    for entity in modelspace.query("ARC[layer=='SLOTS']"):
        center = entity.dxf.center
        key = (round(float(center.x), 5), round(float(center.y), 5))
        arcs_by_center.setdefault(key, []).append(entity)

    unpaired = set(range(len(slot_lines)))
    slot_count = 0
    while unpaired:
        first_index = min(unpaired)
        first = slot_lines[first_index]
        ux, uy = first["direction"]
        candidates = []
        for second_index in unpaired:
            if second_index == first_index:
                continue
            second = slot_lines[second_index]
            vx, vy = second["direction"]
            if abs(abs(ux*vx + uy*vy) - 1) > TOLERANCE_MM:
                continue
            if abs(first["length"] - second["length"]) > TOLERANCE_MM:
                continue
            dx = second["midpoint"][0] - first["midpoint"][0]
            dy = second["midpoint"][1] - first["midpoint"][1]
            along = dx*ux + dy*uy
            across = abs(-dx*uy + dy*ux)
            if abs(along) <= TOLERANCE_MM and across > TOLERANCE_MM:
                candidates.append((across, second_index))
        if not candidates:
            raise ValueError(f"DXF slot straight side has no matching parallel side: {path}")
        width, second_index = min(candidates)
        second = slot_lines[second_index]
        center = [(first["midpoint"][0] + second["midpoint"][0]) / 2,
                  (first["midpoint"][1] + second["midpoint"][1]) / 2]
        if width <= 0 or first["length"] <= 0:
            raise ValueError(f"DXF slot dimensions are invalid: {path}")
        first_start, first_end = first["start"], first["end"]
        second_start, second_end = second["start"], second["end"]
        direct = math.dist(first_start, second_start) + math.dist(first_end, second_end)
        crossed = math.dist(first_start, second_end) + math.dist(first_end, second_start)
        if direct <= crossed:
            arc_centers = (((first_start[0] + second_start[0]) / 2,
                            (first_start[1] + second_start[1]) / 2),
                           ((first_end[0] + second_end[0]) / 2,
                            (first_end[1] + second_end[1]) / 2))
        else:
            arc_centers = (((first_start[0] + second_end[0]) / 2,
                            (first_start[1] + second_end[1]) / 2),
                           ((first_end[0] + second_start[0]) / 2,
                            (first_end[1] + second_start[1]) / 2))
        for arc_center in arc_centers:
            arc_key = (round(arc_center[0], 5), round(arc_center[1], 5))
            arcs = arcs_by_center.get(arc_key, [])
            if len(arcs) != 1 or abs(float(arcs[0].dxf.radius) - width / 2) > TOLERANCE_MM:
                raise ValueError(f"DXF slot end arc missing or mismatched at {arc_key}: {path}")
        angle = math.degrees(math.atan2(uy, ux)) % 180
        features.append({"profile": "slot", "center": center,
                         "width": width, "length": first["length"] + width,
                         "angle": angle})
        unpaired.remove(first_index)
        unpaired.remove(second_index)
        slot_count += 1
    if sum(len(items) for items in arcs_by_center.values()) != 2 * slot_count:
        raise ValueError(f"DXF slot arc count does not match the straight profiles: {path}")
    return features


def _match_body_dxf_features(ctx: BuildContext, checks: list[dict]) -> dict:
    hole_table_path = ctx.out / "aluminum" / "hole-table.json"
    table = _load_json(hole_table_path)
    from . import body

    specs = body.plate_specs(ctx)
    total_rows = len(table["holes"])
    profile_counts = {profile: sum(row["profile"] == profile for row in table["holes"])
                      for profile in ("slot", "round")}
    expected_counts = {"slot": 36, "round": 10}
    body_physical_plates = sum(spec.quantity for spec in specs)
    counts_ok = total_rows == 46 and profile_counts == expected_counts and body_physical_plates == 5
    _append(checks, "body-hole-table-counts", "pass" if counts_ok else "fail",
            "Compare physical hole rows and plate instances against the R9 body contract.",
            holeRows=total_rows, profileCounts=profile_counts,
            expectedProfileCounts=expected_counts,
            physicalBodyPlateCount=body_physical_plates,
            expectedBodyPlateCount=5)

    mismatch_count = 0
    per_plate = []
    for spec in specs:
        dxf_path = ctx.out / "aluminum" / f"{spec.id.lower()}-qty{spec.quantity}-mm.dxf"
        features = _dxf_features(dxf_path)
        expected = [row for row in table["holes"]
                    if row["plate"] == spec.id and
                    row["plate_instance"] == spec.primary_instance_id]
        unmatched = list(features)
        mismatches = []
        for row in expected:
            profile = row["profile"]
            center = [float(value) for value in row["center_uv"]]
            candidates = [item for item in unmatched
                          if item["profile"] == profile and
                          math.dist(item["center"], center) <= TOLERANCE_MM]
            if len(candidates) != 1:
                mismatches.append({"holeId": row["id"], "problem": "missing or duplicate center",
                                   "centerUvMm": center})
                continue
            item = candidates[0]
            unmatched.remove(item)
            if profile == "slot":
                size_ok = (abs(item["width"] - float(row["width"])) <= TOLERANCE_MM and
                           abs(item["length"] - float(row["length"])) <= TOLERANCE_MM and
                           abs((item["angle"] - float(row["angle_local_deg"]) + 90) % 180 - 90)
                           <= TOLERANCE_MM)
            else:
                size_ok = abs(item["diameter"] - float(row["width"])) <= TOLERANCE_MM
            if not size_ok:
                mismatches.append({"holeId": row["id"], "problem": "profile size/angle differs",
                                   "expected": {key: row.get(key) for key in
                                                ("width", "length", "angle_local_deg")},
                                   "actual": item})
        if unmatched:
            mismatches.append({"problem": "unmatched DXF features", "features": unmatched})
        mismatch_count += len(mismatches)
        per_plate.append({"partId": spec.id, "quantity": spec.quantity,
                          "primaryInstance": spec.primary_instance_id,
                          "expectedFeatures": len(expected), "actualFeatures": len(features),
                          "mismatches": mismatches})
    _append(checks, "body-dxf-vs-hole-table", "pass" if mismatch_count == 0 else "fail",
            "Reimported body DXF centers, slot profiles, and round holes match the primary patterns in hole-table.json.",
            mismatchCount=mismatch_count, patterns=per_plate,
            physicalWeightedSlotCount=sum(
                spec.quantity * sum(row["profile"] == "slot" for row in table["holes"]
                                    if row["plate"] == spec.id and
                                    row["plate_instance"] == spec.primary_instance_id)
                for spec in specs),
            physicalWeightedRoundCount=sum(
                spec.quantity * sum(row["profile"] == "round" for row in table["holes"]
                                    if row["plate"] == spec.id and
                                    row["plate_instance"] == spec.primary_instance_id)
                for spec in specs))
    return {"table": table, "specs": specs}


def _step_hole_positions(table: dict, specs: tuple, step_shapes: dict[str, cq.Shape],
                         checks: list[dict]) -> None:
    mismatches = []
    matched = 0
    for spec in specs:
        shape = step_shapes.get(f"aluminum/{spec.id.lower()}-qty{spec.quantity}-mm.step")
        if shape is None:
            mismatches.append({"partId": spec.id, "problem": "STEP not reimported"})
            continue
        rows = [row for row in table["holes"]
                if row["plate"] == spec.id and
                row["plate_instance"] == spec.primary_instance_id]
        box = shape.BoundingBox()
        limits = ((box.xmin, box.xmax), (box.ymin, box.ymax), (box.zmin, box.zmax))
        dimensions = [high-low for low, high in limits]
        normal_axis = min(range(3), key=lambda axis: dimensions[axis])
        thickness = float(spec.thickness_mm)
        for row in rows:
            center = [float(value) for value in row["center_xyz"]]
            if abs(center[normal_axis]-limits[normal_axis][0]) <= TOLERANCE_MM:
                inward_sign = 1.0
            elif abs(center[normal_axis]-limits[normal_axis][1]) <= TOLERANCE_MM:
                inward_sign = -1.0
            else:
                mismatches.append({"holeId": row["id"], "problem": "hole datum is not on STEP plate face"})
                continue
            center[normal_axis] += inward_sign * thickness / 2
            hole_center = cq.Vector(*center)
            normal = [0.0, 0.0, 0.0]
            normal[normal_axis] = inward_sign

            def in_material(point: cq.Vector) -> bool:
                return shape.isInside(point, 1e-6)

            if in_material(hole_center):
                mismatches.append({"holeId": row["id"], "problem": "expected hole center contains material"})
                continue
            profile = row["profile"]
            if profile == "slot":
                axis_values = [float(value) for value in row["axis"]]
                axis_length = math.sqrt(sum(value*value for value in axis_values))
                axis_values = [value/axis_length for value in axis_values]
                axis = cq.Vector(*axis_values)
                normal_vector = cq.Vector(*normal)
                across = normal_vector.cross(axis)
                if across.Length <= 1e-9:
                    mismatches.append({"holeId": row["id"], "problem": "slot axis parallel to plate normal"})
                    continue
                across = across.normalized()
                void_samples = (hole_center + axis*3.25, hole_center - axis*3.25,
                                hole_center + across*2.5)
                material_samples = (hole_center + axis*4.0,
                                    hole_center - axis*4.0,
                                    hole_center + across*3.0)
            else:
                in_plane = [cq.Vector(*(1.0 if index == axis else 0.0 for index in range(3)))
                            for axis in range(3) if axis != normal_axis]
                void_samples = tuple(hole_center + direction*2.5 for direction in in_plane)
                material_samples = tuple(hole_center + direction*3.0 for direction in in_plane)
            if any(in_material(point) for point in void_samples):
                mismatches.append({"holeId": row["id"], "problem": "profile interior sample contains material"})
                continue
            if not all(in_material(point) for point in material_samples):
                mismatches.append({"holeId": row["id"], "problem": "profile exterior sample is void"})
                continue
            matched += 1
    expected_primary = sum(len(spec.pattern_holes) for spec in specs)
    _append(checks, "body-step-vs-hole-table-positions",
            "pass" if not mismatches and matched == expected_primary else "fail",
            "Reimported STEP plate voids and profile boundaries match every primary hole-table center.",
            matchedPrimaryPatternFeatures=matched, expectedPrimaryPatternFeatures=expected_primary,
            physicalTableRows=len(table["holes"]), mismatchCount=len(mismatches), mismatches=mismatches[:25])


def _validate_plate_dimensions(ctx: BuildContext, specs: tuple,
                               step_shapes: dict[str, cq.Shape], checks: list[dict]) -> None:
    body_manifest = _load_json(ctx.out / "hardware-envelopes" / "body-manifest.json")
    body_checks = []
    for spec in specs:
        key = f"aluminum/{spec.id.lower()}-qty{spec.quantity}-mm.step"
        shape = step_shapes.get(key)
        expected = sorted([float(spec.width_mm), float(spec.height_mm), float(spec.thickness_mm)])
        actual = sorted(_bbox(shape)["dimensionsMm"]) if shape is not None else []
        matches = (len(actual) == 3 and
                   all(abs(actual[index]-expected[index]) <= TOLERANCE_MM for index in range(3)))
        body_checks.append({"partId": spec.id, "quantity": spec.quantity,
                            "expectedMm": expected, "actualMm": actual, "matches": matches})
    body_plate_count = sum(spec.quantity for spec in specs)
    body_count_ok = (body_plate_count == 5 and
                     body_manifest.get("dimensions", {}).get("plateCount") == 5)
    body_pass = body_count_ok and all(item["matches"] for item in body_checks)
    _append(checks, "body-plate-dimensions-and-count", "pass" if body_pass else "fail",
            "The five physical body plates reimport with their parameter-derived flat-pattern dimensions.",
            physicalPlateCount=body_plate_count,
            sourceManifestPlateCount=body_manifest.get("dimensions", {}).get("plateCount"),
            plates=body_checks)

    lid_id = "7U40-R9-LID-PLATE"
    lid_path_key = f"aluminum/{lid_id.lower()}-qty1-mm.step"
    lid_shape = step_shapes.get(lid_path_key)
    frame_wall = float(ctx.value("lid", "frame_wall"))
    edge_gap = float(ctx.value("lid", "plate_edge_gap"))
    expected_lid = sorted([
        float(ctx.value("guards", "top_edge_guard_exterior_x")) - 2*(frame_wall+edge_gap),
        float(ctx.value("guards", "top_edge_guard_exterior_y")) - 2*(frame_wall+edge_gap),
        float(ctx.value("lid", "plate_thickness")),
    ])
    actual_lid = sorted(_bbox(lid_shape)["dimensionsMm"]) if lid_shape is not None else []
    lid_match = (len(actual_lid) == 3 and
                 all(abs(actual_lid[index]-expected_lid[index]) <= TOLERANCE_MM
                     for index in range(3)))
    lid_manifest = _load_json(ctx.out / "pa12" / "lid" / "manifest.json")
    lid_count_ok = lid_id in lid_manifest.get("parts", [])
    _append(checks, "lid-plate-dimensions-and-count", "pass" if lid_match and lid_count_ok else "fail",
            "The sixth plate is the current candidate lid plate, checked against its frame and edge-gap parameters.",
            physicalPlateCount=1, includedInLidManifest=lid_count_ok,
            expectedMm=expected_lid, actualMm=actual_lid)


def _preview_payload(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    match = re.search(r'window\.ZUDO_R9_MODEL_GZIP\s*=\s*("(?:\\.|[^"\\])*")\s*;', source)
    if not match:
        raise ValueError(f"preview model assignment missing: {path}")
    encoded = json.loads(match.group(1))
    return json.loads(gzip.decompress(base64.b64decode(encoded)))


def _part_mesh_digest(payload: dict, part_id: str) -> str | None:
    import hashlib

    records = [part for part in payload.get("parts", []) if part.get("partId") == part_id]
    if not records:
        return None
    return hashlib.sha256(json.dumps(records, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _stl_role(relative: str) -> tuple[str, str]:
    path = Path(relative)
    if "hardware-envelopes" in path.parts:
        if path.name.startswith("7u40-r9-pcb-"):
            return (
                "source-derived display geometry",
                "PCB outline polygons are preserved from the saved R6 panel geometry and extruded for assembly display; this is not a PCB manufacturing export.",
            )
        return (
            "provisional reference envelope",
            "Hardware, bracket, rail, spacer, washer, bolt, nut, and foot solids are assembly envelopes with provisional or unselected details; they are not manufacturing candidates.",
        )
    if "coupons" in path.parts and "c2" in path.parts and "rail-envelope" in path.name:
        return (
            "source-derived display geometry",
            "C2 includes an axis-aligned rail source bounding envelope for section context; it is not the source rail profile or a manufactured coupon.",
        )
    return (
        "unapproved R9 candidate geometry",
        "Generated case, guard, lid, or coupon geometry; the file remains an unapproved candidate.",
    )


def _temp_params(ctx: BuildContext, namespace: str, key: str, value) -> tuple[tempfile.TemporaryDirectory, BuildContext]:
    temporary = tempfile.TemporaryDirectory(prefix="zudo-r9-param-check-")
    repo_root = Path(temporary.name)
    package_root = repo_root / "engineering" / "r9-prototype-01"
    params_dir = package_root / "params"
    params_dir.mkdir(parents=True)
    for source_name in ("r6-body", "r8-preview"):
        source = ctx.root.resolve().parents[1] / "engineering" / source_name
        target = repo_root / "engineering" / source_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)
    for source in (ctx.root / "params").glob("*.json"):
        shutil.copy2(source, params_dir / source.name)
    changed_path = params_dir / f"{namespace}.json"
    changed = _load_json(changed_path)
    if key not in changed:
        temporary.cleanup()
        raise KeyError(f"unknown parameter {namespace}.{key}")
    changed[key]["value"] = value
    changed_path.write_text(json.dumps(changed, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    params = {}
    for name in ("body", "slots", "guards", "lid", "coupons"):
        data = _load_json(params_dir / f"{name}.json")
        for item in data.values():
            if set(item) != {"value", "unit", "status", "source", "note"}:
                temporary.cleanup()
                raise ValueError(f"invalid temporary parameter record in {name}")
        params[name] = data
    for mirror in ("top_edge_guard_opening_x", "top_edge_guard_opening_y",
                   "top_edge_guard_exterior_x", "top_edge_guard_exterior_y",
                   "top_edge_seated_guard_z", "top_edge_adhesive_allowance"):
        if params["guards"][mirror]["value"] != params["lid"][mirror]["value"]:
            temporary.cleanup()
            raise ValueError(f"temporary top-edge mirror mismatch: {mirror}")
    temp_ctx = BuildContext(package_root, package_root / "out", params,
                            revision=ctx.revision, model=ctx.model)
    for directory in ("aluminum", "pa12", "hardware-envelopes", "coupons", "assembly", "preview"):
        (temp_ctx.out / directory).mkdir(parents=True, exist_ok=True)
    return temporary, temp_ctx


def _export_temp_part(ctx: BuildContext, part: Part) -> None:
    stem = f"{part.id.lower()}-qty{part.qty}-mm"
    for kind in part.export_kinds:
        path = ctx.out / part.category / f"{stem}.{kind}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "step":
            export_step(part.solid, path)
            if part.category == "coupons":
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


def _regenerate_parameter_variant(ctx: BuildContext, namespace: str, key: str,
                                  value) -> tuple[dict, dict, dict, dict]:
    temporary, variant_ctx = _temp_params(ctx, namespace, key, value)
    try:
        for name in ("body", "slots", "guards", "lid", "coupons"):
            module = importlib.import_module(f"r9.{name}")
            parts = module.build(variant_ctx)
            for part in parts:
                _export_temp_part(variant_ctx, part)
            if name == "coupons":
                module.finalize(variant_ctx)
        importlib.import_module("r9.preview_data").build(variant_ctx)

        body_hashes = {}
        for part_id, quantity in (("7U40-R9-AL-BOTTOM", 1),
                                  ("7U40-R9-AL-FRONT-BACK", 2),
                                  ("7U40-R9-AL-LEFT-RIGHT", 2)):
            path = variant_ctx.out / "aluminum" / f"{part_id.lower()}-qty{quantity}-mm.step"
            body_hashes[path.name] = sha256_file(path)
        coupon_manifest = _load_json(variant_ctx.out / "coupons" / "coupon-manifest.json")
        payload = _preview_payload(variant_ctx.out / "preview" / "model-data.js")
        return body_hashes, coupon_manifest, payload, {
            "parameterValue": payload["parameters"][namespace][key],
            "temporaryParameterCopy": True,
            "generatedCouponManifest": True,
            "generatedPreviewModel": True,
        }
    finally:
        temporary.cleanup()


def _parameter_change_checks(ctx: BuildContext, checks: list[dict]) -> None:
    baseline_body_hashes = {
        path.name: sha256_file(path)
        for path in (ctx.out / "aluminum").glob("7u40-r9-al-*-qty*-mm.step")
        if "lid" not in path.name
    }
    baseline_coupon_manifest = _load_json(ctx.out / "coupons" / "coupon-manifest.json")
    baseline_payload = _preview_payload(ctx.out / "preview" / "model-data.js")
    scenarios = (
        {"namespace": "guards", "key": "fitClearancePerSide", "value": 0.17,
         "couponId": "C1-01", "previewPartId": "7U40-R9-PA12-GUARD-T1P2-TOP-A",
         "expectedCouponField": "fitClearancePerSideMm"},
        {"namespace": "lid", "key": "top_edge_lid_locator_clearance", "value": 0.75,
         "couponId": "C2-01", "previewPartId": "7U40-R9-PA12-LID-FRAME-FR",
         "expectedCouponField": "lidLocatorClearanceMm"},
    )
    for scenario in scenarios:
        namespace, key = scenario["namespace"], scenario["key"]
        body_hashes, coupon_manifest, payload, run_metadata = _regenerate_parameter_variant(
            ctx, namespace, key, scenario["value"])
        body_unchanged = body_hashes == baseline_body_hashes
        _append(checks, f"parameter-{namespace}-{key}-body-invariant",
                "pass" if body_unchanged else "fail",
                "A guard/lid-only parameter change leaves the independent aluminum body plate CAD unchanged.",
                parameterValue=scenario["value"], bodyCadHashesUnchanged=body_unchanged,
                bodyCadFiles=sorted(body_hashes))
        value_ok = run_metadata["parameterValue"] == scenario["value"]
        _append(checks, f"parameter-{namespace}-{key}-preview-parameter",
                "pass" if value_ok else "fail",
                "The isolated preview data carries the perturbed parameter value.",
                expected=scenario["value"], actual=run_metadata["parameterValue"])
        coupon = next((item for item in coupon_manifest["coupons"]
                       if item["id"] == scenario["couponId"]), None)
        baseline_coupon = next((item for item in baseline_coupon_manifest["coupons"]
                                if item["id"] == scenario["couponId"]), None)
        variant_coupon_hashes = ({item["path"]: item["sha256"] for item in coupon.get("fileHashes", [])}
                                 if coupon else {})
        baseline_coupon_hashes = ({item["path"]: item["sha256"] for item in baseline_coupon.get("fileHashes", [])}
                                  if baseline_coupon else {})
        coupon_changed = (bool(variant_coupon_hashes) and
                          variant_coupon_hashes != baseline_coupon_hashes)
        coupon_baseline_value = (coupon.get("baselineParameters", {}).get(scenario["expectedCouponField"])
                                 if coupon else None)
        coupon_consistent = coupon_baseline_value == scenario["value"]
        _append(checks, f"parameter-{namespace}-{key}-coupon",
                "pass" if coupon_changed and coupon_consistent else "fail",
                "The dependent coupon is regenerated, its bytes change, and its recorded baseline matches the new parameter.",
                couponId=scenario["couponId"], expectedParameterValue=scenario["value"],
                recordedCouponValue=coupon_baseline_value,
                couponFiles=sorted(variant_coupon_hashes),
                couponBytesChanged=coupon_changed)
        preview_digest = _part_mesh_digest(payload, scenario["previewPartId"])
        baseline_preview_digest = _part_mesh_digest(baseline_payload, scenario["previewPartId"])
        preview_changed = (preview_digest is not None and
                           baseline_preview_digest is not None and
                           preview_digest != baseline_preview_digest)
        _append(checks, f"parameter-{namespace}-{key}-preview-geometry",
                "pass" if preview_changed else "fail",
                "The preview mesh for the dependent guard/lid part changes after regeneration.",
                partId=scenario["previewPartId"], previewMeshChanged=preview_changed,
                changedMeshSha256=preview_digest,
                baselineMeshSha256=baseline_preview_digest)


def _module_check_aggregation(ctx: BuildContext, checks: list[dict]) -> list[str]:
    slot_report = _load_json(ctx.out / "aluminum" / "slot-checks.json")
    slot_failures = slot_report["failures"]
    slot_counts = slot_report["counts"]
    expected_counts = {"slots": 36, "roundRailFix": 10}
    slot_counts_ok = slot_counts == expected_counts
    _append(checks, "s2-slot-profile-counts", "pass" if slot_counts_ok else "fail",
            "Aggregate S2 slot/round-hole count check.", counts=slot_counts,
            expected=expected_counts)
    for key in ("edge", "ligament", "toolAccess", "guardContact"):
        rows = slot_failures.get(key, [])
        _append(checks, f"s2-slot-{key}", "pass" if not rows else "fail",
                f"S2 {key} checks must have no modeled failure rows.",
                failureCount=len(rows), failures=rows)
    bearing = slot_failures.get("bearingCoverage", [])
    _append(checks, "s2-slot-bearing-coverage",
            "flag" if bearing else "pass",
            "The provisional 10 mm washer does not meet nominal bearing overlap at current wall slots; larger OD remains a candidate.",
            failureCount=len(bearing),
            requiredWasherOdCandidateMm=slot_report.get("criteria", {}).get("bearingRequiredOdMm"),
            selectedWasherOdMm=10.0)

    assembly = _load_json(ctx.out / "assembly" / "assembly-checks.json")
    static = assembly["staticInterference"]
    contacts = static.get("contacts", [])
    _append(checks, "s4b-tested-static-interference",
            "pass" if static.get("testedSolidPairsPass") and not contacts else "fail",
            "Tested lid-frame/top-guard BREP pair has no nominal interference above threshold.",
            contacts=contacts,
            testedSolidPairClasses=static.get("testedSolidPairClasses", []))
    if not static.get("complete"):
        _append(checks, "s4b-static-interference-coverage", "flag",
                "Assembly collision coverage is partial; untested pair classes remain.",
                untestedPairClasses=static.get("untestedPairClasses", []))
    lift = assembly["liftPath"]
    lift_pass = lift.get("testedSolidPathPass") and lift.get("envelopeScreenPass")
    _append(checks, "s4b-lift-path-nominal-screen",
            "pass" if lift_pass else "fail",
            "The sampled nominal PA12 frame/top-guard lift path and locator envelope screen are clear.",
            firstContact=lift.get("firstContact"),
            envelopeFirstOverlapCandidate=lift.get("envelopeFirstOverlapCandidate"),
            stepMm=lift.get("stepMm"), endMm=lift.get("endMm"))
    if not lift.get("complete"):
        _append(checks, "s4b-lift-path-coverage", "flag",
                "Lift-path checks cover limited BREP and envelope classes, not all actual assembly solids.",
                scope=lift.get("scope"))
    guard_band = assembly.get("slotsVsRealGuards", {}).get("s2GuardBandFailures", [])
    _append(checks, "s4b-slot-guard-contact", "pass" if not guard_band else "fail",
            "S2 bracket slot profiles are outside the nominal guard contact band.",
            failureCount=len(guard_band), failures=guard_band)
    access = assembly.get("access", {})
    m5_failures = access.get("m5S2NominalToolFailures", [])
    _append(checks, "s4b-m5-nominal-tool-envelope",
            "pass" if not m5_failures else "fail",
            "S2 modeled M5 exterior tool envelopes have no nominal conflicts.",
            failureCount=len(m5_failures), failures=m5_failures)
    if not access.get("m3DriverValidated") or not access.get("m5PhysicalValidated"):
        _append(checks, "s4b-physical-fastener-access", "flag",
                "M3/M5 driver access and physical washer fit are not validated.",
                m3DriverValidated=access.get("m3DriverValidated"),
                m5PhysicalValidated=access.get("m5PhysicalValidated"))
    straps = assembly.get("straps", {})
    _append(checks, "s4b-band-contact-and-deflection", "flag",
            "Straps are schematic; plate-only contact and deflection remain unresolved.",
            strapStatus=straps.get("status"),
            plateOnlyContactExcluded=straps.get("plateOnlyContactExcluded"),
            stations=straps.get("stations", []))
    return list(assembly.get("not_validated", []))


def _preview_checks(ctx: BuildContext, checks: list[dict]) -> None:
    mesh = _load_json(ctx.out / "preview" / "mesh-checks.json")
    mesh_ok = (mesh.get("partsSorted") is True and mesh.get("noR8Meshes") is True and
               mesh.get("railInstanceCount") == 6 and mesh.get("railSourceLengthMm") == 204 and
               mesh.get("modelJsonBytes", LIMIT_BYTES) < LIMIT_BYTES and
               mesh.get("gzipBytes", LIMIT_BYTES) < LIMIT_BYTES)
    _append(checks, "preview-mesh-checks", "pass" if mesh_ok else "fail",
            "Aggregate offline preview mesh ordering, source rail, and size checks.",
            partCount=mesh.get("meshPartCount"), uniquePartIds=mesh.get("uniquePartIds"),
            railInstanceCount=mesh.get("railInstanceCount"),
            railSourceLengthMm=mesh.get("railSourceLengthMm"),
            noR8Meshes=mesh.get("noR8Meshes"), modelJsonBytes=mesh.get("modelJsonBytes"),
            gzipBytes=mesh.get("gzipBytes"))
    file_table = _load_json(ctx.out / "preview" / "file-table.json")
    table_paths = {item["path"] for part in file_table.get("parts", [])
                   for item in part.get("formats", [])}
    coupon_manifest = _load_json(ctx.out / "coupons" / "coupon-manifest.json")
    c2_hashes = [file for coupon in coupon_manifest.get("coupons", [])
                 if coupon.get("id", "").startswith("C2-")
                 for file in coupon.get("fileHashes", [])]
    package_relative = ctx.root.resolve().relative_to(
        ctx.root.resolve().parents[1]).as_posix()
    c2_path_prefix = f"{package_relative}/"
    expected_c2_paths = {
        file["path"].replace("out/", c2_path_prefix + "out/", 1) for file in c2_hashes
    }
    missing_c2 = sorted(expected_c2_paths - table_paths)
    _append(checks, "preview-c2-file-table", "pass" if not missing_c2 else "fail",
            "The preview file table lists all C2 nested coupon files and their paths.",
            c2FileCount=len(c2_hashes), missingPaths=missing_c2,
            tablePartCount=len(file_table.get("parts", [])))

    repo_root = ctx.root.resolve().parents[1]
    public_html = repo_root / "public" / "previews" / "r9-prototype-01.html"
    if public_html.is_file():
        html = public_html.read_text(encoding="utf-8")
        html_has_c2 = all(path.lower() in html.lower() for path in expected_c2_paths)
        _append(checks, "preview-public-html-c2-catalog", "pass" if html_has_c2 else "flag",
                "The single-file preview contains the generated C2 catalog paths if it has been refreshed.",
                htmlExists=True, c2PathsEmbedded=html_has_c2,
                missingPaths=[path for path in expected_c2_paths if path.lower() not in html.lower()])
    else:
        _append(checks, "preview-public-html-c2-catalog", "flag",
                "The single-file preview is generated separately and is absent from this checkout.",
                htmlExists=False, c2PathsEmbedded=False)


def _format_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# R9-PROTOTYPE-01 検証集約",
        "",
        f"**状態:** {report['status']} / 製作承認: なし",
        "",
        f"**集計:** pass {summary['passed']} / flag {summary['flagged']} / fail {summary['failed']}",
        f"**対象:** {report['model']} / {report['units']} / R9候補データ",
        "",
        "## 確認結果",
        "",
        f"- 本体平板: {report['plateCounts']['body']}枚、蓋板: {report['plateCounts']['lid']}枚。",
        f"- 穴テーブル: {report['holeCounts']['total']}件 "
        f"(長穴 {report['holeCounts']['slots']}、丸穴 {report['holeCounts']['round']})。",
        f"- R9生成STL: {report['artifactCounts']['stl']}件をSTEP再取込形状と照合。",
        f"- STEP: {report['artifactCounts']['step']}件、DXF: {report['artifactCounts']['dxf']}件を再取込。",
        f"- パラメーター変更: {report['parameterChangeChecks']['scenarioCount']}ケースを一時コピーで再生成。",
        "- R6元レールSTLはR9生成物ではないため、R9 STLの閉じたメッシュ検査から除外。",
        "",
        "## フラグ",
        "",
    ]
    flags = [check for check in report["checks"] if check["status"] == "flag"]
    if flags:
        lines.extend(f"- {check['id']}: {check['summary']}" for check in flags)
    else:
        lines.append("- なし")
    lines.extend(["", "## 参照メッシュの詳細", ""])
    mesh = report["meshSummary"]
    bbox_flags = [item for item in mesh["flaggedFiles"]
                  if item.get("bboxMaxDeltaMm", 0) > mesh["strictBboxToleranceMm"]]
    if bbox_flags:
        lines.append(
            f"- 参照包絡STLのSTEP境界との差は最大 "
            f"{max(item['bboxMaxDeltaMm'] for item in bbox_flags):.6f} mm。"
            f"厳密照合値は {mesh['strictBboxToleranceMm']:.4f} mm、"
            f"STL書出しの弦誤差許容値は {mesh['bboxTessellationToleranceMm']:.2f} mm。"
        )
        lines.extend(f"  - {item['path']}: {item['bboxMaxDeltaMm']:.6f} mm"
                     for item in bbox_flags)
    else:
        lines.append("- 参照包絡STLの境界差フラグはありません。")
    source_mesh_flags = [item for item in mesh["flaggedFiles"]
                         if item["artifactRole"] == "source-derived display geometry" and
                         not item["closedManifold"]]
    for item in source_mesh_flags:
        lines.append(
            f"- {item['path']}: 閉じたメッシュではありません。"
            f"辺出現数 {json.dumps(item['edgeIncidenceHistogram'], ensure_ascii=False)}。"
            "R6由来輪郭を用いた表示用包絡で、製作用PCBデータとして扱いません。"
        )
    lines.extend(["", "## 未検証", ""])
    lines.extend(f"- {item}" for item in report["not_validated"])
    lines.extend([
        "",
        "CAD再取込・メッシュ検査・名目配置チェックは、現物の嵌合、材料、強度、接着、運搬の結果を示しません。",
        "すべての詳細は同じフォルダーの out/validation.json を参照してください。",
        "",
    ])
    return "\n".join(lines)


def validate_outputs(ctx: BuildContext, generated_outputs: list[dict]) -> dict:
    """Validate the current full build and write JSON plus review summary."""
    checks: list[dict] = []
    ledger_paths = set()
    ledger_mismatches = []
    for entry in generated_outputs:
        path = ctx.root / entry["path"]
        if entry["path"] in ledger_paths:
            ledger_mismatches.append({"path": entry["path"], "problem": "duplicate ledger path"})
            continue
        ledger_paths.add(entry["path"])
        if not path.is_file():
            ledger_mismatches.append({"path": entry["path"], "problem": "missing file"})
            continue
        actual = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        if actual["sha256"] != entry.get("sha256") or actual["bytes"] != entry.get("bytes"):
            ledger_mismatches.append({"path": entry["path"], "problem": "hash/size mismatch",
                                      "recorded": {"sha256": entry.get("sha256"),
                                                   "bytes": entry.get("bytes")},
                                      "actual": actual})
        if path.stat().st_size >= LIMIT_BYTES:
            ledger_mismatches.append({"path": entry["path"], "problem": "file exceeds 25 MiB"})
    _append(checks, "build-output-ledger",
            "pass" if generated_outputs and not ledger_mismatches else "fail",
            "Every generated build-log artifact exists, is below 25 MiB, and matches its recorded digest.",
            outputCount=len(generated_outputs), duplicateOrMismatchCount=len(ledger_mismatches),
            mismatches=ledger_mismatches[:30])

    output_paths = sorted(ledger_paths)
    step_paths = [ctx.root / item for item in output_paths if item.lower().endswith(".step")]
    dxf_paths = [ctx.root / item for item in output_paths if item.lower().endswith(".dxf")]
    stl_paths = [ctx.root / item for item in output_paths if item.lower().endswith(".stl")]
    step_shapes: dict[str, cq.Shape] = {}
    for path in step_paths:
        relative = _relative(ctx, path)
        try:
            shape = _import_step(path)
            valid = shape.isValid()
            solid_count = len(shape.Solids())
            assembly_reference = "/assembly/" in relative
            one_solid_ok = solid_count == 1 or assembly_reference
            _append(checks, f"step:{relative}", "pass" if valid and one_solid_ok else "fail",
                    "STEP reimports as valid CAD; component files contain one solid, assembly references may contain multiple.",
                    isValid=valid, solidCount=solid_count,
                    singleSolidRequired=not assembly_reference,
                    volumeMm3=float(shape.Volume()), bbox=_bbox(shape))
            if valid and one_solid_ok:
                step_shapes[relative.removeprefix("out/")] = shape
        except Exception as error:
            _append(checks, f"step:{relative}", "fail", "STEP import or geometry validity failed.",
                    error=f"{type(error).__name__}: {error}")

    for path in dxf_paths:
        relative = _relative(ctx, path)
        try:
            _, audit = _dxf_audit(path)
            valid = (audit["units"] == ezdxf.units.MM and
                     audit["errorCount"] == 0 and audit["fixCount"] == 0)
            _append(checks, f"dxf:{relative}", "pass" if valid else "fail",
                    "DXF reimports in millimetres and passes ezdxf audit.", **audit)
        except Exception as error:
            _append(checks, f"dxf:{relative}", "fail", "DXF import or audit failed.",
                    error=f"{type(error).__name__}: {error}")

    stl_metrics = []
    stl_failures = []
    stl_flags = []
    for path in stl_paths:
        relative = _relative(ctx, path)
        step_path = path.with_suffix(".step")
        role, role_reason = _stl_role(relative)
        is_candidate = role == "unapproved R9 candidate geometry"
        if not step_path.is_file():
            error = "matching STEP export is missing"
            stl_failures.append({"path": relative, "problem": error})
            _append(checks, f"stl:{relative}", "fail",
                    "STL has no matching STEP geometry for volume/bbox comparison.",
                    error=error, artifactRole=role, roleReason=role_reason)
            continue
        step_key = _relative(ctx, step_path).removeprefix("out/")
        shape = step_shapes.get(step_key)
        if shape is None:
            error = "matching STEP did not pass reimport"
            stl_failures.append({"path": relative, "problem": error})
            _append(checks, f"stl:{relative}", "fail",
                    "STL was not checked against a valid reimported STEP shape.",
                    error=error, artifactRole=role, roleReason=role_reason)
            continue
        try:
            metrics = inspect_binary_stl(path, allow_non_watertight=True)
            cad_bbox = _bbox(shape)
            bbox_axis_deltas = [
                max(abs(metrics["bboxMinMm"][axis] - cad_bbox["minMm"][axis]),
                    abs(metrics["bboxMaxMm"][axis] - cad_bbox["maxMm"][axis]))
                for axis in range(3)
            ]
            bbox_delta = max(bbox_axis_deltas)
            cad_volume = float(shape.Volume())
            volume_delta = abs(metrics["volumeMm3"] - cad_volume)
            volume_tolerance = max(STL_VOLUME_ABSOLUTE_TOLERANCE_MM3,
                                   cad_volume * STL_VOLUME_RELATIVE_TOLERANCE)
            volume_ok = metrics["positiveVolume"] and volume_delta <= volume_tolerance
            bbox_strict_ok = bbox_delta <= STL_BBOX_TOLERANCE_MM
            bbox_tessellation_ok = bbox_delta <= STL_TESSELLATION_TOLERANCE_MM
            topology_ok = metrics["closedManifold"]
            if not volume_ok or not bbox_tessellation_ok:
                status = "fail"
            elif not topology_ok and is_candidate:
                status = "fail"
            elif (not topology_ok or not bbox_strict_ok) and not is_candidate:
                status = "flag"
            else:
                status = "pass"
            row = {
                "path": relative,
                "artifactRole": role,
                "roleReason": role_reason,
                "pairedStep": step_key,
                "triangleCount": metrics["triangleCount"],
                "closedManifold": topology_ok,
                "edgeIncidenceHistogram": metrics["edgeIncidenceHistogram"],
                "positiveVolume": metrics["positiveVolume"],
                "volumeMm3": metrics["volumeMm3"],
                "stepVolumeMm3": cad_volume,
                "volumeDeltaMm3": volume_delta,
                "volumeToleranceMm3": volume_tolerance,
                "volumeMatchesStep": volume_ok,
                "bboxMinMm": metrics["bboxMinMm"],
                "bboxMaxMm": metrics["bboxMaxMm"],
                "stepBboxMinMm": cad_bbox["minMm"],
                "stepBboxMaxMm": cad_bbox["maxMm"],
                "bboxDeltaPerAxisMm": bbox_axis_deltas,
                "bboxMaxDeltaMm": bbox_delta,
                "strictBboxToleranceMm": STL_BBOX_TOLERANCE_MM,
                "exportTessellationToleranceMm": STL_TESSELLATION_TOLERANCE_MM,
                "bboxWithinTessellationTolerance": bbox_tessellation_ok,
                "dimensionsMm": metrics["dimensionsMm"],
                "status": status,
            }
            stl_metrics.append(row)
            if status == "fail":
                stl_failures.append({"path": relative, "problem": {
                    "volumeMatchesStep": volume_ok,
                    "bboxWithinTessellationTolerance": bbox_tessellation_ok,
                    "closedManifold": topology_ok,
                    "artifactRole": role,
                }})
            elif status == "flag":
                stl_flags.append({"path": relative, "artifactRole": role,
                                  "closedManifold": topology_ok,
                                  "bboxMaxDeltaMm": bbox_delta,
                                  "edgeIncidenceHistogram": metrics["edgeIncidenceHistogram"],
                                  "reason": role_reason})
            if status == "pass":
                summary = "STL is watertight, has positive volume, and matches its reimported STEP volume/bbox."
            elif status == "flag":
                summary = "Reference/display STL has a recorded mesh limitation; its STEP BREP remains the geometry source of truth."
            else:
                summary = "STL fails the mesh topology, volume, or bbox check for its declared artifact role."
            _append(checks, f"stl:{relative}", status, summary,
                    **{key: value for key, value in row.items() if key != "status"})
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            stl_failures.append({"path": relative, "problem": message})
            _append(checks, f"stl:{relative}", "fail",
                    "STL is unreadable or differs from its reimported STEP geometry.",
                    error=message, pairedStep=step_key,
                    artifactRole=role, roleReason=role_reason)

    _append(checks, "hardware-envelope-stl-scope", "flag",
            "Hardware-envelope and source-derived PCB STLs are assembly/display references, not manufacturing candidates; each is still listed and checked against its STEP geometry.",
            classifications={
                "provisional reference envelope": "Provisional or unselected hardware and occupancy shapes in out/hardware-envelopes.",
                "source-derived display geometry": "R6 panel-geometry polygons extruded as PCB display envelopes, plus the C2 axis-aligned source-rail envelope.",
                "unapproved R9 candidate geometry": "Body plates, guards, lid, and physical coupon geometry; these require watertight STL meshes.",
            },
            stlCount=len(stl_paths))

    _append(checks, "source-rail-stl-exclusion", "flag",
            "The 40HP rail mesh is saved R6 source geometry, not an R9-made STL; source identity is checked separately.",
            path="engineering/r6-body/source-data/rail40/nuts-v2-40hp-single.stl",
            reason="It is an incoming reference mesh used in the preview and is excluded from R9 output mesh validation.")

    hole_info = _match_body_dxf_features(ctx, checks)
    _step_hole_positions(hole_info["table"], hole_info["specs"], step_shapes, checks)
    _validate_plate_dimensions(ctx, hole_info["specs"], step_shapes, checks)
    assembly_not_validated = _module_check_aggregation(ctx, checks)
    _preview_checks(ctx, checks)
    _parameter_change_checks(ctx, checks)

    failed = sum(check["status"] == "fail" for check in checks)
    passed = sum(check["status"] == "pass" for check in checks)
    flagged = sum(check["status"] == "flag" for check in checks)
    coupon_manifest = _load_json(ctx.out / "coupons" / "coupon-manifest.json")
    c2_file_count = sum(len(coupon.get("fileHashes", []))
                        for coupon in coupon_manifest.get("coupons", [])
                        if coupon.get("id", "").startswith("C2-"))
    report = {
        "schema": "zudo-case-r9-validation-v1",
        "revision": ctx.revision,
        "model": ctx.model,
        "units": "mm",
        "status": "failed" if failed else ("passed_with_flags" if flagged else "passed"),
        "productionApproved": False,
        "summary": {"passed": passed, "flagged": flagged, "failed": failed,
                    "checkCount": len(checks)},
        "plateCounts": {"body": sum(spec.quantity for spec in hole_info["specs"]), "lid": 1},
        "holeCounts": {"total": len(hole_info["table"]["holes"]),
                       "slots": sum(row["profile"] == "slot" for row in hole_info["table"]["holes"]),
                       "round": sum(row["profile"] == "round" for row in hole_info["table"]["holes"])},
        "artifactCounts": {"step": len(step_paths), "dxf": len(dxf_paths),
                           "stl": len(stl_paths), "c2CouponFiles": c2_file_count},
        "meshSummary": {
            "checkedR9StlCount": len(stl_metrics),
            "candidateStlCount": sum(item["artifactRole"] == "unapproved R9 candidate geometry"
                                     for item in stl_metrics),
            "referenceStlCount": sum(item["artifactRole"] == "provisional reference envelope"
                                     for item in stl_metrics),
            "sourceDerivedDisplayStlCount": sum(item["artifactRole"] == "source-derived display geometry"
                                                for item in stl_metrics),
            "flaggedR9StlCount": len(stl_flags),
            "failedR9StlCount": len(stl_failures),
            "flaggedFiles": stl_flags,
            "failedFiles": stl_failures,
            "totalTriangles": sum(item["triangleCount"] for item in stl_metrics),
            "positiveVolumeMm3": round(sum(item["volumeMm3"] for item in stl_metrics), 6),
            "bboxTessellationToleranceMm": STL_TESSELLATION_TOLERANCE_MM,
            "strictBboxToleranceMm": STL_BBOX_TOLERANCE_MM,
        },
        "parameterChangeChecks": {
            "scenarioCount": 2,
            "method": "isolated temporary copy of parameter JSON; body/slots/guards/lid/coupons and preview regenerated",
            "bodyCadInvariantIsExpected": True,
        },
        "not_validated": list(dict.fromkeys([*NOT_VALIDATED, *assembly_not_validated])),
        "checks": checks,
    }
    out_path = ctx.out / "validation.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    (ctx.root / "VALIDATION.md").write_text(_format_markdown(report),
                                            encoding="utf-8", newline="\n")
    return report
