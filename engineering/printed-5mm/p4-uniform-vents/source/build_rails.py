"""P3 preview: install the source 7U40 (3U + 3U + 1U) rail assembly.
No case STL/STEP file is written by this module. Existing source rails/PCBs are
reference hardware, not new print/order parts. All units are millimetres.
"""
from pathlib import Path
import argparse,copy,json,math,hashlib,platform
import cadquery as cq
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'reference/rail-source'
parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,default=ROOT/'reference/p2-model.json')
args=parser.parse_args();model=json.loads(args.base.read_text())
checks=[];solids={};newparts=[]
def check(name,ok,**kw):
 checks.append(dict(check=name,passed=bool(ok),**kw))
 if not ok:raise AssertionError(name+': '+str(kw))
def bounds(s):
 b=s.BoundingBox();return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]
def box(x0,x1,y0,y1,z0,z1):return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def pack_mesh(s):
 v,t=s.tessellate(.04,.19)
 a={'p':[round(q,6) for p in v for q in p.toTuple()],'i':[int(q) for f in t for q in f]}
 return a
def add_mesh(a,id,name,cat,*,note='',explode=(0,0,1.5),group='railUnit',material='',volume=None,**extra):
 pts=np.array(a['p']).reshape(-1,3);key='p3-'+id
 check('finite mesh '+id,np.isfinite(pts).all() and len(a['i'])%3==0 and max(a['i'])<len(pts))
 model['meshes'][key]=a
 row=dict(id=id,name=name,cat=cat,mesh=key,box=np.r_[pts.min(axis=0),pts.max(axis=0)].tolist(),note=note,explode=list(explode),group=group,material=material,volume=volume,solids=1 if volume is not None else None,existingReference=True,**extra)
 newparts.append(row);return row
def add(s,id,name,cat,**kw):
 check('valid reference solid '+id,s.isValid() and len(s.Solids())==1 and s.Volume()>0)
 solids[id]=s
 return add_mesh(pack_mesh(s),id,name,cat,volume=s.Volume(),**kw)
def cyl(axis,lo,hi,c,r):
 lo,hi=sorted([lo,hi]);o=list(c);o[axis]=lo;v=[0,0,0];v[axis]=1
 return cq.Solid.makeCylinder(r,hi-lo,cq.Vector(*o),cq.Vector(*v))
def tube(axis,lo,hi,c,r,ri=2.75):return cyl(axis,lo,hi,c,r).cut(cyl(axis,min(lo,hi)-1,max(lo,hi)+1,c,ri)).clean()
def nutx(lo,hi,y,z):
 lo,hi=sorted((lo,hi));r=8/math.sqrt(3)
 w=cq.Wire.makePolygon([cq.Vector(lo,y+r*math.cos(k*math.pi/3),z+r*math.sin(k*math.pi/3)) for k in range(6)],close=True)
 return cq.Solid.extrudeLinear(w,[],cq.Vector(hi-lo,0,0)).cut(cyl(0,lo-1,hi+1,(0,y,z),2.5)).clean()
# Source identity is enforced before any placement.
receipt=json.loads((ROOT/'reference/SOURCE-RECEIPT.json').read_text())
for f in receipt['files']:
 raw=(REF/f['path']).read_bytes()
 check('source hash '+f['path'],hashlib.sha256(raw).hexdigest()==f['sha256'])
expected={'source-data/panels/panel-geometry.json':'04836d809db024613023beba1cd5d355bf5eb184','source-data/rail40/rail_mesh.json':'178fd2e720d83b92f2430603e5592c5854ca2087','build_geometry.py':'77c998e0bbdd4a390604b7724d8f2f17b3618ffe'}
for path,sha in expected.items():
 b=(REF/path).read_bytes();check('pinned Git blob '+path,hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()==sha)
# Work from the unchanged P2 assembly. The old envelope is removed, not hidden.
base_assembly=copy.deepcopy(model['scenes']['assembly'])
for k,rows in model['scenes'].items():model['scenes'][k]=[p for p in rows if p['cat']!='frame']
old_frame=[p for p in base_assembly if p['cat']=='frame']
for p in old_frame:model['meshes'].pop(p['mesh'],None)
P=model['parameters'];B=P['body'];t=B['panel_thickness'];H=model['dimensions']['body_outside'][2];TOP=H-1.5
W,D,_=model['dimensions']['body_outside'];XI=B['inside_width']/2
ORIGIN_U=157.377228;pcb_t=1.6;rail_length=204.;shift=t-1.5
raw_panels=json.loads((REF/'source-data/panels/panel-geometry.json').read_text())['panels']
normalized={}
for kind in ['fixer7u','padder3u','padder1u']:
 d=copy.deepcopy(raw_panels[kind])
 for contour in [d['outer'],*d['cutouts']]:
  if kind=='fixer7u':contour['points']=[[p[1],p[0]] for p in contour['points']]
  a=np.array(contour['points']);contour['bbox']={'min':a.min(0).tolist(),'max':a.max(0).tolist(),'center':((a.min(0)+a.max(0))/2).tolist(),'dimensions':np.ptp(a,axis=0).tolist()}
 normalized[kind]=d
