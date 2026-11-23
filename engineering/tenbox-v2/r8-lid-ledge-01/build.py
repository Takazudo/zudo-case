#!/usr/bin/env python3
"""Connect the obsolete split-roof ledge gaps in the R8 lid front/back part.

Additive-only revision; all original R5-R8 sources remain immutable.
Run in the pinned Python3.12.14 / CadQuery2.7.0 / NumPy2.3.5 / SciPy1.17.0
environment. The source package includes inputs/ and tools/ for standalone use.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import platform
import re
import shutil
import struct
import zipfile

import cadquery as cq
import numpy as np
import scipy
from scipy.spatial import cKDTree
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "design-config.json").read_text())
LOCAL_INPUTS = ROOT / "inputs"
BASE = ROOT.parent / "r5/source"
CAD = LOCAL_INPUTS if LOCAL_INPUTS.is_dir() else BASE / "10box-v2-r5/step"
PROJECTS = LOCAL_INPUTS if LOCAL_INPUTS.is_dir() else BASE / "h2d-r5/projects"
HELPER = ROOT / "tools/bambu_3mf.py"
if not HELPER.exists():
    HELPER = BASE / "h2d-r5/tools/bambu_3mf.py"
spec = importlib.util.spec_from_file_location("bambu_lid_ledge", HELPER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
MESH = re.compile(rb"<mesh>.*?</mesh>", re.S)
STEM = "10box-v2-lid-frontback-connected-r01"
TOL = 1e-6


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return np.array(box.Get())


def cuboid(v):
    return cq.Solid.makeBox(*(v[i+3]-v[i] for i in range(3)), cq.Vector(*v[:3]))


def shape_mesh(shape):
    vv, ff = shape.tessellate(0.06, 0.20)
    points, lookup, mapping = [], {}, []
    for v in vv:
        p = tuple(round(float(a), 8) for a in v.toTuple())
        if p not in lookup:
            lookup[p] = len(points)
            points.append(p)
        mapping.append(lookup[p])
    triangles = [[mapping[i] for i in face] for face in ff]
    points, triangles, report = h.validate_mesh(points, triangles, "lid front/back")
    adjacency = [set() for _ in points]
    for a, b, c in triangles:
        adjacency[a].update([b, c])
        adjacency[b].update([a, c])
        adjacency[c].update([a, b])
    visited, stack = set(), [0]
    while stack:
        i = stack.pop()
        if i not in visited:
            visited.add(i)
            stack.extend(adjacency[i] - visited)
    require(len(visited) == len(points), "Mesh must be one connected component")
    report["connected_components"] = 1
    return np.array(points), triangles, report


def mesh_xml(points, triangles):
    rows = ["<mesh>", "<vertices>"]
    rows.extend('<vertex x="%s" y="%s" z="%s" />' % tuple(h.fmt(x) for x in p) for p in points)
    rows += ["</vertices>", "<triangles>"]
    rows.extend('<triangle v1="%d" v2="%d" v3="%d" />' % tuple(t) for t in triangles)
    return ("\n".join(rows + ["</triangles>", "</mesh>"])).encode()


def archive_mesh(data):
    root = h.parse_xml(data[h.MODEL], h.MODEL)
    objects = root.findall(f'{h.q("resources")}/{h.q("object")}')
    require([o.get("id") for o in objects] == ["1", "2"], "Unexpected project hierarchy")
    mesh = objects[0].find(h.q("mesh"))
    require(mesh is not None, "Expected one mesh")
    component = objects[1].find(f'{h.q("components")}/{h.q("component")}')
    require(component is not None and component.get("objectid") == "1" and
            component.get("transform") == h.IDENTITY, "Unexpected component pose")
    items = root.findall(f'{h.q("build")}/{h.q("item")}')
    require(len(items) == 1 and items[0].get("objectid") == "2", "Expected one part per plate")
    a = np.array([float(x) for x in items[0].get("transform").split()])
    matrix = np.eye(4)
    matrix[:3, :3] = a[:9].reshape(3, 3).T
    matrix[:3, 3] = a[9:]
    points = np.array([[float(v.get(k)) for k in "xyz"] for v in mesh.findall(f'{h.q("vertices")}/{h.q("vertex")}')])
    triangles = [[int(t.get(k)) for k in ["v1", "v2", "v3"]] for t in mesh.findall(f'{h.q("triangles")}/{h.q("triangle")}')]
    return points, triangles, matrix


def recover_pose(source, target):
    """Find the saved proper rigid pose; diagonal placement is retained."""
    candidates = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product([-1., 1.], repeat=3):
            axes = np.eye(3)[list(perm)] * np.array(signs)[:, None]
            if np.linalg.det(axes) < 0.5:
                continue
            for degrees in (0, 45):
                a = math.radians(degrees)
                yaw = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
                rotation = yaw @ axes
                posed = source @ rotation.T
                if np.max(np.abs(np.ptp(posed, axis=0) - np.ptp(target, axis=0))) > .0001:
                    continue
                translation = target.min(0) - posed.min(0)
                posed += translation
                error = max(float(cKDTree(target).query(posed)[0].max()), float(cKDTree(posed).query(target)[0].max()))
                candidates.append((error, rotation, translation))
    candidates.sort(key=lambda x: x[0])
    require(candidates and candidates[0][0] < .0001, "Saved print pose could not be verified")
    require(len(candidates) == 1 or candidates[1][0] > 1, "Ambiguous print pose")
    error, rotation, translation = candidates[0]
    return rotation, translation, error


def write_stl(path, points, triangles):
    data = bytearray(("10BOX-v2 connected lid ledge; millimeters; print two".encode()).ljust(80, b" "))
    data += struct.pack("<I", len(triangles))
    for face in triangles:
        a, b, c = points[list(face)]
        normal = np.cross(b-a, c-a)
        normal /= np.linalg.norm(normal)
        data += struct.pack("<12fH", *normal, *a, *b, *c, 0)
    path.write_bytes(data)
    dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3,3)), ('attribute', '<u2')])
    raw_points = np.frombuffer(path.read_bytes(), dtype=dtype, count=len(triangles), offset=84)['vertices'].astype(float).reshape(-1,3)
    pts, inverse = np.unique(raw_points, axis=0, return_inverse=True)
    tris = inverse.reshape(-1,3).tolist()
    _, _, audit = h.validate_mesh(pts.tolist(), tris, path.name)
    require(np.max(np.abs(np.asarray(pts).min(0) - points.min(0))) < .0001, "STL readback minimum changed")
    require(np.max(np.abs(np.asarray(pts).max(0) - points.max(0))) < .0001, "STL readback maximum changed")
    return audit


def print_project(pid, old_shape, new_shape, out):
    template = PROJECTS / (pid + ".3mf")
    original = h.read_archive(template)
    cleaned = dict(original)
    require(not h.clear_generated_data(cleaned, geometry_changed=True) and cleaned == original,
            "Unexpected generated caches in the frozen source project")
    old_local, _, build = archive_mesh(original)
    old_world = (np.c_[old_local, np.ones(len(old_local))] @ build.T)[:, :3]
    source, _, _ = shape_mesh(old_shape)
    rotation, translation, error = recover_pose(source, old_world)
    points, triangles, mesh_check = shape_mesh(new_shape)
    world = points @ rotation.T + translation
    local = (np.c_[world, np.ones(len(world))] @ np.linalg.inv(build).T)[:, :3]
    require(np.allclose(local.min(0), old_local.min(0), atol=.0001, rtol=0) and
            np.allclose(local.max(0), old_local.max(0), atol=.0001, rtol=0), "Saved part footprint changed")
    updated = dict(original)
    updated[h.MODEL], count = MESH.subn(lambda _: mesh_xml(local, triangles), original[h.MODEL])
    require(count == 1, "Expected exactly one mesh replacement")
    path = out / "projects" / (pid + "-connected-r01.3mf")
    # Keep each saved member's timestamps/attributes rather than introducing
    # the build clock into the new 3MF. Only the model payload differs, and the
    # archive is byte-repeatable when regenerated from the source package.
    require(not path.exists(), "Existing print project preserved")
    with zipfile.ZipFile(template) as frozen, zipfile.ZipFile(path, "w") as target:
        for info in frozen.infolist():
            target.writestr(copy.copy(info), updated[info.filename])
    actual = h.read_archive(path)
    changed = [n for n in original if original[n] != actual[n]]
    require(set(actual) == set(original) and changed == [h.MODEL], "Unexpected archive changes")
    require(MESH.sub(b"<mesh />", actual[h.MODEL]) == MESH.sub(b"<mesh />", original[h.MODEL]),
            "Model metadata or print placement changed")
    checks = h.validate_project(actual, original, layout=True)
    require(checks["settings_bytes_unchanged"] and not checks["contains_toolpaths"], "Settings/toolpath regression")
    conf = h.parse_xml(actual[h.OBJECTS], h.OBJECTS)
    overrides = {e.get("key"): e.get("value") for e in conf.find("object").findall("metadata")}
    settings = h.settings(actual)
    brim = float(overrides["brim_width"]) + float(overrides["brim_object_gap"])
    envelope = np.r_[world.min(0)[:2]-brim, world.max(0)[:2]+brim]
    # Frozen common nozzle area is x25..325,y0..320. Wrap exclusion starts y310.
    require(envelope[0] >= 25 and envelope[1] >= 0 and envelope[2] <= 325 and envelope[3] < 310,
            "Saved brim envelope exceeds the nozzle area or wrapping exclusion")
    require(abs(world.min(0)[2]) < 1e-7, "Part not grounded")
    return local, triangles, {
        "part": pid, "file": str(path.relative_to(out)), "source_sha256": digest(template),
        "sha256": digest(path), "changed_archive_members": changed,
        "model_metadata_and_pose_unchanged": True, "global_settings_bytes_unchanged": True,
        "object_plate_settings_bytes_unchanged": actual[h.OBJECTS] == original[h.OBJECTS],
        "rotation": rotation.tolist(), "translation": translation.tolist(), "pose_recovery_error_mm": error,
        "bounds_xyz_mm": [world.min(0).tolist(), world.max(0).tolist()],
        "brim_envelope_xy_mm": envelope.tolist(), "brim_and_exclusion_check_passed": True,
        "printer": settings["printer_model"], "nozzle_diameter_mm": settings["nozzle_diameter"],
        "filament_presets": settings["filament_settings_id"],
        "mesh": mesh_check, "structural_validation": checks,
        "studio_application_loaded": False, "sliced": False
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    require(not out.exists(), "Choose a new output directory")
    versions = [platform.python_version(), cq.__version__, np.__version__, scipy.__version__]
    require(versions == ["3.12.14", "2.7.0", "2.3.5", "1.17.0"], "Use the pinned CAD environment")
    for name, expected in CFG["input_sha256"].items():
        path = (PROJECTS if name.endswith(".3mf") else CAD) / name
        require(digest(path) == expected, "Input changed: " + name)
    for folder in ["step", "projects", "source/inputs", "source/tools"]:
        (out/folder).mkdir(parents=True, exist_ok=True)
    old = {pid: cq.importers.importStep(str(CAD/(pid+".step"))).val()
           for pid in ["lid-front", "lid-back", "lid-top-single"]}
    require(old["lid-front"].rotate((0,0,0),(0,0,1),180).cut(old["lid-back"]).Volume() < TOL and
            old["lid-back"].cut(old["lid-front"].rotate((0,0,0),(0,0,1),180)).Volume() < TOL,
            "Front/back are no longer one common part")
    overlap = CFG["fusion_overlap_mm"]
    blocks = [cuboid([a-overlap, CFG["wall_inner_y"]-overlap, CFG["bridge_bottom_z"],
                      b+overlap, CFG["bridge_inner_y"], CFG["bridge_top_z"]])
              for a, b in CFG["gap_x_intervals"]]
    front = old["lid-front"]
    for block in blocks:
        front = front.fuse(block).clean()
    new = {"lid-front": front, "lid-back": front.rotate((0,0,0),(0,0,1),180)}
    allowed = blocks[0].fuse(blocks[1])
    reports = []
    common_points = common_faces = None
    for pid, shape in new.items():
        before = old[pid]
        region = allowed if pid == "lid-front" else allowed.rotate((0,0,0),(0,0,1),180)
        added = shape.cut(before)
        removed = before.cut(shape).Volume()
        outside = added.cut(region).Volume()
        roof_before = before.intersect(old["lid-top-single"]).Volume()
        roof_after = shape.intersect(old["lid-top-single"]).Volume()
        require(shape.isValid() and len(shape.Solids()) == 1, "Expected one valid CAD solid")
        require(removed < TOL and outside < TOL, "Change escaped the two bridge regions")
        require(np.allclose(bounds(shape), bounds(before), atol=TOL, rtol=0), "Overall bounds changed")
        require(roof_after <= roof_before + TOL, "New roof interference")
        strip = cuboid([-160,-144.99,103.1,160,-142.01,107.5])
        if pid == "lid-back":
            strip = strip.rotate((0,0,0),(0,0,1),180)
        require(len(before.intersect(strip).Solids()) == 5 and len(shape.intersect(strip).Solids()) == 3,
                "Two central ledge gaps must close while two outer windows stay open")
        step = out/"step"/(pid+".step")
        cq.exporters.export(shape, str(step))
        # STEP geometry is unchanged; fix only the exporter timestamp so repeated
        # source-package builds have identical output and receipt bytes.
        step.write_text(re.sub(r"(FILE_NAME\('[^']*',)'[^']*'", r"\1'2026-11-24T00:00:00'", step.read_text(), count=1))
        readback = cq.importers.importStep(str(step)).val()
        require(readback.isValid() and abs(readback.Volume()-shape.Volume()) < TOL, "STEP readback changed")
        points, faces, project = print_project(pid, before, shape, out)
        if pid == "lid-front":
            common_points, common_faces = points - points.min(0), faces
        reports.append({"part": pid, "cad_valid": True, "solid_count": 1,
                        "bounds_assembly_mm": bounds(shape).tolist(), "volume_before_mm3": before.Volume(),
                        "volume_after_mm3": shape.Volume(), "added_volume_mm3": added.Volume(),
                        "removed_volume_mm3": removed, "added_outside_target_regions_mm3": outside,
                        "ledge_sections_before": 5, "ledge_sections_after": 3,
                        "roof_overlap_before_mm3": roof_before, "roof_overlap_after_mm3": roof_after,
                        "roof_overlap_increase_mm3": roof_after-roof_before,
                        "step_sha256": digest(step), "project": project})
    stl = out/(STEM+".stl")
    stl_check = write_stl(stl, common_points, common_faces)
    shutil.copy2(out/"projects/lid-front-connected-r01.3mf", out/(STEM+".3mf"))
    for name in CFG["input_sha256"]:
        shutil.copy2((PROJECTS if name.endswith(".3mf") else CAD)/name, out/"source/inputs"/name)
    for name in ["build.py", "design-config.json"]:
        shutil.copy2(ROOT/name, out/"source"/name)
    if (ROOT/"render_preview.py").exists():
        shutil.copy2(ROOT/"render_preview.py", out/"source/render_preview.py")
    shutil.copy2(HELPER, out/"source/tools/bambu_3mf.py")
    report = {"revision": CFG["revision"], "base_commit": CFG["source_commit"], "units": "mm",
              "common_part_quantity": 2, "front_back_rotation_equivalence_degrees": 180,
              "cad_versions": versions, "parts": reports, "stl": {"file": stl.name,
              "sha256": digest(stl), "print_pose_dimensions_mm": np.ptp(common_points,axis=0).tolist(),
              "validation": stl_check}, "sliced": False, "studio_application_loaded": False,
              "physically_tested": False, "production_approved": False,
              "note": "Two legacy central ledge gaps filled only. Existing outer bracket windows, holes and inherited ledge height variations retained. No increase to inherited roof overlap."}
    write_json(out/"validation.json", report)
    print(json.dumps({"output": str(out), "stl": stl.name, "quantity": 2,
                      "parts": [{k:p[k] for k in ["part","added_volume_mm3","removed_volume_mm3","roof_overlap_increase_mm3"]} for p in reports]},indent=2))


if __name__ == "__main__":
    main()
