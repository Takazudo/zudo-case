from pathlib import Path
import json, zipfile, math, hashlib, argparse
import numpy as np
import cadquery as cq
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
parser=argparse.ArgumentParser(description='Independently verify exported R7 geometry and hardware orientation from the repository root. Requires CadQuery and NumPy.')
parser.add_argument('--cad', required=True, type=Path, help='Completed CAD output directory containing model_data.json and step/.')
parser.add_argument('--out', required=True, type=Path, help='Destination JSON report.')
args=parser.parse_args()
root=Path.cwd(); inp=args.cad; report=args.out
m=json.loads((inp/'model_data.json').read_text()); parts={p['id']:p for p in m['parts']}; rows=m['bracketParameters']['fasteners']; checks=[]
def record(name, passed, **kw):checks.append({'check':name,'passed':bool(passed),**kw})
def pts(p):return np.array(m['meshes'][p['mesh']]['p']).reshape(-1,3)
def bounds(s):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(s.wrapped,b,False,False);return list(b.Get())
def box(b):return cq.Solid.makeBox(*(b[i+3]-b[i]for i in range(3)),cq.Vector(*b[:3]))
def cyl(row):
 n=np.array(row['inward_normal']);c=np.array(row['nut_seat_xyz_mm']);h=row['nut_height_mm']
 return cq.Solid.makeCylinder(8/math.sqrt(3),h,cq.Vector(*c),cq.Vector(*n)).cut(cq.Solid.makeCylinder(2.5,h+2,cq.Vector(*(c-n)),cq.Vector(*n))).clean()
record('52 complete bracket fasteners',len(rows)==52 and len({r['id']for r in rows})==52,count=len(rows))
record('8 newly added sidewall fasteners',sum(r['axis']=='wall'and r['wall']in('body-left','body-right')for r in rows)==8)
record('26 bracket bodies',sum(p['cat']=='brackets'for p in m['parts'])==26)
for r in rows:
 n=np.array(r['inward_normal']);seat=np.array(r['nut_seat_xyz_mm']);bearing=np.array(r['head_bearing_xyz_mm']);exterior=np.array(r['exterior_xyz_mm'])
 ids=r['parts'];nut=next(parts[i]for i in ids if parts[i].get('fastenerRole')=='nut');bolt=next(parts[i]for i in ids if parts[i].get('fastenerRole')=='bolt');washer=next(parts[i]for i in ids if parts[i].get('fastenerRole')=='washer')
 ns=pts(nut)@n;bs=pts(bolt)@n;ws=pts(washer)@n
 nut_ok=np.allclose([ns.min(),ns.max()],[seat@n,seat@n+r['nut_height_mm']],atol=1e-5)
 bolt_ok=np.allclose([bs.min(),bs.max()],[bearing@n-1.4,bearing@n+r['nominal_screw_length_mm']],atol=1e-5)
 washer_ok=np.allclose([ws.min(),ws.max()],[exterior@n-1,exterior@n],atol=1e-5)
 projection=bs.max()-ns.max();engagement=min(bs.max()-ns.min(),r['nut_height_mm'])
 record('actual mesh fastener orientation '+r['id'],nut_ok and bolt_ok and washer_ok and ns.min()>exterior@n,thread_projection_mm=round(float(projection),6),full_nut_engagement=bool(engagement>=r['nut_height_mm']-1e-5))
 record('actual mesh complete nut engagement '+r['id'],projection>=-1e-5 and engagement>=r['nut_height_mm']-1e-5)
# Source-based reference gaps and exported R7 side ledges.
base=root/'engineering/tenbox-v2/r5/source/10box-v2-r5/step'
front=cq.importers.importStep(str(base/'body-front.step')).val();led=front.intersect(box([-180,-144.9999,30,180,-140,47]));lb=[bounds(s)for s in led.Solids()]
# Central front bracket in unmodified stock floor.
refcenter=-58.862054999996005
left=max(b[3]for b in lb if b[3]<refcenter);right=min(b[0]for b in lb if b[0]>refcenter)
record('front reference nominal3mm eachside',abs((refcenter-8-left)-3)<.02 and abs((right-refcenter-8)-3)<.02,measured_clearances_mm=[refcenter-8-left,right-refcenter-8])
for wall,sgn in [('body-left',-1),('body-right',1)]:
 shape=cq.importers.importStep(str(inp/'step'/f'{wall}.step')).val(); clip=[-163.6999,-150,-1,-153.7,150,76]if sgn<0 else[153.7,-150,-1,163.6999,150,76]
 ledges=[bounds(s)for s in shape.intersect(box(clip)).Solids()]
 record('two supported ledges '+wall,len(ledges)==2,ledge_bounds_mm=ledges)
 for b in [p for p in m['parts']if p.get('attachmentWall')==wall and p['cat']=='brackets' and p['group']=='body']:
  bb=b['box'];candidates=[x for x in ledges if abs(x[2]-(41.02 if bb[1]<0 else 5.02))<.001]
  d=min(min(abs(x[1]-bb[4]),abs(x[4]-bb[1]))for x in candidates)
  record('actual ledge side gap '+b['id'],abs(d-3)<1e-5,gap_mm=d)
# Rail shapes are exactly the R6 meshes translated by1.5mm Z.
with zipfile.ZipFile(root/'public/downloads/candidate/tenbox-v2-r6-review.zip')as z:
 name=next(x for x in z.namelist()if x.endswith('model_data.json'))
 old=json.loads(z.read(name))
op={p['id']:p for p in old['parts']}
for p in m['parts']:
 if not p['id'].startswith('r7-rail-'):continue
 o=op[p['id'].replace('r7-','r6-',1)];a=np.array(old['meshes'][o['mesh']]['p']).reshape(-1,3);b=pts(p)
 record('exact R6 rail/frame mesh translated '+p['id'],old['meshes'][o['mesh']]['i']==m['meshes'][p['mesh']]['i'] and np.allclose(a+[0,0,1.5],b,atol=1e-6))
