"""C1 guard-fit, C2 lid-stack, and C3 bracket-slot coupons for R9 7U40."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile

import cadquery as cq

from . import body, guards, lid, slots
from .common import export_dxf, export_step, export_stl, inspect_binary_stl, sha256_file
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
             for name in ("body", "guards", "slots", "lid", "coupons")]
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


def _c2_bounds(shape: cq.Shape) -> dict:
    bounds = shape.BoundingBox()
    return {
        "minMm": [round(v, 6) for v in (bounds.xmin, bounds.ymin, bounds.zmin)],
        "maxMm": [round(v, 6) for v in (bounds.xmax, bounds.ymax, bounds.zmax)],
        "dimensionsMm": [round(v, 6) for v in (bounds.xlen, bounds.ylen, bounds.zlen)],
    }


def _c2_clip(shape: cq.Shape, box: cq.Shape, name: str) -> cq.Shape:
    clipped = shape.intersect(box).clean()
    if not clipped.isValid() or not clipped.Solids() or clipped.Volume() <= 1e-7:
        raise ValueError(f"C2 local box did not produce a valid solid: {name}")
    return clipped


def _c2_local_feature(center_x: float, center_y: float, half_x: float, half_y: float,
                      clip_bounds: tuple[float, float, float, float],
                      name: str) -> tuple[float, float] | None:
    """Return a fully retained local DXF feature; reject a crop through one."""
    feature = (center_x-half_x, center_x+half_x, center_y-half_y, center_y+half_y)
    clip = clip_bounds
    if (feature[1] < clip[0]-1e-7 or feature[0] > clip[1]+1e-7 or
            feature[3] < clip[2]-1e-7 or feature[2] > clip[3]+1e-7):
        return None
    if (feature[0] < clip[0]-1e-7 or feature[1] > clip[1]+1e-7 or
            feature[2] < clip[2]-1e-7 or feature[3] > clip[3]+1e-7):
        raise ValueError(f"C2 clip intersects only part of a DXF feature: {name}")
    return center_x-clip[0], center_y-clip[2]


def _c2_body_wall_dxf(source: Part, clipped: cq.Shape) -> tuple[tuple, tuple, tuple]:
    """Map the vertical front wall's flat X/Z profile to local DXF XY."""
    source_box = source.solid.BoundingBox()
    clip_box = clipped.BoundingBox()
    outline = ((0.0, 0.0), (clip_box.xlen, 0.0),
               (clip_box.xlen, clip_box.zlen), (0.0, clip_box.zlen))
    holes = []
    for index, (x, z, radius) in enumerate(source.dxf_holes):
        assembly_x, assembly_z = source_box.xmin + x, source_box.zmin + z
        center = _c2_local_feature(assembly_x, assembly_z, radius, radius,
                                   (clip_box.xmin, clip_box.xmax, clip_box.zmin, clip_box.zmax),
                                   f"front-wall hole {index}")
        if center:
            holes.append((*center, radius))
    dxf_slots = []
    for index, (x, z, length, width, angle) in enumerate(source.dxf_slots):
        assembly_x, assembly_z = source_box.xmin + x, source_box.zmin + z
        radians = math.radians(angle)
        half_x = (length*abs(math.cos(radians)) + width*abs(math.sin(radians))) / 2
        half_z = (length*abs(math.sin(radians)) + width*abs(math.cos(radians))) / 2
        center = _c2_local_feature(assembly_x, assembly_z, half_x, half_z,
                                   (clip_box.xmin, clip_box.xmax, clip_box.zmin, clip_box.zmax),
                                   f"front-wall slot {index}")
        if center:
            dxf_slots.append((*center, length, width, angle))
    return outline, tuple(holes), tuple(dxf_slots)


