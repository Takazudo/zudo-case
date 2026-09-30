#!/usr/bin/env python3
"""Emit (do not apply) candidate-ledger additions for locally verified output.

Requires an explicit --after-local-verification. Never writes project/*,
engineering/release, approval/gates/prices or public files. Hashes are recomputed;
cloud hashes must not be reused after a different-toolchain regeneration.
"""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'out');p.add_argument('--after-local-verification',action='store_true');a=p.parse_args()
    if not a.after_local_verification:p.error('First perform locked regeneration, DXF parity, tests and human review; then explicitly use --after-local-verification')
    out=a.out.resolve();report=json.loads((out/'validation.json').read_text());manifest=json.loads((out/'outputs-manifest.json').read_text())
    if report.get('passed') is not True or report.get('reference_hardware_included') is not True:
        raise SystemExit('Full candidate checks with reference hardware are required')
    for source in manifest.get('inputs',[]):
        if hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest()!=source['sha256']:raise SystemExit('Generator changed since build: '+source['path'])
    candidates=[];lid=[]
    for f in manifest['files']:
        path=out/f['path'];h=hashlib.sha256(path.read_bytes()).hexdigest()
        if h!=f['sha256']:raise SystemExit('Output changed: '+f['path'])
        if path.suffix not in ('.step','.stl','.dxf') or f['path'].startswith('assembly/'):continue
        rel=f['path'];is_lid=('/lid/' in rel or rel.startswith('aluminum/t1p'))
        c={'id':'r9f-'+re.sub('[^a-z0-9]+','-',rel.lower()).strip('-'),
           'component':'lid' if is_lid else 'coupon' if rel.startswith('coupons/') else 'body',
           'model':'7u40','revision':manifest['revision'],
           'path':'engineering/r9-fitfix-01/out/'+rel,'sha256':h}
        candidates.append(c)
        if is_lid and '/t1p2/' in rel:lid.append(c['id'])
    result={'NOT_AUTOMATICALLY_APPLIED':True,'candidate_files_to_append':candidates,
            'proposed_current_lid_manufacturing':{'model':'7u40','revision':manifest['revision'],'candidate_ids':lid},
            'preserve':{'production_approved':False,'published_release_files':[],'all_G_results':'unchanged; physical tests are still pending'},
            'integration_warning':'Update/parameterize existing sync-r9-ledger/current-spec/docs checks to understand the new candidate. Do not overwrite old references or mark manufactured.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
