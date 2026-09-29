"""C1 guard-fit and C3 bracket-slot coupons for the R9 7U40 candidate."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math

import cadquery as cq

from . import body, guards, slots
from .common import sha256_file
from .types import BuildContext, Part


def _coupon_value(ctx: BuildContext, key: str):
    return ctx.value("coupons", key)


def _guard_values(ctx: BuildContext, *, thickness: float | None = None,
                  fit: float | None = None, adhesive: float | None = None) -> dict:
    """Copy candidate guard-section values, applying only the named variant."""
    return {
        "t": float(ctx.value("guards", "main_thickness") if thickness is None else thickness),
        "metalThickness": float(ctx.value("body", "metal_thickness")),
        "cover": float(ctx.value("guards", "cover")),
        "innerOverhang": float(ctx.value("guards", "innerOverhang")),
        "fitClearancePerSide": float(ctx.value("guards", "fitClearancePerSide") if fit is None else fit),
        "adhesiveLayer": float(ctx.value("guards", "adhesiveLayer") if adhesive is None else adhesive),
        "edgeRounding": float(ctx.value("guards", "edgeRounding")),
    }


def _marked_guard_segment(params: dict, length: float, coupon_id: str) -> cq.Shape:
    """Use the production guard section with raised, inspectable PA12 text."""
    from_section = guards.guard_section({**params, "length": length, "orientation": "top"})
    text = (cq.Workplane("YZ", origin=(params["t"], length / 2, -params["cover"] / 2))
            .text(coupon_id, float(params["labelSize"]), float(params["labelRise"]),
                  combine=False, font="Arial", kind="regular")
            .val())
    marked = from_section.fuse(text).clean()
    if not marked.isValid() or len(marked.Solids()) != 1:
        raise ValueError(f"invalid marked guard coupon: {coupon_id}")
    return marked


def _labelled_params(ctx: BuildContext, **overrides) -> dict:
    params = _guard_values(ctx, **overrides)
    params["labelSize"] = float(_coupon_value(ctx, "c1_mark_size"))
    params["labelRise"] = float(_coupon_value(ctx, "c1_mark_rise"))
    return params


def _part_files(ctx: BuildContext, part: Part) -> list[str]:
    stem = f"{part.id.lower()}-qty{part.qty}-mm"
    return [(ctx.out / part.category / f"{stem}.{kind}").relative_to(ctx.root).as_posix()
            for kind in part.export_kinds]


def _manifest_record(ctx: BuildContext, coupon_id: str, parts: list[Part], *, quantity: int,
                     baseline: dict, changed: dict | None, material: str,
                     purpose: str, results: dict | None = None,
                     details: dict | None = None) -> dict:
    record = {
        "id": coupon_id,
        "files": [path for part in parts for path in _part_files(ctx, part)],
        "quantity": quantity,
        "baselineParameters": baseline,
        "changedParameter": changed,
        "intendedMaterial": material,
        "purpose": purpose,
        "results": results or {
            "physicalFit": None,
            "fastenerFit": None,
            "retention": None,
            "notes": None,
        },
    }
    if details:
        record["details"] = details
    return record


def _input_records(ctx: BuildContext, sources: dict) -> list[dict]:
    repo_root = ctx.root.resolve().parents[1]
    paths = [ctx.root / "params" / f"{name}.json"
             for name in ("body", "guards", "slots", "coupons")]
    paths.extend(sources["paths"].values())
    records = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        relative = path.relative_to(repo_root)
        records.append({"path": relative.as_posix(), "sha256": sha256_file(path),
                        "bytes": path.stat().st_size})
    return records


def _build_c1(ctx: BuildContext) -> tuple[list[Part], list[dict]]:
    parts: list[Part] = []
    records: list[dict] = []
    length = float(_coupon_value(ctx, "c1_segment_length"))
    edge_height = float(_coupon_value(ctx, "c1_edge_height"))
    baseline_params = _labelled_params(ctx)
    baseline = {
        "guardThicknessMm": baseline_params["t"],
        "fitClearancePerSideMm": baseline_params["fitClearancePerSide"],
        "adhesiveLayerMm": baseline_params["adhesiveLayer"],
        "segmentLengthMm": length,
        "aluminumThicknessMm": baseline_params["metalThickness"],
    }
    material = "PA12-HP black dyed candidate"

    # Baseline cross-section and length. Labels are raised on the visible outer
    # face; the aluminum edge coupon is a reusable fixture for all C1 variants.
    baseline_id = "C1-01"
    baseline_part = Part(f"7U40-R9-CPN-{baseline_id}",
                         _marked_guard_segment(baseline_params, length, baseline_id),
                         "coupons", material, 1, ("step", "stl"))
    parts.append(baseline_part)
    records.append(_manifest_record(ctx,
        baseline_id, [baseline_part], quantity=1, baseline=baseline,
        changed=None, material=material,
        purpose="Baseline 40 mm body-guard section to trial over the matching 1.5 mm aluminum edge.",
    ))

    variants = []
    for fit in _coupon_value(ctx, "c1_fit_clearance_variants"):
        variants.append(("fitClearancePerSideMm", float(ctx.value("guards", "fitClearancePerSide")),
                         float(fit), {"fit": float(fit)}))
    for adhesive in _coupon_value(ctx, "c1_adhesive_layer_variants"):
        variants.append(("adhesiveLayerMm", float(ctx.value("guards", "adhesiveLayer")),
                         float(adhesive), {"adhesive": float(adhesive)}))
    for thickness in _coupon_value(ctx, "c1_thickness_variants"):
        variants.append(("guardThicknessMm", float(ctx.value("guards", "main_thickness")),
                         float(thickness), {"thickness": float(thickness)}))

    for index, (field, baseline_value, variant_value, override) in enumerate(variants, start=2):
        coupon_id = f"C1-{index:02d}"
        params = _labelled_params(ctx, **override)
        part = Part(f"7U40-R9-CPN-{coupon_id}",
                    _marked_guard_segment(params, length, coupon_id),
                    "coupons", material, 1, ("step", "stl"))
        parts.append(part)
        records.append(_manifest_record(ctx,
            coupon_id, [part], quantity=1, baseline=dict(baseline),
            changed={"name": field, "baselineValue": baseline_value, "couponValue": variant_value},
            material=material,
            purpose=f"Compare one guard-section parameter: {field}.",
        ))

    # A two-piece 40 mm sample isolates the candidate split-end gap. C1-06 is
    # the candidate gap; C1-07 changes only that gap to zero.
    split_length = float(_coupon_value(ctx, "c1_split_pair_length"))
    candidate_relief = float(ctx.value("guards", "splitEndRelief"))
    first_split_index = len(variants) + 2
    split_variants = [(f"C1-{first_split_index:02d}", candidate_relief, None),
                      (f"C1-{first_split_index + 1:02d}", 0.0, {
                          "name": "splitEndReliefMm",
                          "baselineValue": candidate_relief,
                          "couponValue": 0.0,
                      })]
    for coupon_id, relief, changed in split_variants:
        params = _labelled_params(ctx)
        segment_length = (split_length - relief) / 2
        if segment_length <= 0:
            raise ValueError("split pair relief must leave positive segment lengths")
        pair_parts = [
            Part(f"7U40-R9-CPN-{coupon_id}-A",
                 _marked_guard_segment(params, segment_length, coupon_id),
                 "coupons", material, 1, ("step", "stl")),
            Part(f"7U40-R9-CPN-{coupon_id}-B",
                 _marked_guard_segment(params, segment_length, coupon_id),
                 "coupons", material, 1, ("step", "stl")),
        ]
        parts.extend(pair_parts)
        split_baseline = {**baseline, "segmentLengthMm": split_length,
                          "splitEndReliefMm": candidate_relief}
        records.append(_manifest_record(ctx,
            coupon_id, pair_parts, quantity=2, baseline=split_baseline, changed=changed,
            material=material,
            purpose="Short two-piece pair for checking the centered guard split relief on an aluminum edge.",
            details={"piecesPerCoupon": 2, "pieceLengthMm": segment_length,
                     "centerGapMm": relief,
                     "piecePlacementMm": [0.0, segment_length + relief]},
        ))

    thickness = float(ctx.value("body", "metal_thickness"))
    if not math.isclose(thickness, 1.5, abs_tol=1e-9):
        raise ValueError("C1 aluminum fixture contract requires the candidate 1.5 mm sheet")
    edge_id = "C1-AL-EDGE"
    edge_part = Part(
        "7U40-R9-CPN-C1-AL-EDGE",
        cq.Solid.makeBox(thickness, length, edge_height,
                         cq.Vector(-thickness, 0, -edge_height)),
        "coupons", "A5052 aluminum t1.5 candidate", 1, ("step", "dxf"),
        dxf_outline=((0, 0), (length, 0), (length, edge_height), (0, edge_height)),
    )
    parts.append(edge_part)
    records.append(_manifest_record(ctx,
        edge_id, [edge_part], quantity=1, baseline={"aluminumThicknessMm": thickness,
                                                    "lengthMm": length,
                                                    "edgeHeightMm": edge_height},
        changed=None, material="A5052 aluminum t1.5 candidate",
        purpose="Reusable small plate-edge fixture for the C1 PA12 guard coupons.",
        details={"reusedFor": [record["id"] for record in records]},
    ))
    return parts, records


def _slot_context(ctx: BuildContext, slot_length: float) -> BuildContext:
    params = deepcopy(ctx.params)
    params["slots"]["slot_length"]["value"] = slot_length
    return replace(ctx, params=params)


def _c3_joint_records(ctx: BuildContext):
    joint_id = str(_coupon_value(ctx, "c3_joint_id"))
    sources, _, _, _, specs = body._geometry_records(ctx)
    selected = []
    for spec in specs:
        if spec.part_type not in ("bottom", "front_back"):
            continue
        for hole in spec.pattern_holes:
            if hole.role == "bracket" and hole.joint_id == joint_id:
                selected.append((spec, hole))
    if len(selected) != 2 or {spec.part_type for spec, _ in selected} != {"bottom", "front_back"}:
        raise ValueError(f"C3 joint must resolve to one bottom and one wall hole: {joint_id}")
    return selected, sources


def _c3_coupon_plate(ctx: BuildContext, spec, source_hole, *, coupon_id: str,
                     profile: str, slot_length: float,
                     round_diameter: float) -> tuple[Part, dict]:
    plate_width = float(_coupon_value(ctx, "c3_plate_width"))
    plate_reach = float(_coupon_value(ctx, "c3_plate_reach"))
    thickness = float(ctx.value("body", "metal_thickness"))
    if not math.isclose(thickness, 1.5, abs_tol=1e-9):
        raise ValueError("C3 plate contract requires the candidate 1.5 mm sheet")
    center_u, center_v = source_hole.center_local_mm
    origin_u, origin_v = center_u - plate_width / 2, 0.0
    local_hole = replace(source_hole,
                         center_local_mm=(center_u - origin_u, center_v - origin_v))
    if not (0 < local_hole.center_local_mm[0] < plate_width and
            0 < local_hole.center_local_mm[1] < plate_reach):
        raise ValueError(f"C3 coupon no longer contains the source hole: {source_hole.id}")

    variant_ctx = _slot_context(ctx, slot_length)
    _, candidate_slots = slots.profiles(spec, variant_ctx)
    source_profile = next((row for row in candidate_slots
                           if abs(row[0] - center_u) < 1e-8 and abs(row[1] - center_v) < 1e-8), None)
    if source_profile is None:
        raise ValueError(f"candidate slot profile missing for {source_hole.id}")
    dxf_slots = ()
    dxf_holes = ()
    if profile == "slot":
        dxf_slots = ((local_hole.center_local_mm[0], local_hole.center_local_mm[1],
                      source_profile[2], source_profile[3], source_profile[4]),)
        cutter = slots.cutter(local_hole, thickness, variant_ctx)
    elif profile == "round":
        # The shared slot cutter uses the same cylindrical path as the body's
        # round rail-fix holes.
        round_hole = replace(local_hole, role="rail-fix", diameter_mm=round_diameter)
        cutter = slots.cutter(round_hole, thickness, variant_ctx)
        dxf_holes = ((local_hole.center_local_mm[0], local_hole.center_local_mm[1],
                      round_diameter / 2),)
    else:
        raise ValueError(f"unsupported C3 profile: {profile}")

    solid = cq.Solid.makeBox(plate_width, plate_reach, thickness, cq.Vector(0, 0, 0))
    solid = solid.cut(cutter).clean()
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError(f"invalid C3 plate coupon: {coupon_id}/{spec.part_type}")
    face = "BOTTOM" if spec.part_type == "bottom" else "WALL"
    part = Part(
        f"7U40-R9-CPN-{coupon_id}-{face}", solid, "coupons",
        "A5052 aluminum t1.5 candidate", 1, ("step", "dxf"),
        dxf_outline=((0, 0), (plate_width, 0), (plate_width, plate_reach), (0, plate_reach)),
        dxf_holes=dxf_holes, dxf_slots=dxf_slots,
    )
    detail = {
        "plateFace": face,
        "sourceHoleId": source_hole.id,
        "sourceJointId": source_hole.joint_id,
        "sourceBracketId": source_hole.bracket_id,
        "sourceEdgeOffsetMm": round(center_v, 6),
        "couponHoleCenterMm": [round(v, 6) for v in local_hole.center_local_mm],
        "slotAngleDeg": source_profile[4] if profile == "slot" else None,
        "holeDiameterMm": round_diameter if profile == "round" else source_hole.diameter_mm,
    }
    return part, detail


def _build_c3(ctx: BuildContext) -> tuple[list[Part], list[dict], dict]:
    all_parts: list[Part] = []
    records: list[dict] = []
    selected, sources = _c3_joint_records(ctx)
    slot_width = float(ctx.value("slots", "slot_width"))
    baseline_length = float(ctx.value("slots", "slot_length"))
    round_diameter = float(_coupon_value(ctx, "c3_round_reference_diameter"))
    thickness = float(ctx.value("body", "metal_thickness"))
    joint_id = str(_coupon_value(ctx, "c3_joint_id"))
    configurations = [("C3-01", "slot", baseline_length, None)]
    for index, length in enumerate(_coupon_value(ctx, "c3_slot_length_variants"), start=2):
        configurations.append((f"C3-{index:02d}", "slot", float(length), {
            "name": "slotLengthMm", "baselineValue": baseline_length,
            "couponValue": float(length),
        }))
    if bool(_coupon_value(ctx, "c3_include_round_reference")):
        reference_id = f"C3-{len(configurations) + 1:02d}"
        configurations.append((reference_id, "round", round_diameter, {
            "name": "profile", "baselineValue": "slot",
            "couponValue": "round phi 5.5 mm",
        }))

    for coupon_id, profile, slot_length, changed in configurations:
        coupon_parts = []
        details = []
        for spec, hole in selected:
            part, detail = _c3_coupon_plate(
                ctx, spec, hole, coupon_id=coupon_id, profile=profile,
                slot_length=slot_length if profile == "slot" else baseline_length,
                round_diameter=round_diameter,
            )
            coupon_parts.append(part)
            details.append(detail)
        all_parts.extend(coupon_parts)
        baseline = {
            "plateThicknessMm": thickness,
            "slotWidthMm": slot_width,
            "slotLengthMm": baseline_length,
            "jointId": joint_id,
        }
        records.append(_manifest_record(ctx,
            coupon_id, coupon_parts, quantity=1, baseline=baseline, changed=changed,
            material="A5052 aluminum t1.5 candidate",
            purpose="Two-face edge coupons for trialing a real L bracket, fasteners, washer coverage, adjustment and clamping.",
            results={"physicalFit": None, "bracketFit": None,
                     "fastenerFit": None, "washerCoverage": None, "notes": None},
            details={"pairedPlateCount": 2, "profile": profile,
                     "trialSlotLengthMm": slot_length if profile == "slot" else None,
                     "trialHoleDiameterMm": round_diameter if profile == "round" else None,
                     "sourceJointId": joint_id, "plates": details,
                     "physicalScrewAndWasherSelection": "provisional"},
        ))
    return all_parts, records, sources


def build(ctx: BuildContext) -> list[Part]:
    """Build C1 and C3; C2 can add a separate builder and parameter prefix."""
    c1_parts, c1_records = _build_c1(ctx)
    c3_parts, c3_records, sources = _build_c3(ctx)
    parts = [*c1_parts, *c3_parts]
    records = [*c1_records, *c3_records]
    ids = [part.id for part in parts]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate coupon part ID")
    out = ctx.out / "coupons"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "zudo-case-r9-coupons-v1",
        "revision": ctx.revision,
        "model": ctx.model,
        "units": "mm",
        "status": "unapproved_prototype",
        "manufacturingApproval": False,
        "inputs": _input_records(ctx, sources),
        "coupons": records,
    }
    (out / "coupon-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return parts


def finalize(ctx: BuildContext) -> dict:
    """Hash exported coupon files after the generic Part exporter finishes."""
    path = ctx.out / "coupons" / "coupon-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for record in manifest["coupons"]:
        file_hashes = []
        for relative in record["files"]:
            target = ctx.root / relative
            file_hashes.append({"path": relative, "sha256": sha256_file(target),
                                "bytes": target.stat().st_size})
        record["fileHashes"] = file_hashes
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")
    return {"path": path.relative_to(ctx.root).as_posix(), "sha256": sha256_file(path),
            "bytes": path.stat().st_size}
