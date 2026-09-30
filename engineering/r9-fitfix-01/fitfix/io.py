"""Deterministic-ish CAD exports, explicit local-toolchain provenance and readback.

STEP timestamps/product counters and STL ordering are normalized. Byte stability
is tested in this environment only; cross-CadQuery-version equality is NOT assumed.
"""
from __future__ import annotations
from collections import OrderedDict, Counter
from pathlib import Path
import hashlib, json, math, re, struct
import cadquery as cq
import ezdxf
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

REVISION='R9-FITFIX-01'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bounds(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s.wrapped,b,False,False);b=cq.BoundBox(b)
    return {'min':[b.xmin,b.ymin,b.zmin],'max':[b.xmax,b.ymax,b.zmax],
            'size':[b.xlen,b.ylen,b.zlen]}

def write_json(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def step(s,p):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    cq.exporters.export(s,str(p),exportType='STEP')
    text=p.read_text().replace('\r\n','\n')
    text=re.sub(r'FILE_NAME\s*\(.*?\);',
                f"FILE_NAME('{REVISION}','1970-01-01T00:00:00',('ZUDO CASE'),('ZUDO CASE'),'prototype exporter','ZUDO CASE','');",
                text,count=1,flags=re.S)
    text=re.sub(r'Open CASCADE STEP translator ([0-9.]+) [0-9]+',r'Open CASCADE STEP translator \1 0',text)
    p.write_text('\n'.join(x.rstrip() for x in text.splitlines())+'\n')

def triangles(s,tolerance=.01,angle=.1):
    vv,ff=s.tessellate(tolerance,angle)
    return np.array([v.toTuple() for v in vv],dtype=np.float64),np.array(ff,dtype=np.int64)

def stl(s,p):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    vv,ff=triangles(s);records=[]
    for f in ff:
        pts=[tuple(vv[i]) for i in f];pts=min(pts[n:]+pts[:n] for n in range(3))
        a,b,c=(np.asarray(x) for x in pts);normal=np.cross(b-a,c-a);d=float(np.linalg.norm(normal))
        if d<=0:raise ValueError('Degenerate triangle')
        records.append(struct.pack('<12fH',*(normal/d),*pts[0],*pts[1],*pts[2],0))
    records.sort();p.write_bytes((REVISION+' mm prototype').encode().ljust(80,b'\0')+
                                 struct.pack('<I',len(records))+b''.join(records))

def inspect_stl(p,s):
    raw=Path(p).read_bytes()
    if len(raw)<84:raise AssertionError(f'Short STL: {p}')
    n=struct.unpack_from('<I',raw,80)[0]
    if not n or len(raw)!=84+50*n:raise AssertionError(f'Invalid STL size: {p}')
    dt=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
    triangles=np.frombuffer(raw,dtype=dt,offset=84,count=n)['vertices'].astype(np.float64)
    vertices,inverse=np.unique(triangles.reshape(-1,3),axis=0,return_inverse=True)
    faces=inverse.reshape(-1,3)
    directed=Counter((int(a),int(b)) for f in faces for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])))
    edges=Counter(tuple(sorted(e)) for e in directed.elements())
    closed=all(count==2 for count in edges.values())
    winding=all(a!=b and directed[(a,b)]==1 and directed[(b,a)]==1 for a,b in edges)
    volume=float(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6)
    if not closed or not winding or volume<=0:
        raise AssertionError(f'Invalid mesh {p}: incidence={dict(Counter(edges.values()))}, winding={winding}')
    e=bounds(s);bboxerror=float(np.abs(np.array([vertices.min(axis=0),vertices.max(axis=0)])-np.array([e['min'],e['max']])).max())
    volerror=abs(volume-s.Volume())
    if bboxerror>.011 or volerror>max(.1,s.Volume()*.0005):
        raise AssertionError(f'Mesh/CAD mismatch: {p}, bbox {bboxerror}, volume {volerror}')
    return dict(watertight=True,winding_consistent=True,positive_volume=True,
                vertices=len(vertices),triangles=n,bbox_error_mm=bboxerror,
                volume_error_mm3=float(volerror),cad_volume_mm3=s.Volume(),
                edge_incidence_histogram={str(k):v for k,v in Counter(edges.values()).items()})

def dxf(p,width,height,holes=(),slots=(),radius=0):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    old=ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing=True
    try:
        doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM;msp=doc.modelspace()
        for layer in ('OUTLINE','HOLES','SLOTS'):doc.layers.new(layer)
        if radius:
            r=radius;bulge=math.tan(math.pi/8)
            contour=[(r,0,0,0,0),(width-r,0,0,0,bulge),(width,r,0,0,0),
                     (width,height-r,0,0,bulge),(width-r,height,0,0,0),
                     (r,height,0,0,bulge),(0,height-r,0,0,0),(0,r,0,0,bulge)]
        else:contour=[(0,0),(width,0),(width,height),(0,height)]
        msp.add_lwpolyline(contour,close=True,dxfattribs={'layer':'OUTLINE'})
        for x,y,diameter in holes:msp.add_circle((x,y),diameter/2,dxfattribs={'layer':'HOLES'})
        for x,y,length,w,ang in slots:
            h=(length-w)/2;r=w/2;th=math.radians(ang)
            def point(a,b):return (x+a*math.cos(th)-b*math.sin(th),y+a*math.sin(th)+b*math.cos(th))
            msp.add_line(point(-h,-r),point(h,-r),dxfattribs={'layer':'SLOTS'})
            msp.add_arc(point(h,0),r,start_angle=(ang-90)%360,end_angle=(ang+90)%360,dxfattribs={'layer':'SLOTS'})
            msp.add_line(point(h,r),point(-h,r),dxfattribs={'layer':'SLOTS'})
            msp.add_arc(point(-h,0),r,start_angle=(ang+90)%360,end_angle=(ang+270)%360,dxfattribs={'layer':'SLOTS'})
        doc.classes.add_required_classes(doc.dxfversion)
        doc.classes.classes=OrderedDict(sorted(doc.classes.classes.items()));doc.saveas(p)
    finally:ezdxf.options.write_fixed_meta_data_for_testing=old
    back=ezdxf.readfile(p)
    assert back.units==4 and len(back.modelspace().query('CIRCLE'))==len(holes)
    assert len(back.modelspace().query('ARC'))==2*len(slots)
    if back.audit().has_errors:raise AssertionError(f'DXF audit failed: {p}')

def mesh_record(s,id,group):
    v,f=triangles(s,.04,.15)
    return dict(id=id,group=group,positions=v.astype(np.float32).ravel().tolist(),
                indices=f.ravel().tolist())
