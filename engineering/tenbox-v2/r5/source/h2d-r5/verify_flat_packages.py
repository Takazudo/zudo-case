"""Independently parse and verify every delivered R5 3MF and the common-floor STL.

This verifier does not import the builder or generic helper's layout functions.
It checks actual mesh/build transforms and the saved nozzle/exclusion settings.
It is not a Bambu Studio slice or a physical printing test.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, re, zipfile
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import ConvexHull
import verify_studio_import_contract as studio_contract

ROOT = Path(__file__).resolve().parent


def matrix(text):
    v = [float(x) for x in (text or '1 0 0 0 1 0 0 0 1 0 0 0').split()]
    assert len(v) == 12
    return np.array([[v[0], v[3], v[6], v[9]], [v[1], v[4], v[7], v[10]],
                     [v[2], v[5], v[8], v[11]], [0., 0., 0., 1.]])


def rect(values):
    if isinstance(values, str):
        values = values.split(',')
    p = np.array([[float(x) for x in s.split('x')] for s in values])
    return np.r_[p.min(0), p.max(0)]


def overlap(a, b):
    return a[0] < b[2]-1e-7 and a[2] > b[0]+1e-7 and a[1] < b[3]-1e-7 and a[3] > b[1]+1e-7


def meta(node):
    return {e.attrib['key']: e.attrib['value'] for e in node.findall('metadata')}


def inside(r, area):
    return bool(r[0] >= area[0]-1e-6 and r[1] >= area[1]-1e-6 and
                r[2] <= area[2]+1e-6 and r[3] <= area[3]+1e-6)


def clip(poly, axis, boundary, upper):
    result = []
    for i, a in enumerate(poly):
        b = poly[(i+1) % len(poly)]
        da, db = a[axis]-boundary, b[axis]-boundary
        ina, inb = (da <= 0, db <= 0) if upper else (da >= 0, db >= 0)
        if ina:
            result.append(a)
        if ina != inb:
            result.append(a+(b-a)*(da/(da-db)))
    return np.array(result)


def polygon_area(poly):
    if len(poly) < 3:
        return 0.
    q = np.roll(poly, -1, axis=0)
    return abs(float(np.sum(poly[:, 0]*q[:, 1]-poly[:, 1]*q[:, 0])))/2


def distance_to_segment(p, a, b):
    ab = b-a
    t = max(0., min(1., float(np.dot(p-a, ab)/np.dot(ab, ab))))
    return float(np.linalg.norm(p-(a+t*ab)))


def exclusion_test(points, excluded):
    hull = points[ConvexHull(points[:, :2]).vertices, :2]
    checked = []
    for e in excluded:
        intersection = hull.copy()
        for axis, boundary, upper in [(0, e[0], False), (0, e[2], True),
                                      (1, e[1], False), (1, e[3], True)]:
            if len(intersection):
                intersection = clip(intersection, axis, boundary, upper)
        assert polygon_area(intersection) < 1e-8
        other = np.array([[e[0], e[1]], [e[2], e[1]], [e[2], e[3]], [e[0], e[3]]])
        gap = min([distance_to_segment(p, a, b) for p in hull for a, b in zip(other, np.roll(other, -1, axis=0))] +
                  [distance_to_segment(p, a, b) for p in other for a, b in zip(hull, np.roll(hull, -1, axis=0))])
        checked.append({'rectangle_xy_mm': e.tolist(), 'hull_overlap_area_mm2': 0.,
                        'minimum_hull_clearance_mm': gap})
    return checked


def mesh_integrity(points, triangles):
    edges, directed, links = Counter(), Counter(), defaultdict(set)
    volume = 0.
    for a, b, c in triangles:
        assert len({a, b, c}) == 3
        va, vb, vc = points[[a, b, c]]
        cross = np.cross(vb-va, vc-va)
        assert np.dot(cross, cross) > 1e-20
        volume += float(np.dot(va-points[0], cross))/6
        for s, t in [(a, b), (b, c), (c, a)]:
            edges[tuple(sorted((s, t)))] += 1
            directed[(s, t)] += 1
            links[s].add(t)
            links[t].add(s)
    assert all(n == 2 for n in edges.values())
    assert all(n == directed[(b, a)] for (a, b), n in directed.items())
    assert volume > 0
    seen, stack = set(), [0]
    while stack:
        i = stack.pop()
        if i not in seen:
            seen.add(i)
            stack.extend(links[i]-seen)
    assert len(seen) == len(points)
    return {'vertices': len(points), 'triangles': len(triangles),
            'closed_two_manifold': True, 'consistent_winding': True,
            'connected_component_count': 1, 'positive_signed_volume_mm3': volume}


def read_ascii_stl(path):
    points, triangles, lookup = [], [], {}
    flat = [tuple(float(x) for x in m.groups()) for m in
            re.finditer(r'\bvertex\s+(\S+)\s+(\S+)\s+(\S+)', path.read_text())]
    assert len(flat) % 3 == 0
    for i in range(0, len(flat), 3):
        tri = []
        for p in flat[i:i+3]:
            if p not in lookup:
                lookup[p] = len(points)
                points.append(p)
            tri.append(lookup[p])
        triangles.append(tri)
    return np.array(points), triangles


def main():
    expected = json.loads((ROOT/'h2d-project-report.json').read_text())
    frozen = {r['part_id']: r for r in json.loads((ROOT/'source-flat-r4/source-metadata.json').read_text())['parts']}
    project_dir = ROOT/expected.get('projects_directory', 'projects')
    with zipfile.ZipFile(ROOT/'source-template/h2d-empty.3mf') as z:
        original = z.read('Metadata/project_settings.config')
    assert hashlib.sha256(original).hexdigest() == '99b34023dcf3d8142abb119f426ca54d499a4d07026c7e406e2b062147c7a356'
    reports, all_ids, floor_points = [], [], None
    for part in expected['parts']:
        pid = part['part_id']
        path = ROOT/part['project_file']
        isfloor, isroof = pid == 'body-bottom-common', pid == 'lid-top-single'
        left_only = isfloor or isroof
        import_checked = studio_contract.audit(path, original)
        assert import_checked['source_dispatch_contract_pass'], import_checked['errors']
        with zipfile.ZipFile(path) as z:
            actual = z.read('Metadata/project_settings.config')
            settings = json.loads(actual)
            assert actual == original
            config = ET.fromstring(z.read('Metadata/model_settings.config'))
            assert len(config.findall('plate')) == 1
            plate = meta(config.find('plate'))
            objects = {e.attrib['id']: meta(e) for e in config.findall('object')}
            scene = ET.fromstring(z.read('3D/3dmodel.model'))
            resources = {o.attrib['id']: o for o in scene.findall('{*}resources/{*}object')}
            nozzle_areas = [rect(a) for a in settings['extruder_printable_area']]
            common = np.array([max(a[0] for a in nozzle_areas), max(a[1] for a in nozzle_areas),
                               min(a[2] for a in nozzle_areas), min(a[3] for a in nozzle_areas)])
            excluded = [rect(settings[k]) for k in ['bed_exclude_area', 'wrapping_exclude_area'] if settings.get(k)]
            if left_only:
                assert plate['filament_map_mode'] == 'Manual'
                assignment = [int(x) for x in plate['filament_maps'].split()]
                assert assignment == [int(x) for x in settings['filament_map']] == [1, 1]
                assert settings['physical_extruder_map'] == ['1', '0']
                selected = assignment[0]-1
                area = nozzle_areas[selected]
                height = float(settings['extruder_printable_height'][selected])
                assert area.tolist() == [0., 0., 325., 320.]
            else:
                area = common
                height = min(float(v) for v in settings['extruder_printable_height'])

            def mesh_for(oid, transform):
                o = resources[oid]
                mesh = o.find('{*}mesh')
                if mesh is not None:
                    p = np.array([[float(v.attrib[a]) for a in ['x', 'y', 'z']]
                                  for v in mesh.findall('{*}vertices/{*}vertex')])
                    t = [[int(v.attrib[a]) for a in ['v1', 'v2', 'v3']]
                         for v in mesh.findall('{*}triangles/{*}triangle')]
                    return (np.c_[p, np.ones(len(p))]@transform.T)[:, :3], t
                merged, triangles = [], []
                count = 0
                for c in o.findall('{*}components/{*}component'):
                    p, t = mesh_for(c.attrib['objectid'], transform@matrix(c.get('transform')))
                    merged.append(p)
                    triangles.extend([[i+count for i in tri] for tri in t])
                    count += len(p)
                return np.concatenate(merged), triangles

            items = []
            for item in scene.findall('{*}build/{*}item'):
                oid = item.attrib['objectid']
                p, triangles = mesh_for(oid, matrix(item.get('transform')))
                lo, hi = p.min(0), p.max(0)
                overrides = objects[oid]
                brim_type = overrides.get('brim_type', settings['brim_type'])
                width = float(overrides.get('brim_width', settings['brim_width']))
                gap = float(overrides.get('brim_object_gap', settings['brim_object_gap']))
                allowance = 0. if brim_type == 'no_brim' else width+gap
                env = np.r_[lo[:2]-allowance, hi[:2]+allowance]
                assert inside(env, area)
                assert abs(lo[2]) < 1e-6 and hi[2] <= height+1e-6
                assert overrides['extruder'] == '1'
                row = {'name': overrides['name'], 'model_bounds_mm': [lo.tolist(), hi.tolist()],
                       'brim_type': brim_type, 'brim_width_mm': width, 'brim_gap_mm': gap,
                       'checked_envelope_mm': env.tolist(),
                       'nozzle_scope': 'locked left only' if left_only else 'common',
                       'checked_nozzle_area_mm': area.tolist(), 'inside_selected_scope': True,
                       'clear_of_wrapping_exclusion': True, 'on_bed_and_below_height': True}
                if isfloor:
                    assert brim_type == 'no_brim' and width == 0 and abs(gap-.1) < 1e-9
                    assert overrides['enable_support'] == '0'
                    assert np.allclose(lo, [4.0747338584, 4.4031609832, 0.], atol=1e-7)
                    assert np.allclose(hi, [320.9252661416, 315.5968390168, 5.], atol=1e-7)
                    margins = [lo[0], 325-hi[0], lo[1], 320-hi[1]]
                    assert min(margins) > 4
                    assert not inside(env, common)
                    assert any(overlap(env, e) for e in excluded), 'Expected bbox overlap must be handled by the actual shape test.'
                    exc = exclusion_test(p, excluded)
                    assert all(e['minimum_hull_clearance_mm'] > 21.19 for e in exc)
                    row.update({'common_area_pass': False, 'minimum_nozzle_edge_margins_mm': margins,
                                'exclusion_check_method': 'Actual posed mesh convex hull versus saved exclusion polygons',
                                'actual_shape_exclusion_checks': exc,
                                'mesh_integrity': mesh_integrity(p, triangles)})
                    floor_points = p
                else:
                    assert not any(overlap(env, e) for e in excluded)
                if isroof:
                    assert brim_type == 'no_brim' and width == 0 and abs(gap-.1) < 1e-9
                    assert overrides['enable_support'] == '0'
                    assert np.allclose(lo, [4., 10., 0.], atol=1e-7)
                    assert np.allclose(hi, [321., 300., 5.], atol=1e-7)
                    assert not inside(env, common)
                    row['common_area_pass'] = False
                items.append(row)
            for i, a in enumerate(items):
                for b in items[i+1:]:
                    assert not overlap(a['checked_envelope_mm'], b['checked_envelope_mm'])
            assert len(items) == part['stored_object_count']
            assert part['required_physical_quantity'] == len(items)*part['plate_runs_for_assembly']
            assert len(part['assembly_ids']) == part['required_physical_quantity']
            assert not any(n.lower().endswith('.gcode') for n in z.namelist())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == part['project_sha256']
            if not isfloor:
                assert digest == frozen[pid]['project_sha256']
            all_ids.extend(part['assembly_ids'])
            reports.append({'project': path.name, 'passed': True, 'stored_object_count': len(items),
                            'required_physical_quantity': part['required_physical_quantity'],
                            'assembly_ids': part['assembly_ids'], 'global_settings_bytes_unchanged': True,
                            'studio_xml_dispatch_contract_pass': True, 'studio_application_loaded': False,
                            'plate_filament_map_mode': plate.get('filament_map_mode'),
                            'plate_filament_maps': plate.get('filament_maps'), 'objects': items})
    assert len(reports) == 15 and sum(r['stored_object_count'] for r in reports) == 22
    assert sum(r['required_physical_quantity'] for r in reports) == 23
    assert len(all_ids) == len(set(all_ids)) == 23
    assert len(list(project_dir.glob('*.3mf'))) == 15
    assert [p.name for p in project_dir.glob('*bottom*.3mf')] == ['body-bottom-common.3mf']
    cad_ids = {p['id'] for p in json.loads((ROOT.parent/'10box-v2-r5/model_data.json').read_text())['parts']}
    assert set(all_ids) == cad_ids
    stl_path = ROOT/'meshes/body-bottom-common-print.stl'
    stl_p, stl_t = read_ascii_stl(stl_path)
    stl_check = mesh_integrity(stl_p, stl_t)
    assert {tuple(p) for p in np.round(stl_p, 8)} == {tuple(p) for p in np.round(floor_points, 8)}
    stl_check.update({'source_is_same_verified_3mf_posed_mesh': True,
                      'model_bounds_xyz_mm': [stl_p.min(0).tolist(), stl_p.max(0).tolist()],
                      'sha256': hashlib.sha256(stl_path.read_bytes()).hexdigest()})
    with (ROOT/'assembly-bom.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['project', 'stored_objects', 'plate_runs', 'required_parts', 'assembly_ids'])
        for r in expected['parts']:
            writer.writerow([r['project_file'], r['stored_object_count'], r['plate_runs_for_assembly'],
                             r['required_physical_quantity'], '; '.join(r['assembly_ids'])])
    out = {'scope': 'Independent actual-package mesh/build, effective brim, selected-nozzle reach, actual-shape exclusion, and BOM validation. All physical parts have flat placements; no Studio slice or physical-print test is claimed.',
           'project_count': 15, 'stored_object_count': 22, 'required_physical_part_count': 23,
           'all_included_projects_passed': True, 'flat_layouts_cover_all_required_parts': True,
           'all_studio_xml_dispatch_contracts_pass': True, 'studio_application_loaded': False,
           'sliced': False, 'unresolved_flat_parts': [], 'common_floor_print_stl': stl_check,
           'reports': reports}
    (ROOT/'independent-package-review.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({'projects': 15, 'stored_objects': 22, 'required_physical_parts': 23,
                      'all_included_passed': True, 'common_floor_print_stl_passed': True,
                      'sliced': False}))


if __name__ == '__main__':
    main()
