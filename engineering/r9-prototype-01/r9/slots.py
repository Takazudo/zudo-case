"""Provisional bracket slots in the R9 7U40 plate patterns."""
from __future__ import annotations

import json
import math

import cadquery as cq

from .body import HoleRecord, PlateSpec, _geometry_records, _pcb_parts, _rail_envelopes
from .types import BuildContext, Part


def value(ctx: BuildContext, key: str) -> float:
    return float(ctx.value("slots", key))


def angle(hole: HoleRecord) -> int:
    """Local flat-pattern angle, normal to the joint's bend line."""
    if hole.role != "bracket":
        raise ValueError(hole.id)
    bottom_joint = "-BOTTOM-" in hole.joint_id
    if hole.plate_id.endswith("-BOTTOM"):
        return 90 if "-FRONT-" in hole.joint_id or "-BACK-" in hole.joint_id else 0
    if hole.plate_id.endswith("-FRONT-BACK") or hole.plate_id.endswith("-LEFT-RIGHT"):
        return 90 if bottom_joint else 0
    raise ValueError(hole.plate_id)


def profiles(spec: PlateSpec, ctx: BuildContext):
    length, width = value(ctx, "slot_length"), value(ctx, "slot_width")
    rounds = tuple((h.center_local_mm[0], h.center_local_mm[1], h.diameter_mm / 2)
                   for h in spec.pattern_holes if h.role == "rail-fix")
    slots = tuple((h.center_local_mm[0], h.center_local_mm[1], length, width, angle(h))
                  for h in spec.pattern_holes if h.role == "bracket")
    return rounds, slots


def cutter(hole: HoleRecord, thickness_mm: float, ctx: BuildContext) -> cq.Shape:
    x, y = hole.center_local_mm
    if hole.role == "rail-fix":
        return cq.Solid.makeCylinder(hole.diameter_mm / 2, thickness_mm + 2,
                                     cq.Vector(x, y, -1), cq.Vector(0, 0, 1))
    length, width = value(ctx, "slot_length"), value(ctx, "slot_width")
    if length <= width or width <= 0:
        raise ValueError("slot length must exceed positive width")
    return (cq.Workplane("XY", origin=(0, 0, -1)).center(x, y)
            .slot2D(length, width, angle(hole)).extrude(thickness_mm + 2).val())


def segment(hole: HoleRecord, length: float, width: float):
    x, y = hole.center_local_mm
    half = (length - width) / 2 if hole.role == "bracket" else 0
    if hole.role == "bracket" and angle(hole) == 90:
        return (x, y - half), (x, y + half), width / 2
    return (x - half, y), (x + half, y), width / 2


def segment_distance(a, b) -> float:
    """Minimum distance between horizontal/vertical centerline segments."""
    a0, a1, _ = a
    b0, b1, _ = b
    if a0[0] == a1[0] and b0[1] == b1[1]:
        dx = max(b0[0] - a0[0], a0[0] - b1[0], 0)
        dy = max(a0[1] - b0[1], b0[1] - a1[1], 0)
    elif a0[1] == a1[1] and b0[0] == b1[0]:
        dx = max(a0[0] - b0[0], b0[0] - a1[0], 0)
        dy = max(b0[1] - a0[1], a0[1] - b1[1], 0)
    else:
        dx = max(a0[0] - b1[0], b0[0] - a1[0], 0)
        dy = max(a0[1] - b1[1], b0[1] - a1[1], 0)
    return math.hypot(dx, dy)


def tool_access(hole: HoleRecord, spec: PlateSpec, ctx: BuildContext, obstacles: list[tuple[float, ...]]) -> bool:
    """Exterior cylindrical driver envelope against nominal solid envelopes."""
    radius = value(ctx, "driver_envelope_diameter") / 2
    depth = value(ctx, "driver_envelope_length")
    center = hole.center_assembly_mm
    side = -1 if spec.part_type == "bottom" or hole.plate_instance in ("FRONT", "LEFT") else 1
    axial = 2 if spec.part_type == "bottom" else 1 if spec.part_type == "front_back" else 0
    low, high = [], []
    for index, coordinate in enumerate(center):
        if index == axial:
            low.append(coordinate - depth if side < 0 else coordinate)
            high.append(coordinate if side < 0 else coordinate + depth)
        else:
            low.append(coordinate - radius)
            high.append(coordinate + radius)
    # A bounding-box overlap is conservative for the cylindrical tool. Merely
    # touching the exterior metal at the hole mouth is not an obstruction.
    return not any(all(min(high[i], box[2 * i + 1]) - max(low[i], box[2 * i]) > 1e-7
                       for i in range(3)) for box in obstacles)


