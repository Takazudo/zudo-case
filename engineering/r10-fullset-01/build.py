#!/usr/bin/env python3
"""R10 selected one-case prototype. Locked CadQuery 2.7; no supplier operations."""
from pathlib import Path
import argparse, json, sys, hashlib, zipfile, math
from collections import Counter
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent/'r9-fitfix-01'),str(ROOT.parent/'r9-lid-m5-01')]
import cadquery as cq
from fitfix import io
from fitfix.geometry import Body,Guard,interface
from fitfix.reference import load_reference
from lidm5.geometry import M5,lid_parts_m5
from fullset import geometry as g
REV='R10-FULLSET-01'
io.REVISION=REV

def washer(p):
    w,l,t=p['width'],p['length'],p['thickness'];r=p['corner_radius'];e=p['eccentricity']
    assert min(w,l,t,p['hole_diameter'])>0 and all(math.isfinite(v) for v in (w,l,t,r,e,p['xy_fit'],p['elephant_foot']))
    if p['shape']=='round':s=g.disk(0,e,0,t,w/2)
    elif p['shape']=='capsule':s=g.slot(0,e,l,w,0,t,90)
    else:s=g.rr(-w/2,w/2,e-l/2,e+l/2,0,t,r)
    hole=p['hole_diameter']/2+p['xy_fit']
    if hole<=0:raise ValueError('Nonpositive compensated bore')
    s=s.cut(g.disk(0,0,-1,t+1,hole))
    ef=p['elephant_foot']
    if ef<0 or ef>=t:raise ValueError('elephant_foot must be >=0 and < thickness')
    if ef:s=s.cut(cq.Solid.makeCone(hole+ef,hole,ef,cq.Vector(0,0,0)))
    return s.clean()

def export(s,out,stem):
    assert s.isValid() and len(s.Solids())==1 and s.Volume()>0,stem
    st=out/(stem+'.step');sl=out/(stem+'.stl');io.step(s,st);io.stl(s,sl)
    check=io.inspect_stl(sl,s);back=cq.importers.importStep(str(st)).val()
    assert back.isValid() and len(back.Solids())==1
    assert abs(back.Volume()-s.Volume())<max(.001,s.Volume()*1e-8)
    assert max(abs(a-b) for a,b in zip(io.bounds(s)['size'],io.bounds(back)['size']))<1e-5
    return dict(step=stem+'.step',stl=stem+'.stl',dimensions_mm=io.bounds(s)['size'],readback=check)

