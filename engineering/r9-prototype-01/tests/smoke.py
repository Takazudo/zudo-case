"""Round-trip and byte-stability smoke test for the pinned local toolchain."""
from pathlib import Path
import sys
import argparse
import math
from tempfile import TemporaryDirectory
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cadquery as cq
import ezdxf
from r9.common import export_dxf, export_step, export_stl, inspect_binary_stl, write_zip
from r9.types import BuildContext, Part
from build import export_part, parse_modules


def assert_slot_dxf(path, center, angle):
    drawing = ezdxf.readfile(path)
    entities = [e for e in drawing.modelspace() if e.dxf.layer == "SLOTS"]
    lines = [e for e in entities if e.dxftype() == "LINE"]
    arcs = [e for e in entities if e.dxftype() == "ARC"]
    assert len(entities) == 4 and len(lines) == 2 and len(arcs) == 2
    assert all(abs(e.dxf.radius - 1.5) < 1e-8 for e in arcs)
    line_ends = [(e.dxf.start.x, e.dxf.start.y) for e in lines] + [
        (e.dxf.end.x, e.dxf.end.y) for e in lines
    ]
    for arc in arcs:
        for degrees in (arc.dxf.start_angle, arc.dxf.end_angle):
            radians = math.radians(degrees)
            endpoint = (arc.dxf.center.x + arc.dxf.radius * math.cos(radians),
                        arc.dxf.center.y + arc.dxf.radius * math.sin(radians))
            assert any(math.dist(endpoint, line_end) < 1e-8 for line_end in line_ends)
    if angle == 0:
        assert sorted(round(e.dxf.center.x, 6) for e in arcs) == [4.5, 11.5]
        assert all(abs(e.dxf.center.y - center[1]) < 1e-8 for e in arcs)
        assert all(abs(e.dxf.start.y - e.dxf.end.y) < 1e-8 for e in lines)
    else:
        assert sorted(round(e.dxf.center.y, 6) for e in arcs) == [-3.5, 3.5]
        assert all(abs(e.dxf.center.x - center[0]) < 1e-8 for e in arcs)
        assert all(abs(e.dxf.start.x - e.dxf.end.x) < 1e-8 for e in lines)
    return drawing


def main():
    assert parse_modules(None) == ("body", "slots", "guards", "lid", "coupons", "preview_data", "checks")
    assert parse_modules("body,slots") == ("body", "slots")
    for bad in ("body,body", "body,nope", "body,", ""):
        try:
            parse_modules(bad)
        except argparse.ArgumentTypeError:
            pass
        else:
            raise AssertionError(f"accepted invalid --only value: {bad!r}")
    # Through hole and elongated slot both pierce the plate.
    plate = cq.Workplane("XY").box(30, 20, 5).faces(">Z").workplane().pushPoints([(-9, 0)]).hole(4)
    plate = plate.faces(">Z").workplane().center(8, 0).slot2D(10, 3).cutThruAll().val()
    with TemporaryDirectory() as temporary:
        roots = [Path(temporary) / name for name in ("first", "second")]
        snapshots = []
        for root in roots:
            step, dxf, stl, archive = (root / f"sample.{suffix}" for suffix in ("step", "dxf", "stl", "zip"))
            vertical_dxf = root / "vertical.dxf"
            export_step(plate, step)
            export_dxf(dxf, [(-15, -10), (15, -10), (15, 10), (-15, 10)],
                       holes=[(-9, 0, 2)],
                       slots=[(8, 0, 10, 3, 0)])
            export_dxf(vertical_dxf, [(-15, -10), (15, -10), (15, 10), (-15, 10)],
                       slots=[(0, 0, 10, 3, 90)])
            export_stl(plate, stl)
            write_zip(archive, {"sample.step": step, "sample.dxf": dxf, "sample.stl": stl})
            imported = cq.importers.importStep(str(step)).val()
            assert imported.isValid() and abs(imported.Volume() - plate.Volume()) < 1e-4
            drawing = assert_slot_dxf(dxf, (8, 0), 0)
            assert_slot_dxf(vertical_dxf, (0, 0), 90)
            assert drawing.dxfversion == "AC1024" and drawing.units == ezdxf.units.MM
            assert {entity.dxf.layer for entity in drawing.modelspace()} == {"OUTLINE", "HOLES", "SLOTS"}
            assert len(list(drawing.modelspace().query("CIRCLE"))) == 1
            assert len(list(drawing.modelspace().query("LWPOLYLINE"))) == 1
            assert inspect_binary_stl(stl, plate)["closedManifold"]
            with zipfile.ZipFile(archive) as z:
                assert z.namelist() == sorted(z.namelist())
            snapshots.append({suffix: (root / f"sample.{suffix}").read_bytes() for suffix in ("step", "dxf", "stl", "zip")})
            snapshots[-1]["vertical.dxf"] = vertical_dxf.read_bytes()
        ctx = BuildContext(roots[0], roots[0] / "out", {})
        part = Part("7U40-R9-CPN-SMOKE", plate, "coupons", "test", 1,
                    ("step", "stl", "dxf"),
                    ((-15, -10), (15, -10), (15, 10), (-15, 10)),
                    ((-9, 0, 2),), ((8, 0, 10, 3, 0),))
        assert len(export_part(ctx, part)) == 3
        for suffix in snapshots[0]:
            assert snapshots[0][suffix] == snapshots[1][suffix], f"{suffix} export changed bytes"
    print("smoke: STEP/DXF/STL/ZIP round-trip and byte identity passed")


if __name__ == "__main__":
    main()
