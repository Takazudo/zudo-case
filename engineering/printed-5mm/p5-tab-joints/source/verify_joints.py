"""Independent exported BRep checks against immutable received J3 fixtures."""
from pathlib import Path
import json, itertools, hashlib
import cadquery as cq
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def check(name,ok,**kw):
    checks.append(dict(check=name,passed=bool(ok),**kw))
    if not ok: raise ValueError(checks[-1])
def read(path): return cq.importers.importStep(str(path)).val()
def box(x0,x1,y0,y1,z0,z1):return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
fixture=ROOT/'reference/accepted-j3'
for f in json.loads((fixture/'RECEIPT.json').read_text())['files']:
    check('immutable acceptance '+f['path'],hashlib.sha256((fixture/f['path']).read_bytes()).hexdigest()==f['sha256'])
parts={p.stem:read(p) for p in (ROOT/'step').glob('*.step')}
body={k:s for k,s in parts.items() if k.startswith(('wall-','floor-'))}
for pid,s in body.items():
    accepted=read(fixture/(pid+'.step'))
    differences=[s.cut(accepted).Volume(),accepted.cut(s).Volume()]
    check('accepted J3 bidirectional Boolean '+pid,max(differences)<1e-5,difference_mm3=differences)
    check('accepted J3 area '+pid,abs(s.Area()-accepted.Area())<1e-4)
    check('positive connected BRep '+pid,s.isValid() and len(s.Solids())==1 and s.Volume()>0)
for pid in ('wall-left','wall-right'):
    s=body[pid];b=s.BoundingBox()
    check('side overall '+pid,all(abs(x-y)<1e-5 for x,y in zip([b.xlen,b.ylen,b.zlen],[5,349,98])))
    for name,z0,z1 in [('upper',87,94.5),('lower',-3.5,-3.4)]:
        band=s.intersect(box(-120,120,-180,180,z0,z1)).BoundingBox()
        check('341mm '+name+' '+pid,abs(band.ylen-341)<1e-5)
    end=max((f for f in s.Faces() if f.geomType()=='PLANE' and f.BoundingBox().xlen<1e-5),key=lambda f:f.Area())
    check('46 separate openings '+pid,len(end.innerWires())==46)
for a,b in itertools.combinations(body,2):
    volume=body[a].intersect(body[b]).Volume()
    check('body separate '+a+'/'+b,volume<1e-5,overlap_mm3=volume)
for side,sign in [('left',-1),('right',1)]:
    for dx in (0,1,2,3,4.7,6,12,24):
        s=body['wall-'+side].translate((sign*dx,0,0))
        volume=sum(s.intersect(body[k]).Volume() for k in ('wall-front','wall-back','floor-1','floor-2'))
        check('X insertion '+side+'/'+str(dx),volume<1e-5,overlap_mm3=volume)
for pid,lid in parts.items():
    if not pid.startswith('lid-'):continue
    for dz in (0,.5,1,4,7.5,15):
        volume=sum(lid.translate((0,0,dz)).intersect(s).Volume() for s in body.values())
        check('lid lift '+pid+'/'+str(dz),volume<1e-5,overlap_mm3=volume)
model=json.loads((ROOT/'source/model.json').read_text())
assembly=model['scenes']['assembly']
windows=json.loads((fixture/'GEOMETRY.json').read_text())['receiver_windows']
projection=[]
for w in windows:
    sign=1 if w['part']=='wall-right' else -1;y,z=w['center_yz'];ww,hh=w['size_yz']
    candidates=[]
    for row in assembly:
        b=row['box'];on=b[0]>=90 and b[3]>=112 if sign>0 else b[3]<=-90 and b[0]<=-112
        if row['group']!='lid' and row['cat'] in ('brackets','washers','hardware','railHardware','railSpacers') and on:
            dy=max(b[1]-(y+ww/2),(y-ww/2)-b[4],0);dz=max(b[2]-(z+hh/2),(z-hh/2)-b[5],0)
            candidates.append(((dy*dy+dz*dz)**.5,row['id']))
    gap,near=min(candidates);projection.append(dict(id=w['id'],gap_mm=gap,nearest=near))
    check('receiver hardware projection '+w['id'],gap>0,minimum_mm=gap,nearest=near)
check('receiver hardware minimum',abs(min(r['gap_mm'] for r in projection)-1.131370849898482)<1e-5)
model['joint']={'receiver_hardware_distances':projection,'receiver_count':16,'integral_tab_count':16,'shoulder_clearance_mm':.15,'tip_recess_mm':.3,'insertion_mm':4.7,'slot_clearance_each_mm':.2}
(ROOT/'JOINTS.json').write_text(json.dumps(model['joint'],indent=2)+'\n')
model['checks'].extend(checks)
model['dimensions'].update(body_with_registration_lands=[236.4,349,98],foot_clearance_mm=1.5)
import copy
assembly=model['scenes']['assembly']
model['scenes']['baseline']=copy.deepcopy(assembly)
for row in model['scenes']['baseline']:
    if row['id'] in model['baseline_body']:row.update(model['baseline_body'][row['id']])
model['scenes']['insert']=[copy.deepcopy(r) for r in assembly if r['id'] in body]
for key,ids in {'side':['wall-right'],'lid-alignment':['wall-right','lid-edge-right'],'floor':['floor-1','floor-2']}.items():
    model['scenes'][key]=[copy.deepcopy(row) for row in assembly if row['id'] in ids]
for key,region,ids in [('end-joint',box(104,121,-177,-157,12,34),['wall-right','wall-front']),('floor-joint',box(102,121,44,76,-5,10),['wall-right','floor-2'])]:
    rows=[]
    for pid in ids:
        shape=body[pid].intersect(region).clean();verts,faces=shape.tessellate(.025,.15)
        meshkey=key+'-'+pid
        model['meshes'][meshkey]={'p':[round(x,6) for v in verts for x in v.toTuple()],'i':[int(x) for f in faces for x in f]}
        row=copy.deepcopy(next(r for r in assembly if r['id']==pid));b=shape.BoundingBox()
        row.update(id=meshkey,mesh=meshkey,box=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],volume=shape.Volume(),explode=[0,0,0])
        rows.append(row)
    model['scenes'][key]=rows
(ROOT/'DIMENSIONS.json').write_text(json.dumps(model['dimensions'],indent=2))
(ROOT/'source/model.json').write_text(json.dumps(model,separators=(',',':')))
(ROOT/'evidence/joint-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print('P5 joint checks:',len(checks))
