"""Round-trip and byte-stability smoke test for the pinned local toolchain."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cadquery as cq
import ezdxf
from r9.common import export_dxf, export_step, export_stl, inspect_binary_stl, write_zip
from r9.types import BuildContext, Part
from build import export_part


def main():
    # Through hole and elongated slot both pierce the plate.
    plate = cq.Workplane("XY").box(30, 20, 5).faces(">Z").workplane().pushPoints([(-9, 0)]).hole(4)
    plate = plate.faces(">Z").workplane().center(8, 0).slot2D(10, 3).cutThruAll().val()
    with TemporaryDirectory() as temporary:
        roots = [Path(temporary) / name for name in ("first", "second")]
        snapshots = []
        for root in roots:
            step, dxf, stl, archive = (root / f"sample.{suffix}" for suffix in ("step", "dxf", "stl", "zip"))
            export_step(plate, step)
            export_dxf(dxf, [(-15, -10), (15, -10), (15, 10), (-15, 10)],
                       holes=[(-9, 0, 2)],
                       slots=[(8, 0, 10, 3)])
            export_stl(plate, stl)
            write_zip(archive, {"sample.step": step, "sample.dxf": dxf, "sample.stl": stl})
            imported = cq.importers.importStep(str(step)).val()
            assert imported.isValid() and abs(imported.Volume() - plate.Volume()) < 1e-4
            drawing = ezdxf.readfile(dxf)
            assert drawing.dxfversion == "AC1024" and drawing.units == ezdxf.units.MM
            assert {entity.dxf.layer for entity in drawing.modelspace()} == {"OUTLINE", "HOLES", "SLOTS"}
            assert len(list(drawing.modelspace().query("CIRCLE"))) == 1
            assert len(list(drawing.modelspace().query("LWPOLYLINE"))) == 2
            slot_entity = next(e for e in drawing.modelspace().query("LWPOLYLINE") if e.dxf.layer == "SLOTS")
            assert sum(abs(point[4]) == 1 for point in slot_entity) == 2
            assert inspect_binary_stl(stl, plate)["closedManifold"]
            with zipfile.ZipFile(archive) as z:
                assert z.namelist() == sorted(z.namelist())
            snapshots.append({suffix: (root / f"sample.{suffix}").read_bytes() for suffix in ("step", "dxf", "stl", "zip")})
        ctx = BuildContext(roots[0], roots[0] / "out", {})
        part = Part("7U40-R9-CPN-SMOKE", plate, "coupons", "test", 1,
                    ("step", "stl", "dxf"),
                    ((-15, -10), (15, -10), (15, 10), (-15, 10)),
                    ((-9, 0, 2),), ((8, 0, 10, 3),))
        assert len(export_part(ctx, part)) == 3
        for suffix in snapshots[0]:
            assert snapshots[0][suffix] == snapshots[1][suffix], f"{suffix} export changed bytes"
    print("smoke: STEP/DXF/STL/ZIP round-trip and byte identity passed")


if __name__ == "__main__":
    main()