# Swept nuts allow any angular orientation, independent of tessellation/selected angle.
for bid in sorted({r['bracket']for r in rows}):
 rr=[r for r in rows if r['bracket']==bid];d=cyl(rr[0]).distance(cyl(rr[1]));record('independent rotating nut separation '+bid,d>.68,minimum_distance_mm=d)
railnuts=[p for p in m['parts']if p['id'].startswith('rail-nut-')]
record('8 rail-mount nuts remain outside',len(railnuts)==8 and all(abs(np.mean(pts(p)[:,0]))>168.7 for p in railnuts))
# Rail washers must clear the lift-off lid with positive distance, not merely zero overlap.
lid_shapes={n:cq.importers.importStep(str(inp/'step'/f'{n}.step')).val() for n in ['lid-left','lid-right','lid-front','lid-back','lid-top-single']}
railwashers=[p for p in m['parts'] if p['id'].startswith('rail-washer-')]
record('8 rail-specific OD10 washers',len(railwashers)==8)
for p in railwashers:
 b=p['box'];x=b[0];y=(b[1]+b[4])/2;z=(b[2]+b[5])/2
 radial=np.linalg.norm(pts(p)[:,1:3]-[y,z],axis=1)
 record('actual rail washer OD10 ID5 t1 '+p['id'],np.allclose([radial.min(),radial.max(),b[3]-b[0]],[2.5,5,1],atol=1e-5))
 shape=cq.Solid.makeCylinder(5,1,cq.Vector(x,y,z),cq.Vector(1,0,0)).cut(cq.Solid.makeCylinder(2.5,3,cq.Vector(x-1,y,z),cq.Vector(1,0,0))).clean()
 distances={n:shape.distance(lid) for n,lid in lid_shapes.items()}
 # Only lid material in the washer's XY projection can enter its vertical lift path.
 # The small X epsilon includes the coplanar bearing face and is conservative.
 projection_box=[x-.0001,y-5,-100,x+1.0001,y+5,200]
 projected=[lid.intersect(box(projection_box))for lid in lid_shapes.values()]
 projected=[lid for lid in projected if lid.Volume()>1e-9]
 min_gap=min(distances.values());vertical_gap=min(bounds(lid)[2]for lid in projected)-(z+5)
 record('rail washer positive lid and lift-sweep clearance '+p['id'],min_gap>.17 and vertical_gap>.17,closed_lid_distance_mm=min_gap,vertical_lift_sweep_lower_bound_mm=vertical_gap,projection_domain_xy_mm=[projection_box[0],projection_box[1],projection_box[3],projection_box[4]])
for r in rows:
 w=next(parts[i]for i in r['parts']if parts[i].get('fastenerRole')=='washer');v=pts(w);n=np.array(r['inward_normal']);c=np.array(r['head_bearing_xyz_mm']);delta=v-c
 radial=np.linalg.norm(delta-np.outer(delta@n,n),axis=1)
 record('L-bracket OD15 washer retained '+r['id'],np.allclose([radial.min(),radial.max()],[2.5,7.5],atol=1e-5))
# Quantify washer bearing without inferring strength from supported area.
bearing_observations=[]
side_shapes={w:cq.importers.importStep(str(inp/'step'/f'{w}.step')).val()for w in ['body-left','body-right']}
expected_slot_bearing=math.pi*7.5**2-(5.5*5+math.pi*2.75**2)
for row in [r for r in rows if r['axis']=='wall'and r['wall']in side_shapes]:
 center=np.array(row['exterior_xyz_mm']);normal=np.array(row['inward_normal']);d=.01
 ring=cq.Solid.makeCylinder(7.5,d,cq.Vector(*center),cq.Vector(*normal)).cut(cq.Solid.makeCylinder(2.5,d,cq.Vector(*center),cq.Vector(*normal))).clean()
 supported=ring.intersect(side_shapes[row['wall']]).Volume()/d
 observation={'joint':row['id'],'wall':row['wall'],'axis_xyz_mm':center.tolist(),'supported_area_mm2':supported,'slot_only_supported_area_mm2':expected_slot_bearing,'supported_fraction_relative_to_slot_only':supported/expected_slot_bearing}
 if expected_slot_bearing-supported>1e-4:
  y,z=center[1:3]
  vent=min(m['ventParameters']['side_layout'],key=lambda v:abs(v['y']-y))
  observation.update(washer_vent_edge_overlap_mm=7.5+vent['width']/2-abs(vent['y']-y),screw_head_to_vent_edge_gap_mm=abs(vent['y']-y)-vent['width']/2-6)
 bearing_observations.append(observation)
results={'reviewed_model_sha256':hashlib.sha256((inp/'model_data.json').read_bytes()).hexdigest(),'input':str(inp),'scope':'Independent exported-mesh orientation/count checks, exact STEP ledge measurements, preserved rail mesh comparison, angle-independent BRep nut-pair distances, positive rail-washer/lid separation, and quantified side-washer bearing. No physical or slicer validation.','checks':checks,'check_count':len(checks),'all_passed':all(c['passed']for c in checks),'washer_bearing_observations':bearing_observations,'bearing_interpretation':'Two shallow inner side washers span a small vent-edge void while their screw heads clear the vent. Partial bearing is not a shaft/material collision. No strength/load approval is inferred.'}
report.write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'report':str(report),'checks':len(checks),'all_passed':results['all_passed'],'failures':[c for c in checks if not c['passed']]},indent=2))
if not results['all_passed']:raise SystemExit(1)
