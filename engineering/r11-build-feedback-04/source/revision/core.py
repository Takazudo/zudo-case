"""Shared exact CAD primitives and datum for the R11 review candidate (mm)."""
from pathlib import Path
import json, math
import cadquery as cq

ROOT=Path(__file__).resolve().parents[1]
P=json.loads((ROOT/'parameters.json').read_text())
W,D,H,T=(P['body'][k] for k in ('width','depth','height','metal'))
XM,YM=W/2-T,D/2-T
GAP=P['guard']['fit_per_face']
WALL=P['guard']['wall']
FACES={
 'front':((0,-D/2,0),(1,0,0),(0,0,1),(0,-1,0),'前板'),
 'back':((0,D/2,0),(-1,0,0),(0,0,1),(0,1,0),'後板'),
 'right':((W/2,0,0),(0,1,0),(0,0,1),(1,0,0),'右側板'),
 'left':((-W/2,0,0),(0,-1,0),(0,0,1),(-1,0,0),'左側板'),
 'floor':((0,0,0),(1,0,0),(0,-1,0),(0,0,-1),'底板')}

def box(x0,x1,y0,y1,z0,z1):
    assert min(x1-x0,y1-y0,z1-z0)>1e-8,(x0,x1,y0,y1,z0,z1)
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))

def fuse(shapes):
    shapes=list(shapes)
    assert shapes
    return shapes[0].fuse(*shapes[1:]).clean() if len(shapes)>1 else shapes[0].clean()

def disk(u,v,n0,n1,r,ri=0):
    s=cq.Solid.makeCylinder(r,n1-n0,cq.Vector(u,v,n0))
    return s.cut(cq.Solid.makeCylinder(ri,n1-n0+2,cq.Vector(u,v,n0-1))).clean() if ri else s

def slot(u,v,length,width,n0,n1,ang=0):
    return cq.Workplane('XY',origin=(u,v,n0)).slot2D(length,width,ang).extrude(n1-n0).val()

def rr(u0,u1,v0,v1,n0,n1,r=1.5):
    return cq.Workplane('XY').box(u1-u0,v1-v0,n1-n0,centered=(True,True,False)).edges('|Z').fillet(min(r,(u1-u0)/2-.01,(v1-v0)/2-.01)).val().translate(((u0+u1)/2,(v0+v1)/2,n0))

def world(s,f):
    o,u,v,n,_=FACES[f]
    return s.moved(cq.Plane(origin=o,xDir=u,normal=n).location)

def worldpoint(f,u,v,n=0):
    o,a,b,c,_=FACES[f]
    return [o[k]+a[k]*u+b[k]*v+c[k]*n for k in range(3)]

def bounds(s):
    """Analytic BRep bounds, independent of any cached preview triangulation."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    b=Bnd_Box()
    BRepBndLib.AddOptimal_s(s.wrapped,b,useTriangulation=False,useShapeTolerance=False)
    return list(b.Get())

def part(id,shape,name,cat,role='nylon',note='',explode=None,**extra):
    shape=shape.clean()
    if not shape.isValid() or not shape.Solids() or shape.Volume()<1e-7:raise ValueError('Invalid shape '+id)
    return dict(id=id,shape=shape,name=name,cat=cat,role=role,note=note,explode=explode or [0,0,0],**extra)

def hexprism(u,v,n0,n1,af=8,angle=0,ri=0):
    r=af/math.sqrt(3)
    pts=[cq.Vector(u+r*math.cos(math.radians(angle)+k*math.pi/3),v+r*math.sin(math.radians(angle)+k*math.pi/3),n0) for k in range(6)]
    s=cq.Solid.extrudeLinear(cq.Wire.makePolygon(pts,close=True),[],cq.Vector(0,0,n1-n0))
    return s.cut(disk(u,v,n0-1,n1+1,ri)).clean() if ri else s

def head(u,v,n0,n1,diameter=12):
    s=disk(u,v,n0,n1,diameter/2)
    # Recess is on the visible/exterior face.
    return s.cut(hexprism(u,v,n1-.7,n1+.1,4)).clean()

def roundwasher(u,v,n0,n1):
    return disk(u,v,n0,n1,7.5,2.5)

def normal_explode(f,scale=1):
    return [a*scale for a in FACES[f][3]]