def records(ctx: BuildContext) -> tuple[list[dict], dict]:
    sources, design, brackets, _, specs = _geometry_records(ctx)
    _, rail_instances = _rail_envelopes(design, sources)
    _, pcb_records = _pcb_parts(design)
    obstacles = [box for bracket in brackets for box in bracket["boxes"]]
    for item in rail_instances:
        lo, hi = item["bboxMinMm"], item["bboxMaxMm"]
        obstacles.append((lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    for group in pcb_records:
        for item in group["instances"]:
            lo, hi = item["bboxMinMm"], item["bboxMaxMm"]
            obstacles.append((lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    width, length, travel = (value(ctx, k) for k in ("slot_width", "slot_length", "slot_travel"))
    edge_min, ligament_min = value(ctx, "edge_margin_min"), value(ctx, "ligament_min")
    overlap = value(ctx, "bearing_overlap")
    guard_cover = float(ctx.value("guards", "cover"))
    if not math.isclose(travel, (length - width) / 2, abs_tol=1e-9):
        raise ValueError("travel must equal (length-width)/2")
    rows = []
    for spec in specs:
        for hole in spec.holes:
            line = segment(hole, length, width)
            a, b, radius = line
            edge = min(min(a[0], b[0]) - radius, spec.width_mm - max(a[0], b[0]) - radius,
                       min(a[1], b[1]) - radius, spec.height_mm - max(a[1], b[1]) - radius)
            neighbors = [other for other in spec.holes
                         if other.plate_instance == hole.plate_instance and other.id != hole.id]
            ligament = min((segment_distance(line, segment(n, length, width))
                            - radius - segment(n, length, width)[2] for n in neighbors), default=None)
            slotted = hole.role == "bracket"
            bearing_part = "head" if spec.part_type == "bottom" else "outer washer"
            bearing_od = (float(ctx.value("body", "bracket_head_diameter" if bearing_part == "head"
                                          else "nylon_outer_diameter")) if slotted else None)
            required_od = length + 2 * travel + 2 * overlap
            # Upper wall contact band is the adopted 5 mm guard cover. The slot
            # direction is vertical only for lower wall joints.
            top_of_profile = hole.center_assembly_mm[2] + (length / 2 if angle(hole) == 90 else width / 2) if slotted else 0
            guard_ok = (top_of_profile < float(ctx.value("body", "case_height")) - guard_cover
                        if slotted and spec.part_type != "bottom" else True)
            if slotted:
                if spec.part_type == "bottom":
                    axis = [0, 1, 0] if angle(hole) == 90 else [1, 0, 0]
                elif angle(hole) == 90:
                    axis = [0, 0, 1]
                else:
                    axis = [1, 0, 0] if spec.part_type == "front_back" else [0, 1, 0]
            else:
                # A circle has no long axis; record its bore normal instead.
                axis = [-1, 0, 0] if hole.plate_instance == "LEFT" else [1, 0, 0]
            rows.append({
                "id": hole.id, "plate": spec.id, "plate_instance": hole.plate_instance,
                "face": hole.face, "joint": hole.joint_id, "bracket": hole.bracket_id,
                "role": "rail-fix" if not slotted else "datum" if spec.part_type == "bottom" else "adjust",
                "profile": "slot" if slotted else "round",
                "center_uv": list(hole.center_local_mm), "center_xyz": list(hole.center_assembly_mm),
                "axis": axis, "axis_meaning": "slot long axis" if slotted else "round bore normal",
                "angle_local_deg": angle(hole) if slotted else None,
                "width": width if slotted else hole.diameter_mm,
                "length": length if slotted else hole.diameter_mm,
                "travel": travel if slotted else 0,
                "edge_margin": round(edge, 6),
                "ligament_min": round(ligament, 6) if ligament is not None else None,
                "bearing_part": bearing_part if slotted else None,
                "bearing_status": "provisional" if slotted else None,
                "bearing_od": bearing_od,
                "coverage_ok": bearing_od + 1e-9 >= required_od if slotted else None,
                "tool_access_ok": tool_access(hole, spec, ctx, obstacles) if slotted else None,
                "guard_contact_ok": guard_ok if slotted else None,
            })
    failures = {
        "edge": [r["id"] for r in rows if r["edge_margin"] < edge_min],
        "ligament": [r["id"] for r in rows if r["ligament_min"] is not None and r["ligament_min"] < ligament_min],
        "bearingCoverage": [r["id"] for r in rows if r["coverage_ok"] is False],
        "toolAccess": [r["id"] for r in rows if r["tool_access_ok"] is False],
        "guardContact": [r["id"] for r in rows if r["guard_contact_ok"] is False],
    }
    checks = {
        "schema": "zudo-case-r9-slot-checks-v1", "status": "unapproved_prototype",
        "criteria": {"edgeMarginMinMm": edge_min, "ligamentMinMm": ligament_min,
                     "bearingOverlapMm": overlap,
                     "bearingFormula": "OD >= L + 2*abs(e) + 2*overlap",
                     "bearingRequiredOdMm": required_od,
                     "guardContactBandMm": guard_cover,
                     "toolEnvelopeDiameterMm": value(ctx, "driver_envelope_diameter"),
                     "toolEnvelopeLengthMm": value(ctx, "driver_envelope_length")},
        "counts": {"slots": sum(r["profile"] == "slot" for r in rows),
                   "roundRailFix": sum(r["profile"] == "round" for r in rows)},
        "failures": failures,
        "bearingProposal": "Provisional 10 mm outer washer fails; candidate OD >= 11.5 mm, subject to fit and supplier confirmation.",
        "limitations": [
            "No intentional adjustment along bend lines; along-edge position follows CAD hole spacing.",
            "Datums: bottom lower face and wall exterior faces. 仮締め → 外形/直角を整える → 本締め.",
            "An exterior normal driver cylinder was checked against bracket boxes and source PCB/rail bounding envelopes. Driver size and physical access remain provisional.",
            "Rail-fix holes remain round φ5.5: independent rail frame is located by its fixer PCB.",
        ],
    }
    return rows, checks


def build(ctx: BuildContext) -> list[Part]:
    rows, checks = records(ctx)
    out = ctx.out / "aluminum"
    out.mkdir(parents=True, exist_ok=True)
    (out / "hole-table.json").write_text(json.dumps({"schema": "zudo-case-r9-hole-table-v1",
        "revision": ctx.revision, "model": ctx.model, "units": "mm", "status": "unapproved_prototype",
        "holes": rows}, indent=2) + "\n")
    (out / "slot-checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    return []
