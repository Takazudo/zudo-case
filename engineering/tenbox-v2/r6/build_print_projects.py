#!/usr/bin/env python3
"""Build the complete R6 unsliced H2D set without changing saved print settings.

Only the two sidewalls and common floor receive replacement meshes. All twelve
other archives are copied byte-for-byte from R5. The changed archives retain
their model XML outside <mesh>, including object IDs, components and build poses,
and retain every other ZIP member byte-for-byte. No slicer or printer is invoked.

Run with the exact R5 Python/CadQuery environment:
  python build_print_projects.py --cad /path/to/r6-cad --out /absent/print-folder
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import shutil
import sys

import cadquery as cq
import numpy as np
import scipy
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'r5' / 'source'
BASE_CAD = BASE / '10box-v2-r5'
BASE_PRINT = BASE / 'h2d-r5'
CHANGED = {'body-left', 'body-right', 'body-bottom-common'}
FLOOR = 'body-bottom-common'
MESH = re.compile(rb'<mesh>.*?</mesh>', re.S)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h = load_module('tenbox_r6_bambu', BASE_PRINT / 'tools/bambu_3mf.py')
sys.path.insert(0, str(BASE_PRINT))
import verify_studio_import_contract as studio_contract  # noqa: E402
import verify_flat_packages as independent  # noqa: E402


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jwrite(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def archive_mesh(data):
    """Read the actual simple mesh/component/build hierarchy, not preview data."""
    root = h.parse_xml(data[h.MODEL], h.MODEL)
    resources = root.findall(f'{h.q("resources")}/{h.q("object")}')
    require([o.get('id') for o in resources] == ['1', '2'], 'Unexpected resource IDs')
    mesh = resources[0].find(h.q('mesh'))
    require(mesh is not None, 'Object 1 must be the mesh')
    components = resources[1].findall(f'{h.q("components")}/{h.q("component")}')
    require(len(components) == 1 and components[0].get('objectid') == '1',
            'Object 2 must contain only mesh object 1')
    require(components[0].get('transform') == h.IDENTITY, 'Component pose changed')
    builds = root.findall(f'{h.q("build")}/{h.q("item")}')
    require(len(builds) == 1 and builds[0].get('objectid') == '2', 'Unexpected build')
    vertices = np.array([[float(v.get(a)) for a in 'xyz']
                         for v in mesh.findall(f'{h.q("vertices")}/{h.q("vertex")}')])
    triangles = [[int(t.get(a)) for a in ['v1', 'v2', 'v3']]
                 for t in mesh.findall(f'{h.q("triangles")}/{h.q("triangle")}')]
    transform = independent.matrix(builds[0].get('transform'))
    return vertices, triangles, transform, builds[0].get('transform')


def nearest_error(a, b):
    return max(float(cKDTree(b).query(a)[0].max()),
               float(cKDTree(a).query(b)[0].max()))


def source_points(model, pid):
    pid = 'body-bottom-back' if pid == FLOOR else pid
    part = next(p for p in model['parts'] if p['id'] == pid)
    return np.asarray(model['meshes'][part['mesh']]['p']).reshape(-1, 3)


def original_pose(pid, previous, old_local, build):
    old_world = (np.c_[old_local, np.ones(len(old_local))] @ build.T)[:, :3]
    source = source_points(previous, pid)
    if pid == FLOOR:
        recorded = json.loads((BASE_PRINT / 'floor-print-pose.json').read_text())
        rotation = np.array(recorded['rotation_matrix_row_major']).reshape(3, 3)
        translation = np.array(recorded['translation_mm'])
        error = nearest_error(source @ rotation.T + translation, old_world)
        require(error < 0.0001, 'Saved floor pose does not match the actual R5 project')
        proof = {'method': 'Saved R5 floor pose, checked against actual 3MF vertices',
                 'source_pose_sha256': sha(BASE_PRINT / 'floor-print-pose.json'),
                 'bidirectional_vertex_error_mm': error}
    else:
        candidates = []
        for perm in itertools.permutations(range(3)):
            for signs in itertools.product([-1., 1.], repeat=3):
                rotation = np.eye(3)[list(perm)] * np.array(signs)[:, None]
                if np.linalg.det(rotation) < 0.5:
                    continue
                posed = source @ rotation.T
                if np.max(np.abs(np.ptp(posed, axis=0) - np.ptp(old_world, axis=0))) > 0.0001:
                    continue
                translation = old_world.min(0) - posed.min(0)
                error = nearest_error(posed + translation, old_world)
                candidates.append((error, rotation, translation))
        candidates.sort(key=lambda row: row[0])
        require(candidates and candidates[0][0] < 0.0001, 'Cannot recover original flat pose')
        require(len(candidates) == 1 or candidates[1][0] > 1., 'Ambiguous original flat pose')
        error, rotation, translation = candidates[0]
        proof = {'method': 'All 24 proper signed axis permutations and bbox translation; bidirectional KD-tree comparison to actual R5 3MF vertices',
                 'bidirectional_vertex_error_mm': error,
                 'next_candidate_error_mm': candidates[1][0] if len(candidates) > 1 else None}
    require(np.allclose(rotation.T @ rotation, np.eye(3)) and
            abs(np.linalg.det(rotation) - 1.) < 1e-10, 'Pose must be a proper rigid rotation')
    return rotation, translation, proof


def step_mesh(path):
    solid = cq.importers.importStep(str(path)).val()
    require(solid.isValid() and len(solid.Solids()) == 1 and solid.Volume() > 0,
            f'{path.name}: expected one valid solid')
    vertices, triangles = solid.tessellate(0.06, 0.20)
    points, lookup, remap = [], {}, []
    for vertex in vertices:
        point = tuple(round(float(v), 8) for v in vertex.toTuple())
        if point not in lookup:
            lookup[point] = len(points)
            points.append(point)
        remap.append(lookup[point])
    triangles = [[remap[i] for i in triangle] for triangle in triangles]
    points, triangles, checked = h.validate_mesh(points, triangles, path.name)
    checked['single_valid_cad_solid'] = True
    checked['cad_volume_mm3'] = solid.Volume()
    return np.array(points), triangles, checked


def xml_mesh(points, triangles):
    # Lexical names remain unprefixed for the pinned Studio importer. The parent
    # model's existing default core namespace and p/BambuStudio declarations stay.
    lines = ['<mesh>', '        <vertices>']
    for p in points:
        lines.append('          <vertex ' + ' '.join(f'{a}="{h.fmt(p[i])}"'
                     for i, a in enumerate('xyz')) + ' />')
    lines += ['        </vertices>', '        <triangles>']
    lines += [f'          <triangle v1="{t[0]}" v2="{t[1]}" v3="{t[2]}" />'
              for t in triangles]
    lines += ['        </triangles>', '      </mesh>']
    return '\n'.join(lines).encode()


def layout_check(data, world, triangles, pid):
    settings = h.settings(data)
    conf = h.parse_xml(data[h.OBJECTS], h.OBJECTS)
    overrides = independent.meta(conf.find('object'))
    plate = independent.meta(conf.find('plate'))
    areas = [independent.rect(a) for a in settings['extruder_printable_area']]
    if pid == FLOOR:
        require(plate['filament_map_mode'] == 'Manual' and plate['filament_maps'] == '1 1',
                'Common floor must retain the explicit saved left-nozzle mapping')
        require(settings['physical_extruder_map'] == ['1', '0'], 'Physical nozzle map changed')
        area = areas[0]
        require(area.tolist() == [0., 0., 325., 320.], 'Unexpected left nozzle area')
    else:
        area = np.array([max(a[0] for a in areas), max(a[1] for a in areas),
                         min(a[2] for a in areas), min(a[3] for a in areas)])
    require(overrides['extruder'] == '1', 'Filament-slot override changed')
    brim_type = overrides.get('brim_type', settings['brim_type'])
    width = float(overrides.get('brim_width', settings['brim_width']))
    gap = float(overrides.get('brim_object_gap', settings['brim_object_gap']))
    allowance = 0. if brim_type == 'no_brim' else width + gap
    lo, hi = world.min(0), world.max(0)
    envelope = np.r_[lo[:2] - allowance, hi[:2] + allowance]
    require(independent.inside(envelope, area), f'{pid}: mesh/brim exceeds saved nozzle area')
    require(abs(lo[2]) < 1e-7 and hi[2] <= min(map(float, settings['extruder_printable_height'])),
            f'{pid}: print must be grounded and within saved height')
    excluded = [independent.rect(settings[key]) for key in ['bed_exclude_area', 'wrapping_exclude_area']
                if settings.get(key)]
    if pid == FLOOR:
        require(brim_type == 'no_brim' and width == 0 and overrides['enable_support'] == '0',
                'Common floor brim/support settings changed')
        exclusion_checks = independent.exclusion_test(world, excluded)
        require(all(x['minimum_hull_clearance_mm'] > 21.19 for x in exclusion_checks),
                'Floor lost its original projected-hull exclusion clearance')
    else:
        require(not any(independent.overlap(envelope, e) for e in excluded),
                f'{pid}: retained brim envelope intersects exclusion')
        exclusion_checks = [{'method': 'Conservative mesh bounds plus effective brim',
                             'clear_of_saved_exclusions': True}]
    return {'model_bounds_xyz_mm': [lo.tolist(), hi.tolist()],
            'model_dimensions_xyz_mm': (hi-lo).tolist(), 'nozzle_area_xy_mm': area.tolist(),
            'plate_filament_map_mode': plate.get('filament_map_mode'),
            'plate_filament_maps': plate.get('filament_maps'), 'extruder': overrides['extruder'],
            'brim_type': brim_type, 'brim_width_mm': width, 'brim_gap_mm': gap,
            'checked_envelope_xy_mm': envelope.tolist(), 'exclusion_checks': exclusion_checks,
            'mesh_integrity': independent.mesh_integrity(world, triangles),
            'on_bed': True, 'passed': True}


def write_stl(path, points, triangles):
    lines = ['solid tenbox_v2_r6_print_pose']
    for a, b, c in triangles:
        p, q, r = points[[a, b, c]]
        normal = np.cross(q-p, r-p)
        normal /= np.linalg.norm(normal)
        lines.append('  facet normal ' + ' '.join(format(v, '.16g') for v in normal))
        lines.append('    outer loop')
        lines += ['      vertex ' + ' '.join(format(v, '.16g') for v in point) for point in [p, q, r]]
        lines += ['    endloop', '  endfacet']
    lines.append('endsolid tenbox_v2_r6_print_pose')
    path.write_text('\n'.join(lines) + '\n')
    read_points, read_triangles = independent.read_ascii_stl(path)
    checked = independent.mesh_integrity(read_points, read_triangles)
    require(nearest_error(read_points, points) < 1e-10, 'STL print pose differs from actual 3MF')
    return checked


def replace_project(pid, cad, out, previous):
    source = BASE_PRINT / 'projects' / f'{pid}.3mf'
    original = h.read_archive(source)
    cleaned = dict(original)
    require(not h.clear_generated_data(cleaned, geometry_changed=True) and cleaned == original,
            'Frozen R5 input unexpectedly contains generated caches')
    conf = h.parse_xml(original[h.OBJECTS], h.OBJECTS)
    before = h.xml_bytes(conf)
    require(h.xml_bytes(h.clean_plate_cache(conf, geometry_changed=True)) == before,
            'Frozen R5 input unexpectedly contains stale plate cache references')
    old_local, _, build, build_text = archive_mesh(original)
    rotation, translation, pose_proof = original_pose(pid, previous, old_local, build)
    step = cad / 'step' / f'{pid}.step'
    points, triangles, source_check = step_mesh(step)
    world = points @ rotation.T + translation
    local = (np.c_[world, np.ones(len(world))] @ np.linalg.inv(build).T)[:, :3]
    require(np.allclose(local.min(0), old_local.min(0), atol=0.0001, rtol=0) and
            np.allclose(local.max(0)[:2], old_local.max(0)[:2], atol=0.0001, rtol=0),
            f'{pid}: footprint or bed contact changed; original print pose must be reviewed')
    if pid == FLOOR:
        require(abs(local.max(0)[2] - old_local.max(0)[2]) < 0.0001,
                'Common floor outside thickness changed')
    else:
        # Relocated support ledges are shallower (3 mm instead of 5 mm), so the
        # wall is now 8 mm high in its unchanged outside-face-down print pose.
        require(0 < local.max(0)[2] <= old_local.max(0)[2] + 0.0001,
                'Sidewall became taller than its saved flat placement envelope')
    payload, count = MESH.subn(lambda _: xml_mesh(local, triangles), original[h.MODEL])
    require(count == 1, 'Target archive must contain exactly one unprefixed mesh')
    updated = dict(original)
    updated[h.MODEL] = payload
    path = out / 'projects' / source.name
    h.write_archive(updated, path, source)
    actual = h.read_archive(path)  # Validate the written archive, not the in-memory proposal.
    require(set(actual) == set(original), 'Archive member inventory changed')
    changed = [name for name in original if actual[name] != original[name]]
    require(changed == [h.MODEL], 'Only the model mesh payload may change')
    require(MESH.sub(b'<mesh />', actual[h.MODEL]) == MESH.sub(b'<mesh />', original[h.MODEL]),
            'Model metadata/components/build pose changed outside mesh')
    actual_local, actual_triangles, actual_build, actual_build_text = archive_mesh(actual)
    require(actual_build_text == build_text, 'Build transform changed')
    require(np.allclose(actual_local, local, atol=1e-8, rtol=0) and
            actual_triangles == [list(t) for t in triangles], '3MF mesh roundtrip changed geometry')
    actual_world = (np.c_[actual_local, np.ones(len(actual_local))] @ actual_build.T)[:, :3]
    checked = h.validate_project(actual, original, layout=pid != FLOOR)
    require(checked['settings_bytes_unchanged'] and not checked['contains_toolpaths'],
            'Settings changed or toolpaths appeared')
    imported = studio_contract.audit(path, original[h.SETTINGS])
    require(imported['source_dispatch_contract_pass'], str(imported['errors']))
    layout = layout_check(actual, actual_world, actual_triangles, pid)
    stl = out / 'meshes' / f'{pid}-print.stl'
    stl_check = write_stl(stl, actual_world, actual_triangles)
    pose = {'part_id': pid, 'rotation_matrix_row_major': rotation.ravel().tolist(),
            'assembly_to_plate_translation_mm': translation.tolist(),
            'unchanged_3mf_build_transform': build_text, 'recovery': pose_proof}
    result = {'part_id': pid, 'project_file': f'projects/{pid}.3mf',
              'project_sha256': sha(path), 'source_project_sha256': sha(source),
              'source_step': f'step/{pid}.step', 'source_step_sha256': sha(step),
              'changed_geometry_in_r6': True, 'changed_archive_members': changed,
              'global_settings_bytes_unchanged': actual[h.SETTINGS] == original[h.SETTINGS],
              'object_plate_settings_bytes_unchanged': actual[h.OBJECTS] == original[h.OBJECTS],
              'model_xml_outside_mesh_bytes_unchanged': True, 'build_pose_unchanged': True,
              'source_mesh_validation': source_check, 'structural_validation': checked,
              'studio_xml_dispatch_validation': imported, 'layout': layout, 'pose': pose,
              'print_stl': {'path': str(stl.relative_to(out)), 'sha256': sha(stl), **stl_check}}
    jwrite(out / 'validation' / f'{pid}.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cad', required=True, type=Path, help='Generated R6 CAD folder containing step/ and model_data.json')
    parser.add_argument('--out', required=True, type=Path, help='New output directory; existing directories are never overwritten')
    args = parser.parse_args()
    versions = {'python': '.'.join(map(str, sys.version_info[:3])), 'cadquery': cq.__version__,
                'numpy': np.__version__, 'scipy': scipy.__version__}
    require(versions == {'python': '3.12.14', 'cadquery': '2.7.0', 'numpy': '2.3.5', 'scipy': '1.17.0'},
            f'Use the pinned R5 environment; found {versions}')
    cad, out = args.cad.resolve(), args.out.resolve()
    require(not out.exists(), f'Existing output preserved: {out}')
    require(not out.is_relative_to(BASE), 'Output cannot be inside the immutable R5 inputs')
    require((cad / 'model_data.json').is_file(), 'R6 model_data.json is missing')
    require(all((cad / 'step' / f'{pid}.step').is_file() for pid in CHANGED), 'Changed R6 STEP files are missing')
    previous = json.loads((BASE_CAD / 'model_data.json').read_text())
    inventory = json.loads((BASE_PRINT / 'h2d-project-report.json').read_text())
    source_projects = list((BASE_PRINT / 'projects').glob('*.3mf'))
    require(len(source_projects) == len(inventory['parts']) == 15, 'Expected all 15 original projects')
    for item in inventory['parts']:
        require(sha(BASE_PRINT / item['project_file']) == item['project_sha256'],
                f'Frozen project hash mismatch: {item["part_id"]}')
    for name in ['projects', 'meshes', 'validation']:
        (out / name).mkdir(parents=True, exist_ok=False)
    results = []
    for item in inventory['parts']:
        pid = item['part_id']
        if pid in CHANGED:
            result = replace_project(pid, cad, out, previous)
        else:
            source, target = BASE_PRINT / item['project_file'], out / 'projects' / f'{pid}.3mf'
            shutil.copyfile(source, target)
            require(sha(source) == sha(target), 'Unchanged archive copy differs')
            actual = h.read_archive(target)
            structural = h.validate_project(actual, h.read_archive(source), layout=False)
            imported = studio_contract.audit(target, actual[h.SETTINGS])
            require(imported['source_dispatch_contract_pass'] and not structural['contains_toolpaths'],
                    f'{pid}: copied package failed structural/import validation')
            result = {'part_id': pid, 'project_file': f'projects/{pid}.3mf',
                      'project_sha256': sha(target), 'source_project_sha256': sha(source),
                      'changed_geometry_in_r6': False, 'archive_bytes_unchanged': True,
                      'global_settings_bytes_unchanged': True, 'object_plate_settings_bytes_unchanged': True,
                      'structural_validation': structural,
                      'studio_xml_dispatch_validation': imported,
                      'layout_evidence': 'Byte-identical R5 package; original nozzle/brim/pose and independent layout evidence retained'}
        for key in ['assembly_ids', 'stored_object_count', 'required_physical_quantity', 'plate_runs_for_assembly']:
            result[key] = item[key]
        results.append(result)
        print(f'{pid}: ' + ('mesh replaced; settings and pose retained' if pid in CHANGED else 'R5 archive byte-identical'), flush=True)
    require(sum(x['stored_object_count'] for x in results) == 22 and
            sum(x['required_physical_quantity'] for x in results) == 23 and
            sum(x['plate_runs_for_assembly'] for x in results) == 16, 'Print inventory changed')
    require(sum(not x['changed_geometry_in_r6'] for x in results) == 12, 'Expected 12 unchanged archives')
    printed_ids = [pid for item in results for pid in item['assembly_ids']]
    current = json.loads((cad / 'model_data.json').read_text())
    require(set(printed_ids).issubset({p['id'] for p in current['parts']}) and len(set(printed_ids)) == 23,
            'Print inventory no longer maps to all 23 named printed assembly parts')
    report = {'revision': '10BOX-V2-R6', 'projects_directory': 'projects',
              'project_count': 15, 'stored_object_count': 22, 'required_physical_part_count': 23,
              'plate_runs_for_assembly': 16, 'changed_project_count': 3, 'byte_identical_project_count': 12,
              'global_settings_bytes_unchanged': True, 'object_plate_settings_bytes_unchanged': True,
              'sliced': False, 'studio_application_loaded': False, 'production_approved': False,
              'environment': versions, 'parts': results,
              'scope': 'Actual written 3MF geometry, topology, saved print poses, settings bytes and import dispatch checked. Modified floor retains the original projected-hull bed-exclusion clearance. No Studio application load, toolpath generation or physical print is claimed.'}
    jwrite(out / 'h2d-project-report.json', report)
    jwrite(out / 'print-poses.json', {'poses': [r['pose'] for r in results if r['changed_geometry_in_r6']]})
    with (out / 'assembly-bom.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['project', 'stored_objects', 'plate_runs', 'required_parts', 'assembly_ids'])
        for item in results:
            writer.writerow([item['project_file'], item['stored_object_count'], item['plate_runs_for_assembly'],
                             item['required_physical_quantity'], '; '.join(item['assembly_ids'])])
    print(json.dumps({k: report[k] for k in ['project_count', 'stored_object_count', 'required_physical_part_count',
          'changed_project_count', 'byte_identical_project_count', 'sliced']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
