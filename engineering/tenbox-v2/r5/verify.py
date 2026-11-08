"""Check actual accepted exports/settings, not only saved evidence reports."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, re, sys, zipfile
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return json.loads(path.read_text())

def verify(out):
    accepted = ROOT/'source'
    if not accepted.exists():
        raise ValueError('Missing bundled acceptance baseline')
    assert load(out/'10box-v2-r5/design-config.json') == load(accepted/'10box-v2-r5/design-config.json')
    for name in ['source-r4', 'source-preserved']:
        for before in (accepted/'10box-v2-r5'/name).rglob('*'):
            if before.is_file():
                assert sha(before) == sha(out/'10box-v2-r5'/name/before.relative_to(accepted/'10box-v2-r5'/name))
    import cadquery as cq
    import numpy as np
    import struct
    for before in (accepted/'10box-v2-r5/step').glob('*.step'):
        after = out/'10box-v2-r5/step'/before.name
        if before.stem.startswith('body-bottom-'):
            original = cq.importers.importStep(str(before)).val()
            actual = cq.importers.importStep(str(after)).val()
            assert actual.isValid() and len(actual.Solids()) == 1
            assert original.cut(actual).Volume()+actual.cut(original).Volume() < 1e-5, before.name
        else:
            assert sha(before) == sha(after), before.name
    for before in (accepted/'10box-v2-r5/stl-review').glob('*.stl'):
        assert sha(before) == sha(out/'10box-v2-r5/stl-review'/before.name), before.name
    sys.path.insert(0, str(out/'h2d-r5'))
    import verify_flat_packages as flats
    import verify_studio_import_contract as studio
    mesh_checks = []
    for path in sorted((out/'10box-v2-r5/stl-review').glob('*.stl')):
        raw = path.read_bytes()
        count = struct.unpack_from('<I', raw, 80)[0]
        assert len(raw) == 84+50*count
        dtype = np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
        records = np.frombuffer(raw, dtype=dtype, count=count, offset=84)
        vertices, inverse = np.unique(records['vertices'].reshape(-1,3), axis=0, return_inverse=True)
        triangles = inverse.reshape(-1,3)
        flats.mesh_integrity(vertices.astype(float), triangles)
        normals = np.cross(records['vertices'][:,1]-records['vertices'][:,0], records['vertices'][:,2]-records['vertices'][:,0])
        assert np.all(np.einsum('ij,ij->i', normals, records['normal']) > 0), path.name
        mesh_checks.append(path.name)
    template = out/'h2d-r5/source-template/h2d-empty.3mf'
    with zipfile.ZipFile(template) as archive:
        settings = archive.read('Metadata/project_settings.config')
    report = load(out/'h2d-r5/h2d-project-report.json')
    assert (report['project_count'], report['stored_object_count'], report['required_physical_part_count']) == (15, 22, 23)
    assert sum(p['plate_runs_for_assembly'] for p in report['parts']) == 16
    checks = []
    for row in report['parts']:
        project = out/'h2d-r5'/row['project_file']
        audit = studio.audit(project, settings)
        assert audit['source_dispatch_contract_pass'], audit
        with zipfile.ZipFile(project) as fresh, zipfile.ZipFile(accepted/'h2d-r5/projects'/project.name) as saved:
            assert fresh.namelist() == saved.namelist()
            # UUIDs and archive timestamps may vary; configuration/mesh semantics may not.
            for name in fresh.namelist():
                if name.endswith('.model'):
                    model = ET.fromstring(fresh.read(name))
                    for mesh in model.findall('.//{*}mesh'):
                        points = np.array([[float(v.attrib[a]) for a in ['x','y','z']] for v in mesh.findall('{*}vertices/{*}vertex')])
                        triangles = np.array([[int(t.attrib[a]) for a in ['v1','v2','v3']] for t in mesh.findall('{*}triangles/{*}triangle')])
                        flats.mesh_integrity(points, triangles)
                    normalize = lambda raw: re.sub(rb'p:[Uu][Uu][Ii][Dd]="[^"]+"', b'p:UUID="BENIGN-UUID"', raw)
                    assert normalize(fresh.read(name)) == normalize(saved.read(name)), (project.name, name)
                if name.endswith('.config') or name == '[Content_Types].xml':
                    assert fresh.read(name) == saved.read(name), (project.name, name)
            if row['part_id'] != 'body-bottom-common':
                assert project.read_bytes() == (accepted/'h2d-r5/projects'/project.name).read_bytes()
        checks.append(project.name)
    floor = load(out/'h2d-r5/floor-print-pose.json')
    roof = load(out/'h2d-r5/roof-print-pose.json')
    for pose, before in [(floor, load(accepted/'h2d-r5/floor-print-pose.json')), (roof, load(accepted/'h2d-r5/roof-print-pose.json'))]:
        for key in ['rotation_matrix_row_major', 'translation_mm', 'plate_override', 'left_area_xy_mm']:
            assert pose[key] == before[key], key
        for actual, expected in zip(pose['model_dimensions_xyz_mm'], before['model_dimensions_xyz_mm']):
            assert abs(actual-expected) < 1e-6
    assert floor['yaw_degrees'] == -45 and floor['supports'] is False and floor['brim_width_mm'] == 0
    assert roof['brim_width_mm'] == 0
    assert (out/'10box-v2-r5/step/body-bottom-common.step').read_bytes() == (out/'10box-v2-r5/step/body-bottom-back.step').read_bytes()
    assert (out/'10box-v2-r5/stl-review/body-bottom-common.stl').read_bytes() == (out/'10box-v2-r5/stl-review/body-bottom-back.stl').read_bytes()
    geometry = load(out/'10box-v2-r5/geometry-checks.json')
    assert all(row['passed'] for row in geometry)
    integrity = load(out/'10box-v2-r5/review-checks/stl-integrity.json')
    assert all(row['passed'] for row in integrity['reports'])
    print(json.dumps({'projects': checks, 'bom': 23, 'plate_runs': 16, 'geometry_checks': len(geometry), 'settings_unchanged': True, 'actual_stl_integrity': mesh_checks, 'actual_project_mesh_integrity': True, 'production_approved': False}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'source')
    verify(parser.parse_args().out.resolve())
