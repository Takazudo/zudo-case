"""Reuse all fifteen committed R7 H2D projects after checking R8 print geometry.

Only purchased rail/frame/padder placement changes. Every 3MF remains byte-identical.
Checks inspect written archives; no slicer or printer is invoked.
"""
from pathlib import Path
import argparse, copy, gzip, hashlib, importlib.util, json, sys, zipfile
import numpy as np

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
BASE_PRINT = ROOT.parent / 'r5/source/h2d-r5'
SOURCE_ARCHIVE = REPOSITORY / 'public/downloads/candidate/tenbox-v2-r7-print.zip'
SOURCE_ARCHIVE_SHA256 = 'db851ff28b8391771d3d227be386c47703615d8c8028c8ce572ee744d65f6718'
spec = importlib.util.spec_from_file_location('tenbox_r8_bambu', BASE_PRINT / 'tools/bambu_3mf.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
sys.path.insert(0, str(BASE_PRINT))
import verify_studio_import_contract as studio_contract


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def jwrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def points(model, part):
    return (np.asarray(model['meshes'][part['mesh']]['p']).reshape(-1, 3)
            + np.asarray(part.get('staticOffset', [0, 0, 0])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cad', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    cad, out = args.cad.resolve(), args.out.resolve()
    require(not out.exists(), f'Existing output preserved: {out}')
    require(not out.is_relative_to(ROOT.parent / 'r5'), 'Immutable R5 input cannot be an output')
    require(sha(SOURCE_ARCHIVE.read_bytes()) == SOURCE_ARCHIVE_SHA256, 'Committed R7 print archive changed')
    baseline_raw = gzip.decompress((ROOT / 'reference/r7-model-data.json.gz').read_bytes())
    baseline_receipt = json.loads((ROOT / 'reference/r7-model-receipt.json').read_text())
    require(sha(baseline_raw) == baseline_receipt['uncompressed_sha256'], 'Frozen R7 model changed')
    previous = json.loads(baseline_raw)
    current = json.loads((cad / 'model_data.json').read_text())
    old_parts = {p['id']: p for p in previous['parts']}
    new_parts = {p['id']: p for p in current['parts']}
    with zipfile.ZipFile(SOURCE_ARCHIVE) as z:
        require(z.testzip() is None, 'R7 print archive CRC failure')
        members = {name: z.read(name) for name in z.namelist()}
    inventory = json.loads(members['h2d-project-report.json'])
    printed_ids = [pid for item in inventory['parts'] for pid in item['assembly_ids']]
    require(len(printed_ids) == len(set(printed_ids)) == 23, 'Expected 23 distinct printed parts')
    comparisons = []
    for pid in printed_ids:
        old, new = old_parts[pid], new_parts[pid]
        before, after = points(previous, old), points(current, new)
        indices_match = previous['meshes'][old['mesh']]['i'] == current['meshes'][new['mesh']]['i']
        require(before.shape == after.shape, f'{pid}: printed vertex count changed')
        error = float(np.max(np.abs(before - after)))
        require(indices_match and error <= 0.000001, f'{pid}: printed shape or placement changed')
        require(np.allclose(old['box'], new['box'], atol=0.000001, rtol=0), f'{pid}: printed bounds changed')
        comparisons.append({'part_id': pid, 'triangle_indices_unchanged': True,
                            'maximum_world_vertex_error_mm': error, 'passed': True})
    out.mkdir(parents=True)
    for name, raw in members.items():
        if name in {'MANIFEST.sha256', 'README.md', 'h2d-project-report.json'}:
            continue
        output_name = name.replace("validation/", "validation/r7/", 1) if name.startswith("validation/") else name
        target = out / output_name
        require(target.resolve().is_relative_to(out), 'Unsafe archive member')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    results = []
    for item in inventory['parts']:
        name = item['project_file']
        target = out / name
        actual_raw = target.read_bytes()
        require(actual_raw == members[name] and sha(actual_raw) == item['project_sha256'], name)
        actual = h.read_archive(target)
        structural = h.validate_project(actual, actual, layout=False)
        imported = studio_contract.audit(target, actual[h.SETTINGS])
        require(structural['settings_bytes_unchanged'] and not structural['contains_toolpaths'], name)
        require(imported['source_dispatch_contract_pass'], f'{name}: Studio XML dispatch failure')
        imported['path'] = name
        result = copy.deepcopy(item)
        for key in ["source_step", "source_step_sha256", "source_mesh_validation", "changed_archive_members"]:
            if key in result:
                result["r7_" + key] = result.pop(key)
        result["changed_archive_members"] = []
        result.update({'source_project_sha256': item['project_sha256'],
                       'r5_source_project_sha256': item['source_project_sha256'],
                       'changed_geometry_in_r8': False, 'archive_bytes_unchanged': True,
                       'global_settings_bytes_unchanged': True,
                       'object_plate_settings_bytes_unchanged': True,
                       'structural_validation': structural,
                       'studio_xml_dispatch_validation': imported,
                       'layout_evidence': 'Byte-identical committed R7 project; its saved pose, nozzle, brim and layout checks are retained.'})
        results.append(result)
        print(f'{item["part_id"]}: committed R7 archive byte-identical', flush=True)
    require(len(results) == 15 and sum(x['stored_object_count'] for x in results) == 22 and
            sum(x['required_physical_quantity'] for x in results) == 23 and
            sum(x['plate_runs_for_assembly'] for x in results) == 16, 'Print inventory changed')
    comparison = {'based_on': 'R7', 'source_model_sha256': sha(baseline_raw),
                  'current_model_sha256': sha((cad / 'model_data.json').read_bytes()),
                  'part_count': len(comparisons), 'all_passed': True, 'parts': comparisons}
    jwrite(out / 'printed-geometry-comparison.json', comparison)
    report = {'revision': '10BOX-V2-R8', 'based_on': 'R7', 'projects_directory': 'projects',
              'source_print_archive': SOURCE_ARCHIVE.relative_to(REPOSITORY).as_posix(),
              'source_print_archive_sha256': SOURCE_ARCHIVE_SHA256,
              'retained_r7_validation_directory': 'validation/r7',
              'project_count': 15, 'stored_object_count': 22, 'required_physical_part_count': 23,
              'plate_runs_for_assembly': 16, 'changed_project_count': 0, 'byte_identical_project_count': 15,
              'global_settings_bytes_unchanged': True, 'object_plate_settings_bytes_unchanged': True,
              'sliced': False, 'studio_application_loaded': False, 'production_approved': False,
              'parts': results, 'printed_geometry': comparison,
              'scope': 'All 23 printed assembly meshes and positions match R7. All 15 written 3MF files are byte-identical to committed R7. ZIP structure and import dispatch rechecked; saved layout evidence retained. Native Studio, slicing and physical fit not performed.'}
    jwrite(out / 'h2d-project-report.json', report)
    print(json.dumps({k: report[k] for k in ['project_count', 'required_physical_part_count',
          'changed_project_count', 'byte_identical_project_count', 'sliced']}))


if __name__ == '__main__':
    main()
