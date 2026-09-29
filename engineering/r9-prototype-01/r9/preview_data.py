"""R9 preview meshes and real-BREP section images; display data only."""
from __future__ import annotations

import base64
import gzip
import io
import json
import math
from pathlib import Path
import struct
import zlib

import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

from .common import sha256_file
from .types import BuildContext, Part


LIMIT_BYTES = 25 * 1024 * 1024
TESSELLATION_TOLERANCE_MM = 0.05
ANGULAR_TOLERANCE_RAD = 0.25
SECTION_WIDTH = 960
SECTION_HEIGHT = 540

PART_NAMES = {
    "7U40-R9-AL-BOTTOM": "底板",
    "7U40-R9-AL-FRONT-BACK": "前板・後板",
    "7U40-R9-AL-LEFT-RIGHT": "左板・右板",
    "7U40-R9-HW-PANEL-BRACKET": "L字ブラケット（模式）",
    "7U40-R9-HW-RAIL-UNIT-ENVELOPE": "レールユニット包絡",
    "7U40-R9-PCB-FIXER": "fixer PCB",
    "7U40-R9-PCB-PADDER-3U": "3U padder PCB",
    "7U40-R9-PCB-PADDER-1U": "1U padder PCB",
    "7U40-R9-HW-INNER-SPACER": "内側スペーサー（包絡）",
    "7U40-R9-HW-WASHER-1MM": "1mmワッシャー（包絡）",
    "7U40-R9-HW-CASE-MOUNT-BOLT": "本体固定M5（包絡）",
    "7U40-R9-HW-RAIL-END-BOLT": "レール端M5（包絡）",
    "7U40-R9-HW-PANEL-JOINT-BOLT": "板接合M5（包絡）",
    "7U40-R9-HW-M5-NUT": "M5ナット（包絡）",
    "7U40-R9-HW-FOOT": "ゴム脚（包絡）",
    "7U40-R9-LID-PLATE": "載せ蓋アルミ板",
}

GUARD_NAMES = {
    "TOP-A": "上端ガード A",
    "TOP-B": "上端ガード B",
    "LOWER-WIDTH-HALF": "前後下辺ガード 半分",
    "LOWER-DEPTH-A": "左右下辺ガード A",
    "LOWER-DEPTH-B": "左右下辺ガード B",
    "VERTICAL-CORNER": "縦辺コーナーガード",
}

PALETTE = {
    "aluminum": "#343b43",
    "guard": "#237494",
    "hardware": "#79838d",
    "pcb": "#8a7352",
    "lid": "#535d68",
    "rail": "#87949e",
    "provisional-envelope": "#d18235",
}


def _repo(ctx: BuildContext) -> Path:
    return ctx.root.resolve().parents[1]


def _part_path(ctx: BuildContext, category: str, part_id: str, qty: int, kind: str) -> Path:
    stem = f"{part_id.lower()}-qty{qty}-mm"
    return ctx.out / category / f"{stem}.{kind}"


def _shape(path: Path) -> cq.Shape:
    if not path.is_file():
        raise FileNotFoundError(f"R9 preview input missing; run body/slots/guards/lid first: {path}")
    try:
        return cq.importers.importStep(str(path)).val()
    except Exception as error:
        raise ValueError(f"could not import generated R9 STEP: {path}") from error


def _bbox(shape: cq.Shape) -> tuple[list[float], list[float], list[float]]:
    box = shape.BoundingBox()
    low = [float(box.xmin), float(box.ymin), float(box.zmin)]
    high = [float(box.xmax), float(box.ymax), float(box.zmax)]
    dimensions = [high[i] - low[i] for i in range(3)]
    return low, high, dimensions


def _center(low: list[float], high: list[float]) -> tuple[float, float, float]:
    return tuple((low[i] + high[i]) / 2 for i in range(3))


def _align_axis(shape: cq.Shape, target_axis: str, target_low: list[float], target_high: list[float],
                source_axis: str) -> cq.Shape:
    source_low, source_high, _ = _bbox(shape)
    start, end = _center(source_low, source_high), _center(target_low, target_high)
    result = shape.translate(tuple(-v for v in start))
    axes = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}
    a, b = axes[source_axis], axes[target_axis]
    cross = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    dot = max(-1.0, min(1.0, sum(a[i]*b[i] for i in range(3))))
    length = math.sqrt(sum(v*v for v in cross))
    if length > 1e-10:
        axis = tuple(v / length for v in cross)
        result = result.rotate((0, 0, 0), axis, math.degrees(math.acos(dot)))
    elif dot < 0:
        result = result.rotate((0, 0, 0), (0, 1, 0) if source_axis != "Y" else (1, 0, 0), 180)
    return result.translate(end)


