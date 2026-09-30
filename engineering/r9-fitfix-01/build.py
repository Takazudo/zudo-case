#!/usr/bin/env python3
"""Regenerate the isolated 7U40 #99/#100/#101 fix candidate.

Run in the repository's locked environment:
  uv run --project ../r9-prototype-01 python build.py
Cloud execution used the available CadQuery version; see out/environment.json.
The repository's current R9 outputs/ledgers are NOT overwritten by this command.
"""
from __future__ import annotations
import argparse,base64,csv,hashlib,json,math,platform,shutil,sys,time,zipfile
from dataclasses import replace
from pathlib import Path
import cadquery as cq
import ezdxf,numpy as np
from fitfix.geometry import *
from fitfix import io
from fitfix.reference import load_reference,slotted_plates
from fitfix.coupons import coupon_families
from fitfix.validation import validate_variant,validate_mutations,pairs,overlap

ROOT=Path(__file__).resolve().parent

def flat_dxf_for_coupon(p,part):
    bb=io.bounds(part.shape);axis=min(range(3),key=lambda x:bb['size'][x]);uv=[x for x in range(3) if x!=axis]
    if abs(bb['size'][axis]-1.5)>1e-5:raise ValueError('Coupon metal not t1.5')
    holes=set()
    for e in part.shape.Edges():
        if e.geomType()=='CIRCLE' and abs(e.Length()-2*math.pi*e.radius())<1e-5:
            c=e.Center().toTuple();holes.add(tuple(round(x,8) for x in (c[uv[0]]-bb['min'][uv[0]],c[uv[1]]-bb['min'][uv[1]],2*e.radius())))
    io.dxf(p,bb['size'][uv[0]],bb['size'][uv[1]],sorted(holes))
    return dict(origin_assembly_mm=bb['min'],axes=uv,thickness_axis=axis,holes=[list(h) for h in sorted(holes)])

