"""Deterministic prototype exports and mesh validation, all dimensions in mm."""
from __future__ import annotations

from collections import Counter, OrderedDict
from hashlib import sha256
from pathlib import Path
import math
from tempfile import NamedTemporaryFile
import re
import struct
import zipfile

import cadquery as cq
import ezdxf
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib


def sha256_file(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def export_step(shape: cq.Shape, path: Path) -> None:
    """Write STEP with a canonical ISO-10303 HEADER; preserve the OCC DATA section.

    CadQuery/OCC writes a creation date and application identity. Rewrite only
    FILE_NAME HEADER record and OCC translator product counter, plus stable line
    endings. Other DATA records are preserved. The smoke test checks repeated
    byte stability with the pinned toolchain.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(suffix=".step", dir=path.parent, delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        cq.exporters.export(shape, str(temporary), exportType="STEP")
        raw = temporary.read_text(encoding="utf-8").replace("\r\n", "\n")
        canonical = re.sub(
            r"FILE_NAME\s*\(.*?\);",
            "FILE_NAME('R9-PROTOTYPE-01','1970-01-01T00:00:00',('ZUDO CASE'),('ZUDO CASE'),'R9 prototype exporter','ZUDO CASE','');",
            raw, count=1, flags=re.DOTALL,
        )
        if canonical == raw:
            raise ValueError("STEP FILE_NAME header missing")
        # OCC increments this translator product suffix within a process.
        canonical = re.sub(r"Open CASCADE STEP translator ([0-9.]+) [0-9]+",
                           r"Open CASCADE STEP translator \1 0", canonical)
        path.write_bytes(canonical.encode("utf-8"))
    finally:
        temporary.unlink(missing_ok=True)


def export_dxf(path: Path, outline, holes=(), slots=()) -> None:
    """2-D plate drawing: closed outline, circular holes, and obround slots, R2010/mm.

    Each slot is (center_x, center_y, overall_length, width, angle_degrees).
    Angle 0 is horizontal; positive angles rotate counterclockwise in XY.
    Every slot is exactly two LINE and two ARC entities on SLOTS.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        doc = ezdxf.new("R2010", setup=False)
        doc.units = ezdxf.units.MM
        for layer in ("OUTLINE", "HOLES", "SLOTS"):
            doc.layers.new(layer)
        msp = doc.modelspace()
        msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": "OUTLINE"})
        for x, y, radius in holes:
            msp.add_circle((x, y), radius, dxfattribs={"layer": "HOLES"})
        for x, y, length, width, angle in slots:
            if width <= 0 or length <= width or not all(math.isfinite(v) for v in (x, y, length, width, angle)):
                raise ValueError("slot dimensions and angle must be finite; length must exceed positive width")
            straight = (length - width) / 2
            radius = width / 2
            theta = math.radians(angle)
            ux, uy = math.cos(theta), math.sin(theta)
            vx, vy = -uy, ux

            def point(along: float, across: float) -> tuple[float, float]:
                return (x + along * ux + across * vx,
                        y + along * uy + across * vy)

            left, right = point(-straight, 0), point(straight, 0)
            left_bottom, right_bottom = point(-straight, -radius), point(straight, -radius)
            right_top, left_top = point(straight, radius), point(-straight, radius)
            msp.add_line(left_bottom, right_bottom, dxfattribs={"layer": "SLOTS"})
            msp.add_arc(right, radius, start_angle=(angle - 90) % 360,
                        end_angle=(angle + 90) % 360, dxfattribs={"layer": "SLOTS"})
            msp.add_line(right_top, left_top, dxfattribs={"layer": "SLOTS"})
            msp.add_arc(left, radius, start_angle=(angle + 90) % 360,
                        end_angle=(angle + 270) % 360, dxfattribs={"layer": "SLOTS"})
        # ezdxf discovers some required classes from a set of in-use DXF types.
        # Register them here and sort the class table before saveas() so hash
        # randomization cannot reorder the otherwise identical CLASS records.
        doc.classes.add_required_classes(doc.dxfversion)
        doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
        doc.saveas(path)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous


STL_TESSELLATION_TOLERANCE_MM = 0.01
STL_ANGULAR_TOLERANCE_RAD = 0.1
STL_VOLUME_RELATIVE_TOLERANCE = 0.0005
STL_VOLUME_ABSOLUTE_TOLERANCE_MM3 = 0.1
STL_BBOX_TOLERANCE_MM = 0.0001


def export_stl(shape: cq.Shape, path: Path,
               tolerance=STL_TESSELLATION_TOLERANCE_MM,
               angular_tolerance=STL_ANGULAR_TOLERANCE_RAD) -> None:
    """Binary STL with fixed header and lexicographically ordered triangles."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vertices, faces = shape.tessellate(tolerance, angular_tolerance)
    records = []
    for face in faces:
        points = [tuple(float(v) for v in vertices[i].toTuple()) for i in face]
        # Rotation preserves winding while removing arbitrary first vertex.
        rotations = [points[i:] + points[:i] for i in range(3)]
        points = min(rotations)
        a, b, c = (np.asarray(p, dtype=np.float64) for p in points)
        normal = np.cross(b - a, c - a)
        length = np.linalg.norm(normal)
        if length == 0:
            raise ValueError("degenerate STL triangle")
        normal /= length
        records.append(struct.pack("<12fH", *normal, *points[0], *points[1], *points[2], 0))
    records.sort()
    header = b"ZUDO CASE R9-PROTOTYPE-01 mm".ljust(80, b"\0")
    path.write_bytes(header + struct.pack("<I", len(records)) + b"".join(records))


def write_zip(path: Path, entries: dict[str, Path | bytes]) -> None:
    """Stored ZIP; sorted POSIX entry names and DOS epoch timestamp."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(entries):
            if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                raise ValueError(f"unsafe ZIP entry: {name}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            source = entries[name]
            archive.writestr(info, source if isinstance(source, bytes) else Path(source).read_bytes())


def inspect_binary_stl(path: Path, cad_shape: cq.Shape | None = None, *,
                       allow_non_watertight: bool = False) -> dict:
    """Check closed oriented edge incidence, positive volume and bounding box."""
    raw = Path(path).read_bytes()
    if len(raw) < 84:
        raise ValueError("short STL")
    count = struct.unpack_from("<I", raw, 80)[0]
    if count == 0 or len(raw) != 84 + 50 * count:
        raise ValueError("invalid binary STL size")
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")])
    triangles = np.frombuffer(raw, dtype=dtype, offset=84, count=count)["vertices"].astype(np.float64)
    _, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    edges = Counter(tuple(sorted((int(a), int(b)))) for face in faces for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])))
    histogram = Counter(edges.values())
    volume = float(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)
    bbox_min = triangles.reshape(-1, 3).min(axis=0)
    bbox_max = triangles.reshape(-1, 3).max(axis=0)
    closed_manifold = histogram == {2: len(edges)}
    if (not closed_manifold or volume <= 0) and not allow_non_watertight:
        raise ValueError(f"non-watertight or inverted STL: {histogram}, volume={volume}")
    if cad_shape is not None:
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(cad_shape.wrapped, box, False, False)
        bb = cq.BoundBox(box)
        expected = np.array([bb.xlen, bb.ylen, bb.zlen])
        volume_tolerance = max(STL_VOLUME_ABSOLUTE_TOLERANCE_MM3,
                               cad_shape.Volume() * STL_VOLUME_RELATIVE_TOLERANCE)
        if abs(volume - cad_shape.Volume()) > volume_tolerance:
            raise ValueError("STL/CAD volume mismatch")
        if np.max(abs((bbox_max - bbox_min) - expected)) > STL_BBOX_TOLERANCE_MM:
            raise ValueError("STL/CAD bbox mismatch")
    return {"triangleCount": count, "closedManifold": closed_manifold,
            "edgeIncidenceHistogram": {str(key): value for key, value in sorted(histogram.items())},
            "positiveVolume": volume > 0, "volumeMm3": volume,
            "bboxMinMm": bbox_min.tolist(), "bboxMaxMm": bbox_max.tolist(),
            "dimensionsMm": (bbox_max - bbox_min).tolist()}
