"""Reviewed P4 vent schema and exact CadQuery cuts in panel-local U/Z/N."""
import math
import cadquery as cq

REVISION = 'P4-PRINTED-5MM-UNIFORM-VENTS'
WALLS = ('front','back','right','left')

def validate(p):
    if p.get('revision') != REVISION: raise ValueError('Wrong P4 revision')
    v=p['ventilation']
    if v['pattern'] != 'uniform-four-walls': raise ValueError('Unsupported ventilation pattern')
    if set(v['centers']) != set(WALLS): raise ValueError('Only four body walls may have vents')
    for key in ('width','height','radius','pitch','center_z','minimum_hardware_clearance','minimum_hole_clearance','minimum_web','minimum_edge_margin'):
        if isinstance(v[key],bool) or not isinstance(v[key],(int,float)) or not math.isfinite(v[key]) or v[key]<=0: raise ValueError('Invalid '+key)
    if v['radius']>=min(v['width'],v['height'])/2: raise ValueError('Not a straight-sided rounded rectangle')
    for f,centers in v['centers'].items():
        expected=[11*k for k in range(-12,13)] if f in ('left','right') else [11*(k-7.5) for k in range(16)]
        if not isinstance(centers,list) or any(isinstance(c,bool) or not isinstance(c,(float,int)) or not math.isfinite(c) for c in centers): raise ValueError('Malformed centers')
        if centers!=expected: raise ValueError('Missing, duplicate, shifted or unreviewed vent center')
        half=170.5 if f in ('left','right') else 113.2
        if min(half-abs(c)-v['width']/2 for c in centers)<v['minimum_edge_margin']: raise ValueError('Vent edge margin')
        if min(b-a-v['width'] for a,b in zip(centers,centers[1:]))<v['minimum_web']: raise ValueError('Vent overlap or reduced web')
    if min(v['center_z']-v['height']/2-5,94.5-v['center_z']-v['height']/2)<v['minimum_edge_margin']: raise ValueError('Vent Z edge margin')
    fixed={'width':3.,'height':32.,'radius':.5,'pitch':11.,'center_z':46.,'minimum_hardware_clearance':4.,'minimum_hole_clearance':6.9,'minimum_web':8.,'minimum_edge_margin':25.}
    if any(v[k]!=val for k,val in fixed.items()): raise ValueError('Unreviewed vent dimensions or limits')
    return v

def rounded(u,v,z0=-6,z1=1):
    return cq.Workplane('XY',origin=(u,v['center_z'],z0)).rect(v['width'],v['height']).extrude(z1-z0).edges('|Z').fillet(v['radius']).val()

def holes_expected(f):
    long=f in ('right','left')
    rows=[(u,15.,90,'lower') for u in ([-126.5,-25,25,126.5] if long else [-59.5,59.5])]
    rows += [(sgn*(155.5 if long else 103.2),z,0,'corner') for z in [40.,70.] for sgn in [-1,1]]
    if long:
        ys=[22.8453565-157.377228,90.111288-157.377228,157.37722-157.377228,224.6431425-157.377228,291.873764-157.377228]
        rows += [(y if f=='right' else -y,71.6894265,None,'rail') for y in ys]
    return rows

def cut_wall(s,f,rows,p,check):
    v=validate(p)
    check('P4 dedicated fastening coordinates '+f,rows==holes_expected(f))
    cutters=[rounded(u,v) for u in v['centers'][f]]
    result=s.cut(*cutters).clean()
    area=len(cutters)*(v['width']*v['height']-(4-math.pi)*v['radius']**2)
    check('P4 removed exact through vent volume '+f,abs(s.Volume()-result.Volume()-area*5)<1e-5,removed_mm3=s.Volume()-result.Volume())
    b0=s.BoundingBox();b1=result.BoundingBox()
    check('P4 exterior and thickness unchanged '+f,all(abs(getattr(b0,k)-getattr(b1,k))<1e-7 for k in ['xmin','ymin','zmin','xmax','ymax','zmax']))
    hole_shapes=[]
    for n,(u,z,a,kind) in enumerate(rows):
        hole=cq.Solid.makeCylinder(2.75,7,cq.Vector(u,z,-6)) if a is None else cq.Workplane('XY',origin=(u,z,-6)).slot2D(10.5,5.5,a).extrude(7).val()
        hole_shapes.append(hole)
        region=cq.Solid.makeBox(16,16,9,cq.Vector(u-8,z-8,-7))
        check(f'P4 unchanged fastening BRep region {f}/{n}',s.intersect(region).cut(result).Volume()<1e-6)
    gap=min(c.distance(h) for c in cutters for h in hole_shapes)
    check('P4 screw hole separation '+f,gap>=v['minimum_hole_clearance'],minimum_mm=gap)
    for n,c in enumerate(cutters):
        check(f'P4 through full thickness {f}/{n}',result.intersect(c).Volume()<1e-6 and abs(s.intersect(c).Volume()-area*5/len(cutters))<1e-5)
    web=min(a.distance(b) for i,a in enumerate(cutters) for b in cutters[:i])
    check('P4 web '+f,web>=v['minimum_web']-1e-7,minimum_mm=web)
    return result,{'wall':f,'count':len(cutters),'centers':v['centers'][f],'width':3,'height':32,'radius':.5,'pitch':11,'z_range':[30,62],'open_area_mm2':area,'minimum_hole_clearance_mm':gap,'minimum_web_mm':web,'minimum_edge_mm':min(25,min((170.5 if f in ('left','right') else 113.2)-abs(u)-1.5 for u in v['centers'][f])),'holes':rows}
