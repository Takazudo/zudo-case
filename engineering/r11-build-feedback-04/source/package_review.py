#!/usr/bin/env python3
"""Package only the successful final review, with data/check consistency gates."""
from pathlib import Path
import argparse,csv,hashlib,json,re,shutil,zipfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'out'
def read(name):return json.loads((OUT/name).read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();dst=args.destination.resolve();dst.mkdir(parents=True,exist_ok=True)
    manifest=read('parts-manifest.json');checks=read('validation.json');refs=read('reference-clearance.json')
    renders=read('preview-renders/render-report.json'); inline=read('inline-renders/inline-report.json')
    delta=read('revision-delta.json'); sizes=read('pa12-size-audit.json')
    baseline=ROOT/'reference/r11-03-baseline'
    assembly_path=json.loads((baseline/'assembly-path-check.json').read_text())
    pricing=json.loads((ROOT/'research/jlc-pa12-pricing-audit.json').read_text())
    assert manifest['validation']['passed'] and checks['passed'] and refs['pass_'] and renders['passed'] and inline['passed'] and delta['passed']
    assert assembly_path['passed'] and assembly_path['complete_route']
    assert all(digest((baseline if name=='parameters.json' else ROOT)/name)==value for name,value in assembly_path['input_hashes'].items()),'Inherited body assembly path inputs are not preserved'
    assert checks['inner_ear_review']['baseline_delta']['checks']['twelve_body_nylon_solids_exactly_unchanged']
    assert checks['lid_locator_review']['passed']
    assert delta['current_manifest_sha256']==digest(OUT/'parts-manifest.json')
    assert sizes['source_manifest_sha256']==digest(OUT/'parts-manifest.json')
    assert pricing['revision']==manifest['revision'] and len(pricing['parts'])==20
    assert next(x['sha256'] for x in pricing['inputs'] if x['path']=='out/parts-manifest.json')==digest(OUT/'parts-manifest.json')
    assert all(p['price'] is None and not p['uploaded'] and p['file_exists'] for p in pricing['parts'])
    assert all(digest(ROOT/p['intended_stl_path'])==p['stl_sha256'] for p in pricing['parts'])
    model_hash=digest(OUT/'scene.json')
    assert renders['model_sha256']==model_hash,'Final preview renders use stale geometry'
    assert inline['source']['source_scene_sha256']==model_hash,'Inline preview uses stale geometry'
    assert renders['template_sha256']==digest(ROOT/'revision/viewer.html'),'Rendered template is stale'
    embedded=re.search(r'<script id="model-data" type="application/json">(.*?)</script>',(OUT/'preview.html').read_text(),re.S)
    assert embedded and json.loads(embedded.group(1))==read('scene.json'),'Standalone preview geometry is stale'
    for p in manifest['parts']:
        for f in p['files'].values():assert digest(OUT/f['path'])==f['sha256'],f
    assert digest(OUT/manifest['assembly_shell']['file']['path'])==manifest['assembly_shell']['file']['sha256']
    rows=[]
    for p in manifest['parts']:
        if p['category']!='aluminum':continue
        flat=p['flat_pattern']
        for k,(x,y,d) in enumerate(flat['round_holes_xy_d_mm']):
            rows.append([p['id'],'round-'+str(k+1),'round',x,y,d,d,''])
        for k,(x,y,length,width,angle) in enumerate(flat['slots_xy_length_width_angle_mm']):
            rows.append([p['id'],'slot-'+str(k+1),'slot',x,y,width,length,angle])
    with (OUT/'panel-hole-map.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['panel_id','hole_id','shape','x_mm','y_mm','width_or_diameter_mm','total_length_mm','angle_deg']);w.writerows(rows)
    report=dict(revision=manifest['revision'],production_approved=False,
                base_commit=json.loads((ROOT/'parameters.json').read_text())['base_commit'],
                scene_sha256=model_hash,component_count=checks['component_count'],
                all_nominal_cad_checks_pass=True,original_frame_clearance_pass=True,
                exported_part_models=len(manifest['parts']),named_shell_assembly_solids=26,
                body_lap_pairs=len(checks['body_lap_contacts']),
                body_bearing_contacts=len(checks['body_fastener_bearing_contacts']),
                lid_bearing_contacts=len(checks['lid']['fastener_bearing']),
                panel_slots_checked=len(checks['slot_extension_checks']),
                exported_panel_holes=len(rows),interactive_preview_views=len(read('scene.json')['scenes']),rendered_preview_states=len(renders['views']),
                original_frame_reference_scope=refs['scope'],
                preview_test_scope=renders['renderer'],
                followup_delta=dict(lid_locator_edges_before=2,lid_locator_edges_after=4,
                                    locator_hardware_reliefs_before=4,locator_hardware_reliefs_after=8,
                                    revised_lid_nylon_parts=6,unchanged_body_nylon_parts=12,
                                    unchanged_lid_nylon_parts=2,unchanged_sheets=6,loose_washers=64),
                inside_ear_review=checks['inner_ear_review']['checks'],
                lid_locator_review=checks['lid_locator_review'],
                inherited_body_assembly_path_check=dict(source='reference/r11-03-baseline/assembly-path-check.json',
                    unchanged_body_geometry_verified=True,report=assembly_path),
                pricing_status=sizes['price_status'],pa12_total_solid_cm3=sizes['total_solid_volume_cm3'],
                max_pa12_axis_mm=sizes['maximum_axis_mm'],
                limitations=['Nominal geometry review; physical fit and purchased hardware remain unmeasured.',
                             'No load, fatigue, tightening-torque or printer-process qualification.',
                             'No live-browser layout or WebGL test; actual CPU mesh rendering and controls tested.',
                             'JLC minimum-price qualification and actual prices are unconfirmed; uploading CAD was blocked pending explicit permission.',
                             'Hanging method for slot-only floor/front/back panels has not been confirmed by JLC.'])
    (OUT/'review-summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    shutil.copyfile(OUT/'preview.html',dst/'zudo-case-r11-04-preview.html')
    shutil.copyfile(ROOT/'README.md',dst/'zudo-case-r11-04-review-notes.md')
    shutil.copyfile(OUT/'preview-renders/lidguides.png',dst/'zudo-case-r11-04-lid-guides.png')
    shutil.copyfile(OUT/'preview-renders/lidfit-exploded.png',dst/'zudo-case-r11-04-lid-side-fit.png')
    shutil.copyfile(ROOT/'research/jlc-pa12-pricing-audit.md',dst/'zudo-case-r11-04-pricing-audit.md')
    quote_rows=[]
    for p in manifest['parts']:
        if p['category']!='pa12':continue
        quoted_name='r11-04-'+p['id']+'-qty1-mm.stl'
        quote_rows.append(dict(file=quoted_name,part_id=p['id'],quantity=1,
                               sha256=p['files']['stl']['sha256'],dimensions_mm=p['dimensions_mm'],
                               volume_mm3=p['volume_mm3'],source=p['files']['stl']['path']))
    quote_plan=dict(revision=manifest['revision'],purpose='Automatic quotation only',
                    destination='https://jlc3dp.com/3d-printing-quote',
                    technology='MJF',material='PA12-HP Nylon',finish='Dyed Black',
                    quantity_each=1,files=quote_rows,uploaded=False,price=None,
                    permission_status='Explicit authorization needed after automatic approval rejection',
                    includes_order_submission=False,includes_supplier_message=False,includes_payment=False)
    (OUT/'quote-upload-plan.json').write_text(json.dumps(quote_plan,indent=2))
    quote_readme=('R11-BUILD-FEEDBACK-04 / twenty PA12 STL models / units mm\n\n'
                  'Purpose: automatic JLC3DP price calculation only, MJF / PA12-HP Nylon / Dyed Black, quantity1 per file.\n'
                  'Destination: https://jlc3dp.com/3d-printing-quote\n'
                  'No files have been uploaded. Explicit permission is needed after automatic approval review blocked the earlier attempt.\n'
                  'No order submission, supplier message, payment, or new terms acceptance is included.\n'
                  'See quote-upload-plan.json for the exact file hashes and dimensions. These are current R11-04 files; the full design package also contains clearly marked historical comparison inputs.\n')
    quote_path=dst/'zudo-case-r11-04-pa12-quote-files.zip'
    with zipfile.ZipFile(quote_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('README.txt',quote_readme)
        z.write(OUT/'quote-upload-plan.json','quote-upload-plan.json')
        for row in quote_rows:z.write(OUT/row['source'],row['file'])
    with zipfile.ZipFile(quote_path) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.endswith('.stl')])==20
        for row in quote_rows:assert hashlib.sha256(z.read(row['file'])).hexdigest()==row['sha256']
    changed_ids={'lid-corner-fl','lid-corner-fr','lid-corner-bl','lid-corner-br',
                 'lid-middle-left','lid-middle-right'}
    changed=[p for p in manifest['parts'] if p['id'] in changed_ids]
    assert len(changed)==6 and all(p['category']=='pa12' for p in changed)
    changed_plan=dict(revision=manifest['revision'],compared_to='R11-BUILD-FEEDBACK-03',
                      production_approved=False,quantity_each=1,units='mm',parts=changed,
                      unchanged_lid_parts=['lid-middle-front','lid-middle-back'],
                      source_manifest_sha256=digest(OUT/'parts-manifest.json'))
    changed_path=dst/'zudo-case-r11-04-changed-lid-parts.zip'
    with zipfile.ZipFile(changed_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('README.txt','R11-04 / six revised lid pieces compared with R11-03 / units mm\n\n'
                   'Quantity 1 each: four corners and left/right middle spans. Each has STEP and STL.\n'
                   'Front/back lid middle spans, all body pieces, all sheets and hardware are unchanged.\n'
                   'Nominal CAD review candidate; physical fit and tightening remain unqualified.\n'
                   'Keep the two unchanged front/back lid spans to complete the eight-piece lid.\n')
        z.writestr('changed-parts-manifest.json',json.dumps(changed_plan,indent=2))
        for p in changed:
            for kind in ('step','stl'):
                item=p['files'][kind];z.write(OUT/item['path'],Path(item['path']).name)
    with zipfile.ZipFile(changed_path) as z:
        assert z.testzip() is None
        for p in changed:
            for kind in ('step','stl'):
                item=p['files'][kind];assert hashlib.sha256(z.read(Path(item['path']).name)).hexdigest()==item['sha256']
    zip_path=dst/'zudo-case-r11-04-design-files.zip'
    excluded={'__pycache__','.DS_Store'}
    files=[p for p in ROOT.rglob('*') if p.is_file() and not any(s in excluded for s in p.parts)
           and p.suffix not in ('.pyc','.zip')]
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(files):z.write(p,Path('zudo-case-r11-04')/p.relative_to(ROOT))
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        assert 'zudo-case-r11-04/out/assembly-shell.step' in z.namelist()
    print(json.dumps(dict(report=report,files=[dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p))
                     for p in sorted(dst.iterdir()) if p.is_file()]),indent=2))

if __name__=='__main__':main()