def _c2_lid_plate_dxf(source: Part, clipped: cq.Shape) -> tuple[tuple, tuple, tuple]:
    """Map the horizontal plate coupon to DXF XY and retain any full holes."""
    source_box = source.solid.BoundingBox()
    clip_box = clipped.BoundingBox()
    outline = ((0.0, 0.0), (clip_box.xlen, 0.0),
               (clip_box.xlen, clip_box.ylen), (0.0, clip_box.ylen))
    holes = []
    for index, (x, y, radius) in enumerate(source.dxf_holes):
        assembly_x, assembly_y = source_box.xmin + x, source_box.ymin + y
        center = _c2_local_feature(assembly_x, assembly_y, radius, radius,
                                   (clip_box.xmin, clip_box.xmax, clip_box.ymin, clip_box.ymax),
                                   f"lid-plate hole {index}")
        if center:
            holes.append((*center, radius))
    return outline, tuple(holes), ()


def _c2_export(ctx: BuildContext, coupon_id: str, part: Part) -> list[str]:
    destination = ctx.out / "coupons" / "c2" / coupon_id.lower()
    destination.mkdir(parents=True, exist_ok=True)
    stem = f"{part.id.lower()}-qty{part.qty}-mm"
    paths = []
    kinds = ("step", "stl", *(('dxf',) if part.dxf_outline is not None else ()))
    for kind in kinds:
        target = destination / f"{stem}.{kind}"
        if kind == "step":
            export_step(part.solid, target)
            target.write_bytes(b"\n".join(
                line.rstrip(b" \t") for line in target.read_bytes().split(b"\n")
            ))
        elif kind == "stl":
            export_stl(part.solid, target)
            inspect_binary_stl(target, part.solid)
        else:
            export_dxf(target, part.dxf_outline, part.dxf_holes, part.dxf_slots)
        if target.stat().st_size >= 25 * 1024 * 1024:
            raise ValueError(f"C2 output exceeds the 25 MiB file limit: {target}")
        paths.append(target.relative_to(ctx.root).as_posix())
    return paths


def _c2_intersection_volume(a: cq.Shape, b: cq.Shape) -> float:
    a_box, b_box = a.BoundingBox(), b.BoundingBox()
    if any(xmax < ymin-1e-7 or ymax < xmin-1e-7 for xmin, xmax, ymin, ymax in (
            (a_box.xmin, a_box.xmax, b_box.xmin, b_box.xmax),
            (a_box.ymin, a_box.ymax, b_box.ymin, b_box.ymax),
            (a_box.zmin, a_box.zmax, b_box.zmin, b_box.zmax))):
        return 0.0
    return a.intersect(b).Volume()


def _c2_lift_off_check(lid_parts: list[cq.Shape], stationary_parts: list[tuple[str, cq.Shape]]) -> dict:
    """Sample a vertical lift, then stop when Z bounds prove later separation."""
    lid_min_z = min(part.BoundingBox().zmin for part in lid_parts)
    fixed_max_z = max(shape.BoundingBox().zmax for _, shape in stationary_parts)
    last_rise = max(1, math.ceil(fixed_max_z-lid_min_z) + 1)
    rise_values = list(range(last_rise+1))
    collision = None
    for rise in rise_values:
        for part_index, part in enumerate(lid_parts):
            moved = part.translate((0, 0, rise))
            for fixed_id, fixed in stationary_parts:
                volume = _c2_intersection_volume(moved, fixed)
                if volume > 1e-6:
                    collision = {"riseMm": rise, "movingPartIndex": part_index,
                                 "fixedPartId": fixed_id, "intersectionVolumeMm3": round(volume, 6)}
                    break
            if collision:
                break
        if collision:
            break
    if collision:
        raise ValueError(f"C2 vertical lift path intersects candidate geometry: {collision}")
    return {
        "motion": "straight vertical lift in +Z",
        "sampleStepMm": 1,
        "sampledRiseMm": [0, last_rise],
        "sampleCount": len(rise_values),
        "candidateBrepIntersectionFound": False,
        "separatedByZBoundsAfterLastSample": True,
        "physicalLiftOffResult": None,
    }