def _mesh_shape(part_id: str, name: str, category: str, instance_id: str,
                shape: cq.Shape, variant: str | None = None) -> dict:
    vertices, triangles = shape.tessellate(TESSELLATION_TOLERANCE_MM, ANGULAR_TOLERANCE_RAD)
    low, high, dimensions = _bbox(shape)
    item = {
        "partId": part_id,
        "instanceId": instance_id,
        "name": name,
        "category": category,
        "positions": [round(float(n), 6) for vertex in vertices for n in vertex.toTuple()],
        "indices": [int(index) for triangle in triangles for index in triangle],
        "dimensionsMm": [round(v, 6) for v in dimensions],
        "bboxMinMm": [round(v, 6) for v in low],
        "bboxMaxMm": [round(v, 6) for v in high],
        "status": "未承認 / 表示専用",
    }
    if variant:
        item["variant"] = variant
    return item


def _rail_stl_mesh(path: Path, matrix: list[list[float]], instance_id: str) -> dict:
    raw = path.read_bytes()
    if len(raw) < 84:
        raise ValueError("short source 40HP rail STL")
    count = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + count * 50:
        raise ValueError("invalid source 40HP rail STL size")
    positions: list[float] = []
    indices: list[int] = []
    vertices: dict[tuple[float, float, float], int] = {}
    for face in range(count):
        values = struct.unpack_from("<12fH", raw, 84 + face * 50)
        face_indices = []
        for offset in (3, 6, 9):
            x, y, z = values[offset:offset+3]
            point = tuple(round(matrix[row][0]*x + matrix[row][1]*y + matrix[row][2]*z + matrix[row][3], 6)
                          for row in range(3))
            index = vertices.get(point)
            if index is None:
                index = len(vertices)
                vertices[point] = index
                positions.extend(point)
            face_indices.append(index)
        indices.extend(face_indices)
    coords = [positions[i:i+3] for i in range(0, len(positions), 3)]
    low = [min(point[axis] for point in coords) for axis in range(3)]
    high = [max(point[axis] for point in coords) for axis in range(3)]
    return {
        "partId": "R6-40HP-RAIL-DISPLAY",
        "instanceId": instance_id,
        "name": "40HPレール（R6保存STL / 表示専用）",
        "category": "rail",
        "positions": positions,
        "indices": indices,
        "dimensionsMm": [round(high[i]-low[i], 6) for i in range(3)],
        "bboxMinMm": low,
        "bboxMaxMm": high,
        "sourceLengthMm": 204,
        "status": "R6 source / 表示専用 / 未承認",
    }


def _copy_guard(shape: cq.Shape, quantity: int) -> list[tuple[str, cq.Shape]]:
    mirrors = [("A", shape)]
    if quantity == 2:
        mirrors.append(("B", shape.mirror("YZ")))
    elif quantity == 4:
        mirrors.extend((
            ("B", shape.mirror("YZ")),
            ("C", shape.mirror("XZ")),
            ("D", shape.mirror("YZ").mirror("XZ")),
        ))
    elif quantity != 1:
        raise ValueError(f"no R9 assembly placement rule for guard qty={quantity}")
    return mirrors


