"""R9 guard candidates; dimensions and assembly coordinates are millimetres."""
from __future__ import annotations

import json
import math

import cadquery as cq

from .common import export_step, export_stl, inspect_binary_stl, sha256_file
from .types import BuildContext, Part


def guard_section(params: dict) -> cq.Shape:
    """Edge channel for body guards and fit coupons.

    The metal exterior face is local X=0; its edge is Z=0. Extrusion runs
    along +Y for ``length``. Fit and adhesive allowances are separate empty
    spaces. ``orientation='bottom'`` reverses Z. Adhesion is unvalidated.
    """
    t, metal, cover, overhang, fit, adhesive, length = (
        float(params[key]) for key in ("t", "metalThickness", "cover",
        "innerOverhang", "fitClearancePerSide", "adhesiveLayer", "length"))
    orientation = params.get("orientation", "top")
    gap = fit + adhesive
    if orientation not in ("top", "bottom") or not all(math.isfinite(v) for v in
            (t, metal, cover, overhang, fit, adhesive, length)):
        raise ValueError("invalid guard section parameter")
    if min(t, metal, cover, overhang, length) <= 0 or min(fit, adhesive) < 0 or gap <= 0 or gap >= min(t, overhang):
        raise ValueError("guard channel walls or slip-fit gap invalid")
    points = [(-metal-overhang, t), (t, t), (t, -cover),
              (gap, -cover), (gap, gap), (-metal-gap, gap),
              (-metal-gap, -cover), (-metal-overhang, -cover)]
    sign = 1 if orientation == "top" else -1
    wire = cq.Wire.makePolygon([cq.Vector(x, 0, sign*z) for x, z in points], close=True)
    solid = cq.Solid.extrudeLinear(wire, [], cq.Vector(0, length, 0))
    radius = float(params.get("edgeRounding", 0))
    if radius < 0 or radius >= min(t, cover):
        raise ValueError("invalid exterior edge rounding")
    if radius:
        edge = [e for e in solid.Edges() if e.geomType() == "LINE" and
                abs(e.Length()-length) < 1e-6 and
                abs(e.BoundingBox().xmin-t) < 1e-6 and
                abs(e.BoundingBox().zmin-sign*t) < 1e-6]
        if len(edge) != 1:
            raise ValueError("exterior rounding edge missing")
        solid = solid.fillet(radius, edge).clean()
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError("invalid guard section solid")
    return solid


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0, y0, z0))


def _edge(params, length, angle, x, y, z, orientation):
    section = guard_section({**params, "length": length, "orientation": orientation})
    return section.rotate((0, 0, 0), (0, 0, 1), angle).translate(cq.Vector(x, y, z))


def _perimeter(params, width, depth, z, orientation):
    t = params["t"]
    edges = [
        _edge(params, width+2*t, -90, -width/2-t, -depth/2, z, orientation),
        _edge(params, width+2*t, 90, width/2+t, depth/2, z, orientation),
        _edge(params, depth+2*t, 180, -width/2, depth/2+t, z, orientation),
        _edge(params, depth+2*t, 0, width/2, -depth/2-t, z, orientation),
    ]
    solid = edges[0].fuse(*edges[1:]).clean()
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError("invalid guard perimeter")
    return solid


def _clip(solid, x0, x1, y0, y1):
    part = solid.intersect(_box(x0, x1, y0, y1, -1000, 1000)).clean()
    if not part.isValid() or len(part.Solids()) != 1:
        raise ValueError("invalid split guard")
    return part


def _corner(params, width, depth, height):
    t = params["t"]
    gap = params["fitClearancePerSide"] + params["adhesiveLayer"]
    cover = params["cover"]
    x, y = -width/2, -depth/2
    a = _box(x-t, x-gap, y-t, y+cover, cover, height-cover)
    b = _box(x-t, x+cover, y-t, y-gap, cover, height-cover)
    solid = a.fuse(b).clean()
    radius = params["edgeRounding"]
    if radius:
        edge = [e for e in solid.Edges() if e.geomType() == "LINE" and
                abs(e.Length()-(height-2*cover)) < 1e-6 and
                abs(e.BoundingBox().xmin-(x-t)) < 1e-6 and
                abs(e.BoundingBox().ymin-(y-t)) < 1e-6]
        if len(edge) != 1:
            raise ValueError("vertical exterior rounding edge missing")
        solid = solid.fillet(radius, edge).clean()
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise ValueError("invalid vertical corner guard")
    return solid


