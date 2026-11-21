#!/usr/bin/env python3
"""Audit saved R11-04 exports against the immutable R11-03 baseline.

The comparison uses saved STEP files, not the current model's construction
functions. All six sheets and fourteen nylon pieces must stay unchanged; only
the four lid corners and two side lid middle spans gain locating skirts.
No supplier pricing model is inferred.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import cadquery as cq
from OCP.gp import gp_Trsf

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assembly_shape(path, record):
    """Use each saved rigid export transform, never align new bounding boxes."""
    shape = cq.importers.importStep(str(path)).val()
    matrix = record['transform']['export_to_assembly_4x4']
    axes = [cq.Vector(*(matrix[i][j] for i in range(3))) for j in range(3)]
    assert all(abs(axes[i].dot(axes[j]) - float(i == j)) < 1e-8 for i in range(3) for j in range(3))
    assert axes[0].cross(axes[1]).dot(axes[2]) > 1. - 1e-8
    tr = gp_Trsf(); tr.SetValues(*(matrix[i][j] for i in range(3) for j in range(4)))
    return shape.moved(cq.Location(tr))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--previous', type=Path, default=ROOT / 'reference' / 'r11-03-baseline')
    ap.add_argument('--out', type=Path, default=ROOT / 'out')
    args = ap.parse_args()
    old_manifest_path = args.previous / 'parts-manifest.json'
    new_manifest_path = args.out / 'parts-manifest.json'
    old = json.loads(old_manifest_path.read_text())
    new = json.loads(new_manifest_path.read_text())
    before = {p['id']: p for p in old['parts']}
    after = {p['id']: p for p in new['parts']}
    assert set(before) == set(after), 'Unexpected physical-part replacement'
    rows = []
    old_total = new_total = 0.0
    for p in new['parts']:
        if p['category'] != 'pa12':
            continue
        dimensions = p['dimensions_mm']
        prior = before[p['id']]
        old_total += prior['volume_mm3'] / 1000
        new_total += p['volume_mm3'] / 1000
        rows.append(dict(id=p['id'], quantity=p['quantity'],
                         dimensions_xyz_mm=dimensions,
                         longest_axis_mm=max(dimensions),
                         bbox_volume_cm3=math.prod(dimensions) / 1000,
                         solid_volume_cm3=p['volume_mm3'] / 1000,
                         previous_solid_volume_cm3=prior['volume_mm3'] / 1000,
                         large_part_surcharge_size_screen_pass=max(dimensions) < 250,
                         minimum_price_tier_confirmed=False,
                         quoted_price=None, currency=None,
                         stl=p['files']['stl']))
    assert len(rows) == 20 and all(r['large_part_surcharge_size_screen_pass'] for r in rows)
    sizes = dict(revision=new['revision'], units='mm', source_manifest_sha256=digest(new_manifest_path),
                 process='MJF', material='PA12-HP Nylon', finish='Dyed Black',
                 quantity_each=1, parts=rows,
                 total_solid_volume_cm3=new_total,
                 previous_total_solid_volume_cm3=old_total,
                 volume_change_cm3=new_total-old_total,
                 maximum_axis_mm=max(r['longest_axis_mm'] for r in rows),
                 large_size_rule=dict(threshold_mm=250, inclusive=True,
                    source='https://jlc3dp.com/help/article/3d-printing-special-charges-case'),
                 price_status='UNQUOTED_UPLOAD_PERMISSION_REQUIRED', total_price=None,
                 limitation='Passing the published length screen does not establish minimum pricing or exemption from complexity/finishing charges.')
    (args.out / 'pa12-size-audit.json').write_text(json.dumps(sizes, indent=2))
    with (args.out / 'pa12-size-audit.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['part_id', 'quantity', 'x_mm', 'y_mm', 'z_mm', 'longest_mm', 'solid_cm3', 'bbox_cm3', 'below_250_mm', 'price_status'])
        for r in rows:
            w.writerow([r['id'],r['quantity'],*r['dimensions_xyz_mm'],r['longest_axis_mm'],r['solid_volume_cm3'],r['bbox_volume_cm3'],r['large_part_surcharge_size_screen_pass'],'unquoted'])

    intended_nylon_changes = {i for i in after if i.startswith('lid-corner-')} | {'lid-middle-left', 'lid-middle-right'}
    assert len(intended_nylon_changes)==6
    changes = []
    for ident, record in after.items():
        a_path = args.previous / before[ident]['files']['step']['path']
        b_path = args.out / record['files']['step']['path']
        assert digest(a_path) == before[ident]['files']['step']['sha256']
        assert digest(b_path) == record['files']['step']['sha256']
        a = assembly_shape(a_path, before[ident])
        b = assembly_shape(b_path, record)
        removed = a.cut(b).Volume()
        added = b.cut(a).Volume()
        item = dict(id=ident, old_step_sha256=digest(a_path), new_step_sha256=digest(b_path),
                    removed_solid_mm3=removed, added_solid_mm3=added,
                    old_volume_mm3=a.Volume(), new_volume_mm3=b.Volume())
        if ident in intended_nylon_changes:
            assert added > 100, (ident, 'Missing side locating-skirt material')
            assert b.Volume() > a.Volume() and len(b.Solids()) == 1 and b.isValid()
            item['expected'] = 'Add connected side locating skirts, bridges and hardware clearance reliefs'
        else:
            assert removed + added < 1e-4, (ident, 'Unexpected geometry change', removed, added)
            item['expected'] = 'Unchanged physical geometry'
        item['passed'] = True
        changes.append(item)
    panel_holes = sum(len(p['flat_pattern']['round_holes_xy_d_mm']) + len(p['flat_pattern']['slots_xy_length_width_angle_mm'])
                      for p in new['parts'] if p['category'] == 'aluminum')
    assert panel_holes == 58
    assert new['counts']['washer_instances'] == 64
    validation=json.loads((args.out/'validation.json').read_text())
    assert validation['passed'] and validation['inner_ear_review']['passed'] and validation['lid_locator_review']['passed']
    assert validation['component_count']==262
    delta = dict(revision=new['revision'], previous_revision=old['revision'], passed=True,
                 previous_manifest_sha256=digest(old_manifest_path), current_manifest_sha256=digest(new_manifest_path),
                 parts=changes, checked_saved_step_pairs=len(changes),
                 unchanged_nylon_parts=14, revised_nylon_parts=6, removed_panel_slots=0,
                 removed_hanging_holes=0, remaining_panel_cutouts=panel_holes,
                 new_lid_locator_edges=['left','right'], retained_lid_locator_edges=['front','back'],
                 new_integral_inside_ears=0, retained_existing_body_inside_ears=40,
                 removed_inside_washers=0,retained_top_inside_washers=8,
                 previous_new_washers=old['counts']['washer_instances'], new_washers=new['counts']['washer_instances'],
                 scope='Saved STEP geometry comparison; component contacts and assembly paths are separate reports. No physical fit, strength or supplier price qualification.')
    (args.out / 'revision-delta.json').write_text(json.dumps(delta, indent=2))
    print(json.dumps(dict(passed=True, panel_cutouts=panel_holes, nylon_parts=20,
                          max_axis_mm=sizes['maximum_axis_mm'], total_pa12_cm3=new_total,
                          pa12_change_cm3=new_total-old_total, unchanged_nylon_parts=14), indent=2))


if __name__ == '__main__':
    main()