def _build_c2(ctx: BuildContext) -> tuple[list[Part], list[dict]]:
    """Clip candidate body, guard and lift-off-lid solids into one front section."""
    box_min = [float(value) for value in _coupon_value(ctx, "c2_coupon_box_min")]
    box_max = [float(value) for value in _coupon_value(ctx, "c2_coupon_box_max")]
    if any(box_max[index] <= box_min[index] for index in range(3)):
        raise ValueError("C2 local coupon box must have positive dimensions")
    clip_box = cq.Solid.makeBox(*(box_max[index]-box_min[index] for index in range(3)),
                                cq.Vector(*box_min))
    baseline_clearance = float(ctx.value("lid", "top_edge_lid_locator_clearance"))
    clearance_variants = [float(value) for value in _coupon_value(ctx, "c2_lid_locator_clearance_variants")]
    if (len(clearance_variants) != 2 or any(value <= 0 for value in clearance_variants) or
            len({round(value, 9) for value in [baseline_clearance, *clearance_variants]}) != 3):
        raise ValueError("C2 requires three distinct positive locator clearances including the lid baseline")

    # Module builders are the source of truth for the solids. Redirect their
    # intermediate exports into a temporary directory so this coupon hook only
    # delivers C2 files and the combined coupon manifest.
    with tempfile.TemporaryDirectory(prefix=".r9-c2-source-", dir=ctx.root) as temporary:
        source_ctx = replace(ctx, out=Path(temporary) / "out")
        body_parts = {part.id: part for part in body.build(source_ctx)}
        guard_parts = {part.id: part for part in guards.build(source_ctx)}
        wall_source = body_parts["7U40-R9-AL-FRONT-BACK"]
        rail_source = body_parts["7U40-R9-HW-RAIL-UNIT-ENVELOPE"]
        guard_source = guard_parts["7U40-R9-PA12-GUARD-T1P2-TOP-A"]
        # TOP-A is the candidate front-left quadrant; its mirrored partner is
        # the same emitted geometry placed at the front-right coupon station.
        guard_solid = guard_source.solid.mirror("YZ")
        wall_solid = _c2_clip(wall_source.solid, clip_box, wall_source.id)
        rail_solid = _c2_clip(rail_source.solid, clip_box, rail_source.id)
        guard_cropped = _c2_clip(guard_solid, clip_box, guard_source.id)

        wall_dxf = _c2_body_wall_dxf(wall_source, wall_solid)
        stationary = [(wall_source.id, wall_solid), (guard_source.id, guard_cropped),
                      (rail_source.id, rail_solid)]
        wall_box, rail_box = wall_source.solid.BoundingBox(), rail_source.solid.BoundingBox()
        front_gap = rail_box.ymin-wall_box.ymax
        if front_gap <= 0:
            raise ValueError("C2 candidate front wall and rail envelope overlap")

        parts: list[Part] = []
        records: list[dict] = []
        clearances = [("C2-01", baseline_clearance, None)]
        clearances.extend((f"C2-{index:02d}", value, {
            "name": "top_edge_lid_locator_clearance",
            "baselineValue": baseline_clearance,
            "couponValue": value,
        }) for index, value in enumerate(clearance_variants, start=2))

        for coupon_id, clearance, changed in clearances:
            variant_params = deepcopy(ctx.params)
            variant_params["lid"]["top_edge_lid_locator_clearance"]["value"] = clearance
            lid_ctx = replace(source_ctx, params=variant_params)
            lid_parts = {part.id: part for part in lid.build(lid_ctx)}
            frame_source = lid_parts["7U40-R9-PA12-LID-FRAME-FR"]
            plate_source = lid_parts["7U40-R9-LID-PLATE"]
            frame_solid = _c2_clip(frame_source.solid, clip_box, frame_source.id)
            plate_solid = _c2_clip(plate_source.solid, clip_box, plate_source.id)
            plate_dxf = _c2_lid_plate_dxf(plate_source, plate_solid)

            components = [
                ("BODY-WALL", wall_source.id, wall_solid,
                 "A5052 aluminum t1.5 candidate", wall_dxf),
                ("RAIL-ENVELOPE", rail_source.id, rail_solid,
                 rail_source.material, None),
                ("GUARD", guard_source.id, guard_cropped,
                 guard_source.material, None),
                ("LID-FRAME", frame_source.id, frame_solid,
                 frame_source.material, None),
                ("LID-PLATE", plate_source.id, plate_solid,
                 plate_source.material, plate_dxf),
            ]
            coupon_parts = []
            component_details = []
            for role, source_id, solid, material, dxf in components:
                part_id = f"7U40-R9-CPN-{coupon_id}-{role}"
                part = Part(part_id, solid, "coupons", material, 1, (),
                            dxf_outline=dxf[0] if dxf else None,
                            dxf_holes=dxf[1] if dxf else (),
                            dxf_slots=dxf[2] if dxf else ())
                files = _c2_export(ctx, coupon_id, part)
                parts.append(part)
                coupon_parts.append(part)
                detail = {"partId": part_id, "sourcePartId": source_id,
                          "material": material, "boundsAssemblyMm": _c2_bounds(solid),
                          "files": files}
                if role == "GUARD":
                    detail["sourcePlacement"] = "mirror of candidate TOP-A across assembly YZ plane"
                if role == "RAIL-ENVELOPE":
                    detail["sourceRepresentation"] = "source rail mesh bounding box; rail profile is not represented"
                if role in ("BODY-WALL", "LID-PLATE"):
                    detail["dxfTransform"] = {
                        "originAssemblyMm": [round(solid.BoundingBox().xmin, 6),
                                             round(solid.BoundingBox().ymin, 6),
                                             round(solid.BoundingBox().zmin, 6)],
                        "basisU": [1, 0, 0],
                        "basisV": [0, 0, 1] if role == "BODY-WALL" else [0, 1, 0],
                        "thicknessAxis": [0, 1, 0] if role == "BODY-WALL" else [0, 0, 1],
                    }
                component_details.append(detail)

            lift_off = _c2_lift_off_check(
                [frame_solid, plate_solid], stationary,
            )
            baseline = {
                "bodyMetalThicknessMm": float(ctx.value("body", "metal_thickness")),
                "guardThicknessMm": float(ctx.value("guards", "main_thickness")),
                "guardFitClearancePerSideMm": float(ctx.value("guards", "fitClearancePerSide")),
                "guardAdhesiveLayerMm": float(ctx.value("guards", "adhesiveLayer")),
                "lidLocatorClearanceMm": baseline_clearance,
                "lidFrameSeatZMm": float(ctx.value("lid", "frame_seat_z")),
                "lidLocatorBottomZMm": float(ctx.value("lid", "locator_bottom_z")),
                "lidPlateThicknessMm": float(ctx.value("lid", "plate_thickness")),
                "frontWallToRailEnvelopeGapMm": round(front_gap, 6),
                "couponBoxAssemblyMm": {"min": box_min, "max": box_max},
            }
            file_paths = [path for component in component_details for path in component["files"]]
            record = _manifest_record(
                ctx, coupon_id, coupon_parts, quantity=1, baseline=baseline,
                changed=changed,
                material="PA12-HP and A5052 t1.5 candidate section; rail envelope is reference-only",
                purpose="Local front body/guard/lid section for locator clearance and plate support trials.",
                results={"physicalFit": None, "locatorFit": None,
                         "retention": None, "notes": None},
                details={
                    "coordinateSystem": "R9 7U40 assembly coordinates; coupon pieces are not recentered",
                    "cutMethod": "intersection of candidate module solids with one local axis-aligned box",
                    "couponBoxAssemblyMm": {"min": box_min, "max": box_max},
                    "locatorClearanceMm": clearance,
                    "frontWallInnerFaceYmm": round(wall_box.ymax, 6),
                    "railEnvelopeFrontFaceYmm": round(rail_box.ymin, 6),
                    "frontWallToRailEnvelopeGapMm": round(front_gap, 6),
                    "railGapNote": "Candidate gap uses the R9 source-rail bounding envelope; the non-manifold rail STL profile is not part of this BREP coupon.",
                    "verticalRemovalPathCheck": lift_off,
                    "components": component_details,
                },
            )
            record["files"] = file_paths
            records.append(record)
    return parts, records


def build(ctx: BuildContext) -> list[Part]:
    """Build the C1, C2 and C3 candidate coupon families."""
    c1_parts, c1_records = _build_c1(ctx)
    c2_parts, c2_records = _build_c2(ctx)
    c3_parts, c3_records, sources = _build_c3(ctx)
    parts = [*c1_parts, *c2_parts, *c3_parts]
    records = [*c1_records, *c2_records, *c3_records]
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