fixer=normalized['fixer7u']
check('PCB longitudinal datum',abs(fixer['outer']['bbox']['center'][0]-ORIGIN_U)<1e-8)
def pcb(kind,x0,offset_u=0,offset_v=0):
 d=normalized[kind]
 def wire(points):return cq.Wire.makePolygon([cq.Vector(x0,u+offset_u-ORIGIN_U,TOP-v-offset_v) for u,v in points],close=True)
 s=cq.Solid.extrudeLinear(wire(d['outer']['points']),[wire(c['points']) for c in d['cutouts']],cq.Vector(pcb_t,0,0))
 check('source outline volume '+kind+str(x0)+str(offset_u),abs(s.Volume()-d['materialAreaMm2']*pcb_t)<1e-4)
 return s
for sx in [-1,1]:
 side='left' if sx<0 else 'right'
 lo=min(sx*103.6,sx*105.2)
 add(pcb('fixer7u',lo),f'rail-fixer-{side}',f'{side.title()} 7U side frame · PCB 1.6mm','railPCB',note='Original 7U fixer outline and all cutouts. Rigidly placed at the P2 frame datum, not a bounding box.',material='Existing FR4 side frame; black finish in appearance mode',side=sx,role='fixer')
 for row,(kind,u,v) in enumerate([('padder3u',0,0),('padder3u',134.531860,0),('padder1u',269.039027,-.025081)]):
  lo=min(sx*102,sx*103.6)
  add(pcb(kind,lo,u,v),f'rail-padder-{side}-{row+1}',f'{side.title()} {"3U" if row<2 else "1U"} padder · row {row+1}','railPads',note='Source PCB contour, windows and original hole locations; 1.6mm thick. No contour repair or scale.',material='Existing FR4 padder; 1.6mm',side=sx,role='padder',row=row)