def zip_subset(path,files,root):
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(set(files)):
            info=zipfile.ZipInfo(f.relative_to(root).as_posix(),date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16;z.writestr(info,f.read_bytes())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference-root',type=Path,default=ROOT.parent/'r6-body');ap.add_argument('--out',type=Path,default=ROOT/'out');ap.add_argument('--skip-reference-hardware',action='store_true',help='Only for quick debugging; cannot be called full validation')
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();data=json.loads((ROOT/'parameters.json').read_text());b=Body(**data['body'])
    g=Guard(**{k:v for k,v in data['guard'].items() if k!='comparison_wall'});l=data['lid']
    entries=[];r6=None;hardware=[];rails=[];reference_parts=[];flat=[];hole_table=[]
    if not args.skip_reference_hardware:
        r6,entries=load_reference(args.reference_root)
        reference_dimensions=(r6.W,r6.D,r6.H,r6.T)
        requested_dimensions=(b.width,b.depth,b.height,b.metal)
        if any(abs(x-y)>1e-6 for x,y in zip(reference_dimensions,requested_dimensions)):
            raise ValueError('Body dimensions must match the pinned nominal R6/R9 reference. Update the reference adapter for a body redesign; changing the guard parameters remains supported.')
        reference_parts,flat,hole_table=slotted_plates(r6,entries)
        hardware=[Part(e['id'],r6.SHAPES[e['id']],group='reference-hardware') for e in entries
                  if e['id'] in r6.SHAPES and e.get('role')!='aluminumPanel']
        for e in entries:
            if e.get('role')=='rail':
                v=np.array(e['positions']).reshape(-1,3);lo=v.min(axis=0);hi=v.max(axis=0)
                rails.append(Part(e['id'],box(lo[0],hi[0],lo[1],hi[1],lo[2],hi[2]),group='reference-rail-envelope'))
        assert len(rails)==6
    else:reference_parts=body_envelopes(b)
    manifest=[];meshchecks=[];bom=[];scene={'revision':data['revision'],'status':'UNAPPROVED / fit-fix candidate','body':vars(b),'variants':{},'reference':[],'coupons':{}}
    def export(part,folder,variant='shared',order_quantity=None):
        folder=out/folder;folder.mkdir(parents=True,exist_ok=True)
        stem=f'7u40-r9f-{part.id}-qty{part.quantity}-mm';st=folder/(stem+'.step');sl=folder/(stem+'.stl')
        io.step(part.shape,st);io.stl(part.shape,sl);record=io.inspect_stl(sl,part.shape)
        meshchecks.append(dict(path=sl.relative_to(out).as_posix(),**record))
        reimport=cq.importers.importStep(str(st)).val()
        assert reimport.isValid() and len(reimport.Solids())==1
        assert abs(reimport.Volume()-part.shape.Volume())<max(.001,part.shape.Volume()*1e-8)
        for pp in (st,sl):manifest.append(dict(path=pp.relative_to(out).as_posix(),sha256=io.digest(pp),bytes=pp.stat().st_size,part=part.id,variant=variant))
        bm=dict(part=part.id,variant=variant,material=part.material,group=part.group,
                per_set_quantity=part.quantity,order_quantity=part.quantity if order_quantity is None else order_quantity,
                dimensions_mm=io.bounds(part.shape)['size'],volume_mm3=part.shape.Volume(),stl=sl.relative_to(out).as_posix(),step=st.relative_to(out).as_posix())
        bom.append(bm);return bm
    for p in flat:
        part=Part('body-'+p['id'],p['shape'],p['quantity'],'A5052 t1.5 black anodized candidate','body-metal')
        r=export(part,'aluminum/body','shared');dx=out/'aluminum/body'/f'7u40-r9f-{part.id}-qty{p["quantity"]}-mm.dxf'
        io.dxf(dx,p['width'],p['height'],p['holes'],p['slots']);r['dxf']=dx.relative_to(out).as_posix()
    io.write_json(out/'aluminum/hole-table.json',{'provenance':'R6 hole centers with the R9 slot rule; compare to on-disk R9 DXF before integration','holes':hole_table})
    # Nominal reference only: no hardware or PCB STL is an order item.
    for p in reference_parts:scene['reference'].append(io.mesh_record(p.shape,p.id,'metal'))
    for e in entries:
        if e.get('role')=='aluminumPanel':continue
        if e.get('role')=='rail':
            scene['reference'].append(dict(id=e['id'],group='rails',positions=e['positions'],indices=e['indices']))
        elif e['id'] in r6.SHAPES:
            group='pcb' if e.get('role') in ('fixer','padder') else 'hardware'
            scene['reference'].append(io.mesh_record(r6.SHAPES[e['id']],e['id'],group))
    report={'scope':'nominal CAD and file readback; no physical fit/loads/adhesion test',
            'reference_hardware_scope':'Pinned R6 nominal placements, which R9 retained; slotted plates reconstructed from the pinned R6 centers and R9 rule. Not execution of the entire R9 pipeline.',
            'reference_hardware_included':not args.skip_reference_hardware,
            'variants':{},'coupons':{},'physical_results':None,'production_approved':False}
    for tag,gg in [('t1p2',g),('t1p0',replace(g,wall=data['guard']['comparison_wall']))]:
        print('Build',tag,flush=True)
        gp=guard_parts(b,gg,tag);instances=guard_instances(gp);lp,holes=lid_parts(b,gg,l);i=interface(b,gg,l)
        for p in gp:export(p,f'pa12/{tag}/guards',tag)
        for p in lp:
            r=export(p,f'pa12/{tag}/lid' if p.group=='lid' else f'aluminum/{tag}',tag)
            if p.group=='lid-metal':
                w,d,t=i['lid_plate_mm'];dx=out/f'aluminum/{tag}/7u40-r9f-lid-plate-qty1-mm.dxf'
                io.dxf(dx,w,d,[(x+w/2,y+d/2,l['assembly_hole']) for x,y in holes],radius=l['plate_corner_radius']);r['dxf']=dx.relative_to(out).as_posix()
        io.step(cq.Compound.makeCompound([p.shape for p in reference_parts+instances+lp]),out/f'assembly/{tag}-assembled-REFERENCE.step')
        scene['variants'][tag]={'interface':i,'meshes':[io.mesh_record(p.shape,p.id,'lid' if p.group=='lid' else 'lidMetal' if p.group=='lid-metal' else 'guards') for p in instances+lp]}
        io.write_json(out/f'interface-{tag}.json',i)
        report['variants'][tag]=validate_variant(b,gg,l,instances,lp,hardware,rails)
        print('Validation',tag,report['variants'][tag]['passed'],report['variants'][tag]['failed_checks'],flush=True)
    couponrecords=coupon_families(b,g,l)
    for c in couponrecords:
        rows=[];meshes=[]
        for p in c['parts']:
            reuse=c['id'] in ('C2-02','C2-03') and not p.id.endswith('-frame')
            r=export(p,'coupons/'+c['id'].lower(),'coupon',0 if reuse else None)
            if p.group=='coupon-metal':
                pp=out/'coupons'/c['id'].lower()/f'7u40-r9f-{p.id}-qty{p.quantity}-mm.dxf'
                r['dxf_transform']=flat_dxf_for_coupon(pp,p);r['dxf']=pp.relative_to(out).as_posix()
            rows.append(r);meshes.append(io.mesh_record(p.shape,p.id,'metal' if p.group=='coupon-metal' else 'lid' if '-frame' in p.id else 'guards'))
        check=pairs(c['parts']);report['coupons'][c['id']]=check
        serial={k:v for k,v in c.items() if k!='parts'};serial['parts']=rows
        io.write_json(out/'coupons'/c['id'].lower()/'manifest.json',serial)
        scene['coupons'][c['id']]={'meshes':meshes,'description':c['purpose']}
        print('Coupon',c['id'],check['passed'],flush=True)
    report['parameter_mutations']=validate_mutations(b,g,l)
    report['mesh_step_checks']=meshchecks
    report['passed']=all(v['passed'] for v in report['variants'].values()) and all(v['passed'] for v in report['coupons'].values())
    report['unverified']=['Original R9 CI (separate verification)',
                          'Continuous motion between sampled lift positions',
                          'Actual module knobs, head/nut/driver dimensions and washer selection',
                          'Adhesive fills the final measured lateral gap and retains guards',
                          'Manufacturing tolerances/warpage, long-part shrinkage, anodized finish',
                          'Physical strap tension, lid deflection, drop/fatigue/transport',
                          'Local documentation/ledger/preview integration into main']
    io.write_json(out/'validation.json',report)
    env={'python':sys.version,'cadquery':cq.__version__,'ezdxf':ezdxf.__version__,'numpy':np.__version__,'platform':platform.platform(),
         'repository_python_cq_range_compatible':sys.version_info[:2]==(3,12) and cq.__version__.startswith('2.7.'),'lockfile_execution_verified':None,'seconds':round(time.monotonic()-started,2)}
    io.write_json(out/'environment.json',env);io.write_json(out/'BOM.json',bom)
    with (out/'BOM.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['variant','part','material','per_set_quantity','order_quantity','volume_mm3','stl','step','dxf'],extrasaction='ignore');writer.writeheader();writer.writerows(bom)
    io.write_json(out/'scene.json',scene)
    # Preview uses the generated shapes. All JS and mesh data are inline.
    from fitfix.preview import make_preview
    make_preview(scene,ROOT/'vendor/three-bundle.js',out/'preview.html')
    # Separate ordering categories, with a readable quantity table in each.
    notice=out/'NOT-APPROVED.txt';notice.write_text('UNAPPROVED PROTOTYPE — mm — each STL is one part; use the quantity table.\nAluminum STEP/DXF are separate from PA12. Hardware/rails are references only.\nThis is an unapproved fit-fix candidate; see environment.json for the generating toolchain.\n',encoding='utf-8')
    def order_table(name,rows):
        path=out/'order-tables'/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=['part','material','order_quantity','stl','step','dxf'],extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
        return path
    for tag in ('t1p2','t1p0'):
        rows=[r for r in bom if r['variant']==tag and r['group'] in ('guard','lid')]
        table=order_table('pa12-'+tag+'.csv',rows)
        zip_subset(out/f'7u40-{tag}-pa12-NOT-APPROVED.zip',[out/r['stl'] for r in rows]+[table,notice],out)
    for tag in ('t1p2','t1p0'):
        rows=[r for r in bom if r['group']=='body-metal' or (r['variant']==tag and r['group']=='lid-metal')]
        table=order_table('aluminum-'+tag+'.csv',rows)
        zip_subset(out/f'7u40-{tag}-aluminum-NOT-APPROVED.zip',[out/r[k] for r in rows for k in ('step','dxf')]+[table,notice],out)
    rows=[r for r in bom if r['variant']=='coupon' and r['group']=='coupon' and r['order_quantity']>0]
    table=order_table('coupons-pa12.csv',rows)
    zip_subset(out/'fit-coupons-pa12-NOT-APPROVED.zip',[out/r['stl'] for r in rows]+[table,notice],out)
    rows=[r for r in bom if r['variant']=='coupon' and r['group']=='coupon-metal' and r['order_quantity']>0]
    table=order_table('coupons-metal.csv',rows)
    zip_subset(out/'fit-coupons-metal-NOT-APPROVED.zip',[out/r[k] for r in rows for k in ('step','dxf')]+[table,notice],out)
    files=[]
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name not in ('outputs-manifest.json','environment.json'):
            files.append(dict(path=path.relative_to(out).as_posix(),sha256=io.digest(path),bytes=path.stat().st_size))
    inputs=[]
    for source in sorted([ROOT/'build.py',ROOT/'parameters.json',ROOT/'vendor/three-bundle.js',ROOT.parent/'r9-prototype-01/uv.lock',*list((ROOT/'fitfix').glob('*.py'))]):
        inputs.append(dict(path=__import__('os').path.relpath(source, ROOT),sha256=io.digest(source)))
    io.write_json(out/'outputs-manifest.json',{'revision':data['revision'],'base_commit':data['base_commit'],'production_approved':False,'inputs':inputs,'files':files})
    print('DONE',len(files),'files;',len(meshchecks),'mesh readbacks; passed=',report['passed'],'seconds=',env['seconds'],flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