def _scene_meshes(ctx: BuildContext, params: dict, build_parts: list[Part]) -> tuple[list[dict], dict]:
    data: list[dict] = []
    source_hashes: dict[str, str] = {}
    body_path = ctx.out / "hardware-envelopes" / "body-manifest.json"
    body_manifest = json.loads(body_path.read_text(encoding="utf-8"))
    components = {entry["id"]: entry for entry in body_manifest["components"]}
    part_by_id = {part.id: part for part in build_parts}

    # Each generated plate STEP is already in the primary instance's assembly
    # frame. Move only repeated copies by target * inverse(primary) placement.
    for part_id in ("7U40-R9-AL-BOTTOM", "7U40-R9-AL-FRONT-BACK", "7U40-R9-AL-LEFT-RIGHT"):
        part = part_by_id[part_id]
        shape = _shape(_part_path(ctx, "aluminum", part_id, part.qty, "step"))
        source_hashes[str(_part_path(ctx, "aluminum", part_id, part.qty, "step").relative_to(_repo(ctx)))] = sha256_file(_part_path(ctx, "aluminum", part_id, part.qty, "step"))
        primary_id = {"7U40-R9-AL-BOTTOM": "BOTTOM", "7U40-R9-AL-FRONT-BACK": "FRONT",
                      "7U40-R9-AL-LEFT-RIGHT": "RIGHT"}[part_id]
        source_matrix = next(item["localToAssembly"] for item in components[part_id]["instances"]
                             if item["id"] == primary_id)
        for instance in components[part_id]["instances"]:
            if instance["id"] == primary_id:
                placed = shape
            elif part_id == "7U40-R9-AL-FRONT-BACK" and instance["id"] == "BACK":
                target_y = instance["localToAssembly"][1][3]
                source_y = source_matrix[1][3]
                placed = shape.translate((0, target_y-source_y, 0))
            elif part_id == "7U40-R9-AL-LEFT-RIGHT" and instance["id"] == "LEFT":
                placed = shape.mirror("YZ")
            else:
                raise ValueError(f"no R9 plate instance transform: {part_id}/{instance['id']}")
            data.append(_mesh_shape(part_id, PART_NAMES[part_id], "aluminum", instance["id"], placed))

    # Body hardware copies use their generated BREP exemplars plus the exact
    # instance records. Rebuild each L bracket with the same body helper so
    # its actual drilled holes remain in the viewer mesh.
    from . import body as body_module
    _, _, bracket_definitions, _, _ = body_module._geometry_records(ctx)
    bracket_shapes = {definition["id"]: body_module._make_bracket_solid(definition)
                      for definition in bracket_definitions}
    for part in build_parts:
        if part.category != "hardware-envelopes" or "RAIL-UNIT-ENVELOPE" in part.id:
            continue
        if "PANEL-BRACKET" in part.id:
            for item in components[part.id]["instances"]:
                shape = bracket_shapes[item["id"]]
                data.append(_mesh_shape(part.id, PART_NAMES[part.id], "hardware", item["id"], shape))
            continue
        path = _part_path(ctx, "hardware-envelopes", part.id, part.qty, "step")
        shape = _shape(path)
        source_hashes[str(path.relative_to(_repo(ctx)))] = sha256_file(path)
        instances = components[part.id]["instances"]
        if not instances:
            raise ValueError(f"R9 hardware instances missing: {part.id}")
        source_axis = instances[0].get("axis")
        for item in instances:
            low, high = item.get("bboxMinMm"), item.get("bboxMaxMm")
            if low is None or high is None:
                raise ValueError(f"R9 hardware bbox missing: {part.id}/{item.get('id')}")
            if part.id.startswith("7U40-R9-PCB-"):
                placed = shape.mirror("YZ") if item.get("side") == "RIGHT" else shape
                p_low, p_high, _ = _bbox(placed)
                center = _center(low, high)
                placed = placed.translate(tuple(center[i] - (p_low[i]+p_high[i])/2 for i in range(3)))
                category = "pcb"
            else:
                target_axis = item.get("axis") or source_axis
                if not source_axis or not target_axis:
                    raise ValueError(f"R9 hardware axis missing: {part.id}/{item.get('id')}")
                placed = _align_axis(shape, target_axis, low, high, source_axis)
                category = "hardware"
            data.append(_mesh_shape(part.id, PART_NAMES.get(part.id, part.id), category,
                                    item.get("id", f"{part.id}-{len(data)}"), placed))

    # Use the original, pinned 204 mm R6 source rail mesh, transformed by the
    # R9 source registration matrices. It is never rescaled from 60HP.
    rail_source = _repo(ctx) / "engineering" / "r6-body" / "source-data" / "rail40" / "nuts-v2-40hp-single.stl"
    rail_meta = json.loads((rail_source.parent / "rail_dimensions.json").read_text(encoding="utf-8"))
    if float(rail_meta["exact_mesh_measurements"]["long_axis_length_mm"]) != 204.0:
        raise ValueError("40HP source rail length differs from the confirmed 204 mm")
    source_hashes[str(rail_source.relative_to(_repo(ctx)))] = sha256_file(rail_source)
    rail_component = components["7U40-R9-HW-RAIL-UNIT-ENVELOPE"]
    for item in rail_component["instances"]:
        data.append(_rail_stl_mesh(rail_source, item["sourceTransform"], item["id"]))

    # Guard STEP files are assembly-coordinate shapes. The per-part quantity
    # rules are the mirrored copies used by the same R9 perimeter generator.
    guard_parts = [part for part in build_parts if part.id.startswith("7U40-R9-PA12-GUARD-")]
    for part in guard_parts:
        variant = "t1p2" if "T1P2" in part.id else "t1p0"
        role = part.id.rsplit("-", 1)[-1]
        path = ctx.out / "pa12" / "guards" / variant / f"{part.id.lower()}-qty{part.qty}-mm.step"
        shape = _shape(path)
        source_hashes[str(path.relative_to(_repo(ctx)))] = sha256_file(path)
        for suffix, placed in _copy_guard(shape, part.qty):
            record = _mesh_shape(part.id, GUARD_NAMES.get(role, "PA12ガード"), "guard",
                                 f"{part.id}-{suffix}", placed, variant)
            record["defaultVisible"] = variant == "t1p2"
            data.append(record)

    # The four frame quarters and the lid plate already have explicit
    # assembly placement in their generated STEP files.
    lid_manifest_path = ctx.out / "pa12" / "lid" / "manifest.json"
    lid_manifest = json.loads(lid_manifest_path.read_text(encoding="utf-8"))
    lid_parts = [part for part in build_parts if part.id.startswith("7U40-R9-") and
                 (part.id == "7U40-R9-LID-PLATE" or part.id.startswith("7U40-R9-PA12-LID-FRAME-"))]
    lid_files = {item["partId"]: item["path"] for item in lid_manifest["deliverables"]
                 if item["path"].endswith(".step")}
    for part in lid_parts:
        if part.id == "7U40-R9-LID-PLATE":
            path = _part_path(ctx, "aluminum", part.id, part.qty, "step")
            name, category = PART_NAMES[part.id], "lid"
        else:
            path = ctx.root / lid_files[part.id]
            name, category = f"PA12蓋枠 / {part.id.rsplit('-', 1)[-1]}", "lid"
        shape = _shape(path)
        source_hashes[str(path.relative_to(_repo(ctx)))] = sha256_file(path)
        data.append(_mesh_shape(part.id, name, category, part.id, shape))

    # This transparent mesh is an explicit display envelope only: panel 2 mm
    # plus provisional knob height, not a model of every module.
    metal = params["body"]["metal_thickness"]["value"]
    rise = params["lid"]["module_panel_thickness"]["value"] + params["lid"]["knob_envelope_height"]["value"]
    case_height = params["body"]["case_height"]["value"]
    body_meshes = [mesh for mesh in data if mesh["category"] == "aluminum" and
                   mesh["partId"] in ("7U40-R9-AL-BOTTOM", "7U40-R9-AL-FRONT-BACK", "7U40-R9-AL-LEFT-RIGHT")]
    case_depth = max(mesh["bboxMaxMm"][1] for mesh in body_meshes) - min(mesh["bboxMinMm"][1] for mesh in body_meshes)
    panel = cq.Solid.makeBox(float(params["body"]["rail_length"]["value"]),
                             max(1.0, case_depth - 12.0), rise,
                             cq.Vector(-float(params["body"]["rail_length"]["value"])/2,
                                       -max(1.0, case_depth-12.0)/2,
                                       float(case_height)-float(metal)))
    panel_thickness = params["lid"]["module_panel_thickness"]["value"]
    knob_height = params["lid"]["knob_envelope_height"]["value"]
    knob = _mesh_shape("7U40-R9-PREVIEW-KNOB-ENVELOPE",
                       f"パネル厚{panel_thickness:g} mm＋ノブ高さ{knob_height:g} mm（仮）",
                       "provisional-envelope", "KNOB-ENVELOPE", panel)
    knob["defaultVisible"] = False
    knob["provisional"] = True
    data.append(knob)

    data.sort(key=lambda item: (item["partId"], item["instanceId"]))
    return data, source_hashes


