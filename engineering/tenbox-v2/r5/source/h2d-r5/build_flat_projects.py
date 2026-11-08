"""Build the complete unsliced R5 flat H2D project set from bundled inputs.

The common floor and roof use the saved left nozzle with a supported plate
Manual assignment. Global project settings bytes are preserved. No slicer or
printer is invoked. Requires Python3, numpy, scipy, and CadQuery.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, shutil, subprocess, sys, uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import numpy as np
from scipy.spatial import ConvexHull
import cadquery as cq

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
CAD = WORK / '10box-v2-r5'
TEMPLATE = ROOT / 'source-template/h2d-empty.3mf'
spec = importlib.util.spec_from_file_location('bambu_helper_r5', ROOT / 'tools/bambu_3mf.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
C = math.sqrt(.5)
ROTATION = np.array([[C, C, 0.], [-C, C, 0.], [0., 0., 1.]])
TRANSLATION = np.array([162.5 - C*72.49716, 160. - C*72.49716, 0.])
FLOOR_ID = 'body-bottom-common'
OVERRIDES = {'brim_type': 'no_brim', 'brim_width': '0',
             'brim_object_gap': '0.1', 'enable_support': '0'}


def jwrite(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_step(path):
    solid = cq.importers.importStep(str(path)).val()
    assert solid.isValid() and len(solid.Solids()) == 1
    v, t = solid.tessellate(.06, .20)
    points, lookup, remap = [], {}, []
    for p in v:
        p = tuple(round(float(x), 8) for x in p.toTuple())
        if p not in lookup:
            lookup[p] = len(points)
            points.append(p)
        remap.append(lookup[p])
    triangles = [[remap[i] for i in tri] for tri in t]
    _, _, checked = h.validate_mesh(points, triangles, path.name)
    return np.array(points), triangles, checked


def clip(poly, normal, limit):
    out = []
    for i, a in enumerate(poly):
        b = poly[(i+1) % len(poly)]
        da, db = float(np.dot(normal, a)-limit), float(np.dot(normal, b)-limit)
        if da <= 1e-9:
            out.append(a)
        if (da <= 0) != (db <= 0):
            out.append(a + (b-a)*(da/(da-db)))
    return np.array(out)


def area(poly):
    if len(poly) < 3:
        return 0.
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(poly, np.roll(poly, -1, axis=0))))/2


def point_segment(p, a, b):
    d = b-a
    t = np.clip(np.dot(p-a, d)/np.dot(d, d), 0., 1.)
    return float(np.linalg.norm(p-(a+t*d)))


def distance(a, b):
    return min([point_segment(p, q, r) for p in a for q, r in zip(b, np.roll(b, -1, axis=0))] +
               [point_segment(p, q, r) for p in b for q, r in zip(a, np.roll(a, -1, axis=0))])


def floor_clearance(posed, settings):
    left = np.array(h.rect_from_polygon(settings['extruder_printable_area'][0], 'left nozzle'))
    assert np.allclose(left, [0., 0., 325., 320.])
    lo, hi = posed.min(0), posed.max(0)
    edge = [lo[0]-left[0], left[2]-hi[0], lo[1]-left[1], left[3]-hi[1]]
    assert min(edge) > 4.
    assert abs(lo[2]) < 1e-7 and abs(hi[2]-5.) < 1e-7
    hull = posed[ConvexHull(posed[:, :2]).vertices, :2]
    exclusions = []
    for key in ['bed_exclude_area', 'wrapping_exclude_area']:
        if not settings.get(key):
            continue
        rect = np.array(h.rect_from_polygon(settings[key], key))
        x0, y0, x1, y1 = rect
        polygon = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
        intersection = hull.copy()
        for normal, limit in [([-1, 0], -x0), ([1, 0], x1), ([0, -1], -y0), ([0, 1], y1)]:
            if len(intersection):
                intersection = clip(intersection, normal, limit)
        assert area(intersection) < 1e-8
        clearance = distance(hull, polygon)
        assert clearance > 20.
        exclusions.append({'setting': key, 'rectangle_xy_mm': rect.tolist(),
                           'projected_hull_overlap_area_mm2': area(intersection),
                           'projected_hull_clearance_mm': clearance})
    rear = clip(hull, [0, -1], -310.)
    return {'left_nozzle_area_xy_mm': left.tolist(),
            'minimum_nozzle_edge_margins_mm': dict(zip(['left', 'right', 'front', 'rear'], edge)),
            'projected_hull_xy_mm': hull.tolist(), 'exclusions': exclusions,
            'portion_above_y310_xrange_mm': [float(rear[:, 0].min()), float(rear[:, 0].max())],
            'bounding_rectangle_intersects_wrapping_exclusion': True,
            'validation_method': 'Conservative projected mesh convex hull against the saved exclusion polygon; model bbox is used only for rectangular nozzle reach.'}


def setmeta(node, key, value):
    element = next((e for e in node.findall('metadata') if e.get('key') == key), None)
    if element is None:
        element = ET.SubElement(node, 'metadata', {'key': key})
    element.set('value', str(value))


def create_floor(posed, triangles, target):
    """Write the documented mesh/component 3MF structure using actual left reach."""
    data = h.read_archive(TEMPLATE)
    original_settings = data[h.SETTINGS]
    settings = h.settings(data)
    assert settings['filament_map'] == ['1', '1'] and settings['physical_extruder_map'] == ['1', '0']
    root, conf = h.parse_xml(data[h.MODEL], h.MODEL), h.parse_xml(data[h.OBJECTS], h.OBJECTS)
    resources, build = root.find(h.q('resources')), root.find(h.q('build'))
    assert resources is not None and build is not None and len(resources) == len(build) == 0
    assert not conf.findall('object') and len(conf.findall('plate')) == 1
    plate, assemble = conf.find('plate'), conf.find('assemble')
    assert assemble is not None and not len(assemble)
    position = np.array([float(h.fmt(v)) for v in posed.min(0)])
    normalized = np.array([[float(h.fmt(c)) for c in v] for v in posed-position])
    final_posed = normalized+position
    clearance = floor_clearance(final_posed, settings)
    build.set(f'{{{h.PROD}}}UUID', str(uuid.uuid4()))
    if not any(e.tag.startswith('{'+h.BBL+'}') or any(k.startswith('{'+h.BBL+'}') for k in e.attrib) for e in root.iter()):
        root.set('xmlns:BambuStudio', h.BBL)
    obj = ET.SubElement(resources, h.q('object'), {'id': '1', 'type': 'model', f'{{{h.PROD}}}UUID': str(uuid.uuid4())})
    mesh = ET.SubElement(obj, h.q('mesh'))
    vs, ts = ET.SubElement(mesh, h.q('vertices')), ET.SubElement(mesh, h.q('triangles'))
    for v in normalized:
        ET.SubElement(vs, h.q('vertex'), {axis: h.fmt(v[i]) for i, axis in enumerate(('x', 'y', 'z'))})
    for t in triangles:
        ET.SubElement(ts, h.q('triangle'), {axis: str(t[i]) for i, axis in enumerate(('v1', 'v2', 'v3'))})
    wrapper = ET.SubElement(resources, h.q('object'), {'id': '2', 'type': 'model', f'{{{h.PROD}}}UUID': str(uuid.uuid4())})
    comp = ET.SubElement(wrapper, h.q('components'))
    ET.SubElement(comp, h.q('component'), {'objectid': '1', 'transform': h.IDENTITY, f'{{{h.PROD}}}UUID': str(uuid.uuid4())})
    transform = '1 0 0 0 1 0 0 0 1 ' + ' '.join(h.fmt(v) for v in position)
    ET.SubElement(build, h.q('item'), {'objectid': '2', 'transform': transform, 'printable': '1', f'{{{h.PROD}}}UUID': str(uuid.uuid4())})
    ob = ET.Element('object', {'id': '2'})
    conf.insert(0, ob)
    h.meta(ob, 'name', 'R5 common floor — flat −45 degrees — print twice')
    h.meta(ob, 'extruder', '1')
    for k, v in OVERRIDES.items():
        h.meta(ob, k, v)
    part = ET.SubElement(ob, 'part', {'id': '1', 'subtype': 'normal_part'})
    h.meta(part, 'name', FLOOR_ID)
    h.meta(part, 'matrix', h.MATRIX4)
    setmeta(plate, 'plater_name', 'R5 common floor — LEFT nozzle — print twice')
    setmeta(plate, 'filament_map_mode', 'Manual')
    setmeta(plate, 'filament_maps', '1 1')
    instance = ET.SubElement(plate, 'model_instance')
    for k, v in [('object_id', '2'), ('instance_id', '0'), ('identify_id', '1')]:
        h.meta(instance, k, v)
    ET.SubElement(assemble, 'assemble_item', {'object_id': '2', 'instance_id': '0', 'transform': transform, 'offset': '0 0 0'})
    for key, value in [('Title', '10BOX v2 R5 — common floor — flat H2D left nozzle'),
                       ('Description', 'Clipped floor, flat at −45 degrees, print twice. Left nozzle Manual map1 1. No brim or supports. Unsliced; load and slice in Studio.'),
                       ('ModificationDate', datetime.now(timezone.utc).date().isoformat())]:
        element = next((e for e in root.findall(h.q('metadata')) if e.get('name') == key), None)
        if element is None:
            element = ET.Element(h.q('metadata'), {'name': key})
            root.insert(list(root).index(resources), element)
        element.text = value
    removed = h.clear_generated_data(data, geometry_changed=True)
    data[h.MODEL] = h.xml_bytes(root)
    data[h.OBJECTS] = h.xml_bytes(h.clean_plate_cache(conf, geometry_changed=True))
    checked = h.validate_project(data, h.read_archive(TEMPLATE), layout=False)
    assert data[h.SETTINGS] == original_settings and checked['settings_bytes_unchanged']
    assert not checked['layout_checked'] and not checked['contains_toolpaths']
    h.write_archive(data, target, TEMPLATE)
    checked.update({'validation_scope': 'Helper mesh/package check only; actual selected-left nozzle and projected-hull exclusion check is separate. No generic common-area bbox layout pass is claimed.',
                    'plate_override': {'filament_map_mode': 'Manual', 'filament_maps': '1 1'},
                    'clearance': clearance, 'removed_cache_members': removed})
    return final_posed, checked, clearance


def write_ascii_stl(path, points, triangles):
    lines = ['solid R5_body_bottom_common_flat_minus45']
    for tri in triangles:
        a, b, c = points[tri]
        normal = np.cross(b-a, c-a)
        normal /= np.linalg.norm(normal)
        lines.append('  facet normal ' + ' '.join(format(x, '.16g') for x in normal))
        lines.append('    outer loop')
        for p in [a, b, c]:
            lines.append('      vertex ' + ' '.join(format(x, '.16g') for x in p))
        lines.extend(['    endloop', '  endfacet'])
    lines.append('endsolid R5_body_bottom_common_flat_minus45')
    path.write_text('\n'.join(lines)+'\n')
    v, t, checked = h.read_mesh(path.name, path.parent)
    assert np.allclose(np.array(v).min(0), points.min(0), atol=1e-8)
    assert np.allclose(np.array(v).max(0), points.max(0), atol=1e-8)
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'projects', help='Fresh project folder under h2d-r5; existing outputs are preserved.')
    args = parser.parse_args()
    outdir = args.output_dir.resolve()
    outrel = outdir.relative_to(ROOT)
    outdir.mkdir(parents=True, exist_ok=True)
    for d in ['meshes', 'manifests', 'validation']:
        (ROOT/d).mkdir(parents=True, exist_ok=True)
    frozen = ROOT/'source-flat-r4'
    previous = json.loads((frozen/'source-metadata.json').read_text())
    for pid in [FLOOR_ID]+[r['part_id'] for r in previous['parts']]:
        if (outdir/f'{pid}.3mf').exists():
            raise RuntimeError('Existing output preserved: '+pid+'; choose a fresh --output-dir')
    source = CAD/'step/body-bottom-common.step'
    assert sha(source) == sha(CAD/'step/body-bottom-back.step'), 'Common source must be the rear-floor alias.'
    vertices, triangles, source_mesh_check = mesh_step(source)
    posed = vertices@ROTATION.T+TRANSLATION
    target = outdir/f'{FLOOR_ID}.3mf'
    posed, checked, clearance = create_floor(posed, triangles, target)
    jwrite(ROOT/'validation/body-bottom-common-structural.json', checked)
    jwrite(ROOT/'meshes/body-bottom-common-print.mesh.json', {'vertices': posed.tolist(), 'triangles': triangles})
    stl = ROOT/'meshes/body-bottom-common-print.stl'
    stl_check = write_ascii_stl(stl, posed, triangles)
    jwrite(ROOT/'validation/body-bottom-common-stl.json', stl_check)
    lo, hi = posed.min(0), posed.max(0)
    pose = {'part_id': FLOOR_ID, 'units': 'mm', 'source_file': source.relative_to(WORK).as_posix(),
            'source_sha256': sha(source), 'assembly_ids': ['body-bottom-back', 'body-bottom-front'],
            'required_physical_quantity': 2, 'stored_object_count': 1,
            'rotation_matrix_row_major': ROTATION.ravel().tolist(), 'translation_mm': TRANSLATION.tolist(),
            'formula': 'x′=(X+Y−72.49716)/sqrt(2)+162.5; y′=(−X+Y−72.49716)/sqrt(2)+160; z′=Z',
            'yaw_degrees': -45, 'model_bounds_xyz_mm': [lo.tolist(), hi.tolist()],
            'model_dimensions_xyz_mm': (hi-lo).tolist(), 'brim_type': 'no_brim', 'brim_width_mm': 0,
            'brim_object_gap_mm': .1, 'supports': False, 'left_area_xy_mm': [0, 0, 325, 320],
            'common_area_xy_mm': [25, 0, 325, 320], 'common_height_mm': 320,
            'excluded_xy_mm': [145, 310, 256, 326],
            'plate_override': {'filament_map_mode': 'Manual', 'filament_maps': '1 1'},
            'clearance': clearance, 'mesh': {'p': np.round(posed, 6).ravel().tolist(), 'i': np.array(triangles).ravel().tolist()}}
    jwrite(ROOT/'floor-print-pose.json', pose)
    jwrite(ROOT/'manifests/body-bottom-common-left-nozzle.json',
           {'schema': '10box-r5-left-nozzle/1', 'source_step': source.relative_to(WORK).as_posix(),
            'source_sha256': sha(source), 'mesh': '../meshes/body-bottom-common-print.mesh.json',
            'orientation': 'Flat broad face down, yaw −45 degrees', 'bed_center_xy_mm': [162.5, 160.],
            'rotation_matrix_row_major': ROTATION.ravel().tolist(), 'translation_mm': TRANSLATION.tolist(),
            'filament_slot': 1, 'logical_nozzle': 'left', 'plate_filament_map_mode': 'Manual',
            'plate_filament_maps': [1, 1], 'object_settings': OVERRIDES,
            'stored_object_count': 1, 'required_physical_quantity': 2, 'clearance': clearance})
    rows = [{'part_id': FLOOR_ID, 'project_file': (outrel/f'{FLOOR_ID}.3mf').as_posix(),
             'assembly_ids': pose['assembly_ids'], 'stored_object_count': 1, 'required_physical_quantity': 2,
             'plate_runs_for_assembly': 2, 'quantity': 2, 'changed_geometry_in_r5': True,
             'source_relative_to_cad': 'step/body-bottom-common.step', 'source_sha256': sha(source),
             'model_dimensions_xyz_mm': (hi-lo).tolist(), 'model_bounds_xyz_mm': [lo.tolist(), hi.tolist()],
             'nozzle_scope': 'left only', 'plate_override': pose['plate_override'],
             'brim': 'none', 'support': 'none', 'orientation': 'Flat, yaw −45 degrees',
             'source_mesh_validation': source_mesh_check, 'clearance': clearance}]
    for old in previous['parts']:
        pid = old['part_id']
        before, target = frozen/old['project_file'], outdir/f'{pid}.3mf'
        source = CAD/old['source_relative_to_cad']
        assert sha(before) == old['project_sha256']
        assert sha(source) == old['source_sha256'], f'{pid}: R5 CAD differs from frozen project provenance'
        shutil.copy2(before, target)
        use_common = old['nozzle_scope'] == 'common'
        checked = h.validate_project(h.read_archive(target), h.read_archive(TEMPLATE), layout=use_common)
        assert checked['settings_bytes_unchanged'] and not checked['contains_toolpaths']
        assert checked['layout_checked'] == use_common
        jwrite(ROOT/'validation'/f'{pid}-frozen-package.json', checked)
        row = dict(old)
        row.update({'project_file': (outrel/f'{pid}.3mf').as_posix(), 'changed_geometry_in_r5': False,
                    'frozen_input': 'source-flat-r4/'+before.name, 'plate_runs_for_assembly': 1,
                    'quantity': row['required_physical_quantity']})
        row.pop('changed_geometry', None)
        rows.append(row)
    roof = json.loads((frozen/'roof-print-pose.json').read_text())
    roof['source_file'] = '10box-v2-r5/step/lid-top-single.step'
    roof['source_sha256'] = sha(CAD/'step/lid-top-single.step')
    jwrite(ROOT/'roof-print-pose.json', roof)
    for row in rows:
        row['project_sha256'] = sha(ROOT/row['project_file'])
    result = {'revision': '10BOX-V2-R5-FLAT-FLOORS-IMPORT-FIX',
              'status': 'Complete flat placements with corrected unprefixed relationship XML and a pinned Studio XML dispatch check. Unsliced; actual Studio load and slice pending.',
              'xml_import_contract_verifier': 'verify_studio_import_contract.py',
              'frozen_r4_archive_bytes_unchanged': False,
              'frozen_r4_geometry_and_settings_bytes_unchanged': True,
              'global_settings_bytes_unchanged': True, 'projects_directory': outrel.as_posix(),
              'project_count': len(rows), 'stored_object_count': sum(r['stored_object_count'] for r in rows),
              'required_physical_part_count': sum(r['required_physical_quantity'] for r in rows),
              'full_assembly_part_count': 23, 'flat_layouts_cover_all_required_parts': True,
              'studio_application_loaded': False, 'sliced': False, 'parts': rows, 'excluded_unresolved_flat_parts': [],
              'layout_scope': 'Common floor and roof use the explicitly locked left nozzle. Other projects use the common nozzle area. Exclusion checks use actual projected hulls, not overlapping model bounding rectangles.',
              'remaining_checks': ['Open and slice all projects in Bambu Studio with the saved H2D profile.',
                                   'Inspect the actual first-layer adhesion and any copied support/brim toolpaths before printing.',
                                   'New floor and roof have no brim; confirm adhesion and flatness with the chosen plate and PLA.'],
              'sources': ['sources/left-nozzle-mapping.md', 'sources/studio-exclusion-check.md',
                          'sources/studio-import-repair.md']}
    assert (result['project_count'], result['stored_object_count'], result['required_physical_part_count']) == (15, 22, 23)
    jwrite(ROOT/'h2d-project-report.json', result)
    subprocess.run([sys.executable, str(ROOT/'verify_studio_import_contract.py'), '--include-frozen'], check=True)
    print(json.dumps({'projects': 15, 'stored_objects': 22, 'required_physical_parts': 23,
                      'floor_pose': str(ROOT/'floor-print-pose.json'), 'floor_print_stl': str(stl),
                      'floor_clearance': clearance}))


if __name__ == '__main__':
    main()