def build(ctx: BuildContext) -> list[Part]:
    p = lambda key: ctx.value("guards", key)
    # The frozen exterior defines the guard envelope; cross-check its width
    # against the rail, PCB, spacer, and metal stack used by the body module.
    main = float(p("main_thickness"))
    width = float(p("top_edge_guard_exterior_x")) - 2*main
    depth = float(p("top_edge_guard_exterior_y")) - 2*main
    height = float(ctx.value("body", "case_height"))
    metal = float(ctx.value("body", "metal_thickness"))
    overhang = float(p("innerOverhang"))
    body_width = (float(ctx.value("body", "rail_length")) +
                  2*(float(ctx.value("body", "fixer_thickness")) +
                     float(ctx.value("body", "padder_thickness")) +
                     float(ctx.value("body", "inner_spacer")) + metal))
    if abs(width-body_width) > 1e-6:
        raise ValueError("frozen top-edge exterior width differs from body stack")
    checks = (
        ("top_edge_guard_exterior_x", width+2*main),
        ("top_edge_guard_exterior_y", depth+2*main),
        ("top_edge_guard_opening_x", width-2*(metal+overhang)),
        ("top_edge_guard_opening_y", depth-2*(metal+overhang)),
        ("top_edge_seated_guard_z", height+2*main),
    )
    for key, expected in checks:
        if p(key) is None or abs(float(p(key))-expected) > 1e-6:
            raise ValueError(f"frozen top-edge interface mismatch: {key}")
    # The frozen lid mirror is still null. Prototype-only candidate exports
    # carry an independent adhesive allowance until an actual tape is chosen.
    if p("top_edge_adhesive_allowance") is not None:
        raise ValueError("frozen adhesive interface changed without lid coordination")
    relief = float(p("splitEndRelief"))
    if not 0 < relief < 2:
        raise ValueError("split-end relief must be between 0 and 2 mm")
    result = []
    for variant, t in (("t1p2", main), ("t1p0", float(p("comparison_thickness")))):
        params = {"t": t, "metalThickness": metal, "cover": float(p("cover")),
                  "innerOverhang": overhang, "fitClearancePerSide": float(p("fitClearancePerSide")),
                  "adhesiveLayer": float(p("adhesiveLayer")),
                  "edgeRounding": float(p("edgeRounding"))}
        top = _perimeter(params, width, depth, height, "top")
        bottom = _perimeter(params, width, depth, 0, "bottom")
        h = relief/2
        parts = [
            ("TOP-A", 2, _clip(top, -1000, -h, -1000, -h)),
            ("TOP-B", 2, _clip(top, -1000, -h, h, 1000)),
            ("LOWER-WIDTH-HALF", 4, _clip(bottom, -1000, -h, -1000, -depth/2+float(p("cover")))),
            ("LOWER-DEPTH-A", 2, _clip(bottom, -1000, -width/2+float(p("cover")), -depth/2+float(p("cover")), -h)),
            ("LOWER-DEPTH-B", 2, _clip(bottom, -1000, -width/2+float(p("cover")), h, depth/2-float(p("cover")))),
            ("VERTICAL-CORNER", 4, _corner(params, width, depth, height)),
        ]
        manifest = {"revision": ctx.revision, "model": ctx.model, "variant": variant,
                    "units": "mm", "exportStatus": "prototype candidate; not approved for manufacture",
                    "retention": "candidate adhesive/tape layer inside slip-fit channel; adhesion and pull-off strength unvalidated",
                    "frozenTopEdgeAdhesiveAllowance": None,
                    "candidateAdhesiveLayerMm": params["adhesiveLayer"],
                    "candidateFitClearancePerSideMm": params["fitClearancePerSide"],
                    "parts": []}
        target = ctx.out / "pa12" / "guards" / variant
        target.mkdir(parents=True, exist_ok=True)
        for role, qty, solid in parts:
            part_id = f"7U40-R9-PA12-GUARD-{variant.upper()}-{role}"
            stem = f"{part_id.lower()}-qty{qty}-mm"
            step, stl = target / f"{stem}.step", target / f"{stem}.stl"
            export_step(solid, step)
            # OCC leaves spaces at line ends in STEP DATA records. Remove only
            # that insignificant whitespace so committed exports pass diff check.
            step.write_bytes(b"\n".join(line.rstrip(b" \t") for line in step.read_bytes().split(b"\n")))
            export_stl(solid, stl)
            mesh = inspect_binary_stl(stl, solid)
            manifest["parts"].append({"id": part_id, "quantity": qty,
                "cadVolumeMm3": solid.Volume(), "mesh": mesh,
                "files": [{"path": str(path.relative_to(ctx.root)), "sha256": sha256_file(path),
                           "bytes": path.stat().st_size} for path in (step, stl)]})
            result.append(Part(part_id, solid, "pa12", "PA12-HP black dyed candidate", qty, ()))
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
                                                        indent=2, sort_keys=True) + "\n")
    return result