class _Raster:
    """Small deterministic RGBA PNG writer for vector section line art."""
    def __init__(self, width: int, height: int, color=(248, 250, 252, 255)):
        self.width, self.height = width, height
        self.pixels = bytearray(color * (width * height))

    def pixel(self, x: int, y: int, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 4
            self.pixels[offset:offset+4] = bytes(color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color, thickness=1):
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        dx, sx = abs(x1-x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1-y0), 1 if y0 < y1 else -1
        error = dx + dy
        while True:
            radius = max(0, thickness//2)
            for yy in range(y0-radius, y0+radius+1):
                for xx in range(x0-radius, x0+radius+1):
                    self.pixel(xx, yy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2*error
            if e2 >= dy:
                error += dy
                x0 += sx
            if e2 <= dx:
                error += dx
                y0 += sy

    def rect(self, x0: int, y0: int, x1: int, y1: int, color, fill=False):
        if fill:
            for y in range(max(0, y0), min(self.height, y1+1)):
                for x in range(max(0, x0), min(self.width, x1+1)):
                    self.pixel(x, y, color)
        else:
            self.line(x0, y0, x1, y0, color)
            self.line(x1, y0, x1, y1, color)
            self.line(x1, y1, x0, y1, color)
            self.line(x0, y1, x0, y0, color)

    def text(self, x: int, y: int, value: str, color=(48, 58, 68, 255), scale=2):
        for char in value.lower():
            glyph = _FONT.get(char, _FONT["?"])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.rect(x + col*scale, y + row*scale,
                                  x + (col+1)*scale-1, y + (row+1)*scale-1,
                                  color, fill=True)
            x += 6 * scale

    def png(self) -> bytes:
        raw = b"".join(b"\0" + self.pixels[y*self.width*4:(y+1)*self.width*4]
                       for y in range(self.height))
        def chunk(kind: bytes, payload: bytes) -> bytes:
            body = kind + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
        return (b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


_FONT = {
    " ": ("00000",)*7, "?": ("01110","10001","00010","00100","00100","00000","00100"),
    "-": ("00000","00000","00000","11111","00000","00000","00000"),
    ".": ("00000","00000","00000","00000","00000","00110","00110"),
    "/": ("00001","00010","00010","00100","01000","01000","10000"),
    ":": ("00000","00110","00110","00000","00110","00110","00000"),
    "_": ("00000","00000","00000","00000","00000","00000","11111"),
    "+": ("00000","00100","00100","11111","00100","00100","00000"),
    "=": ("00000","11111","00000","11111","00000","00000","00000"),
    "0": ("01110","10001","10011","10101","11001","10001","01110"),
    "1": ("00100","01100","00100","00100","00100","00100","01110"),
    "2": ("01110","10001","00001","00010","00100","01000","11111"),
    "3": ("11110","00001","00001","01110","00001","00001","11110"),
    "4": ("00010","00110","01010","10010","11111","00010","00010"),
    "5": ("11111","10000","10000","11110","00001","00001","11110"),
    "6": ("01110","10000","10000","11110","10001","10001","01110"),
    "7": ("11111","00001","00010","00100","01000","01000","01000"),
    "8": ("01110","10001","10001","01110","10001","10001","01110"),
    "9": ("01110","10001","10001","01111","00001","00001","01110"),
    **{chr(code): glyph for code, glyph in zip(range(ord("a"), ord("z")+1), (
        ("01110","10001","10001","11111","10001","10001","10001"),
        ("11110","10001","10001","11110","10001","10001","11110"),
        ("01111","10000","10000","10000","10000","10000","01111"),
        ("11110","10001","10001","10001","10001","10001","11110"),
        ("11111","10000","10000","11110","10000","10000","11111"),
        ("11111","10000","10000","11110","10000","10000","10000"),
        ("01111","10000","10000","10111","10001","10001","01111"),
        ("10001","10001","10001","11111","10001","10001","10001"),
        ("01110","00100","00100","00100","00100","00100","01110"),
        ("00111","00010","00010","00010","10010","10010","01100"),
        ("10001","10010","10100","11000","10100","10010","10001"),
        ("10000","10000","10000","10000","10000","10000","11111"),
        ("10001","11011","10101","10101","10001","10001","10001"),
        ("10001","11001","10101","10011","10001","10001","10001"),
        ("01110","10001","10001","10001","10001","10001","01110"),
        ("11110","10001","10001","11110","10000","10000","10000"),
        ("01110","10001","10001","10001","10101","10010","01101"),
        ("11110","10001","10001","11110","10100","10010","10001"),
        ("01111","10000","10000","01110","00001","00001","11110"),
        ("11111","00100","00100","00100","00100","00100","00100"),
        ("10001","10001","10001","10001","10001","10001","01110"),
        ("10001","10001","10001","10001","10001","01010","00100"),
        ("10001","10001","10001","10101","10101","10101","01010"),
        ("10001","10001","01010","00100","01010","10001","10001"),
        ("10001","10001","01010","00100","00100","00100","00100"),
        ("11111","00001","00010","00100","01000","10000","11111"),
    ))}
}


def _section_segments(shape: cq.Shape, point: tuple[float, float, float], normal: tuple[float, float, float],
                      axes: tuple[int, int]) -> list[list[tuple[float, float]]]:
    plane = gp_Pln(gp_Pnt(*point), gp_Dir(*normal))
    section = BRepAlgoAPI_Section(shape.wrapped, plane, False)
    section.Build()
    result = cq.Shape.cast(section.Shape())
    contours = []
    for edge in result.Edges():
        count = max(2, min(64, int(edge.Length()/1.0) + 2))
        points, _ = edge.sample(count)
        contours.append([(float(p.toTuple()[axes[0]]), float(p.toTuple()[axes[1]])) for p in points])
    return contours


def _draw_geometry(raster: _Raster, shapes: list[tuple[cq.Shape, str]],
                   point: tuple[float, float, float], normal: tuple[float, float, float],
                   axes: tuple[int, int], view: tuple[float, float, float, float]) -> int:
    xmin, xmax, ymin, ymax = view
    viewport = (70, 105, 900, 405)
    x0, y0, x1, y1 = viewport
    scale = min((x1-x0)/(xmax-xmin), (y1-y0)/(ymax-ymin))
    pad_x = (x1-x0 - (xmax-xmin)*scale)/2
    pad_y = (y1-y0 - (ymax-ymin)*scale)/2
    def project(p):
        return (x0+pad_x+(p[0]-xmin)*scale,
                y1-pad_y-(p[1]-ymin)*scale)
    def clip(first, second):
        dx, dy = second[0]-first[0], second[1]-first[1]
        lower, upper = 0.0, 1.0
        for p, q in ((-dx, first[0]-xmin), (dx, xmax-first[0]),
                     (-dy, first[1]-ymin), (dy, ymax-first[1])):
            if abs(p) < 1e-12:
                if q < 0:
                    return None
                continue
            ratio = q / p
            if p < 0:
                lower = max(lower, ratio)
            else:
                upper = min(upper, ratio)
            if lower > upper:
                return None
        return ((first[0]+lower*dx, first[1]+lower*dy),
                (first[0]+upper*dx, first[1]+upper*dy))
    segment_count = 0
    for shape, color in shapes:
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) + (255,)
        contours = _section_segments(shape, point, normal, axes)
        for contour in contours:
            for first, second in zip(contour, contour[1:]):
                visible = clip(first, second)
                if visible is None:
                    continue
                a, b = project(visible[0]), project(visible[1])
                raster.line(*a, *b, rgb, thickness=2)
                segment_count += 1
    return segment_count


def _old_value(repo: Path, namespace: str, key: str, value) -> object:
    if namespace == "slots":
        return {
            "slot_width": "R6 round hole dia 5.5 mm",
            "slot_length": "R6 round hole dia 5.5 mm",
            "slot_travel": "R6 round hole; 0 mm adjustment",
        }.get(key, "R6 had nominal round holes; value not recorded")
    if namespace == "guards":
        return {
            "fitClearancePerSide": "R6 fit not validated / unset",
            "adhesiveLayer": "R6 retention not selected / unset",
            "splitEndRelief": "R6 continuous edge / no split relief",
        }.get(key, value)
    r8 = {
        "top_edge_lid_locator_clearance": ("locatorClearanceToGuardMm", "7u40"),
        "lid_rise": ("lidRiseMm", "7u40"),
        "locator_engagement": ("locatorEngagementMm", "7u40"),
        "locator_thickness": ("locatorThicknessMm", "7u40"),
    }
    if key in r8:
        preview = json.loads((repo / "engineering" / "r8-preview" / "preview-parameters.json").read_text())
        return preview[r8[key][1]][r8[key][0]]
    return value


def _param_sections(ctx: BuildContext, params: dict, part_shapes: dict[str, cq.Shape]) -> list[dict]:
    out = ctx.out / "preview" / "sections"
    out.mkdir(parents=True, exist_ok=True)
    repo = _repo(ctx)
    hole_layout = json.loads((ctx.out / "aluminum" / "hole-layout.json").read_text(encoding="utf-8"))
    slot = next(hole for hole in hole_layout["holes"] if hole["profile"] == "slot")
    plate_id = slot["plateId"]
    slot_center = slot["centerAssemblyMm"][:2]
    slot_shape = part_shapes[plate_id]

    side_local = _shape(_part_path(ctx, "aluminum", "7U40-R9-AL-LEFT-RIGHT", 2, "step"))
    side_panel = side_local
    guard_t1p2 = part_shapes["7U40-R9-PA12-GUARD-T1P2-TOP-A"].mirror("YZ")
    guard_t1p0 = part_shapes["7U40-R9-PA12-GUARD-T1P0-TOP-A"].mirror("YZ")
    lid_frame = part_shapes["7U40-R9-PA12-LID-FRAME-FR"]
    front_body = _shape(_part_path(ctx, "aluminum", "7U40-R9-AL-FRONT-BACK", 2, "step"))
    front_panel = front_body

    entries = []
    for namespace in ("slots", "guards", "lid"):
        for key, record in params[namespace].items():
            if record["status"] not in ("candidate", "provisional", "unvalidated") or record["unit"] == "sha256":
                continue
            param_id = f"{namespace}.{key}"
            filename = f"{namespace}-{key}.png"
            raster = _Raster(SECTION_WIDTH, SECTION_HEIGHT)
            raster.rect(0, 0, SECTION_WIDTH-1, 58, (229, 235, 240, 255), fill=True)
            raster.text(34, 18, "r9-prototype-01 / unapproved", scale=2)
            raster.text(34, 72, param_id, scale=2)
            raster.rect(60, 98, 910, 410, (255, 255, 255, 255), fill=True)
            raster.rect(60, 98, 910, 410, (190, 201, 211, 255))
            if namespace == "slots":
                cx, cy = slot_center
                view = (cx-18, cx+18, cy-18, cy+18)
                section_segments = _draw_geometry(raster, [(slot_shape, PALETTE["aluminum"])],
                                                  (0, 0, 0.75), (0, 0, 1), (0, 1), view)
                section_title = "R9 body plate / real slot-plan section"
                value_view = f"new {record['value']} {record['unit']} / {record['status']}"
            elif namespace == "guards":
                view = (110, 119, 84, 98)
                # The source profile is the R9 generated channel BREP. A real
                # transformed R9 side plate is cut by the same section plane.
                actual_guard = guard_t1p0 if key == "comparison_thickness" else guard_t1p2
                section_segments = _draw_geometry(raster, [(side_panel, PALETTE["aluminum"]),
                                                           (actual_guard, PALETTE["guard"])],
                                                  (0, -40, 0), (0, 1, 0), (0, 2), view)
                section_title = "R9 side plate + PA12 guard / real section"
                value_view = f"new {record['value']} {record['unit']} / {record['status']}"
            else:
                view = (-174, -157, 76, 128)
                section_segments = _draw_geometry(raster, [(front_panel, PALETTE["aluminum"]),
                                                           (guard_t1p2, PALETTE["guard"]),
                                                           (lid_frame, PALETTE["lid"])],
                                                  (50, 0, 0), (1, 0, 0), (1, 2), view)
                section_title = "R9 front panel + guard + lid locator / real section"
                value_view = f"new {record['value']} {record['unit']} / {record['status']}"
            if section_segments == 0:
                raise ValueError(f"empty CAD section for {param_id}")
            raster.text(76, 116, section_title, color=(34, 48, 61, 255), scale=1)
            old = _old_value(repo, namespace, key, record["value"])
            raster.text(76, 434, f"old {str(old)}", scale=1)
            raster.text(76, 456, value_view, scale=1)
            raster.text(76, 485, "CAD section; no physical fit or strength validation", scale=1)
            image_path = out / filename
            image_path.write_bytes(raster.png())
            if image_path.stat().st_size >= LIMIT_BYTES:
                raise ValueError(f"section image exceeds 25 MiB: {image_path}")
            entries.append({
                "paramId": param_id,
                "namespace": namespace,
                "key": key,
                "unit": record["unit"],
                "status": record["status"],
                "old": old,
                "new": record["value"],
                "reason": record["note"],
                "source": record["source"],
                "sectionKind": namespace,
                "image": f"sections/{filename}",
            })
    index_path = out / "index.json"
    index_path.write_text(json.dumps({"revision": ctx.revision, "model": ctx.model, "units": "mm",
                                      "status": "unapproved_prototype", "sections": entries},
                                     indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entries


def _file_table(ctx: BuildContext, build_parts: list[Part]) -> dict:
    packages = {
        "aluminum": "7u40-r9-prototype-01-aluminum-NOT-APPROVED.zip",
        "pa12": "7u40-r9-prototype-01-pa12-NOT-APPROVED.zip",
        "coupons": "7u40-r9-prototype-01-coupons-NOT-APPROVED.zip",
    }
    names = dict(PART_NAMES)
    names.update({part.id: GUARD_NAMES.get(part.id.rsplit("-", 1)[-1], part.id)
                  for part in build_parts if "PA12-GUARD" in part.id})
    names.update({part.id: f"PA12蓋枠 / {part.id.rsplit('-', 1)[-1]}"
                  for part in build_parts if "PA12-LID-FRAME" in part.id})
    records: dict[str, dict] = {}
    for path in sorted(ctx.out.rglob("*-qty*-mm.*")):
        if "preview" in path.relative_to(ctx.out).parts:
            continue
        stem = path.name.rsplit(".", 1)[0]
        marker = "-qty"
        if marker not in stem:
            continue
        part_id, quantity = stem.rsplit(marker, 1)
        if not part_id.upper().startswith("7U40-R9-") or not quantity.endswith("-mm"):
            continue
        quantity = int(quantity[:-3])
        category = path.relative_to(ctx.out).parts[0]
        suffix = path.suffix[1:].lower()
        record = records.setdefault(part_id.upper(), {
            "partId": part_id.upper(), "name": names.get(part_id.upper(), part_id),
            "quantity": quantity, "category": category, "formats": [],
            "packageZip": packages.get(category),
            "packageStatus": "planned / not generated by preview task" if category in packages else "display envelope / no package",
            "status": "未承認 / 製作候補",
        })
        if record["quantity"] != quantity:
            raise ValueError(f"R9 file quantity mismatch for {part_id}")
        file = {"format": suffix, "path": str(path.relative_to(_repo(ctx))),
                "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if file["bytes"] >= LIMIT_BYTES:
            raise ValueError(f"R9 artifact exceeds 25 MiB: {path}")
        record["formats"].append(file)
    for item in records.values():
        item["formats"].sort(key=lambda file: (file["format"], file["path"]))
    return {"revision": ctx.revision, "model": ctx.model, "units": "mm",
            "status": "unapproved_prototype", "packageNames": packages,
            "parts": sorted(records.values(), key=lambda row: row["partId"])}


def build(ctx: BuildContext) -> list[Part]:
    """Read earlier module exports and create deterministic preview-only data."""
    out = ctx.out / "preview"
    out.mkdir(parents=True, exist_ok=True)
    params = ctx.params
    body_manifest = json.loads((ctx.out / "hardware-envelopes" / "body-manifest.json").read_text(encoding="utf-8"))
    build_parts = []
    for component in body_manifest["components"]:
        part_id = component["id"]
        if part_id.startswith("7U40-R9-AL-"):
            category = "aluminum"
        else:
            category = "hardware-envelopes"
        qty = len(component["instances"])
        # Some repeated geometry has one exported exemplar and several
        # assembly instances. Keep that distinction in the catalog.
        if part_id == "7U40-R9-AL-BOTTOM": qty = 1
        if part_id == "7U40-R9-AL-FRONT-BACK" or part_id == "7U40-R9-AL-LEFT-RIGHT": qty = 2
        build_parts.append(Part(part_id, cq.Solid.makeBox(1, 1, 1), category, "generated R9 geometry", qty,
                                ("step", "stl", "dxf") if category == "aluminum" else ("step", "stl")))
    for variant in ("t1p2", "t1p0"):
        manifest = json.loads((ctx.out / "pa12" / "guards" / variant / "manifest.json").read_text(encoding="utf-8"))
        for row in manifest["parts"]:
            part_id = row["id"]
            build_parts.append(Part(part_id, cq.Solid.makeBox(1, 1, 1), "pa12", "PA12-HP", row["quantity"], ()))
    lid_manifest = json.loads((ctx.out / "pa12" / "lid" / "manifest.json").read_text(encoding="utf-8"))
    for part_id in lid_manifest["parts"]:
        category = "aluminum" if part_id == "7U40-R9-LID-PLATE" else "pa12"
        qty = 1
        build_parts.append(Part(part_id, cq.Solid.makeBox(1, 1, 1), category, "generated R9 geometry", qty,
                                ("step", "stl", "dxf") if category == "aluminum" else ()))

    meshes, source_hashes = _scene_meshes(ctx, params, build_parts)
    part_shapes = {part_id: _shape(_part_path(ctx, "aluminum", part_id, qty, "step"))
                   for part_id, qty in (("7U40-R9-AL-BOTTOM", 1),
                                        ("7U40-R9-AL-FRONT-BACK", 2),
                                        ("7U40-R9-AL-LEFT-RIGHT", 2))}
    part_shapes.update({part.id: _shape(ctx.out / "pa12" / "guards" /
                                       ("t1p2" if "T1P2" in part.id else "t1p0") /
                                       f"{part.id.lower()}-qty{part.qty}-mm.step")
                        for part in build_parts if "PA12-GUARD" in part.id})
    part_shapes.update({part.id: _shape(ctx.root / next(file["path"] for file in lid_manifest["deliverables"]
                                                         if file["partId"] == part.id))
                        for part in build_parts if "PA12-LID-FRAME" in part.id})
    part_shapes["7U40-R9-LID-PLATE"] = _shape(_part_path(ctx, "aluminum", "7U40-R9-LID-PLATE", 1, "step"))
    section_entries = _param_sections(ctx, params, part_shapes)

    raw = json.dumps({
        "revision": ctx.revision,
        "model": ctx.model,
        "units": "mm",
        "status": "unapproved_prototype",
        "parts": meshes,
        "parameters": {namespace: {key: item["value"] for key, item in values.items()}
                       for namespace, values in params.items()},
        "geometrySources": {
            "r9": "Generated R9 body/slot/guard/lid STEP geometry",
            "r6Rail": "Original R6 source-data/rail40/nuts-v2-40hp-single.stl; length 204 mm",
            "mixesR8Mesh": False,
        },
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    compressed = buffer.getvalue()
    encoded = base64.b64encode(compressed).decode("ascii")
    model_path = out / "model-data.js"
    model_path.write_text("window.ZUDO_R9_MODEL_GZIP = " + json.dumps(encoded) + ";\n", encoding="utf-8")

    table = _file_table(ctx, build_parts)
    table_path = out / "file-table.json"
    table_path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checks = {
        "revision": ctx.revision,
        "model": ctx.model,
        "units": "mm",
        "status": "unapproved_prototype",
        "meshPartCount": len(meshes),
        "uniquePartIds": len({mesh["partId"] for mesh in meshes}),
        "partsSorted": [(mesh["partId"], mesh["instanceId"]) for mesh in meshes] ==
                       sorted((mesh["partId"], mesh["instanceId"]) for mesh in meshes),
        "railInstanceCount": sum(mesh["partId"] == "R6-40HP-RAIL-DISPLAY" for mesh in meshes),
        "railSourceLengthMm": 204,
        "parameterSectionCount": len(section_entries),
        "modelJsonBytes": len(raw),
        "gzipBytes": len(compressed),
        "noR8Meshes": not any("r8" in mesh["partId"].lower() for mesh in meshes),
        "sourceHashes": dict(sorted(source_hashes.items())),
    }
    checks_path = out / "mesh-checks.json"
    checks_path.write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for path in out.rglob("*"):
        if path.is_file() and path.stat().st_size >= LIMIT_BYTES:
            raise ValueError(f"R9 preview output exceeds 25 MiB: {path}")
    return []