# Original meshes are placed without any scale or topology repair.
rm=json.loads((REF/'source-data/rail40/rail_mesh.json').read_text());rp=np.array(rm['positions']).reshape(-1,3)
check('original rail length 204mm',abs(np.ptp(rp[:,2])-rail_length)<1e-8)
circles=[c for c in fixer['cutouts'] if max(c['bbox']['dimensions'])<6]
wanted=[6.0332935,128.533836,140.5298535,263.030426,275.0617065,308.7211605]
rail_axes=[];rail_bounds=[]
for i,u0 in enumerate(wanted):
 hole=min(circles,key=lambda c:abs(c['bbox']['center'][0]-u0));u,v=hole['bbox']['center'];sy=-1 if i%2==0 else 1
 check('source rail hole '+str(i+1),abs(u-u0)<1e-7)
 y,z=u-ORIGIN_U,TOP-v;cx=14.930564880371094;cy=6.7535858154296875
 mat=np.array([[0,0,sy,-sy*102],[0,sy,0,y-sy*cy],[-1,0,0,z+cx],[0,0,0,1]],float)
 check('rigid rail placement '+str(i+1),abs(np.linalg.det(mat[:3,:3])-1)<1e-10 and np.allclose(mat[:3,:3].T@mat[:3,:3],np.eye(3)))
 pts=rp@mat[:3,:3].T+mat[:3,3];a={'p':np.round(pts,6).reshape(-1).tolist(),'i':rm['indices']}
 row=i//2;name=f'40HP rail {i+1} · {"3U" if row<2 else "1U"} row {row+1}'
 r=add_mesh(a,f'rail-{i+1}',name,'rails',material='Existing nut-type printed rail · original 204mm source mesh',note='Full source rail cross-section and axial recess. Original duplicate/non-manifold faces retained; this mesh is not newly qualified print geometry. Threads/inserts are not modeled.',role='rail',row=row,axis_yz=[y,z],source_matrix=mat.tolist(),source_triangles=len(rm['indices'])//3)
 rail_axes.append([y,z]);rail_bounds.append(r['box'])
 check('rail span retained '+str(i+1),abs(r['box'][3]-r['box'][0]-204)<1e-6)
# Hardware is dimensional display geometry; no thread topology.
mount_y=[x-ORIGIN_U for x in [22.8453565,90.111288,157.37722,224.6431425,291.873764]]
mount_z=TOP-21.3105735
mounts=[]
for sx in [-1,1]:
 side='left' if sx<0 else 'right'
 for i,y in enumerate(mount_y):
  id=f'{side}-{i+1}';c=(0,y,mount_z)
  add(tube(0,sx*105.2,sx*XI,c,5),f'rail-spacer-{id}',f'{side.title()} frame spacer {i+1} · 8mm','railSpacers',note='8mm distance between the outer fixer face and inside of the 5mm wall. OD10 / ID5.5 nominal.',material='Existing/home-print spacer · nominal Ø10 / Ø5.5',role='spacer',explode=(sx*.7,0,1.15))
  add(tube(0,sx*(W/2),sx*(W/2+1),c,5),f'rail-mount-washer-{id}',f'{side.title()} outside rail-mount washer {i+1}','railHardware',note='1mm protective washer outside the case wall, separate from bracket pads.',material='Existing nylon / replacement ASA washer',role='mount-washer',explode=(sx*1.6,0,.8))
  seat=sx*103.6;tip=seat+sx*25;headend=seat-sx*1.4
  screw=cyl(0,headend,seat,c,4.5).fuse(cyl(0,seat,tip,c,2.5)).clean()
  add(screw,f'rail-mount-bolt-{id}',f'{side.title()} M5 frame mount {i+1}','railHardware',note='25mm shank is a display candidate for the new 5mm wall, not a confirmed purchased screw. Head Ø9 ×1.4. Threads omitted.',material='Metal · schematic M5×25 low-head candidate',role='mount-bolt',explode=(-sx*.4,0,1.5))
  add(nutx(sx*(W/2+1),sx*(W/2+6),y,mount_z),f'rail-mount-nut-{id}',f'{side.title()} frame-mount lock nut {i+1}','railHardware',note='M5 AF8 ×5mm nut envelope. Nominal external stack only.',material='Metal lock nut · nominal envelope',role='mount-nut',explode=(sx*1.9,0,.8))
  mounts.append({'side':side,'axis_yz':[y,mount_z],'hole_radius':2.75,'fixer_outer_x':sx*105.2,'wall_inside_x':sx*XI,'wall_outside_x':sx*(W/2),'spacer':8,'grip_to_nut':15.6,'display_bolt_shank':25,'nominal_tip_projection_beyond_nut':4.4})
 for i,(y,z) in enumerate(rail_axes):
  seat=sx*105.2
  screw=cyl(0,seat,seat+sx*1.4,(0,y,z),4.5).fuse(cyl(0,seat-sx*40,seat,(0,y,z),2.5)).clean()
  add(screw,f'rail-end-bolt-{side}-{i+1}',f'{side.title()} rail {i+1} end screw','railHardware',note='Original source display envelope M5×40, Ø9 low head1.4. Shank enters the original axial recess; actual length/threads unconfirmed.',material='Metal · original schematic rail-end fastener',role='rail-end-bolt',explode=(sx*.5,0,1.5))
# Counts and exact mount-hole axis matching against P2 exported walls.
check('six source rails',sum(p['cat']=='rails' for p in newparts)==6)
check('two fixer and six padder PCBs',sum(p['cat']=='railPCB' for p in newparts)==2 and sum(p['cat']=='railPads' for p in newparts)==6)
check('ten 8mm spacers',sum(p.get('role')=='spacer' for p in newparts)==10)
check('ten mount stacks and twelve rail-end screws',len(mounts)==10 and sum(p.get('role')=='rail-end-bolt' for p in newparts)==12)
structure={}
for p in model['scenes']['assembly']:
 f=ROOT/'step'/f'{p["id"]}.step'
 if f.exists() and p['cat'] in ('panels','floor','lidEdges','lidRoof'):structure[p['id']]=cq.importers.importStep(str(f)).val()
for side in ['left','right']:
 wall=structure['wall-'+side];axis=[]
 for e in wall.Edges():
  if e.geomType()=='CIRCLE' and abs(e.radius()-2.75)<1e-6 and abs(e.Length()-2*math.pi*2.75)<1e-5:
   c=e.Center()
   if abs(c.z-mount_z)<1e-5:axis.append([c.y,c.z])
 axis=sorted(set(tuple(round(x,6) for x in p) for p in axis))
 check('existing '+side+' P2 five wall holes match source mount datums',len(axis)==5 and np.allclose(axis,[[round(y,6),round(mount_z,6)] for y in mount_y],atol=1e-6),axes_yz=axis)
 for i in range(5):
  v=solids[f'rail-mount-bolt-{side}-{i+1}'].intersect(wall).Volume()
  check(f'mount shank clears original {side} wall {i+1}',v<1e-5,overlap_mm3=v)
# Reconstruct the unchanged P2 bracket solids from its explicit placements, for
# checking the source-PCB geometry (not a voxel or bbox-only proof).
XI=B['inside_width']/2;YI=B['inside_depth']/2;SH=B['bracket_shim'];T=t
faces={'front':((0,-D/2,0),(1,0,0),(0,-1,0)),'back':((0,D/2,0),(-1,0,0),(0,1,0)),'right':((W/2,0,0),(0,1,0),(1,0,0)),'left':((-W/2,0,0),(0,-1,0),(-1,0,0))}
for f,(o,u,n) in faces.items():
 vals=[-59.5,59.5] if f in ('front','back') else [-126.5,-25,25,126.5]
 for i,x in enumerate(vals):
  v=T+SH;nn=-T-SH
  s=box(x-8,x+8,v,v+20,nn-2,nn).fuse(box(x-8,x+8,v,v+2,nn-20,nn)).clean()
  s=s.cut(cyl(2,nn-3,nn+1,(x,v+10,0),2.75)).cut(cyl(1,v-1,v+3,(x,0,nn-10),2.75)).clean()
  structure[f'bracket-lower-{f}-{i}']=s.moved(cq.Plane(origin=o,xDir=u,normal=n).location)
for sx in [-1,1]:
 for sy in [-1,1]:
  xx=sx*(XI-SH);yy=sy*(YI-SH)
  for k,z in enumerate([40.,70.]):
   a,b=sorted((xx,xx-sx*20));c,d=sorted((yy,yy-sy*2));e,f=sorted((xx,xx-sx*2));g,h=sorted((yy,yy-sy*20))
   s=box(a,b,c,d,z-8,z+8).fuse(box(e,f,g,h,z-8,z+8)).clean()
   s=s.cut(cyl(1,yy-12,yy+13,(xx-sx*10,0,z),2.75)).cut(cyl(0,xx-12,xx+13,(0,yy-sy*10,z),2.75)).clean()
   structure[f'bracket-corner-{sx}-{sy}-{k}']=s
# Checking pairwise nominal solid overlap; contacts at zero volume are allowed.
def intersects_bbox(a,b):return all(min(a[k+3],b[k+3])-max(a[k],b[k])>1e-5 for k in range(3))
collision=[];sb={k:bounds(v) for k,v in structure.items()}
for p in newparts:
 if p['id'] not in solids:continue
 s=solids[p['id']]
 for id,target in structure.items():
  if not intersects_bbox(p['box'],sb[id]):continue
  vol=s.intersect(target).Volume()
  if vol>1e-4:collision.append({'rail_part':p['id'],'case_part':id,'overlap_mm3':round(vol,6)})
# Do not conceal an existing collision by changing the user's case.
checks.append({'check':'new solid assembly vs original panels, floor, lid and body brackets','passed':not collision,'collisions':collision,'scope':'Exact BRep intersections for PCBs, spacers and schematic hardware. Imported rail mesh excluded; threads omitted.'})
print('NOMINAL COLLISIONS',collision,flush=True)
# Static rail/body clearance uses exact mesh extrema; source rails are not claimed
# to be closed manufactured solids.
rail_front=min(b[1] for b in rail_bounds);rail_back=max(b[4] for b in rail_bounds);rail_top=max(b[5] for b in rail_bounds)
check('rail mesh extents inside unchanged walls',rail_front>-YI and rail_back<YI and all(b[0]>-XI and b[3]<XI for b in rail_bounds),front_gap=rail_front+YI,rear_gap=YI-rail_back)
check('module-support rail top stays below rim',rail_top<H,rail_top_z=rail_top,rim_z=H)
# Rim-height locator clears all new solid components along a sampled lift.
lifts=[]
for dz in [0,1,4,7.5,10,20]:
 hits=[]
 for id,shape in structure.items():
  if not id.startswith('lid-edge-'):continue
  moved=shape.translate((0,0,dz));bb=bounds(moved)
  for p in newparts:
   if p['id'] not in solids or not intersects_bbox(bb,p['box']):continue
   v=moved.intersect(solids[p['id']]).Volume()
   if v>1e-4:hits.append([id,p['id'],round(v,6)])
 lifts.append({'lift_mm':dz,'collisions':hits})
checks.append({'check':'sampled stepped-lid lift against new rail-unit solids','passed':all(not r['collisions'] for r in lifts),'samples':lifts,'scope':'PCBs, spacer and fastener BReps; not a continuous sweep / physical test.'})
# Add components and dedicated views. Existing P2 assembly objects are untouched.
model['scenes']['assembly']+=newparts
rail_rows=list(newparts)
model['scenes']['rails']=rail_rows
# A true local cut at the middle side mount; same source geometry, no standalone
# fictitious demo. Include side wall and optional other nearby geometry.
clip=box(99,131,mount_y[2],14,mount_z-12,mount_z+13);mount_scene=[]
def clipped_row(s,p):
 c=s.intersect(clip).clean()
 if c.Volume()<1e-5:return
 a=pack_mesh(c);key='p3-mount-'+p['id'];model['meshes'][key]=a
 r=copy.deepcopy(p);r.update(id='mount-'+p['id'],mesh=key,box=bounds(c),volume=c.Volume(),note=p['note']+' Cut through the screw axis (Y >= middle mount Y) from the installed geometry; not an additional part.')
 mount_scene.append(r)
wallrow=next(p for p in model['scenes']['assembly'] if p['id']=='wall-right')
clipped_row(structure['wall-right'],wallrow)
for p in newparts:
 if p['id'] in solids and intersects_bbox(bounds(clip),p['box']):clipped_row(solids[p['id']],p)
model['scenes']['railMount']=mount_scene
check('rail mount local view exists',len(mount_scene)>=6)
# Full assembly outline/case state and print exports must remain byte-identical.
kept=[p for p in model['scenes']['assembly'] if not p.get('existingReference')]
old=[p for p in base_assembly if p['cat']!='frame']
check('all P2 case component records preserved',kept==old,count=len(old))
check('P2 equal floor, pair and no-strip decisions preserved',model['dimensions']['floor_half_size']==[236.4,170.35,5] and model['dimensions']['paired_support_y']==[-25,25] and not any('splice' in p['id'] for p in model['scenes']['assembly']))
check('all 15 current print exports present',len(list((ROOT/'stl').glob('*.stl')))==15 and len(list((ROOT/'step').glob('*.step')))==15)
check('source assemblies excluded from print inventory',all(not p['id'].startswith('rail-') for p in model['parts']))
params={'source_commit':receipt['reference_commit'],'rail_length':204,'pcb_thickness':1.6,'pcb_top_z':TOP,'floor_datum_shift':shift,'mount_z':mount_z,'mount_y':mount_y,'rail_axis_yz':rail_axes,'spacer_length':8,'mount_bolt_length_display':25,'rail_end_bolt_length_display':40,'assembly_existing_components':len(newparts),'printed_case_changed':False}
model['revision']='P4-PRINTED-5MM-UNIFORM-VENTS'
model['railAssembly']=params
model['dimensions']['rail_unit']={'layout':'3U + 3U + 1U / 40HP','rails':6,'fixer_pcbs':2,'padder_pcbs':6,'spacers':10,'mounts':10,'rail_end_screws':12,'rail_length':204,'pcb_top_z':TOP,'rail_top_z':rail_top,'rail_support_below_rim':H-rail_top,'inside_width':226.4,'frame_width':210.4,'spacer_each':8,'mount_z':mount_z,'source_rigid_only':True}
# Old records are history, not a new physical qualification.
model['checks']=[x for x in model['checks'] if x.get('check')!='all detailed rail/PCB, warpage, print strength, transport']+checks
model['checks'].append({'check':'physical strength, print fit, electrical integration, rail non-manifold topology','status':'UNVERIFIED. Original source rail mesh retains non-manifold/duplicate faces. No manufactured replacement or production approval.'})
(ROOT/'source/model.json').write_text(json.dumps(model,separators=(',',':')))
(ROOT/'evidence/rail-geometry-checks.json').write_text(json.dumps({'checks':checks,'count':len(checks),'passed':all(r['passed'] for r in checks),'nominal_collisions':collision,'parameters':params,'environment':{'python':platform.python_version(),'cadquery':cq.__version__}},indent=2))
(ROOT/'DIMENSIONS.json').write_text(json.dumps(model['dimensions'],indent=2))
(ROOT/'reference/RAIL-PLACEMENT.json').write_text(json.dumps({'parameters':params,'mounts':mounts,'rail_bounds':rail_bounds,'source_transforms':[{'id':r['id'],'matrix':r['source_matrix']} for r in newparts if 'source_matrix'in r]},indent=2))
print('P3:',len(newparts),'new reference parts;',len(model['scenes']['assembly']),'total;',len(checks),'checks;',len(collision),'nominal collisions',flush=True)
