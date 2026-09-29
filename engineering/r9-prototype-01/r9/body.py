"""R9 7U40 body geometry ported from the frozen R6 reference.

`plate_specs(ctx)` exposes the stable hole records and local plate patterns.
Later tolerance work can pass a custom `hole_cutter` to `make_plate_solid`;
the normal `build(ctx)` path deliberately keeps all 46 holes round at 5.5 mm.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Callable

import cadquery as cq

from .common import sha256_file
from .types import BuildContext, Part


PLATE_IDS = {
    "bottom": "7U40-R9-AL-BOTTOM",
    "front_back": "7U40-R9-AL-FRONT-BACK",
    "left_right": "7U40-R9-AL-LEFT-RIGHT",
}


@dataclass(frozen=True)
class HoleRecord:
    """Stable through-hole record shared by body and later slot work."""

    id: str
    role: str
    plate_id: str
    plate_instance: str
    face: str
    bracket_id: str | None
    joint_id: str
    axis: int
    center_assembly_mm: tuple[float, float, float]
    center_local_mm: tuple[float, float]
    diameter_mm: float

    @property
    def axis_name(self) -> str:
        return ("X", "Y", "Z")[self.axis]

    def as_json(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "plateId": self.plate_id,
            "plateInstance": self.plate_instance,
            "face": self.face,
            "bracketId": self.bracket_id,
            "jointId": self.joint_id,
            "axis": self.axis_name,
            "centerAssemblyMm": list(self.center_assembly_mm),
            "centerLocalMm": list(self.center_local_mm),
            "diameterMm": self.diameter_mm,
            "profile": "round",
        }


@dataclass(frozen=True)
class PlateInstance:
    id: str
    local_to_assembly: tuple[tuple[float, float, float, float], ...]

    def as_json(self) -> dict:
        return {"id": self.id, "localToAssembly": [list(row) for row in self.local_to_assembly]}


@dataclass(frozen=True)
class PlateSpec:
    """Flat pattern and stable hole records for one repeated plate type.

    `holes` contains every physical instance. `pattern_holes` contains the
    primary plate instance in local DXF coordinates and is the pattern used by
    the prototype export. All instances of a repeated plate type are checked
    to have the same local pattern.
    """

    id: str
    part_type: str
    quantity: int
    width_mm: float
    height_mm: float
    thickness_mm: float
    instances: tuple[PlateInstance, ...]
    primary_instance_id: str
    holes: tuple[HoleRecord, ...]
    pattern_holes: tuple[HoleRecord, ...]

    @property
    def outline_local_mm(self) -> tuple[tuple[float, float], ...]:
        return ((0.0, 0.0), (self.width_mm, 0.0),
                (self.width_mm, self.height_mm), (0.0, self.height_mm))

    @property
    def primary_matrix(self) -> tuple[tuple[float, float, float, float], ...]:
        for instance in self.instances:
            if instance.id == self.primary_instance_id:
                return instance.local_to_assembly
        raise ValueError(f"primary plate instance missing: {self.id}/{self.primary_instance_id}")


HoleCutter = Callable[[HoleRecord, float], cq.Shape]


def _clean_number(value: float) -> float:
    value = float(value)
    return 0.0 if abs(value) < 1e-14 else value


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_root(ctx: BuildContext) -> Path:
    return ctx.root.resolve().parents[1]


def _load_sources(ctx: BuildContext) -> dict:
    repo = _repo_root(ctx)
    r6 = repo / "engineering" / "r6-body"
    paths = {
        "r6_build_geometry": r6 / "build_geometry.py",
        "design_parameters": r6 / "design-parameters.json",
        "panel_geometry": r6 / "source-data" / "panels" / "panel-geometry.json",
        "rail_dimensions": r6 / "source-data" / "rail40" / "rail_dimensions.json",
        "rail_stl": r6 / "source-data" / "rail40" / "nuts-v2-40hp-single.stl",
        "r6_hole_layout": r6 / "engineering" / "7u40" / "aluminum" / "hole-layout.json",
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    rail_dimensions = _read_json(paths["rail_dimensions"])
    rail_sha = sha256_file(paths["rail_stl"])
    recorded_rail_sha = rail_dimensions["source"]["sha256"]
    if rail_sha != recorded_rail_sha:
        raise ValueError("40HP rail STL SHA-256 differs from rail_dimensions.json")
    return {
        "repo_root": repo,
        "paths": paths,
        "design_parameters": _read_json(paths["design_parameters"]),
        "panel_geometry_raw": _read_json(paths["panel_geometry"]),
        "rail_dimensions": rail_dimensions,
        "r6_hole_layout": _read_json(paths["r6_hole_layout"]),
        "hashes": {key: sha256_file(path) for key, path in paths.items()},
    }


def _bbox_2d(points: list[list[float]]) -> dict:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    lo = [min(xs), min(ys)]
    hi = [max(xs), max(ys)]
    return {
        "min": lo,
        "max": hi,
        "dimensions": [hi[0] - lo[0], hi[1] - lo[1]],
        "center": [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2],
    }


def _normalized_panels(source: dict) -> dict:
    panels = json.loads(json.dumps(source["panels"]))
    for kind, panel in panels.items():
        swap = kind == "fixer7u"
        for contour in [panel["outer"], *panel["cutouts"]]:
            if swap:
                contour["points"] = [[v, u] for u, v in contour["points"]]
            contour["bbox"] = _bbox_2d(contour["points"])
    panels["fixer"] = panels["fixer7u"]
    return panels


def _parameter(ctx: BuildContext, key: str) -> float | list[float]:
    return ctx.value("body", key)


def _design(ctx: BuildContext, sources: dict) -> dict:
    panels = _normalized_panels(sources["panel_geometry_raw"])
    fixer = panels["fixer"]
    fixer_center_u = float(fixer["outer"]["bbox"]["center"][0])
    rail_meta = sources["rail_dimensions"]
    rail_bbox_min = rail_meta["exact_mesh_measurements"]["bbox_min"]
    rail_bbox_max = rail_meta["exact_mesh_measurements"]["bbox_max"]
    rail_extent = rail_meta["exact_mesh_measurements"]["extent_xyz"]

    rail_length = float(_parameter(ctx, "rail_length"))
    source_rail_length = float(rail_meta["exact_mesh_measurements"]["long_axis_length_mm"])
    if abs(rail_length - source_rail_length) > 1e-9:
        raise ValueError(f"rail length must preserve the source 40HP mesh: {source_rail_length} mm")

    tf = float(_parameter(ctx, "fixer_thickness"))
    tp = float(_parameter(ctx, "padder_thickness"))
    spacer = float(_parameter(ctx, "inner_spacer"))
    metal = float(_parameter(ctx, "metal_thickness"))
    frame_width = rail_length + 2 * (tf + tp)
    inner_width = frame_width + 2 * spacer
    case_width = inner_width + 2 * metal
    case_height = float(_parameter(ctx, "case_height"))
    top = case_height - metal

    padder_u_values = [float(v) for v in _parameter(ctx, "padder_u")]
    padder_v_values = [float(v) for v in _parameter(ctx, "padder_v")]
    extents_y = []
    pcb_placements = [
        (fixer, 0.0),
        (panels["padder3u"], padder_u_values[0]),
        (panels["padder3u"], padder_u_values[1]),
        (panels["padder1u"], padder_u_values[2]),
    ]
    for panel, offset in pcb_placements:
        bb = panel["outer"]["bbox"]
        lo = float(bb["min"][0]) + offset - fixer_center_u
        hi = float(bb["max"][0]) + offset - fixer_center_u
        extents_y.extend((lo, hi))

    rail_u_values = [float(v) for v in _parameter(ctx, "rail_hole_u")]
    rail_cutouts = []
    for contour in fixer["cutouts"]:
        bb = contour["bbox"]
        if max(bb["dimensions"]) < 6:
            rail_cutouts.append((float(bb["center"][0]), float(bb["center"][1])))
    rail_axes = []
    for target_u in rail_u_values:
        u, v = min(rail_cutouts, key=lambda item: abs(item[0] - target_u))
        if abs(u - target_u) > 1e-6:
            raise ValueError(f"R6 rail registration hole not found at u={target_u}")
        rail_axes.append((u, v))
    rail_cy = float(_parameter(ctx, "rail_lip_cy"))
    source_y_min = float(rail_bbox_min[1])
    source_y_max = float(rail_bbox_max[1])
    for index, (u, _v) in enumerate(rail_axes):
        sign = -1 if index % 2 == 0 else 1
        world_y_min = min(sign * (source_y_min - rail_cy), sign * (source_y_max - rail_cy)) + u - fixer_center_u
        world_y_max = max(sign * (source_y_min - rail_cy), sign * (source_y_max - rail_cy)) + u - fixer_center_u
        extents_y.extend((world_y_min, world_y_max))

    half_depth = max(abs(extent) for extent in extents_y)
    clearance = float(_parameter(ctx, "front_back_clearance"))
    case_depth = float(math.ceil(2 * (half_depth + clearance + metal)))
    xm = case_width / 2 - metal
    ym = case_depth / 2 - metal
    board_mount_u = [float(v) for v in _parameter(ctx, "mount_u")]
    board_mount_v = float(_parameter(ctx, "mount_v"))
    mount_axes = [(u - fixer_center_u, top - board_mount_v) for u in board_mount_u]
    return {
        "panels": panels,
        "padder_u": padder_u_values,
        "padder_v": padder_v_values,
        "fixer_center_u": fixer_center_u,
        "rail_bbox_min": [float(v) for v in rail_bbox_min],
        "rail_bbox_max": [float(v) for v in rail_bbox_max],
        "rail_extent": [float(v) for v in rail_extent],
        "rail_axes_uv": rail_axes,
        "mount_axes_yz": mount_axes,
        "rail_length": rail_length,
        "fixer_thickness": tf,
        "padder_thickness": tp,
        "spacer": spacer,
        "outer_washer": float(_parameter(ctx, "outer_washer")),
        "metal": metal,
        "frame_width": frame_width,
        "inner_width": inner_width,
        "case_width": case_width,
        "case_depth": case_depth,
        "case_height": case_height,
        "top": top,
        "xm": xm,
        "ym": ym,
        "bracket_outer": [float(v) for v in _parameter(ctx, "bracket_outer")],
        "bracket_thickness": float(_parameter(ctx, "bracket_thickness")),
        "bracket_allowance": float(_parameter(ctx, "bracket_allowance_thickness")),
        "bracket_inset": float(_parameter(ctx, "bracket_hole_inset")),
        "hole_diameter": float(_parameter(ctx, "metal_clearance_hole_diameter")),
        "bottom_xs": [-(xm - float(_parameter(ctx, "bracket_bottom_x_offset"))),
                      xm - float(_parameter(ctx, "bracket_bottom_x_offset"))],
        "bottom_ys": [-case_depth / 2 + float(_parameter(ctx, "bracket_bottom_y_offset")),
                      0.0,
                      case_depth / 2 - float(_parameter(ctx, "bracket_bottom_y_offset"))],
        "vertical_bracket_heights": [float(v) for v in _parameter(ctx, "vertical_bracket_center_heights")],
        "rail_center_x": float(_parameter(ctx, "rail_lip_cx")),
        "rail_center_y": rail_cy,
        "mount_head_height": float(_parameter(ctx, "mount_head_height")),
        "mount_head_diameter": float(_parameter(ctx, "mount_head_diameter")),
        "mount_bolt_length": float(_parameter(ctx, "mount_bolt_length")),
        "rail_end_head_diameter": float(_parameter(ctx, "rail_end_head_diameter")),
        "rail_end_bolt_length": float(_parameter(ctx, "rail_end_bolt_length")),
        "bracket_head_diameter": float(_parameter(ctx, "bracket_head_diameter")),
        "nylon_outer_diameter": float(_parameter(ctx, "nylon_outer_diameter")),
        "nylon_inner_diameter": float(_parameter(ctx, "nylon_inner_diameter")),
        "nut_height": float(_parameter(ctx, "nut_height")),
        "nut_across_flats": float(_parameter(ctx, "nut_across_flats")),
        "foot_diameter": float(_parameter(ctx, "foot_diameter")),
        "foot_height": float(_parameter(ctx, "foot_height")),
        "foot_inset": float(_parameter(ctx, "foot_inset")),
    }


def _local_center(design: dict, plate_type: str, center: tuple[float, float, float]) -> tuple[float, float]:
    x, y, z = center
    if plate_type == "bottom":
        uv = (x + design["case_width"] / 2, y + design["case_depth"] / 2)
    elif plate_type == "front_back":
        uv = (x + design["xm"], z - design["metal"])
    elif plate_type == "left_right":
        uv = (y + design["case_depth"] / 2, z - design["metal"])
    else:
        raise ValueError(f"unknown plate type: {plate_type}")
    return tuple(_clean_number(v) for v in uv)


def _make_hole(design: dict, plate_type: str, instance: str, role: str, axis: int,
               center: tuple[float, float, float], semantic: str,
               bracket_id: str | None, joint_id: str, face: str) -> HoleRecord:
    plate_id = PLATE_IDS[plate_type]
    hole_id = f"{plate_id}-HOLE-{role.upper()}-{instance}-{semantic}"
    return HoleRecord(
        id=hole_id,
        role=role,
        plate_id=plate_id,
        plate_instance=instance,
        face=face,
        bracket_id=bracket_id,
        joint_id=joint_id,
        axis=axis,
        center_assembly_mm=tuple(_clean_number(v) for v in center),
        center_local_mm=_local_center(design, plate_type, center),
        diameter_mm=design["hole_diameter"],
    )


def _range(a: float, b: float) -> tuple[float, float]:
    return (min(a, b), max(a, b))


def _bracket_definitions(design: dict) -> tuple[list[dict], list[HoleRecord]]:
    brackets: list[dict] = []
    holes: list[HoleRecord] = []
    t = design["metal"]
    bt = design["bracket_thickness"]
    leg_x, leg_y, bracket_width = design["bracket_outer"]
    inset = design["bracket_inset"]
    xm, ym = design["xm"], design["ym"]
    case_width, case_depth = design["case_width"], design["case_depth"]

    def add_bracket(slug: str, boxes: list[tuple[float, ...]],
                    hole_specs: list[tuple[str, str, int, tuple[float, float, float], str]]) -> None:
        bracket_id = f"7U40-R9-HW-BRACKET-{slug}"
        joint_id = f"7U40-R9-JNT-{slug}"
        records = [
            _make_hole(design, plate_type, instance, "bracket", axis, center,
                       slug, bracket_id, joint_id, face)
            for plate_type, instance, axis, center, face in hole_specs
        ]
        brackets.append({"id": bracket_id, "jointId": joint_id, "boxes": boxes, "holes": records})
        holes.extend(records)

    # The first 4 brackets join the bottom to the front and rear plates.
    for sy in (-1, 1):
        wall = "FRONT" if sy < 0 else "BACK"
        for x in design["bottom_xs"]:
            x_side = "XN" if x < 0 else "XP"
            slug = f"BOTTOM-{wall}-X{x_side}"
            y0, y1 = _range(sy * ym, sy * (ym - leg_y))
            y2, y3 = _range(sy * ym, sy * (ym - bt))
            boxes = [
                (x - bracket_width / 2, x + bracket_width / 2, y0, y1, t, t + bt),
                (x - bracket_width / 2, x + bracket_width / 2, y2, y3, t, t + leg_y),
            ]
            add_bracket(slug, boxes, [
                ("bottom", "BOTTOM", 2, (x, sy * (ym - inset), 0.0), "outside"),
                ("front_back", wall, 1, (x, sy * case_depth / 2, t + inset), "inside"),
            ])

    # Six bottom-to-side brackets: front, center, and rear on each side.
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        for y in design["bottom_ys"]:
            y_label = "FRONT" if y < 0 else "REAR" if y > 0 else "CENTER"
            slug = f"BOTTOM-{side}-{y_label}"
            x0, x1 = _range(sx * xm, sx * (xm - leg_x))
            x2, x3 = _range(sx * xm, sx * (xm - bt))
            boxes = [
                (x0, x1, y - bracket_width / 2, y + bracket_width / 2, t, t + bt),
                (x2, x3, y - bracket_width / 2, y + bracket_width / 2, t, t + leg_y),
            ]
            add_bracket(slug, boxes, [
                ("bottom", "BOTTOM", 2, (sx * (xm - inset), y, 0.0), "outside"),
                ("left_right", side, 0, (sx * case_width / 2, y, t + inset), "inside"),
            ])

    # Eight corner brackets join each front/rear plate to each side plate.
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        for sy in (-1, 1):
            wall = "FRONT" if sy < 0 else "BACK"
            for height_index, z in enumerate(design["vertical_bracket_heights"]):
                level = "LOWER" if height_index == 0 else "UPPER"
                slug = f"VERTICAL-{side}-{wall}-{level}"
                x0, x1 = _range(sx * xm, sx * (xm - leg_x))
                y0, y1 = _range(sy * ym, sy * (ym - bt))
                x2, x3 = _range(sx * xm, sx * (xm - bt))
                y2, y3 = _range(sy * ym, sy * (ym - leg_y))
                boxes = [
                    (x0, x1, y0, y1, z - bracket_width / 2, z + bracket_width / 2),
                    (x2, x3, y2, y3, z - bracket_width / 2, z + bracket_width / 2),
                ]
                add_bracket(slug, boxes, [
                    ("front_back", wall, 1, (sx * (xm - inset), sy * case_depth / 2, z), "inside"),
                    ("left_right", side, 0, (sx * case_width / 2, sy * (ym - inset), z), "inside"),
                ])
    if len(brackets) != 18 or len(holes) != 36:
        raise AssertionError(f"R6 bracket mapping mismatch: {len(brackets)} brackets, {len(holes)} holes")
    return brackets, holes


def _rail_fix_holes(design: dict) -> list[HoleRecord]:
    records = []
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        for index, (y, z) in enumerate(design["mount_axes_yz"], start=1):
            slug = f"RAIL-FIX-{side}-{index:02d}"
            joint_id = f"7U40-R9-JNT-{slug}"
            records.append(_make_hole(
                design, "left_right", side, "rail-fix", 0,
                (sx * design["case_width"] / 2, y, z), slug, None, joint_id, "inside",
            ))
    if len(records) != 10:
        raise AssertionError(f"expected 10 rail-fix holes, got {len(records)}")
    return records


def _matrix(rows: list[list[float]]) -> tuple[tuple[float, float, float, float], ...]:
    return tuple(tuple(_clean_number(value) for value in row) for row in rows)


def _plate_instances(design: dict) -> dict[str, tuple[PlateInstance, ...]]:
    w, d, t = design["case_width"], design["case_depth"], design["metal"]
    xm, ym = design["xm"], design["ym"]
    identity_bottom = _matrix([
        [1, 0, 0, -w / 2], [0, 1, 0, -d / 2], [0, 0, 1, 0], [0, 0, 0, 1],
    ])
    front = _matrix([
        [1, 0, 0, -xm], [0, 0, -1, -ym], [0, 1, 0, t], [0, 0, 0, 1],
    ])
    back = _matrix([
        [1, 0, 0, -xm], [0, 0, -1, d / 2], [0, 1, 0, t], [0, 0, 0, 1],
    ])
    left = _matrix([
        [0, 0, -1, -xm], [1, 0, 0, -d / 2], [0, 1, 0, t], [0, 0, 0, 1],
    ])
    right = _matrix([
        [0, 0, 1, xm], [1, 0, 0, -d / 2], [0, 1, 0, t], [0, 0, 0, 1],
    ])
    return {
        "bottom": (PlateInstance("BOTTOM", identity_bottom),),
        "front_back": (PlateInstance("FRONT", front), PlateInstance("BACK", back)),
        "left_right": (PlateInstance("LEFT", left), PlateInstance("RIGHT", right)),
    }


def _plate_specs(design: dict, records: list[HoleRecord]) -> tuple[PlateSpec, ...]:
    dimensions = {
        "bottom": (design["case_width"], design["case_depth"], 1, "BOTTOM"),
        "front_back": (design["case_width"] - 2 * design["metal"],
                       design["case_height"] - design["metal"], 2, "FRONT"),
        "left_right": (design["case_depth"],
                       design["case_height"] - design["metal"], 2, "RIGHT"),
    }
    instances = _plate_instances(design)
    specs = []
    for plate_type in ("bottom", "front_back", "left_right"):
        width, height, quantity, primary_id = dimensions[plate_type]
        group_holes = tuple(sorted(
            (hole for hole in records if hole.plate_id == PLATE_IDS[plate_type]), key=lambda hole: hole.id
        ))
        pattern = tuple(hole for hole in group_holes if hole.plate_instance == primary_id)
        if not pattern:
            raise AssertionError(f"no hole pattern for {plate_type}/{primary_id}")
        for instance in instances[plate_type]:
            local = sorted(hole.center_local_mm for hole in group_holes if hole.plate_instance == instance.id)
            expected = sorted(hole.center_local_mm for hole in pattern)
            if len(local) != len(expected) or any(
                max(abs(a - b) for a, b in zip(left, right)) > 1e-6
                for left, right in zip(local, expected)
            ):
                raise AssertionError(f"repeated plate hole patterns differ: {plate_type}/{instance.id}")
        specs.append(PlateSpec(
            id=PLATE_IDS[plate_type],
            part_type=plate_type,
            quantity=quantity,
            width_mm=float(width),
            height_mm=float(height),
            thickness_mm=design["metal"],
            instances=instances[plate_type],
            primary_instance_id=primary_id,
            holes=group_holes,
            pattern_holes=pattern,
        ))
    return tuple(specs)


def _geometry_records(ctx: BuildContext) -> tuple[dict, dict, list[dict], list[HoleRecord], tuple[PlateSpec, ...]]:
    sources = _load_sources(ctx)
    design = _design(ctx, sources)
    brackets, bracket_holes = _bracket_definitions(design)
    holes = sorted([*bracket_holes, *_rail_fix_holes(design)], key=lambda hole: hole.id)
    specs = _plate_specs(design, holes)
    if len(holes) != 46 or sum(hole.role == "bracket" for hole in holes) != 36:
        raise AssertionError("R9 body hole totals differ from the R6 7u40 contract")
    return sources, design, brackets, holes, specs


def plate_specs(ctx: BuildContext) -> tuple[PlateSpec, ...]:
    """Return plate outlines, assembly transforms, and stable round-hole records.

    The slot worker can use `make_plate_solid(spec, hole_cutter=...)` to cut
    slot profiles from the same local plate pattern without changing these IDs.
    """
    return _geometry_records(ctx)[-1]


def _default_round_hole(hole: HoleRecord, thickness_mm: float) -> cq.Shape:
    return cq.Solid.makeCylinder(
        hole.diameter_mm / 2,
        thickness_mm + 2,
        cq.Vector(hole.center_local_mm[0], hole.center_local_mm[1], -1),
        cq.Vector(0, 0, 1),
    )


def make_plate_solid(spec: PlateSpec, hole_cutter: HoleCutter | None = None) -> cq.Shape:
    """Build one assembly-positioned plate from its local outline and records.

    `hole_cutter(record, thickness_mm)` must return a through-cutter in local
    plate coordinates. Omitting it yields the current round φ5.5 geometry.
    """
    shape = cq.Solid.makeBox(spec.width_mm, spec.height_mm, spec.thickness_mm, cq.Vector(0, 0, 0))
    cutter_factory = hole_cutter or _default_round_hole
    for hole in spec.pattern_holes:
        shape = shape.cut(cutter_factory(hole, spec.thickness_mm))
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError(f"invalid local plate solid: {spec.id}")
    if spec.part_type == "bottom":
        placed = shape.translate(cq.Vector(-spec.width_mm / 2, -spec.height_mm / 2, 0))
    elif spec.part_type == "front_back":
        placed = shape.rotate((0, 0, 0), (1, 0, 0), 90).translate(
            cq.Vector(-spec.width_mm / 2, spec.primary_matrix[1][3], spec.thickness_mm)
        )
    elif spec.part_type == "left_right":
        placed = shape.rotate((0, 0, 0), (1, 1, 1), 120).translate(
            cq.Vector(spec.primary_matrix[0][3], -spec.width_mm / 2, spec.thickness_mm)
        )
    else:
        raise ValueError(f"unknown plate type: {spec.part_type}")
    placed = placed.clean()
    if not placed.isValid() or len(placed.Solids()) != 1:
        raise ValueError(f"invalid assembly plate solid: {spec.id}")
    return placed


def _box(bounds: tuple[float, ...]) -> cq.Solid:
    x0, x1, y0, y1, z0, z1 = bounds
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def _axis_vector(axis: int) -> cq.Vector:
    return cq.Vector(*(1.0 if coordinate == axis else 0.0 for coordinate in range(3)))


def _axis_cylinder(axis: int, a0: float, a1: float, center: tuple[float, float, float], radius: float) -> cq.Solid:
    start, end = sorted((a0, a1))
    origin = list(center)
    origin[axis] = start
    return cq.Solid.makeCylinder(radius, end - start, cq.Vector(*origin), _axis_vector(axis))


def _drill(shape: cq.Shape, axis: int, center: tuple[float, float, float], radius: float) -> cq.Shape:
    bounds = shape.BoundingBox()
    low = (bounds.xmin, bounds.ymin, bounds.zmin)[axis] - 1
    high = (bounds.xmax, bounds.ymax, bounds.zmax)[axis] + 1
    result = shape.cut(_axis_cylinder(axis, low, high, center, radius)).clean()
    if not result.isValid() or len(result.Solids()) != 1:
        raise ValueError("invalid drilled envelope")
    return result


def _fuse_boxes(boxes: list[tuple[float, ...]]) -> cq.Shape:
    shape = _box(boxes[0])
    for bounds in boxes[1:]:
        shape = shape.fuse(_box(bounds))
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("L bracket boxes did not form one valid solid")
    return shape


def _make_bracket_solid(definition: dict) -> cq.Shape:
    shape = _fuse_boxes(definition["boxes"])
    for hole in definition["holes"]:
        shape = _drill(shape, hole.axis, hole.center_assembly_mm, hole.diameter_mm / 2)
    if not shape.isValid():
        raise ValueError(f"invalid bracket: {definition['id']}")
    return shape


def _transformed_bbox(matrix: list[list[float]], minimum: list[float], maximum: list[float]) -> tuple[list[float], list[float]]:
    points = []
    for x in (minimum[0], maximum[0]):
        for y in (minimum[1], maximum[1]):
            for z in (minimum[2], maximum[2]):
                source = (x, y, z, 1.0)
                points.append([
                    sum(matrix[row][column] * source[column] for column in range(4))
                    for row in range(3)
                ])
    lo = [min(point[axis] for point in points) for axis in range(3)]
    hi = [max(point[axis] for point in points) for axis in range(3)]
    return ([_clean_number(v) for v in lo], [_clean_number(v) for v in hi])


def _rail_envelopes(design: dict, sources: dict) -> tuple[Part, list[dict]]:
    dimensions = sources["rail_dimensions"]
    rail_meta = dimensions["exact_mesh_measurements"]
    rail_min, rail_max = rail_meta["bbox_min"], rail_meta["bbox_max"]
    center_u = design["fixer_center_u"]
    center_x, center_y = design["rail_center_x"], design["rail_center_y"]
    instances = []
    exemplar = None
    for index, (u, v) in enumerate(design["rail_axes_uv"]):
        sign = -1 if index % 2 == 0 else 1
        target_y, target_z = u - center_u, design["top"] - v
        matrix = [
            [0, 0, sign, -sign * design["rail_length"] / 2],
            [0, sign, 0, target_y - sign * center_y],
            [-1, 0, 0, target_z + center_x],
            [0, 0, 0, 1],
        ]
        low, high = _transformed_bbox(matrix, rail_min, rail_max)
        # makeBox takes min corner and lengths, while the stored bounds are two triples.
        shape = cq.Solid.makeBox(high[0] - low[0], high[1] - low[1], high[2] - low[2], cq.Vector(*low))
        if exemplar is None:
            exemplar = shape
        instances.append({
            "id": f"RAIL-{index + 1:02d}",
            "railIndex": index,
            "row": index // 2,
            "sourceTransform": matrix,
            "axisCenterYZMm": [target_y, target_z],
            "bboxMinMm": low,
            "bboxMaxMm": high,
            "envelopeDimensionsMm": [high[i] - low[i] for i in range(3)],
            "sourceBoundsMm": {"min": rail_min, "max": rail_max},
            "sourceBoundsUsage": "bbox only; original non-manifold mesh is not converted to BREP",
        })
    part = Part(
        id="7U40-R9-HW-RAIL-UNIT-ENVELOPE",
        solid=exemplar,
        category="hardware-envelopes",
        material="Existing 40HP rail source bounding envelope; alloy unconfirmed",
        qty=len(instances),
        export_kinds=("step", "stl"),
    )
    return part, instances


def _panel_wire(points: list[list[float]], x0: float, design: dict,
                offset_u: float, offset_v: float) -> cq.Wire:
    vertices = [
        cq.Vector(x0, float(u) + offset_u - design["fixer_center_u"],
                  design["top"] - float(v) - offset_v)
        for u, v in points
    ]
    return cq.Wire.makePolygon(vertices, close=True)


def _pcb_solid(panel: dict, x0: float, thickness: float, design: dict,
               offset_u: float, offset_v: float) -> cq.Shape:
    outer = _panel_wire(panel["outer"]["points"], x0, design, offset_u, offset_v)
    cutouts = [_panel_wire(contour["points"], x0, design, offset_u, offset_v)
               for contour in panel["cutouts"]]
    shape = cq.Solid.extrudeLinear(outer, cutouts, cq.Vector(thickness, 0, 0))
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("invalid PCB source polygon envelope")
    expected = float(panel["materialAreaMm2"]) * thickness
    if abs(shape.Volume() - expected) > 1e-4:
        raise ValueError(f"PCB source polygon volume mismatch: {shape.Volume()} vs {expected}")
    return shape


def _pcb_parts(design: dict) -> tuple[list[Part], list[dict]]:
    groups: dict[str, list[tuple[cq.Shape, dict]]] = {"FIXER": [], "PADDER-3U": [], "PADDER-1U": []}
    rail_length = design["rail_length"]
    fixer_start = rail_length / 2 + design["padder_thickness"]
    padder_start = rail_length / 2
    padder_us = [float(v) for v in _parameter_from_design(design, "padder_u")]
    padder_vs = [float(v) for v in _parameter_from_design(design, "padder_v")]
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        fixer_x0 = min(sx * fixer_start, sx * (fixer_start + design["fixer_thickness"]))
        fixer = _pcb_solid(design["panels"]["fixer"], fixer_x0, design["fixer_thickness"], design, 0, 0)
        groups["FIXER"].append((fixer, {
            "id": f"FIXER-{side}", "kind": "fixer7u", "side": side,
            "row": None, "placementUVmm": [0.0, 0.0],
        }))
        for row in range(3):
            kind = "padder3u" if row < 2 else "padder1u"
            group = "PADDER-3U" if row < 2 else "PADDER-1U"
            panel = design["panels"][kind]
            offset_u, offset_v = padder_us[row], padder_vs[row]
            x0 = min(sx * padder_start, sx * (padder_start + design["padder_thickness"]))
            padder = _pcb_solid(panel, x0, design["padder_thickness"], design, offset_u, offset_v)
            groups[group].append((padder, {
                "id": f"PADDER-{side}-ROW-{row + 1}", "kind": kind, "side": side,
                "row": row, "placementUVmm": [offset_u, offset_v],
            }))
    parts = []
    component_records = []
    descriptions = {
        "FIXER": ("7U40-R9-PCB-FIXER", "Existing fixer PCB; user-confirmed t1.6 mm"),
        "PADDER-3U": ("7U40-R9-PCB-PADDER-3U", "Existing 3U padder PCB; user-confirmed t1.6 mm"),
        "PADDER-1U": ("7U40-R9-PCB-PADDER-1U", "Existing 1U padder PCB; user-confirmed t1.6 mm"),
    }
    for group_name, members in groups.items():
        part_id, material = descriptions[group_name]
        instances = []
        for shape, metadata in members:
            bb = shape.BoundingBox()
            item = dict(metadata)
            item.update({
                "bboxMinMm": [bb.xmin, bb.ymin, bb.zmin],
                "bboxMaxMm": [bb.xmax, bb.ymax, bb.zmax],
                "dimensionsMm": [bb.xlen, bb.ylen, bb.zlen],
            })
            instances.append(item)
        parts.append(Part(
            id=part_id, solid=members[0][0], category="hardware-envelopes",
            material=material, qty=len(members), export_kinds=("step", "stl"),
        ))
        component_records.append({"id": part_id, "instances": instances})
    return parts, component_records


def _parameter_from_design(design: dict, key: str) -> list[float]:
    # Cached by _geometry_records for the PCB layout without changing R6 placements.
    return design[key]


def _tube(axis: int, start: float, end: float, center: tuple[float, float, float],
          outer_diameter: float, inner_diameter: float) -> cq.Shape:
    outer = _axis_cylinder(axis, start, end, center, outer_diameter / 2)
    inner = _axis_cylinder(axis, min(start, end) - 1, max(start, end) + 1,
                           center, inner_diameter / 2)
    return outer.cut(inner).clean()


def _hex_nut(axis: int, start: float, end: float, center: tuple[float, float, float],
             across_flats: float) -> cq.Shape:
    low, high = sorted((start, end))
    radius = across_flats / math.sqrt(3)
    other_axes = [index for index in range(3) if index != axis]
    points = []
    for index in range(6):
        point = list(center)
        point[axis] = low
        point[other_axes[0]] += radius * math.cos(math.pi * index / 3)
        point[other_axes[1]] += radius * math.sin(math.pi * index / 3)
        points.append(cq.Vector(*point))
    wire = cq.Wire.makePolygon(points, close=True)
    shape = cq.Solid.extrudeLinear(wire, [], _axis_vector(axis) * (high - low))
    shape = shape.cut(_axis_cylinder(axis, low - 1, high + 1, center, 2.5)).clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("invalid M5 nut envelope")
    return shape


def _bolt(axis: int, seat: float, head_end: float, tip: float,
          center: tuple[float, float, float], head_diameter: float) -> cq.Shape:
    head = _axis_cylinder(axis, seat, head_end, center, head_diameter / 2)
    shaft = _axis_cylinder(axis, seat, tip, center, 2.5)
    shape = head.fuse(shaft).clean()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError("invalid M5 bolt envelope")
    return shape


def _shape_box(shape: cq.Shape) -> dict:
    bb = shape.BoundingBox()
    return {
        "bboxMinMm": [_clean_number(bb.xmin), _clean_number(bb.ymin), _clean_number(bb.zmin)],
        "bboxMaxMm": [_clean_number(bb.xmax), _clean_number(bb.ymax), _clean_number(bb.zmax)],
        "dimensionsMm": [_clean_number(bb.xlen), _clean_number(bb.ylen), _clean_number(bb.zlen)],
    }


def _component_part(part_id: str, shape_instances: list[tuple[cq.Shape, dict]], material: str,
                    role: str, export_kinds: tuple[str, ...] = ("step", "stl")) -> tuple[Part, dict]:
    if not shape_instances:
        raise ValueError(f"component has no instances: {part_id}")
    instances = []
    for shape, item in shape_instances:
        record = dict(item)
        record.update(_shape_box(shape))
        instances.append(record)
    part = Part(part_id, shape_instances[0][0], "hardware-envelopes", material,
                len(shape_instances), export_kinds)
    return part, {"id": part_id, "role": role, "instances": instances}


def _hardware_parts(design: dict, brackets: list[dict], holes: list[HoleRecord],
                    rail_instances: list[dict], rail_part: Part,
                    pcb_parts: list[Part], pcb_records: list[dict]) -> tuple[list[Part], list[dict]]:
    parts: list[Part] = []
    components: list[dict] = []

    bracket_shapes = []
    for definition in brackets:
        shape = _make_bracket_solid(definition)
        bracket_shapes.append((shape, {
            "id": definition["id"], "jointId": definition["jointId"],
            "holeIds": [hole.id for hole in definition["holes"]],
            "boxSegmentsMm": [list(box) for box in definition["boxes"]],
        }))
    bracket_part, bracket_record = _component_part(
        "7U40-R9-HW-PANEL-BRACKET", bracket_shapes,
        "Existing metal L bracket; material unconfirmed; physical t2 mm",
        "panelBracket",
    )
    bracket_record["thicknessMm"] = design["bracket_thickness"]
    bracket_record["modelingAllowanceMm"] = design["bracket_allowance"]
    bracket_record["allowanceNote"] = "2.2 mm is a separate occupancy allowance; the physical bracket solid remains measured t2 mm."
    parts.append(bracket_part)
    components.append(bracket_record)

    rail_record = {
        "id": rail_part.id,
        "role": "railUnitConservativeEnvelope",
        "instances": rail_instances,
    }
    parts.append(rail_part)
    components.append(rail_record)
    parts.extend(pcb_parts)
    components.extend(pcb_records)

    # Ten selected fixer mounts: PCB-to-case spacer stack, bolt, washer, and nut.
    mount_bolts = []
    spacers = []
    washers = []
    nuts = []
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        for index, (y, z) in enumerate(design["mount_axes_yz"], start=1):
            center = (0.0, y, z)
            suffix = f"{side}-{index:02d}"
            mount_seat = sx * (design["rail_length"] / 2 + design["padder_thickness"])
            mount_tip = mount_seat + sx * design["mount_bolt_length"]
            mount_head_end = mount_seat - sx * design["mount_head_height"]
            mount_bolts.append((_bolt(0, mount_seat, mount_head_end, mount_tip, center,
                                      design["mount_head_diameter"]), {
                "id": f"MOUNT-BOLT-{suffix}", "role": "mountBolt", "axis": "X",
                "jointId": f"7U40-R9-JNT-RAIL-FIX-{suffix}", "centerMm": [y, z],
                "headHeightMm": design["mount_head_height"],
                "headDiameterMm": design["mount_head_diameter"],
                "shaftLengthMm": design["mount_bolt_length"],
            }))
            spacer_a, spacer_b = sx * design["frame_width"] / 2, sx * (design["frame_width"] / 2 + design["spacer"])
            spacers.append((_tube(0, spacer_a, spacer_b, center,
                                  design["nylon_outer_diameter"], design["nylon_inner_diameter"]), {
                "id": f"INNER-SPACER-{suffix}", "role": "innerSpacer", "axis": "X",
                "jointId": f"7U40-R9-JNT-RAIL-FIX-{suffix}", "centerMm": [y, z],
                "thicknessMm": design["spacer"],
            }))
            washer_a, washer_b = sx * design["case_width"] / 2, sx * (design["case_width"] / 2 + design["outer_washer"])
            washers.append((_tube(0, washer_a, washer_b, center,
                                  design["nylon_outer_diameter"], design["nylon_inner_diameter"]), {
                "id": f"OUTER-WASHER-{suffix}", "role": "outerWasher", "axis": "X",
                "jointId": f"7U40-R9-JNT-RAIL-FIX-{suffix}", "centerMm": [y, z],
                "thicknessMm": design["outer_washer"],
            }))
            nut_start = sx * (design["case_width"] / 2 + design["outer_washer"])
            nut_end = nut_start + sx * design["nut_height"]
            nuts.append((_hex_nut(0, nut_start, nut_end, center, design["nut_across_flats"]), {
                "id": f"M5-NUT-MOUNT-{suffix}", "role": "mountNut", "axis": "X",
                "jointId": f"7U40-R9-JNT-RAIL-FIX-{suffix}", "centerMm": [y, z],
            }))

    rail_end_bolts = []
    for sx in (-1, 1):
        side = "LEFT" if sx < 0 else "RIGHT"
        for rail in rail_instances:
            y, z = rail["axisCenterYZMm"]
            seat = sx * design["frame_width"] / 2
            tip = seat - sx * design["rail_end_bolt_length"]
            head_end = seat + sx * design["mount_head_height"]
            rail_end_bolts.append((_bolt(0, seat, head_end, tip, (0.0, y, z),
                                         design["rail_end_head_diameter"]), {
                "id": f"RAIL-END-BOLT-{side}-{rail['railIndex'] + 1:02d}",
                "role": "railEndBolt", "axis": "X", "railIndex": rail["railIndex"],
                "centerMm": [y, z], "headHeightMm": design["mount_head_height"],
                "headDiameterMm": design["rail_end_head_diameter"],
                "shaftLengthMm": design["rail_end_bolt_length"],
            }))

    panel_bolts = []
    panel_washers = []
    panel_nuts = []
    for hole in holes:
        if hole.role != "bracket":
            continue
        axis, center = hole.axis, hole.center_assembly_mm
        sign = -1 if axis == 2 else (-1 if center[axis] < 0 else 1)
        outside = center[axis]
        if axis == 2:
            seat = outside
            head_end = outside - design["mount_head_height"]
            tip = outside + design["metal"] + design["bracket_thickness"] + design["outer_washer"] + design["nut_height"] + 1
            washer_a = outside + design["metal"] + design["bracket_thickness"]
            washer_b = washer_a + design["outer_washer"]
            nut_a, nut_b = washer_b, washer_b + design["nut_height"]
        else:
            seat = outside - sign * (design["metal"] + design["bracket_thickness"])
            head_end = seat - sign * design["mount_head_height"]
            tip = outside + sign * (design["outer_washer"] + design["nut_height"] + 1)
            washer_a, washer_b = outside, outside + sign * design["outer_washer"]
            nut_a, nut_b = washer_b, outside + sign * design["nut_height"]
        panel_bolts.append((_bolt(axis, seat, head_end, tip, center, design["bracket_head_diameter"]), {
            "id": f"PANEL-BOLT-{hole.id}", "role": "panelJointBolt", "axis": hole.axis_name,
            "holeId": hole.id, "jointId": hole.joint_id, "bracketId": hole.bracket_id,
            "headHeightMm": design["mount_head_height"],
            "headDiameterMm": design["bracket_head_diameter"],
        }))
        panel_washers.append((_tube(axis, washer_a, washer_b, center,
                                    design["nylon_outer_diameter"], design["nylon_inner_diameter"]), {
            "id": f"PANEL-WASHER-{hole.id}", "role": "panelJointWasher", "axis": hole.axis_name,
            "holeId": hole.id, "jointId": hole.joint_id, "bracketId": hole.bracket_id,
            "thicknessMm": design["outer_washer"],
        }))
        panel_nuts.append((_hex_nut(axis, nut_a, nut_b, center, design["nut_across_flats"]), {
            "id": f"PANEL-NUT-{hole.id}", "role": "panelJointNut", "axis": hole.axis_name,
            "holeId": hole.id, "jointId": hole.joint_id, "bracketId": hole.bracket_id,
        }))

    # One 1 mm washer part geometry serves both the 10 outer and 36 panel joints.
    washers.extend(panel_washers)
    component_definitions = [
        ("7U40-R9-HW-INNER-SPACER", spacers, "Spacer envelope; material unconfirmed; t8 mm confirmed, R6 OD/ID provisional", "innerSpacer"),
        ("7U40-R9-HW-WASHER-1MM", washers, "Washer envelope; material unconfirmed; t1 mm confirmed, R6 OD/ID provisional", "washer"),
        ("7U40-R9-HW-CASE-MOUNT-BOLT", mount_bolts, "M5 mount bolt envelope; head height confirmed, length and diameter provisional", "mountBolt"),
        ("7U40-R9-HW-RAIL-END-BOLT", rail_end_bolts, "M5 rail-end bolt envelope; length provisional", "railEndBolt"),
        ("7U40-R9-HW-PANEL-JOINT-BOLT", panel_bolts, "M5 panel joint bolt envelope; head height confirmed, head diameter and length provisional", "panelJointBolt"),
        ("7U40-R9-HW-M5-NUT", nuts + panel_nuts, "M5 lock nut display envelope; nut dimensions provisional", "nut"),
    ]
    for part_id, shape_instances, material, role in component_definitions:
        part, record = _component_part(part_id, shape_instances, material, role)
        parts.append(part)
        components.append(record)

    feet = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = sx * (design["case_width"] / 2 - design["foot_inset"])
            y = sy * (design["case_depth"] / 2 - design["foot_inset"])
            shape = _axis_cylinder(2, -design["foot_height"], 0, (x, y, 0), design["foot_diameter"] / 2)
            feet.append((shape, {
                "id": f"FOOT-{('LEFT' if sx < 0 else 'RIGHT')}-{('FRONT' if sy < 0 else 'REAR')}",
                "role": "foot", "axis": "Z", "centerMm": [x, y],
                "diameterMm": design["foot_diameter"], "heightMm": design["foot_height"],
            }))
    foot_part, foot_record = _component_part(
        "7U40-R9-HW-FOOT", feet,
        "Black rubber foot envelope; provisional size and location; product not selected",
        "foot",
    )
    parts.append(foot_part)
    components.append(foot_record)
    return parts, components


def _hole_layout_json(sources: dict, design: dict, holes: list[HoleRecord],
                      specs: tuple[PlateSpec, ...]) -> dict:
    plate_records = []
    for spec in specs:
        plate_records.append({
            "plateId": spec.id,
            "partType": spec.part_type,
            "quantity": spec.quantity,
            "sizeMm": [spec.width_mm, spec.height_mm, spec.thickness_mm],
            "holeCountEach": len(spec.pattern_holes),
            "holeCountTotal": len(spec.holes),
            "instances": [instance.as_json() for instance in spec.instances],
            "holes": [hole.as_json() for hole in spec.holes],
        })
    role_counts = {
        "bracket": sum(hole.role == "bracket" for hole in holes),
        "rail-fix": sum(hole.role == "rail-fix" for hole in holes),
    }
    return {
        "schema": "zudo-case-r9-body-hole-layout-v1",
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "units": "mm",
        "status": "unapproved_prototype",
        "holeDiameterMm": design["hole_diameter"],
        "plateCount": sum(spec.quantity for spec in specs),
        "totalHoleCount": len(holes),
        "roleCounts": role_counts,
        "coordinateNote": "centerLocalMm uses each flat pattern's lower-left XY origin; centerAssemblyMm uses the R9 assembly coordinates.",
        "reference": {
            "path": "engineering/r6-body/engineering/7u40/aluminum/hole-layout.json",
            "sha256": sources["hashes"]["r6_hole_layout"],
            "regressionToleranceMm": 1e-6,
        },
        "holes": [hole.as_json() for hole in holes],
        "plates": plate_records,
    }


def _body_manifest(sources: dict, ctx: BuildContext, design: dict, brackets: list[dict],
                   holes: list[HoleRecord], specs: tuple[PlateSpec, ...],
                   parts: list[Part], components: list[dict]) -> dict:
    repo = sources["repo_root"]
    source_items = []
    purposes = {
        "r6_build_geometry": "R6 7u40 geometry source ported by this module",
        "design_parameters": "R6 7u40 source parameter values",
        "panel_geometry": "PCB outline and cutout polygons; basis for exact 1.6 mm PCB solids",
        "rail_dimensions": "40HP source mesh bounding box and rail registration",
        "rail_stl": "Original 40HP source rail; hash recorded, never rescaled or converted to BREP",
        "r6_hole_layout": "1e-6 mm plate outline and hole-center regression reference",
    }
    for key, path in sources["paths"].items():
        source_items.append({
            "path": str(path.relative_to(repo)),
            "sha256": sources["hashes"][key],
            "purpose": purposes[key],
        })
    parameter_keys = [
        "rail_length", "rail_hole_u", "padder_u", "padder_v", "mount_u", "mount_v",
        "bracket_bottom_x_offset", "bracket_bottom_y_offset", "rail_lip_cx", "rail_lip_cy",
        "fixer_thickness", "padder_thickness", "mount_head_height", "inner_spacer", "outer_washer",
        "metal_thickness", "case_height", "bracket_outer", "bracket_thickness",
        "bracket_allowance_thickness", "front_back_clearance", "bracket_hole_inset",
        "vertical_bracket_center_heights", "metal_clearance_hole_diameter", "mount_bolt_length",
        "mount_head_diameter", "nylon_outer_diameter", "nylon_inner_diameter", "nut_height",
        "nut_across_flats", "rail_end_bolt_length", "rail_end_head_diameter", "bracket_head_diameter",
        "foot_diameter", "foot_height", "foot_inset",
    ]
    return {
        "schema": "zudo-case-r9-body-manifest-v1",
        "revision": ctx.revision,
        "model": ctx.model,
        "units": "mm",
        "status": "unapproved_prototype",
        "productionApproved": False,
        "sourceFiles": source_items,
        "parameters": {key: ctx.params["body"][key] for key in parameter_keys},
        "dimensions": {
            "aluminumEnvelopeMm": [design["case_width"], design["case_depth"], design["case_height"]],
            "plateCount": sum(spec.quantity for spec in specs),
            "plateThicknessMm": design["metal"],
            "frameWidthMm": design["frame_width"],
            "frameDepthMm": float(design["panels"]["fixer"]["outer"]["bbox"]["dimensions"][0]),
        },
        "holes": {
            "count": len(holes),
            "diameterMm": design["hole_diameter"],
            "roles": {
                "bracket": sum(hole.role == "bracket" for hole in holes),
                "rail-fix": sum(hole.role == "rail-fix" for hole in holes),
            },
            "metadataPath": "out/aluminum/hole-layout.json",
            "slotConversionHook": "r9.body.plate_specs(ctx) and r9.body.make_plate_solid(spec, hole_cutter=...). build(ctx) leaves all holes round.",
        },
        "brackets": {
            "count": len(brackets),
            "physicalThicknessMm": design["bracket_thickness"],
            "modelingAllowanceMm": design["bracket_allowance"],
            "allowanceUsage": "separate clearance allowance only; bracket CAD geometry uses measured 2 mm thickness",
        },
        "rails": {
            "count": len(design["rail_axes_uv"]),
            "sourceRailLengthMm": design["rail_length"],
            "sourceMeshSha256": sources["hashes"]["rail_stl"],
            "envelopeBasis": "axis-aligned boxes from rail_dimensions.json exact source mesh bbox and R6 rigid registration",
            "rawMeshUsedForBrep": False,
            "rescaled": False,
        },
        "pcbs": {
            "sourcePath": "engineering/r6-body/source-data/panels/panel-geometry.json",
            "sourceSha256": sources["hashes"]["panel_geometry"],
            "fixerAndPadderThicknessMm": 1.6,
            "coordinateHandling": "fixer7u raw axes are swapped as in R6; source polygons are retained",
        },
        "components": [
            {"id": part.id, "category": part.category, "material": part.material,
             "quantity": part.qty, "exportKinds": list(part.export_kinds),
             "instances": next((record["instances"] for record in components if record["id"] == part.id), [])}
            for part in parts
        ],
        "limitations": [
            "Nominal prototype geometry only; not an approved manufacturing release.",
            "Bracket hole locations are the R6 proposed 10 mm inset and have not been checked against each physical bracket.",
            "Hardware sizes not confirmed by the user remain provisional envelope assumptions.",
            "This build does not validate fit, strength, drop, fatigue, or transport performance.",
        ],
    }


def build(ctx: BuildContext) -> list[Part]:
    sources, design, bracket_definitions, holes, specs = _geometry_records(ctx)
    plate_parts = []
    for spec in specs:
        part = Part(
            id=spec.id,
            solid=make_plate_solid(spec),
            category="aluminum",
            material="A5052 t1.5 mm candidate; black anodizing candidate",
            qty=spec.quantity,
            export_kinds=("step", "stl", "dxf"),
            dxf_outline=spec.outline_local_mm,
            dxf_holes=tuple((hole.center_local_mm[0], hole.center_local_mm[1], hole.diameter_mm / 2)
                            for hole in spec.pattern_holes),
        )
        plate_parts.append(part)

    rail_part, rail_instances = _rail_envelopes(design, sources)
    pcb_parts, pcb_records = _pcb_parts(design)
    hardware_parts, components = _hardware_parts(
        design, bracket_definitions, holes, rail_instances, rail_part, pcb_parts, pcb_records,
    )
    parts = [*plate_parts, *hardware_parts]
    plate_components = []
    for spec in specs:
        plate_components.append({
            "id": spec.id,
            "role": "aluminumPanel",
            "instances": [
                {
                    **instance.as_json(),
                    "holeIds": [hole.id for hole in spec.holes if hole.plate_instance == instance.id],
                    "holeCount": sum(hole.plate_instance == instance.id for hole in spec.holes),
                }
                for instance in spec.instances
            ],
        })
    all_components = [*plate_components, *components]

    out = ctx.out
    hole_layout = _hole_layout_json(sources, design, holes, specs)
    _write_json(out / "aluminum" / "hole-layout.json", hole_layout)
    _write_json(out / "hardware-envelopes" / "body-manifest.json",
                _body_manifest(sources, ctx, design, bracket_definitions, holes, specs, parts, all_components))
    return parts
