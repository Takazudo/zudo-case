"""P6 roof-only CAD revision from hash-pinned P5 STEP solids. All units mm."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import cadquery as cq
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools'))
import bambu_3mf as b3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(solid):
    b = solid.BoundingBox()
    return [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]


def project(pid, stl, out):
    """Replace only the mesh in the corresponding saved P5 H2D project."""
    template = ROOT/'reference'/f'p5-{pid}-h2d-pla06.3mf'
    with zipfile.ZipFile(template) as z:
        original = {name:z.read(name) for name in z.namelist()}
    assert set(original) == {'3D/3dmodel.model','Metadata/model_settings.config',
        'Metadata/project_settings.config','[Content_Types].xml','_rels/.rels'}
    mesh = trimesh.load(stl,force='mesh')
    vertices = '\n'.join('          <vertex x="{:.12g}" y="{:.12g}" z="{:.12g}" />'.format(*v) for v in mesh.vertices)
    triangles = '\n'.join('          <triangle v1="{}" v2="{}" v3="{}" />'.format(*t) for t in mesh.faces)
    replacement = '<mesh>\n        <vertices>\n'+vertices+'\n        </vertices>\n        <triangles>\n'+triangles+'\n        </triangles>\n      </mesh>'
    model = original['3D/3dmodel.model'].decode()
    revised,count = re.subn(r'<mesh>.*?</mesh>',lambda _:replacement,model,flags=re.S)
    assert count == 1
    revised = revised.replace('P5 geometry unchanged. Settings retained; user will configure print details. No toolpaths.',
        'P6 lid slots 10.5 x 5.5 mm. Saved P5 H2D PLA 0.6 settings and placement retained. Unsliced; no toolpaths.')
    revised = revised.replace(f'P5 {pid} / H2D / unsliced',f'P6 {pid} / H2D / unsliced')
    data = dict(original)
    data['3D/3dmodel.model'] = revised.encode()
    data['Metadata/model_settings.config'] = original['Metadata/model_settings.config'].replace(f'P5 {pid}'.encode(),f'P6 {pid}'.encode())
    oldroot,newroot=ET.fromstring(model),ET.fromstring(revised)
    assert [e.attrib for e in oldroot.iter() if e.tag.endswith(('object','component','build','item'))] == [e.attrib for e in newroot.iter() if e.tag.endswith(('object','component','build','item'))]
    assert data['Metadata/project_settings.config'] == original['Metadata/project_settings.config']
    config=json.loads(data['Metadata/project_settings.config'])
    assert config['printer_model']=='Bambu Lab H2D' and config['nozzle_diameter']==['0.6','0.6']
    assert config['filament_type']==['PLA','PLA'] and config['brim_type']=='no_brim' and config['brim_width']=='0'
    generated=b3.validate_project(data,layout=True)
    assert not generated['contains_toolpaths'] and len(generated['build_items'])==1
    assert sum(m['triangles'] for m in generated['meshes']) == len(mesh.faces)
    ns={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    actual_vertices=np.array([[float(v.get(a)) for a in ('x','y','z')] for v in newroot.findall('.//c:vertex',ns)])
    actual_faces=np.array([[int(v.get(a)) for a in ('v1','v2','v3')] for v in newroot.findall('.//c:triangle',ns)])
    assert np.allclose(actual_vertices,mesh.vertices,atol=1e-8) and np.array_equal(actual_faces,mesh.faces)
    target=out/'projects'/f'p6-{pid}-h2d-pla06.3mf'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted(data):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data[name])
    return {'file':str(target.relative_to(out)),'sha256':sha(target),'template_sha256':sha(template),
        'settings_bytes_unchanged':True,'all_object_ids_uuids_and_transforms_preserved':True,
        'mesh_identical_to_stl':True,'unsliced':True,'studio_load_or_slice_performed':False,
        'printer':'Bambu Lab H2D','nozzle_mm':0.6,'filament':'PLA','brim_mm':0,
        'validation':generated}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'out')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    for sub in ('stl', 'step', 'projects'):
        (out/sub).mkdir(exist_ok=True)
    p = json.loads((ROOT/'parameters.json').read_text())
    assert p['units'] == 'mm' and not p['production_approved']
    assert cq.__version__ == '2.8.0', 'Use the locked CadQuery 2.8.0 environment'
    for row in p['source_inputs']:
        assert sha(ROOT/row['path']) == row['sha256'], row['path']
    length, width = p['slot']['length_mm'], p['slot']['width_mm']
    assert length >= width > 5.0
    travel = (length-width)/2
    z0, z1 = p['roof_z_mm']
    report = {'revision': p['revision'], 'units': 'mm', 'production_approved': False,
              'python': sys.version.split()[0], 'cadquery': cq.__version__,
              'slot': p['slot'], 'parts': [], 'physical_validation': False,
              'scope': 'Only lid-top-1 and lid-top-2; unchanged P5 body, edges, pads, hardware and rail reference inputs.'}
    for row in p['parts']:
        pid = row['id']
        baseline = cq.importers.importStep(str(ROOT/'reference'/f'{pid}.step')).val()
        solid = baseline
        cutters = []
        hole_checks = []
        for hole in row['holes']:
            x, y = hole['center_mm']
            angle = hole['angle_deg']
            assert angle == (90 if hole['face'] in ('front', 'back') else 0)
            cutter = cq.Workplane('XY', origin=(x,y,z0-1)).slot2D(length,width,angle).extrude(z1-z0+2).val()
            cutters.append(cutter)
            solid = solid.cut(cutter)
        solid = solid.clean()
        assert solid.isValid() and len(solid.Solids()) == 1
        assert np.allclose(bounds(solid), bounds(baseline), atol=1e-6)
        assert solid.cut(baseline).Volume() < 1e-6, 'Unexpected added material'
        expected_removed = len(row['holes'])*(length-width)*width*(z1-z0)
        actual_removed = baseline.Volume()-solid.Volume()
        assert abs(actual_removed-expected_removed) < 1e-5, (actual_removed, expected_removed)
        minimum_edge = float('inf')
        b = bounds(solid)
        for hole in row['holes']:
            x, y = hole['center_mm']
            a = math.radians(hole['angle_deg'])
            axis = (round(math.cos(a)), round(math.sin(a)))
            passed = []
            for offset in (-travel, 0., travel):
                cx, cy = x+axis[0]*offset, y+axis[1]*offset
                bolt = cq.Solid.makeCylinder(2.5,z1-z0+2,cq.Vector(cx,cy,z0-1))
                collision = solid.intersect(bolt).Volume()
                assert collision < 1e-6, (pid, hole, offset, collision)
                passed.append({'offset_mm':offset,'m5_shaft_collision_mm3':collision})
            ext_x = length/2 if axis[0] else width/2
            ext_y = length/2 if axis[1] else width/2
            margin = min(x-ext_x-b[0],b[3]-x-ext_x,y-ext_y-b[1],b[4]-y-ext_y)
            minimum_edge = min(minimum_edge, margin)
            hole_checks.append({**hole, 'length_mm':length,'width_mm':width,
                                'edge_margin_mm':round(margin,6),'m5_travel_checks':passed})
        placed = solid.translate(tuple(row['assembly_to_print_translation_mm']))
        stl = out/'stl'/f'{pid}.stl'
        step = out/'step'/f'{pid}.step'
        cq.exporters.export(placed,str(stl),tolerance=.025,angularTolerance=.15)
        cq.exporters.export(solid,str(step))
        txt=step.read_text()
        txt,n=re.subn(r"(FILE_NAME\('Open CASCADE Shape Model',')\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(')",r'\g<1>1980-01-01T00:00:00\g<2>',txt)
        assert n==1
        step.write_text(txt)
        mesh=trimesh.load(stl,force='mesh')
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0
        assert len(mesh.split()) == 1
        assert np.allclose(mesh.bounds[0],[0,0,0],atol=.0001)
        assert np.allclose(mesh.extents,[225.8,165.05,5],atol=.005)
        assert abs(mesh.volume-placed.Volume()) < max(.3,placed.Volume()*.0002)
        step_read=cq.importers.importStep(str(step)).val()
        assert step_read.isValid() and abs(step_read.Volume()-solid.Volume())<.001
        report['parts'].append({'id':pid,'quantity':row['quantity'],
            'assembly_to_print_translation_mm':row['assembly_to_print_translation_mm'],
            'print_dimensions_mm':mesh.extents.tolist(),'print_bounds_mm':mesh.bounds.tolist(),
            'assembly_bounds_mm':bounds(solid),'cad_volume_mm3':solid.Volume(),
            'removed_volume_mm3':actual_removed,'expected_removed_volume_mm3':expected_removed,
            'minimum_edge_margin_mm':round(minimum_edge,6),'watertight':bool(mesh.is_watertight),
            'winding_consistent':bool(mesh.is_winding_consistent),'mesh_components':len(mesh.split()),
            'triangles':len(mesh.faces),'holes':hole_checks,
            'stl_sha256':sha(stl),'step_sha256':sha(step),'bambu_project':project(pid,stl,out)})
    report['passed']=True
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
