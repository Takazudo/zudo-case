"""Export the R11 physical-part models without changing assembled geometry.

PA12 parts keep their assembly orientation and are translated to XYZ minima 0.
The five body sheets use the inverse core.FACES rigid transform, then minima 0;
the lid sheet is already in XY.  Every manifest entry records the inverse rigid
transform back into the assembly.  Local export placement is not a print pose.

Dependencies: CadQuery 2.7 (including OCP), NumPy and ezdxf.  STEP, STL and DXF
writers/readback are the repository's preserved R9 helper in export_io.py.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import math

import cadquery as cq
import ezdxf
import numpy as np

from .core import P, T, FACES, roundwasher
from . import export_io as io


def _matrix(location):
    tr = location.wrapped.Transformation()
    return [[float(tr.Value(i, j)) for j in range(1, 5)] for i in range(1, 4)] + [[0.0, 0.0, 0.0, 1.0]]


def _normalized(shape, face=None):
    face_to_world = (cq.Plane(origin=FACES[face][0], xDir=FACES[face][1], normal=FACES[face][3]).location
                     if face else cq.Location())
    local = shape.moved(face_to_world.inverse)
    local_bounds = io.bounds(local)
    minimum = local_bounds['min']
    result = local.translate(tuple(-v for v in minimum)).clean()
    export_to_world = face_to_world * cq.Location(cq.Vector(*minimum))
    moved_back = result.moved(export_to_world)
    volume_difference = shape.cut(moved_back).Volume() + moved_back.cut(shape).Volume()
    if volume_difference > max(1e-5, shape.Volume() * 1e-9):
        raise AssertionError('Rigid export transform changed physical geometry')
    return result, minimum, dict(
        face=face, placement='local_min_XYZ_zero',
        oriented_local_minimum_before_translation_mm=minimum,
        source_to_oriented_local_4x4=_matrix(face_to_world.inverse),
        export_to_assembly_4x4=_matrix(export_to_world),
        assembly_to_export_4x4=_matrix(export_to_world.inverse),
        roundtrip_symmetric_difference_mm3=volume_difference,
        orientation_note='Sheet flattened into XY; Z is thickness.' if face else 'Assembly orientation preserved; not a validated print orientation.',
    )


def _step_readback(path, expected):
    actual = cq.importers.importStep(str(path)).val()
    eb, ab = io.bounds(expected), io.bounds(actual)
    error = float(np.abs(np.asarray([eb['min'], eb['max']]) - np.asarray([ab['min'], ab['max']])).max())
    volume_error = abs(actual.Volume() - expected.Volume())
    limit = max(1e-5, expected.Volume() * 1e-8)
    checks = dict(valid=actual.isValid(), one_solid=len(actual.Solids()) == 1,
                  dimensions_match=error < 1e-5, volume_match=volume_error < limit)
    if not all(checks.values()):
        raise AssertionError(f'STEP readback mismatch {path}: {checks}, bbox={error}, volume={volume_error}')
    return dict(passed=True, checks=checks, bbox_error_mm=error, volume_error_mm3=volume_error,
                dimensions_mm=ab['size'], local_min_mm=ab['min'])


def _dxf_readback(path, expected, thickness, holes, slots, radius):
    doc = ezdxf.readfile(path)
    if doc.audit().has_errors or doc.units != ezdxf.units.MM:
        raise AssertionError(f'Invalid or non-mm DXF: {path}')
    model = doc.modelspace()
    if len(model.query('CIRCLE')) != len(holes) or len(model.query('ARC')) != 2 * len(slots):
        raise AssertionError(f'DXF hole/slot count mismatch: {path}')
    # This deliberately consumes the SAVED DXF, not the input hole table.  Its
    # true circular/arc wires are extruded and compared to the flattened STEP.
    # CadQuery imports each DXF layer as independent faces.  Extruding all
    # layers at once would union the holes back into the outline.  Respect the
    # saved OUTLINE / HOLES / SLOTS manufacturing-layer semantics explicitly.
    outline = cq.importers.importDXF(str(path), tol=1e-6, include=['OUTLINE'])
    actual = outline.extrude(thickness).val()
    cut_faces = cq.importers.importDXF(str(path), tol=1e-6, include=['HOLES', 'SLOTS'])
    cut_shapes = cut_faces.extrude(thickness + 2).val().translate((0, 0, -1))
    if len(cut_shapes.Solids()) != len(holes) + len(slots):
        raise AssertionError(f'DXF profile count mismatch: {path}')
    actual = actual.cut(cut_shapes).clean()
    eb, ab = io.bounds(expected), io.bounds(actual)
    bounds_error = float(np.abs(np.asarray([eb['min'], eb['max']]) - np.asarray([ab['min'], ab['max']])).max())
    volume_error = abs(actual.Volume() - expected.Volume())
    difference = expected.cut(actual).Volume() + actual.cut(expected).Volume()
    tolerance = max(1e-4, expected.Volume() * 1e-8)
    checks = dict(valid=actual.isValid(), one_solid=len(actual.Solids()) == 1,
                  bounds_match=bounds_error < 1e-5, volume_match=volume_error < tolerance,
                  exact_profile_matches=difference < tolerance)
    if not all(checks.values()):
        raise AssertionError(f'DXF/STEP mismatch {path}: {checks}, volume={volume_error}, difference={difference}')
    return dict(passed=True, checks=checks, circle_count=len(holes), slot_count=len(slots),
                outline_corner_radius_mm=radius, bbox_error_mm=bounds_error,
                volume_error_mm3=volume_error, symmetric_difference_mm3=difference,
                reconstructed_volume_mm3=actual.Volume(),
                source='DXF read back through CadQuery importDXF and extruded by sheet thickness')


def _file(path, root):
    return dict(path=path.relative_to(root).as_posix(), sha256=io.digest(path), bytes=path.stat().st_size)


def export_parts(parts, body_meta, lid_meta, out_path):
    """Write 20 nylon + six sheet models and one reusable circular washer.

    Returns the JSON-serializable manifest also saved as parts-manifest.json.
    CAD/mesh failures raise before the final manifest is written.  The source
    shape dictionaries and original R10 files are never changed.
    """
    out = Path(out_path)
    out.mkdir(parents=True, exist_ok=True)
    nylon = [p for p in parts if p.get('role') == 'nylon' and p.get('cat') in ('corner', 'span', 'lidFrame')]
    metal = [p for p in parts if p.get('role') == 'metal' and p.get('cat') in ('panels', 'lidMetal')]
    if len(nylon) != 20 or len(metal) != 6:
        raise ValueError(f'Expected 20 PA12 + 6 sheet parts, received {len(nylon)} + {len(metal)}')
    ids = [p['id'] for p in nylon + metal]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate physical part IDs')
    washer_quantity = sum(p.get('role') == 'washer' for p in parts)
    washer = dict(id='round-washer', name='丸ワッシャー Ø15 / Ø5 / t1',
                  shape=roundwasher(0, 0, 0, 1), role='washer', cat='washer',
                  material='black ASA from user geometry reference', quantity=washer_quantity,
                  note='One exact geometry, reused for all new loose washers. No printer profile is assigned here.')
    selected = [(p, 'pa12') for p in nylon] + [(p, 'aluminum') for p in metal] + [(washer, 'home-print')]
    records = []
    for source, directory in selected:
        id = source['id']
        if not source['shape'].isValid() or len(source['shape'].Solids()) != 1:
            raise ValueError(f'Expected one valid physical source solid: {id}')
        face = source.get('face') if directory == 'aluminum' and id != 'lid-plate' else None
        if directory == 'aluminum' and id != 'lid-plate' and face not in FACES:
            raise ValueError(f'Missing body sheet face transform: {id}')
        shape, local_min, transform = _normalized(source['shape'], face)
        bb = io.bounds(shape)
        if min(bb['min']) < -1e-6 or max(abs(v) for v in bb['min']) > 1e-5:
            raise AssertionError(f'Export minimum is not zero: {id}: {bb["min"]}')
        step_path = out / directory / (id + '.step')
        stl_path = out / directory / (id + '.stl')
        io.step(shape, step_path)
        step_check = _step_readback(step_path, shape)
        io.stl(shape, stl_path)
        stl_check = io.inspect_stl(stl_path, shape)
        files = dict(step=_file(step_path, out), stl=_file(stl_path, out))
        checks = dict(step=step_check, stl=stl_check)
        holes, slots = [], []
        radius = 0.0
        if directory == 'aluminum':
            if id == 'lid-plate':
                holes = [(x - local_min[0], y - local_min[1], lid_meta['plate_hole_diameter_mm'])
                         for x, y in lid_meta['plate_holes_xy']]
                if lid_meta.get('hanging_hole'):
                    hx, hy = lid_meta['hanging_hole']['xy']
                    holes.append((hx - local_min[0], hy - local_min[1], lid_meta['hanging_hole']['diameter_mm']))
                radius = lid_meta['plate_corner_radius_mm']
            else:
                rows = [r for r in body_meta['hole_table'] if r['face'] == face]
                for r in rows:
                    x, y = r['uc'] - local_min[0], r['vc'] - local_min[1]
                    if r['angle'] is None:
                        holes.append((x, y, r['width']))
                    else:
                        slots.append((x, y, r['length'], r['width'], r['angle']))
            dxf_path = out / directory / (id + '.dxf')
            io.dxf(dxf_path, bb['size'][0], bb['size'][1], holes=holes, slots=slots, radius=radius)
            checks['dxf'] = _dxf_readback(dxf_path, shape, bb['size'][2], holes, slots, radius)
            files['dxf'] = _file(dxf_path, out)
        record = dict(id=id, name=source.get('name', id), category=directory,
                      quantity=source.get('quantity', 1), material=source.get('material',
                          'PA12-HP black candidate' if directory == 'pa12' else 'A5052 black anodized candidate'),
                      dimensions_mm=bb['size'], volume_mm3=shape.Volume(),
                      transform=transform, files=files, checks=checks,
                      note=source.get('note', ''), production_approved=False)
        if directory == 'aluminum':
            record['flat_pattern'] = dict(thickness_mm=bb['size'][2], corner_radius_mm=radius,
                                         round_holes_xy_d_mm=holes, slots_xy_length_width_angle_mm=slots)
        records.append(record)
    counts = Counter(k for r in records for k in r['files'])
    manifest = dict(
        revision=P['revision'], model=P['model'], units='mm', production_approved=False,
        status='CAD_REVIEW_CANDIDATE_NOT_PHYSICALLY_VERIFIED',
        counts=dict(nylon_parts=len(nylon), sheetmetal_parts=len(metal), washer_models=1,
                    washer_instances=washer_quantity, part_models=len(records), files=dict(counts)),
        parts=records,
        validation=dict(passed=True, description='Every exported STEP read back; every STL is closed, positively oriented and CAD-consistent; every saved DXF extruded and compared with the sheet CAD.'),
        notes=[
            'No source geometry was rescaled or changed for export. Each recorded rigid transform restores the exact assembly placement.',
            'PA12 local placement is a file datum, not a printer setup or validated print orientation.',
            'Round washer dimensions come from the supplied transformed 3MF geometry: OD15, ID5, thickness1 mm.',
            'These checks do not establish physical fit, fastening strength, nylon process tolerances, slicer validity or manufacturing approval.',
        ],
    )
    # Preserve the original assembly datum in a second, named STEP assembly.
    # Individual manufacturing files above remain flattened/local-origin files.
    assembly = cq.Assembly(name='R11_7U40_shell')
    colors = {'corner':(.075,.49,.50),'span':(.73,.52,.23),
              'panels':(.34,.41,.44),'lidFrame':(.43,.33,.53),'lidMetal':(.53,.53,.61)}
    for p in nylon + metal:
        assembly.add(p['shape'],name=p['id'],color=cq.Color(*colors[p['cat']]))
    assembly_path=out/'assembly-shell.step'
    assembly.save(str(assembly_path))
    imported=cq.importers.importStep(str(assembly_path)).val()
    expected_volume=sum(p['shape'].Volume() for p in nylon+metal)
    if len(imported.Solids())!=26 or not imported.isValid() or abs(imported.Volume()-expected_volume)>1e-4:
        raise AssertionError('Named shell STEP assembly readback mismatch')
    manifest['assembly_shell']=dict(file=_file(assembly_path,out),solids=26,
        readback_valid=True,volume_error_mm3=abs(imported.Volume()-expected_volume),
        coordinates='Original assembly datum, X width/Y depth/Z up; floor underside Z0',
        scope='Twenty printed components and six sheets; hardware and original rail frame are shown in the interactive preview instead.')
    io.write_json(out / 'parts-manifest.json', manifest)
    return manifest

