"""Full P5 build in a clean output tree. The imported prototype scripts run only on copies."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess, sys, zipfile
ROOT = Path(__file__).resolve().parent
REVISION = 'P5-PRINTED-5MM-TAB-JOINTS-J3'
APPROVED_PARAMETERS_SHA256 = 'e1a3ec08e1535ffd5a959aaf56952e5f885e71640bad25472aeae71f0daa9f26'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def zip_files(dest, base, files):
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(files):
            rel = path.relative_to(base).as_posix()
            info = zipfile.ZipInfo(rel, (1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    out = a.out.resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit('Output must be outside the maintained source tree')
    if out.exists():
        if any(out.iterdir()): raise SystemExit('Output must be empty')
    else: out.mkdir(parents=True)
    if sha(ROOT/'source/parameters.json') != APPROVED_PARAMETERS_SHA256:
        raise SystemExit('Changed P4 parameters require a new reviewed revision and matching docs')
    receipt=json.loads((ROOT/'reference/P4-SOURCE-RECEIPT.json').read_text())
    for f in receipt['reference_inputs']:
        if sha(ROOT/f['path']) != f['sha256']: raise SystemExit('Inherited input changed: '+f['path'])
    params = json.loads((ROOT/'source/parameters.json').read_text())
    if params['revision'] != REVISION or params['body']['panel_thickness'] != 5 or params['body']['inside_width'] != 226.4 or params['body']['inside_depth'] != 331 or params['body']['wall_height'] != 89.5 or params['lid']['rise_to_roof_underside'] != 38 or params['printer']['single_nozzle_xy'] != [325.0,320.0]:
        raise SystemExit('Unsupported P4 profile; review geometry and checks before changing parameters')
    shutil.copytree(ROOT/'source',out/'source',ignore=shutil.ignore_patterns('model.json','__pycache__'))
    shutil.copytree(ROOT/'reference',out/'reference',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('build.py','verify.py','negative.py','validate_parameters.py','regenerate.py','pyproject.toml','uv.lock','.python-version','README.md'):
        shutil.copy2(ROOT/name,out/name)
    for script,args in [('build_case.py',[]),('build_rails.py',['--base',str(out/'source/model.json')]),('ventilation_report.py',[]),('verify_joints.py',[]),('build_html.py',[])]:
        subprocess.run([sys.executable,str(out/'source'/script),*args],check=True)
    # Open CASCADE embeds wall-clock time in the STEP header. This one field has
    # no geometric meaning; normalize it before read-back, hashes and packages.
    for step_path in (out/'step').glob('*.step'):
        raw=step_path.read_text()
        normalized,count=re.subn(r"(FILE_NAME\('Open CASCADE Shape Model',')\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(')",r'\g<1>1980-01-01T00:00:00\g<2>',raw)
        if count!=1: raise SystemExit(f'Unexpected STEP header: {step_path.name}')
        step_path.write_text(normalized)
    # Archived P3 receipts remain immutable. Compare BRep and mesh metrics separately
    # because STEP headers/formatting can differ across exporters and platforms.
    import cadquery as cq
    import trimesh
    baseline=json.loads((ROOT/'reference/ACCEPTED-GEOMETRY.json').read_text())
    comparisons=[]
    for expected in baseline['parts']:
        pid=expected['id']
        if pid.startswith(('wall-','floor-')): continue
        step=out/'step'/f'{pid}.step'; stl=out/'stl'/f'{pid}.stl'
        solid=cq.importers.importStep(str(step)).val(); box=solid.BoundingBox(); mesh=trimesh.load(stl,force='mesh')
        if sha(stl)!=expected['stl_sha256']: raise SystemExit(f'Accepted STL bytes changed: {pid}')
        actual={'volume_mm3':solid.Volume(),'area_mm2':solid.Area(),'bbox_mm':[box.xmin,box.ymin,box.zmin,box.xmax,box.ymax,box.zmax],'faces':len(solid.Faces()),'stl_volume_mm3':mesh.volume,'stl_bounds_mm':mesh.bounds.tolist()}
        for key in ('volume_mm3','area_mm2','stl_volume_mm3'):
            if abs(actual[key]-expected[key])>max(0.01,abs(expected[key])*1e-5): raise SystemExit(f'Accepted geometry changed: {pid} {key}')
        for key in ('bbox_mm','stl_bounds_mm'):
            def flat(v): return [x for row in v for x in row] if isinstance(v[0],list) else v
            if any(abs(a-b)>0.02 for a,b in zip(flat(actual[key]),flat(expected[key]))): raise SystemExit(f'Accepted bounds changed: {pid} {key}')
        if actual['faces']!=expected['faces']: raise SystemExit(f'Accepted BRep face count changed: {pid}')
        comparisons.append({'id':pid,'old_step_sha256':expected['step_sha256'],'new_step_sha256':sha(step),'old_stl_sha256':expected['stl_sha256'],'new_stl_sha256':sha(stl),'metrics':actual})
    (out/'accepted-geometry-comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    model=json.loads((out/'source/model.json').read_text())
    if any(x.get('passed') is False for x in model['checks']): raise SystemExit('A generated geometry check failed')
    if model['revision'] != REVISION or len(model['parts']) != 15 or len(model['railAssembly']) == 0:
        raise SystemExit('Unexpected assembly or print inventory')
    assembly=model['scenes']['assembly']
    if len([p for p in assembly if p.get('existingReference')]) != 66:
        raise SystemExit('Reference component count changed')
    inventory={}
    for part in assembly: inventory.setdefault(part['cat'],[]).append(part['id'])
    (out/'BOM.json').write_text(json.dumps({'revision':REVISION,'printed':model['parts'],'assembly_inventory':inventory,'reference_components':{'rails':6,'frame_pcbs':2,'row_padders':6,'spacers':10,'mount_bolts':10,'outer_washers':10,'mount_nuts':10,'rail_end_screws':12},'body_brackets':20,'lid_brackets':8},ensure_ascii=False,indent=2)+'\n')
    print_ids={p['id'] for p in model['parts']}
    baseline=json.loads((ROOT/'reference/P5-BASELINE.json').read_text())
    old_hashes={f['path']:f['sha256'] for f in baseline['files']}
    mapping=[]
    for pid in sorted(print_ids):
        for ext in ('stl','step'):
            old_path=f'engineering/printed-5mm/p4-uniform-vents/out/{ext}/{pid}.{ext}'
            new_hash=sha(out/ext/f'{pid}.{ext}')
            unchanged=new_hash==old_hashes[old_path]
            changed=pid.startswith(('wall-','floor-'))
            if not changed and not unchanged: raise SystemExit('Unchanged P4 part differs: '+pid)
            mapping.append({'part':pid,'format':ext,'p4_path':old_path,'p4_sha256':old_hashes[old_path],'p5_path':f'{ext}/{pid}.{ext}','p5_sha256':new_hash,'unchanged_bytes':unchanged,'change':'J3 tab joint' if changed else 'unchanged'})
    (out/'PRINT-MAPPING.json').write_text(json.dumps(mapping,indent=2)+'\n')

    structural={x for x in print_ids if x not in {'pad-horizontal','pad-vertical','washer-round'}}
    if len(structural)!=12: raise SystemExit('Structural print count changed')
    start = (ROOT/'README.md').read_text()
    (out/'PRINT-START-HERE.md').write_text(start)
    print_files=[out/folder/f'{p}.{folder}' for p in print_ids for folder in ('stl','step')]
    source_files=[p for p in (out/'source').iterdir() if p.is_file() and p.name!='model.json']+[p for p in (out/'reference').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']+[out/'PRINT-START-HERE.md']+[out/name for name in ('build.py','verify.py','negative.py','validate_parameters.py','regenerate.py','pyproject.toml','uv.lock','.python-version','README.md')]
    zip_files(out/'printed-5mm-p5-tab-joints-stl.zip',out,print_files+[out/'PRINT-START-HERE.md',out/'BOM.json',out/'PRINT-PARTS.csv',out/'PRINT-MAPPING.json',out/'VENTILATION.json',out/'JOINTS.json',out/'reference/accepted-j3/RECEIPT.json',out/'reference/P4-SOURCE-RECEIPT.json'])
    zip_files(out/'printed-5mm-p5-tab-joints-source.zip',out,source_files)
    zip_files(out/'printed-5mm-p5-tab-joints-body.zip',out,[f for f in print_files if f.stem.startswith(('wall-','floor-'))]+[out/'PRINT-START-HERE.md',out/'PRINT-MAPPING.json'])
    artifacts=[p for p in out.rglob('*') if p.is_file() and p.name!='outputs-manifest.json' and '__pycache__' not in p.parts]
    (out/'outputs-manifest.json').write_text(json.dumps({'revision':REVISION,'source_parameter_sha256':sha(ROOT/'source/parameters.json'),'files':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(artifacts)]},indent=2)+'\n')
    print('P5 full build complete:',out)
if __name__=='__main__': main()
