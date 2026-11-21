#!/usr/bin/env python3
"""Rebuild R11 CAD, downloadable data and interactive mesh preview.

All inputs are relative to this directory. The reference/ directory contains
immutable R10 inputs, so the review bundle also builds outside the repository.
"""
from pathlib import Path
import argparse, json, time
from revision.core import ROOT, P
from revision.body import build_body
from revision.lid import build_lid, validate_lid
from revision.preview import make_preview


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--preview-only',action='store_true',help='Build CAD and viewer; skip manufacturing exports')
    ap.add_argument('--verify',action='store_true',help='Run nominal CAD contact/intersection and original-frame checks')
    ap.add_argument('--out',type=Path,default=ROOT/'out')
    args=ap.parse_args();start=time.time();args.out.mkdir(parents=True,exist_ok=True)
    print('Building R11 body and lid…',flush=True)
    body,bm=build_body();lid,lm=build_lid();parts=body+lid
    print(f'Built {len(parts)} solid components in {time.time()-start:.1f}s',flush=True)
    if args.verify:
        from revision.validation import validate_all
        from revision.reference_check import validate_reference
        validation=validate_all(parts,bm,lm)
        reference=validate_reference(parts)
        (args.out/'validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False))
        (args.out/'reference-clearance.json').write_text(json.dumps(reference,indent=2,ensure_ascii=False))
        print('CAD validation:',validation['checks'],flush=True)
        print('Reference clearance:',reference['pass_'],flush=True)
        if not validation['passed'] or not reference['pass_']:
            raise RuntimeError('Review check failed; see validation and reference-clearance reports')
    if not args.preview_only:
        from revision.exporter import export_parts
        manifest=export_parts(parts,bm,lm,args.out)
        print('Exports:',manifest['counts'],flush=True)
    # Generate display triangulations after exact checks and file readback.
    # Some OCC bounding-box methods include tessellation deflection; all design
    # bounds use the separate exact helper, and display meshing stays last.
    report=make_preview(parts,bm,lm,args.out)
    print('Preview:',report,flush=True)
    print(f'Done in {time.time()-start:.1f}s: {args.out}',flush=True)


if __name__=='__main__':main()
