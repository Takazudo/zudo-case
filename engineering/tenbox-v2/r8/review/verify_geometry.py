"""Independent R8 review of saved meshes, exported STEP and frozen R7 inputs.

This verifier does not import the R8 generator or use its reported pass/fail
results. Native slot polygons, the committed R7 review/print archives and the
actual R8 meshes/STEP supply the independent evidence. Run from any directory:

  python review/verify_geometry.py --cad /path/to/cad --out /path/to/report.json

The result is nominal CAD/software evidence, not Studio or physical validation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import tempfile
import zipfile

import cadquery as cq
import numpy as np
from scipy.spatial import ConvexHull
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parents[4]
R7_REVIEW = ROOT / "public/downloads/candidate/tenbox-v2-r7-review.zip"
R7_PRINT = ROOT / "public/downloads/candidate/tenbox-v2-r7-print.zip"
RAIL_SOURCE = ROOT / "engineering/tenbox-v2/r5/source/research/zzmod/rail-3u60-geometry.json"
RAIL_PLACEMENT = ROOT / "engineering/tenbox-v2/r7/reference/rail-placement.json"
POSITION_TOL = 2e-6
VOLUME_TOL = 0.001


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bbox(shape):
    bound = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, bound, False, False)
    return np.asarray(bound.Get(), dtype=float)


def solid_box(bound):
    return cq.Solid.makeBox(*(bound[3:] - bound[:3]), cq.Vector(*bound[:3]))


def cylinder(radius, start, normal, length):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*start), cq.Vector(*normal))


def overlap_bounds(a, b):
    return bool(np.all(np.minimum(a[3:], b[3:]) - np.maximum(a[:3], b[:3]) > 1e-7))


def polygon_wire(points, matrix):
    local = np.asarray(points, dtype=float)
    world = np.c_[local, np.zeros(len(local)), np.ones(len(local))] @ matrix.T
    return cq.Wire.makePolygon([cq.Vector(*p[:3]) for p in world], close=True)


def source_panel(contour, matrix, only_hole=None):
    if only_hole is not None:
        outer = polygon_wire(contour["holes"][only_hole], matrix)
        holes = []
    else:
        outer = polygon_wire(contour["outer"], matrix)
        holes = [polygon_wire(hole, matrix) for hole in contour["holes"]]
    return cq.Solid.extrudeLinear(outer, holes, cq.Vector(*(matrix[:3, 2] * contour["thickness"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cad = args.cad.resolve()
    report = args.out.resolve()
    model = json.loads((cad / "model_data.json").read_text())
    parts = {part["id"]: part for part in model["parts"]}
    checks = []

    def record(name, passed, **details):
        checks.append({"check": name, "passed": bool(passed), **details})
        if not passed:
            print("FAIL " + name, flush=True)

    def points(part, data=model):
        return np.asarray(data["meshes"][part["mesh"]]["p"], dtype=float).reshape(-1, 3)

    def actual_bounds(part):
        vertices = points(part)
        return np.r_[vertices.min(axis=0), vertices.max(axis=0)]

    def circular_x_axis(part, data=model):
        # Cylinder tessellation may omit a cardinal extremum, so the bounding
        # box midpoint is not its axis. Fit the outer projected circular ring.
        projected = np.unique(points(part, data)[:, 1:3], axis=0)
        rim = projected[ConvexHull(projected).vertices]
        solution = np.linalg.lstsq(np.c_[2 * rim, np.ones(len(rim))], np.sum(rim * rim, axis=1), rcond=None)[0]
        center = solution[:2]
        radius = math.sqrt(solution[2] + center @ center)
        residual = float(np.max(np.abs(np.linalg.norm(rim - center, axis=1) - radius)))
        return center, radius, residual

    def same_mesh(current, previous, old_model, offset=None):
        a, b = points(current), points(previous, old_model)
        if a.shape != b.shape:
            return False, None
        expected = b if offset is None else b + offset
        deviation = float(np.max(np.abs(a - expected)))
        indices_equal = model["meshes"][current["mesh"]]["i"] == old_model["meshes"][previous["mesh"]]["i"]
        return indices_equal and deviation <= POSITION_TOL, deviation

    record("frozen R7 review archive hash", sha(R7_REVIEW) == "333de0929dc58a42acf04efa84a30da6f5dd550d5cd4b9fe1e03b06e3d4e6d36")
    record("frozen R7 print archive hash", sha(R7_PRINT) == "db851ff28b8391771d3d227be386c47703615d8c8028c8ce572ee744d65f6718")
    with zipfile.ZipFile(R7_REVIEW) as archive:
        old_model = json.loads(archive.read("model_data.json"))
        old_steps = {name: archive.read(name) for name in archive.namelist() if name.startswith("step/")}
    with zipfile.ZipFile(R7_PRINT) as archive:
        print_inventory = json.loads(archive.read("h2d-project-report.json"))
    old_parts = {part["id"]: part for part in old_model["parts"]}
    printed_ids = [pid for row in print_inventory["parts"] for pid in row["assembly_ids"]]
    record("23 unique physical printed parts retained", len(printed_ids) == len(set(printed_ids)) == 23 and set(printed_ids).issubset(parts))

    native = json.loads(RAIL_SOURCE.read_text())
    placement = json.loads(RAIL_PLACEMENT.read_text())
    contours = native["panelContours"]
    slot_centers = [float((np.asarray(hole)[:, 1].min() + np.asarray(hole)[:, 1].max()) / 2)
                    for hole in contours["frame3u"]["holes"][:2]]
    delta_z = slot_centers[1] - slot_centers[0]
    record("native source lower-slot selection and measured spacing", all(row["frameHoleIndex"] == 1 for group in native["mounts"] for row in group)
           and abs(delta_z - 12.631103) < 1e-9, source_slot_centers_mm=slot_centers, slot_center_spacing_mm=delta_z)

    moving_ids = [pid for pid in old_parts if pid.startswith("r7-rail-")]
    expected_current_ids = {pid.replace("r7-rail-", "r8-rail-", 1) if pid in moving_ids else pid for pid in old_parts}
    record("same assembly inventory with only native rail IDs revised", set(parts) == expected_current_ids,
           previous_part_count=len(old_parts), current_part_count=len(parts), missing=sorted(expected_current_ids - set(parts)), extra=sorted(set(parts) - expected_current_ids))
    record("eleven movable rail frame and padder parts", len(moving_ids) == 11,
           counts={cat: sum(old_parts[pid]["cat"] == cat for pid in moving_ids) for cat in ("rails", "railPCB", "railPads")})
    for old_id, old_part in old_parts.items():
        moving = old_id in moving_ids
        new_id = old_id.replace("r7-rail-", "r8-rail-", 1) if moving else old_id
        if new_id not in parts:
            continue
        okay, error = same_mesh(parts[new_id], old_part, old_model, np.array([0, 0, delta_z]) if moving else None)
        record(("rigid vertical native translation " if moving else "unchanged assembly mesh ") + new_id,
               okay, maximum_vertex_deviation_mm=error, translation_mm=[0, 0, delta_z] if moving else [0, 0, 0])

    print("Checked fixed geometry and eleven native translations", flush=True)
    printed_shapes = {}
    with tempfile.TemporaryDirectory(prefix="tenbox-r8-independent-") as temp:
        temporary = Path(temp)
        for pid in printed_ids:
            path = cad / "step" / (pid + ".step")
            old_bytes = old_steps.get("step/" + pid + ".step")
            if old_bytes is None and old_parts[pid]["group"] == "stand":
                # These four unchanged source-STL parts have never had STEP
                # exports. Their entire world mesh was compared above.
                okay, error = same_mesh(parts[pid], old_parts[pid], old_model)
                record("printed source-mesh stand unchanged " + pid, okay and not path.exists(),
                       comparison_method="identical full indexed world mesh; source is STL, no STEP export",
                       maximum_vertex_deviation_mm=error)
                continue
            shape = cq.importers.importStep(str(path)).val()
            printed_shapes[pid] = shape
            if path.read_bytes() == old_bytes:
                symmetric_difference = 0.0
                method = "identical exported STEP bytes"
            else:
                old_path = temporary / (pid + ".step")
                old_path.write_bytes(old_bytes)
                old_shape = cq.importers.importStep(str(old_path)).val()
                symmetric_difference = shape.cut(old_shape).Volume() + old_shape.cut(shape).Volume()
                method = "exact BRep symmetric difference of independently imported STEP"
            record("printed STEP shape unchanged " + pid, shape.isValid() and len(shape.Solids()) == 1 and symmetric_difference < VOLUME_TOL,
                   comparison_method=method, symmetric_difference_mm3=symmetric_difference)

    # Recreate source panels independently from frozen contour polygons. The R7
    # frame top measures its module plane; no R8 config or generated matrix is used.
    old_frame_planes = [float(points(old_parts[pid], old_model)[:, 2].max()) for pid in moving_ids if old_parts[pid]["cat"] == "railPCB"]
    old_plane = old_frame_planes[0]
    panel_plane = old_plane + delta_z
    record("four source frame planes agree", max(old_frame_planes) - min(old_frame_planes) < POSITION_TOL)
    panel_solids = {}
    panel_matrices = {}
    lower_voids = {}
    for source_part in placement["parts"]:
        if not source_part.get("panel"):
            continue
        pid = "r8-rail-" + source_part["id"]
        matrix = np.asarray(source_part["matrix"], dtype=float)
        matrix[2, 3] += panel_plane - placement["panel_plane_z_mm"]
        contour = contours[source_part["panel"]]
        shape = source_panel(contour, matrix)
        panel_solids[pid] = shape
        panel_matrices[pid] = matrix
        source_vertices = np.asarray(native["geometries"][source_part["panel"]]["positions"], dtype=float).reshape(-1, 3)
        expected = (np.c_[source_vertices, np.ones(len(source_vertices))] @ matrix.T)[:, :3]
        observed = points(parts[pid])
        record("actual mesh matches independently transformed native contour " + pid,
               expected.shape == observed.shape and np.allclose(expected, observed, atol=POSITION_TOL, rtol=0),
               source_polygon_sha256=contour["sha256"], extrusion_thickness_mm=contour["thickness"])
        if source_part["panel"] == "frame3u":
            lower_voids[pid] = source_panel(contour, matrix, only_hole=1)

    # Recover each actual screw axis from its mesh, then prove that its full
    # diameter lies in the specifically selected lower void, not merely in air.
    mount_rows = []
    for side, sign in (("left", -1), ("right", 1)):
        for index in range(1, 5):
            pid = f"rail-bolt-{side}-{index}"
            bounds = actual_bounds(parts[pid])
            (y, z), bolt_head_radius, bolt_axis_fit_residual = circular_x_axis(parts[pid])
            row_name = "front" if y < 0 else "rear"
            frame_id = f"r8-rail-{row_name}-frame3u-{sign}-0"
            pad_id = f"r8-rail-{row_name}-pad3u-{sign}-1"
            frame = panel_solids[frame_id]
            frame_bounds = bbox(frame)
            probe = cylinder(2.5, [frame_bounds[0], y, z], [1, 0, 0], frame_bounds[3] - frame_bounds[0])
            outside_void = probe.cut(lower_voids[frame_id]).Volume()
            material_overlap = frame.intersect(probe).Volume()
            pad_bounds = bbox(panel_solids[pad_id])
            pad_probe = cylinder(2.5, [pad_bounds[0], y, z], [1, 0, 0], pad_bounds[3] - pad_bounds[0])
            pad_overlap = panel_solids[pad_id].intersect(pad_probe).Volume()
            old_axis, _, _ = circular_x_axis(old_parts[pid], old_model)
            spacer_id = f"spacer-{side}-{index}"
            spacer_bounds = actual_bounds(parts[spacer_id])
            spacer_axis, spacer_radius, spacer_axis_fit_residual = circular_x_axis(parts[spacer_id])
            wall = printed_shapes["body-" + side]
            wall_probe = cylinder(2.5, [-180, y, z], [1, 0, 0], 360)
            wall_overlap = wall.intersect(wall_probe).Volume()
            entry = {"bolt": pid, "frame": frame_id, "axis_y_z_mm": [float(y), float(z)],
                     "lower_slot_index": 1, "lower_slot_center_z_mm": panel_plane - slot_centers[1],
                     "shaft_volume_outside_lower_void_mm3": outside_void, "frame_overlap_mm3": material_overlap,
                     "padder_overlap_mm3": pad_overlap, "case_wall_overlap_mm3": wall_overlap,
                     "bolt_axis_circle_fit_residual_mm": bolt_axis_fit_residual,
                     "spacer_axis_circle_fit_residual_mm": spacer_axis_fit_residual}
            mount_rows.append(entry)
            record("actual fixed M5 axis inside lower frame slot " + pid,
                   outside_void < VOLUME_TOL and material_overlap < VOLUME_TOL and pad_overlap < VOLUME_TOL
                   and wall_overlap < VOLUME_TOL and abs(z - (panel_plane - slot_centers[1])) < POSITION_TOL
                   and np.allclose([y, z], old_axis, atol=POSITION_TOL, rtol=0)
                   and np.allclose([y, z], spacer_axis, atol=POSITION_TOL, rtol=0)
                   and abs(bolt_head_radius - 6) < POSITION_TOL and abs(spacer_radius - 5) < POSITION_TOL
                   and max(bolt_axis_fit_residual, spacer_axis_fit_residual) < POSITION_TOL
                   and abs(spacer_bounds[3] - spacer_bounds[0] - 8) < POSITION_TOL, **entry)
    record("model identifies the verified lower slot", model["mountParameters"]["selected_frame_slot"] == "lower")

    print("Checked eight lower-slot axes and 23 printed shapes (19 STEP, four source meshes)", flush=True)
    rows = model["bracketParameters"]["fasteners"]
    row_by_id = {row["id"]: row for row in rows}
    record("all 52 complete bracket fasteners retained", len(rows) == len(row_by_id) == 52)
    record("all 26 bracket bodies retained", sum(part["cat"] == "brackets" for part in parts.values()) == 26)
    record("eight complete sidewall joints retained", sum(row["axis"] == "wall" and row["wall"] in ("body-left", "body-right") for row in rows) == 8)
    normal_map = {"body-left": [1, 0, 0], "body-right": [-1, 0, 0], "body-front": [0, 1, 0], "body-back": [0, -1, 0],
                  "lid-left": [1, 0, 0], "lid-right": [-1, 0, 0], "lid-front": [0, 1, 0], "lid-back": [0, -1, 0]}
    analytic_solids = {}
    nut_envelopes = {}
    for row in rows:
        normal = np.array([0, 0, 1] if row["axis"] == "floor" else [0, 0, -1] if row["axis"] == "roof" else normal_map[row["wall"]], dtype=float)
        ids = row["parts"]
        nut = next(parts[pid] for pid in ids if parts[pid].get("fastenerRole") == "nut")
        bolt = next(parts[pid] for pid in ids if parts[pid].get("fastenerRole") == "bolt")
        washer = next(parts[pid] for pid in ids if parts[pid].get("fastenerRole") == "washer")
        npj, bpj, wpj = (points(part) @ normal for part in (nut, bolt, washer))
        exterior = np.asarray(row["exterior_xyz_mm"])
        seat = np.asarray(row["nut_seat_xyz_mm"])
        bearing = np.asarray(row["head_bearing_xyz_mm"])
        projection = float(bpj.max() - npj.max())
        engagement = float(min(bpj.max() - npj.min(), npj.max() - npj.min()))
        orientation = (np.allclose(row["inward_normal"], normal, atol=1e-8, rtol=0)
                       and np.allclose([npj.min(), npj.max()], [seat @ normal, seat @ normal + row["nut_height_mm"]], atol=1e-5, rtol=0)
                       and np.allclose([bpj.min(), bpj.max()], [bearing @ normal - 1.4, bearing @ normal + row["nominal_screw_length_mm"]], atol=1e-5, rtol=0)
                       and np.allclose([wpj.min(), wpj.max()], [exterior @ normal - 1, exterior @ normal], atol=1e-5, rtol=0)
                       and npj.min() > exterior @ normal)
        record("mesh proves inside bracket nut and outside head " + row["id"], orientation,
               thread_projection_mm=projection, nut_height_mm=float(npj.max() - npj.min()))
        record("full nut engagement from actual meshes " + row["id"], projection >= -1e-5 and engagement >= row["nut_height_mm"] - 1e-5,
               engaged_length_mm=engagement)
        # Conservative exact cylinders enclose the tessellated circular parts.
        analytic_solids[bolt["id"]] = cylinder(6, bearing - normal * 1.4, normal, 1.4).fuse(
            cylinder(2.5, bearing, normal, row["nominal_screw_length_mm"])).clean()
        analytic_solids[washer["id"]] = cylinder(7.5, exterior - normal, normal, 1).cut(
            cylinder(2.5, exterior - normal * 2, normal, 3)).clean()
        envelope = cylinder(8 / math.sqrt(3), seat, normal, row["nut_height_mm"]).cut(
            cylinder(2.5, seat - normal, normal, row["nut_height_mm"] + 2)).clean()
        analytic_solids[nut["id"]] = envelope
        nut_envelopes[row["id"]] = envelope
        delta = points(washer) - bearing
        radial = np.linalg.norm(delta - np.outer(delta @ normal, normal), axis=1)
        record("L bracket washer retains OD15 ID5 " + row["id"], np.allclose([radial.min(), radial.max()], [2.5, 7.5], atol=1e-5, rtol=0))
    record("34 thin and 18 regular bracket nuts retained", sum(abs(row["nut_height_mm"] - 2.7) < 1e-6 for row in rows) == 34
           and sum(abs(row["nut_height_mm"] - 4) < 1e-6 for row in rows) == 18)
    for bracket_id in sorted({row["bracket"] for row in rows}):
        bracket_rows = [row for row in rows if row["bracket"] == bracket_id]
        distance = nut_envelopes[bracket_rows[0]["id"]].distance(nut_envelopes[bracket_rows[1]["id"]])
        record("orthogonal nuts clear at every rotation " + bracket_id, distance > 0.68, minimum_distance_mm=distance)
    rail_nuts = [part for part in parts.values() if part["id"].startswith("rail-nut-")]
    record("eight independent rail nuts stay outside", len(rail_nuts) == 8 and all(np.abs(points(part)[:, 0]).min() >= 169.7 - POSITION_TOL for part in rail_nuts))

    # Build exact planar-faced solids from displayed bracket meshes only when
    # needed. Other round hardware uses conservative analytic envelopes above.
    triangulated = {}

    def mesh_solid(part):
        if part["id"] in triangulated:
            return triangulated[part["id"]]
        vertices = points(part)
        triangles = np.asarray(model["meshes"][part["mesh"]]["i"]).reshape(-1, 3)
        faces = [cq.Face.makeFromWires(cq.Wire.makePolygon([cq.Vector(*vertices[index]) for index in tri], close=True)) for tri in triangles]
        solid = cq.Solid.makeSolid(cq.Shell.makeShell(faces)).clean()
        if solid.Volume() < 0:
            solid = cq.Solid(solid.wrapped.Reversed())
        record("independently reconstructed displayed hardware solid " + part["id"], solid.isValid() and len(solid.Solids()) == 1)
        triangulated[part["id"]] = solid
        return solid

    def hardware_solid(part):
        if part["id"] in analytic_solids:
            return analytic_solids[part["id"]]
        return mesh_solid(part)

    native_rail_envelopes = {pid: solid_box(actual_bounds(part)) for pid, part in parts.items() if pid.startswith("r8-rail-") and part["cat"] == "rails"}
    obstacles = {**panel_solids, **native_rail_envelopes}
    obstacle_bounds = {pid: bbox(shape) for pid, shape in obstacles.items()}
    hardware = [part for part in parts.values() if part["cat"] in ("brackets", "washers", "hardware", "railHardware")]
    collision_pairs = []
    candidate_pairs = 0
    lid_candidate_pairs = 0
    for part in hardware:
        # The nut envelope is slightly wider than the chosen hexagon angle.
        shape = analytic_solids.get(part["id"])
        bound = bbox(shape) if shape is not None else actual_bounds(part)
        conflicts = []
        for obstacle_id, obstacle in obstacles.items():
            if not overlap_bounds(bound, obstacle_bounds[obstacle_id]):
                continue
            candidate_pairs += 1
            lid_candidate_pairs += part["group"] == "lid"
            shape = hardware_solid(part)
            volume = shape.intersect(obstacle).Volume()
            if volume > VOLUME_TOL:
                conflict = {"hardware": part["id"], "native_part": obstacle_id, "overlap_mm3": volume}
                conflicts.append(conflict)
                collision_pairs.append(conflict)
        record("complete hardware clears raised rails frames and padders " + part["id"], not conflicts,
               includes_lid_hardware=part["group"] == "lid", collisions=conflicts)

    shell_pairs = []
    for native_id, shape in obstacles.items():
        conflicts = []
        for printed_id, printed in printed_shapes.items():
            if parts[printed_id]["group"] not in ("body", "lid"):
                continue
            if not overlap_bounds(obstacle_bounds[native_id], bbox(printed)):
                continue
            volume = shape.intersect(printed).Volume()
            if volume > VOLUME_TOL:
                conflicts.append({"printed_part": printed_id, "overlap_mm3": volume})
        record("raised native assembly clears retained body and lid " + native_id, not conflicts, collisions=conflicts)
        shell_pairs.extend({"native_part": native_id, **row} for row in conflicts)

    # The source frame top defines the module plane, and the roof STEP defines
    # its underside. Compute capacity from those actual geometric surfaces.
    actual_planes = [float(points(part)[:, 2].max()) for part in parts.values() if part["cat"] == "railPCB"]
    roof_underside = float(bbox(printed_shapes["lid-top-single"])[2])
    capacity = roof_underside - max(actual_planes)
    knob_clearance = capacity - 27
    record("retained roof capacity and 27mm envelope shortfall measured", max(actual_planes) - min(actual_planes) < POSITION_TOL
           and abs(max(actual_planes) - 88.131103) < POSITION_TOL and abs(capacity - 19.868897) < POSITION_TOL
           and knob_clearance < 0, rail_plane_z_mm=max(actual_planes), roof_underside_z_mm=roof_underside,
           capacity_above_module_plane_mm=capacity, assumed_panel_plus_knob_mm=27, assumed_envelope_clearance_mm=knob_clearance,
           assumed_envelope_fits=False)

    print("Checked complete body/lid hardware and retained lid capacity", flush=True)
    # Recover the exact supported ledges from exported sidewall STEP and measure
    # their clearance to each actual bracket body, retaining the accepted 3 mm.
    for wall_id, sign in (("body-left", -1), ("body-right", 1)):
        clip = np.array([-163.6999, -150, -1, -153.7, 150, 76] if sign < 0 else [153.7, -150, -1, 163.6999, 150, 76])
        ledges = [bbox(shape) for shape in printed_shapes[wall_id].intersect(solid_box(clip)).Solids()]
        record("two supported ledges retained " + wall_id, len(ledges) == 2)
        for part in parts.values():
            if part["cat"] != "brackets" or part.get("attachmentWall") != wall_id or part["group"] != "body":
                continue
            bound = actual_bounds(part)
            candidates = [ledge for ledge in ledges if abs(ledge[2] - (41.02 if bound[1] < 0 else 5.02)) < 0.001]
            gap = min(min(abs(ledge[1] - bound[4]), abs(ledge[4] - bound[1])) for ledge in candidates)
            record("bracket to supported ledge gap retained " + part["id"], abs(gap - 3) < 1e-5, gap_mm=float(gap))

    result = {
        "revision": "10BOX-V2-R8", "reviewed_model_sha256": sha(cad / "model_data.json"),
        "input": str(cad), "source_review_sha256": sha(R7_REVIEW), "source_print_sha256": sha(R7_PRINT),
        "native_contour_source_sha256": sha(RAIL_SOURCE), "verifier_sha256": sha(Path(__file__)),
        "scope": "Independent saved-mesh comparison, exported STEP equality, exact native lower-slot containment, fixed mounting stacks, full body/lid hardware clearance including conservative rotating-nut and native-rail envelopes, and geometric lid capacity. No R8 generator imports or generated pass/fail receipts were used.",
        "checks": checks, "check_count": len(checks), "all_passed": all(row["passed"] for row in checks),
        "mounting_axes": mount_rows, "native_hardware_candidate_pairs": candidate_pairs,
        "lid_hardware_candidate_pairs": lid_candidate_pairs, "hardware_collisions": collision_pairs,
        "body_lid_collisions": shell_pairs,
        "lid": {"rail_plane_z_mm": max(actual_planes), "roof_underside_z_mm": roof_underside,
                "capacity_above_module_plane_mm": capacity, "assumed_panel_plus_knob_mm": 27,
                "assumed_envelope_clearance_mm": knob_clearance, "assumed_envelope_fits": False},
        "native_studio_load": "not_performed", "native_studio_slice": "not_performed",
        "physical_print_fit_load": "not_performed", "production_approved": False,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"report": str(report), "checks": len(checks), "all_passed": result["all_passed"],
                      "failures": [row for row in checks if not row["passed"]]}, indent=2), flush=True)
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
