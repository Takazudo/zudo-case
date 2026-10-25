"""Editable ASA washer CAD, mm. Flat bed at Z=0; hole at XY origin.
Standalone: python washer-source.py --parameters parameters.json --out adjusted
Requires CadQuery 2.7. Geometry shared with the fullset generator.
"""
import math,json,argparse
from pathlib import Path
import cadquery as cq

def washer(p):
    w,l,t=p['width'],p['length'],p['thickness'];r=p['corner_radius'];e=p['eccentricity']
    if not all(math.isfinite(v) for v in (w,l,t,r,e,p['xy_fit'],p['elephant_foot'],p['hole_diameter'])) or min(w,l,t,p['hole_diameter'])<=0:raise ValueError('Finite positive dimensions required')
    if p['shape'] in ('round','capsule') and abs(r-w/2)>1e-8:raise ValueError('Round/capsule corner_radius must equal width/2')
    if p['shape']=='round' and abs(l-w)>1e-8:raise ValueError('Round length must equal width')
    if p['shape']=='capsule' and l<w:raise ValueError('Capsule length must be >= width')
    if p['shape']=='round':s=cq.Solid.makeCylinder(w/2,t,cq.Vector(0,e,0))
    elif p['shape']=='capsule':s=cq.Workplane('XY',origin=(0,e,0)).slot2D(l,w,90).extrude(t).val()
    else:
        if not 0<r<min(w,l)/2:raise ValueError('Invalid corner radius')
        s=cq.Workplane('XY').box(w,l,t,centered=(True,True,False)).edges('|Z').fillet(r).val().translate((0,e,0))
    hole=p['hole_diameter']/2+p['xy_fit']
    if hole<=0:raise ValueError('Nonpositive compensated bore')
    s=s.cut(cq.Solid.makeCylinder(hole,t+2,cq.Vector(0,0,-1)))
    ef=p['elephant_foot']
    if ef<0 or ef>=t:raise ValueError('elephant_foot must be >=0 and < thickness')
    if ef:s=s.cut(cq.Solid.makeCone(hole+ef,hole,ef,cq.Vector(0,0,0)))
    s=s.clean()
    if not s.isValid() or len(s.Solids())!=1:raise ValueError('Washer is not one valid solid')
    # Hole must be enclosed: two circular bore edges survive and no opening to perimeter.
    edges=[e for e in s.Edges() if e.geomType()=='CIRCLE' and abs(e.radius()-hole)<1e-6 and abs(e.Length()-2*math.pi*hole)<1e-5]
    if len(edges)<2:raise ValueError('Bore opens through the outer edge')
    return s

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--parameters',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    for name,p in json.loads(a.parameters.read_text())['types'].items():
        s=washer(p)
        for ext in ['step','stl']:cq.exporters.export(s,str(a.out/(name+'-mm.'+ext)))