def archive(out,name,files):
    with zipfile.ZipFile(out/name,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(set(files)):
            info=zipfile.ZipInfo(f,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,(out/f).read_bytes())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'out');ap.add_argument('--washers-only',action='store_true');ap.add_argument('--washer-parameters',type=Path,default=ROOT/'washers.json');a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if not cq.__version__.startswith('2.7.'):raise ValueError('Use the repository locked CAD environment')
    p=json.loads((ROOT/'parameters.json').read_text());wp=json.loads(a.washer_parameters.read_text());records=[]
    for name,params in wp['types'].items():
        s=washer(params);records.append(dict(id=name,**export(s,out,'home-print/'+name+'-mm')))
    io.write_json(out/'home-print/parameters.json',wp)
    io.write_json(out/'home-print/readback.json',records)
    if a.washers_only:
        print('Home washer geometry exported:',out/'home-print');return
    print('Source intake',flush=True)
    r6,entries=load_reference(ROOT.parent/'r6-body')
    assert all(abs(x-y)<1e-6 for x,y in zip((r6.W,r6.D,r6.H,r6.T),p['body'].values()))
    g.W,g.D,g.H,g.T=r6.W,r6.D,r6.H,r6.T;g.XM,g.YM=r6.XM,r6.YM
    g.XS=list(r6.BOTTOM_XS);g.YS=list(r6.BOTTOM_YS);g.MOUNT_Y=list(r6.MOUNT_YS);g.MOUNT_Z=r6.MOUNT_Z;g.ZS=r6.iv('verticalBracketCenterHeightsMm')
    assert p['guard']['cover']==5 and p['guard']['end_gap']==.5 and p['guard']['vertical_end_gap']==.25
    # One configuration drives the R2 topology; comparisons are never supplier outputs.
    assert p['slot']==dict(length=10.5,width=5.5,nominal_shift=1.)
    assert p['guard']['wall']==1 and p['guard']['fit_per_face']==.1 and p['guard']['adhesive_per_face']==0
    # Printable geometry and placed geometry share the same parameter definitions.
    def cap(u,v,n0,n1,kind='corner',outline_only=False):
        params=wp['types'][kind+'-cap']
        if abs(params['thickness']-(n1-n0))>1e-8:raise ValueError('Thickness changes require stack redesign')
        if outline_only:
            copy=dict(params);copy['hole_diameter']=1e-6;copy['xy_fit']=0;copy['elephant_foot']=0
            shape=washer(copy)
        else:shape=washer(params)
        return shape.translate((u,v,n0))
    def capsule(u,v,n0,n1,ang=0):
        params=wp['types']['capsule-pad']
        if abs(params['thickness']-(n1-n0))>1e-8:raise ValueError('Thickness changes require stack redesign')
        return washer(params).rotate((0,0,0),(0,0,1),ang-90).translate((u,v,n0))
    g.outer_cap=cap;g.coverwasher=capsule
    print('Integrated body and joints',flush=True)
    items=g.build_case(True,p['guard']['wall']);shapes=g.solids
    b=Body(**p['body']);guard=Guard(**p['guard']);lid=p['lid'];m=M5(**p['m5']);m.validate(8,5)
    parts,holes,sites=lid_parts_m5(b,guard,lid,m);inter=interface(b,guard,lid)
    for part in parts:
        g.add(items,part.shape,part.id,part.id,'lid' if part.group=='lid' else 'lidMetal',material=part.material,explode=[0,0,2],role='lid')
    # Real source frame solids and original rail triangle meshes. No contour substitution.
    keep={'rail','fixer','padder','innerSpacer','outerWasher','mountBolt','mountNut','railEndBolt'}
    reference=[]
    for e in entries:
        if e.get('role') not in keep:continue
        if e['role']=='rail':
            key='source-'+e['id'];g.meshes[key]={'p':e['positions'],'i':e['indices']}
            pts=list(zip(*[e['positions'][i:i+3] for i in range(0,len(e['positions']),3)]));bb=[min(v) for v in pts]+[max(v) for v in pts]
            items.append(dict(id=e['id'],name=e['name'],cat='sourceFrame',mesh=key,box=bb,note='Pinned original 204mm rail mesh; unchanged',material='existing rail',role='rail',group=e['id'],volume=None,solids=None,explode=[0,0,1]))
        else:g.add(items,r6.SHAPES[e['id']],e['id'],e['name'],'sourceFrame',material='existing PCB/hardware',role=e['role'],explode=[0,0,1])
        reference.append(dict(id=e['id'],role=e['role'],quantity=1,procurement='existing/reused'))
    # Independent flat plates: local x/y correspond to each explicit face basis.
    registry=[];hole_table=[]
    for f in g.FACES:
        s=g.panel(f,p['slot']['length']);u,v=p['hanging_holes'][f]
        s=s.cut(g.disk(u,v,-g.T-1,1,2)).clean();world=g.world(s,f)
        id='panel-'+f;shapes[id]=world
        item=next(x for x in items if x['id']==id);item['mesh']=g.mesh(world)
        bb=io.bounds(s);lo=bb['min'];flat=s.translate(tuple(-x for x in lo))
        row=dict(id=id,quantity=1,procurement='aluminum',material='A5052 t1.5; deburred; black anodized after machining',**export(flat,out,'aluminum/'+id+'-qty1-mm'))
        rs=[];slots=[]
        for u0,v0,ang,kind in g.panel_holes(f):
            hole_table.append(dict(part=id,local_uv=[u0-lo[0],v0-lo[1]],assembly_xyz=g.worldpoint(f,u0,v0,0),kind=kind,diameter=5.5,slot_length=None if ang is None else 10.5,angle=ang))
            if ang is None:rs.append((u0-lo[0],v0-lo[1],5.5))
            else:slots.append((u0-lo[0],v0-lo[1],10.5,5.5,ang))
        rs.append((u-lo[0],v-lo[1],4));row['hanging_hole_uv']=list(rs[-1][:2]);row['fixture_mark_region']='Around dedicated D4 hole; supplier confirmation pending'
        row['dxf']='aluminum/'+id+'-qty1-mm.dxf';io.dxf(out/row['dxf'],bb['size'][0],bb['size'][1],rs,slots)
        row['local_to_assembly']=dict(origin=g.worldpoint(f,*lo),x=g.FACES[f][1],y=g.FACES[f][2],z=g.FACES[f][3])
        registry.append(row)
    lp=shapes['lid-plate'];z=inter['plate_bottom_z_mm'];hx,hy=p['hanging_holes']['lid'];lp=lp.cut(g.disk(hx,hy,z-1,z+3,2)).clean();shapes['lid-plate']=lp
    next(x for x in items if x['id']=='lid-plate')['mesh']=g.mesh(lp)
    w,d,t=inter['lid_plate_mm'];flat=lp.translate((w/2,d/2,-z))
    row=dict(id='lid-plate',quantity=1,procurement='aluminum',material='A5052 t1.5; deburred; black anodized after machining',**export(flat,out,'aluminum/lid-plate-qty1-mm'))
    row['dxf']='aluminum/lid-plate-qty1-mm.dxf';row['hanging_hole_uv']=[hx+w/2,hy+d/2];row['local_to_assembly']=dict(origin=[-w/2,-d/2,z],x=[1,0,0],y=[0,1,0],z=[0,0,1]);io.dxf(out/row['dxf'],w,d,[(x+w/2,y+d/2,5.5) for x,y in holes]+[(hx+w/2,hy+d/2,4)],radius=lid['plate_corner_radius']);registry.append(row)
    for x,y in holes:hole_table.append(dict(part='lid-plate',local_uv=[x+w/2,y+d/2],assembly_xyz=[x,y,z],kind='lid',diameter=5.5))
    print('Export PA12 full-length parts',flush=True)
    for item in items:
        if item['role'] not in ('guard','lid') or item['id']=='lid-plate':continue
        id=item['id'];s=shapes[id];bb=io.bounds(s);local=s.translate(tuple(-x for x in bb['min']))
        registry.append(dict(id=id,quantity=1,procurement='pa12',material='MJF PA12-HP; black dyed',local_to_assembly=dict(translation=bb['min']),**export(local,out,'pa12/'+id+'-qty1-mm')))
    assert sum(r['quantity'] for r in registry if r['procurement']=='aluminum')==6
    assert sum(r['quantity'] for r in registry if r['procurement']=='pa12')==20
    counts=Counter()
    for item in items:
        id=item['id']
        if id.startswith('inner-') or id.startswith('cap-floor'):kind='capsule-pad'
        elif id.startswith('cap-'):kind='lower-cap' if item['box'][5]<30 else 'corner-cap'
        elif id.startswith('retain-') or id.startswith('outer-washer-'):kind='round-replacement'
        else:continue
        item['print_type']=kind;counts[kind]+=1
    assert counts=={'capsule-pad':46,'corner-cap':16,'lower-cap':10,'round-replacement':20},counts
    for r in records:
        r.update(quantity=counts[r['id']],procurement='home-print' if r['id']!='round-replacement' else 'existing/reused; optional home replacement',material='black ASA',instances=[i['id'] for i in items if i.get('print_type')==r['id']]);registry.append(r)
    manifest=dict(revision=REV,profile=p['selected_profile'],model='7u40',units='mm',production_approved=False,status='preparation-in-progress',parameters_sha256=io.digest(ROOT/'parameters.json'),washer_parameters_sha256=io.digest(a.washer_parameters),parts=registry,existing_frame=reference,interface=inter,prices=p['costs'])
    io.write_json(out/'selected-order.json',manifest);io.write_json(out/'hole-table.json',hole_table)
    io.write_json(out/'scene.json',dict(revision=REV,profile=p['selected_profile'],meshes=g.meshes,scenes={'new1':items}))
    io.write_json(out/'geometry-checks.json',g.audits)
    from fullset.validation import check
    report=check(shapes,items,out)
    print('Nominal validation:',report['passed'],flush=True)
    print('Written',len(registry),'part definitions',out,flush=True)

if __name__=='__main__':main()
