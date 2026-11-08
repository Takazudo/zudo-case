"""10BOX v2 R5: minimal12/16mm floor corner chamfers for flat H2D printing.

Only the two floor shapes change. The rear/common floor is clipped by four
diagonal halfplanes; the front is the same part rotated180degZ and raised36mm.
The clipping diamond deliberately extends beyond the base rectangle so that
the four existing side tabs are not accidentally trimmed.

The two changed standalone STL exports receive independent mesh-integrity
checks after export. No slicer or physical-print claim is made here.
"""
from pathlib import Path
from collections import defaultdict, deque
import copy
import hashlib
import itertools
import json
import math
import shutil
import struct

import cadquery as cq
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT=Path(__file__).resolve().parent
PREVIOUS=ROOT/'source-r4'
CONFIG=json.loads((ROOT/'design-config.json').read_text())
R4_MODEL=json.loads((PREVIOUS/'model_data.json').read_text())
FLOORS=['body-bottom-front','body-bottom-back']
WALLS=['body-left','body-right','body-front','body-back']
TOL=CONFIG['validation_volume_tolerance_mm3']
checks=[]
for d in ['step','stl-review','review-checks']:(ROOT/d).mkdir(exist_ok=True)

def evidence(name,passed,**detail):
    checks.append({'check':name,'passed':bool(passed),**detail})
    print(('PASS' if passed else 'FAIL')+' '+name,flush=True)

def bounds(shape):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(shape.wrapped,b,False,False)
    return list(b.Get())

def box(b):
    return cq.Solid.makeBox(b[3]-b[0],b[4]-b[1],b[5]-b[2],cq.Vector(*b[:3]))

def mesh(s):
    vertices,triangles=s.tessellate(CONFIG['tessellation_linear_tolerance_mm'],CONFIG['tessellation_angular_tolerance_rad'])
    return {'p':[round(x,5) for v in vertices for x in v.toTuple()],
            'i':[int(i) for f in triangles for i in f]}

def export(pid,s):
    cq.exporters.export(s,str(ROOT/'step'/f'{pid}.step'))
    cq.exporters.export(s,str(ROOT/'stl-review'/f'{pid}.stl'),
                        tolerance=CONFIG['tessellation_linear_tolerance_mm'],
                        angularTolerance=CONFIG['tessellation_angular_tolerance_rad'])

def top_faces(s,z):
    return [f for f in s.Faces() if f.normalAt().z>.99 and abs(f.Center().z-z)<1e-6]

def hole_signature(s,z):
    return sorted(tuple(sorted(tuple(round(x,7) for x in v.toTuple()) for v in w.Vertices()))
                  for f in top_faces(s,z) for w in f.innerWires())

def stl_integrity(path,cad_volume):
    raw=path.read_bytes();n=struct.unpack_from('<I',raw,80)[0]
    if len(raw)!=84+50*n:raise ValueError('Expected complete binary STL: '+str(path))
    dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attribute','<u2')])
    records=np.frombuffer(raw,dtype=dtype,count=n,offset=84)
    raw_vertices=records['vertices'].astype(float).reshape(-1,3)
    tol=CONFIG['stl_vertex_weld_tolerance_mm'];tol2=tol*tol
    vertices=[];buckets=defaultdict(list);indices=[];max_weld=0.
    for v in raw_vertices:
        cell=tuple(math.floor(x/tol) for x in v);found=None
        for delta in itertools.product([-1,0,1],repeat=3):
            key=tuple(cell[j]+delta[j] for j in range(3))
            for index in buckets.get(key,[]):
                d2=float(np.dot(v-vertices[index],v-vertices[index]))
                if d2<=tol2:
                    found=index;max_weld=max(max_weld,math.sqrt(d2));break
            if found is not None:break
        if found is None:
            found=len(vertices);vertices.append(v.copy());buckets[cell].append(found)
        indices.append(found)
    vv=np.asarray(vertices);ff=np.asarray(indices,dtype=int).reshape(-1,3)
    edge_use=defaultdict(list);links=defaultdict(list)
    degenerate=0;duplicate_count=0;seen_faces=set();triangles=vv[ff]
    for index,(a,b,c) in enumerate(ff):
        key=tuple(sorted((int(a),int(b),int(c))))
        if key in seen_faces:duplicate_count+=1
        seen_faces.add(key)
        if len(set((a,b,c)))<3 or np.linalg.norm(np.cross(vv[b]-vv[a],vv[c]-vv[a]))<=1e-10:degenerate+=1
        for u,v in [(a,b),(b,c),(c,a)]:edge_use[tuple(sorted((int(u),int(v))))].append(1 if u<v else -1)
        links[int(a)].append((int(b),int(c)));links[int(b)].append((int(c),int(a)));links[int(c)].append((int(a),int(b)))
    boundary=sum(len(v)==1 for v in edge_use.values())
    nonmanifold=sum(len(v)!=2 for v in edge_use.values())
    winding=sum(len(v)==2 and sum(v)!=0 for v in edge_use.values())
    bad_vertex_fans=0
    for vertex,pairs in links.items():
        graph=defaultdict(set)
        for a,b in pairs:graph[a].add(b);graph[b].add(a)
        start=next(iter(graph));visited={start};queue=[start]
        while queue:
            for v in graph[queue.pop()]:
                if v not in visited:visited.add(v);queue.append(v)
        if len(visited)!=len(graph) or any(len(nbr)!=2 for nbr in graph.values()):bad_vertex_fans+=1
    adjacency=defaultdict(set)
    for a,b in edge_use:adjacency[a].add(b);adjacency[b].add(a)
    unvisited=set(range(len(vv)));components=0
    while unvisited:
        components+=1;queue=[unvisited.pop()]
        while queue:
            for nxt in adjacency[queue.pop()]:
                if nxt in unvisited:unvisited.remove(nxt);queue.append(nxt)
    signed_volume=float(np.einsum('ij,ij->i',triangles[:,0],np.cross(triangles[:,1],triangles[:,2])).sum()/6)
    relative_error=abs(signed_volume-cad_volume)/cad_volume
    cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normal_dot=np.einsum('ij,ij->i',records['normal'].astype(float),cross)
    opposed_normals=int(np.sum(normal_dot<=0))
    euler=len(vv)-len(edge_use)+len(ff)
    passed=(degenerate==0 and duplicate_count==0 and boundary==0 and nonmanifold==0
            and winding==0 and bad_vertex_fans==0 and components==1 and signed_volume>0
            and relative_error<=CONFIG['stl_volume_relative_tolerance'] and opposed_normals==0
            and euler==-16)
    return {'passed':passed,'file':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
            'vertex_weld_tolerance_mm':tol,'maximum_actual_weld_distance_mm':max_weld,
            'triangles':len(ff),'welded_vertices':len(vv),'edges':len(edge_use),
            'degenerate_triangles':degenerate,'duplicate_triangles':duplicate_count,
            'boundary_edges':boundary,'non_two_manifold_edges':nonmanifold,
            'inconsistently_wound_edges':winding,'nonmanifold_vertex_fans':bad_vertex_fans,
            'connected_components':components,'opposed_or_zero_stored_normals':opposed_normals,
            'euler_characteristic':euler,'expected_euler_for_nine_through_holes':-16,
            'signed_volume_mm3':signed_volume,'cad_volume_mm3':cad_volume,
            'relative_volume_error':relative_error,
            'maximum_relative_volume_error':CONFIG['stl_volume_relative_tolerance']}

# Preserve every unrelated export exactly.
for folder,ext in [('step','step'),('stl-review','stl')]:
    for p in (PREVIOUS/folder).glob('*.'+ext):
        if p.stem not in FLOORS:shutil.copyfile(p,ROOT/folder/p.name)
r4={pid:cq.importers.importStep(str(PREVIOUS/'step'/f'{pid}.step')).val() for pid in FLOORS+WALLS}

a=CONFIG['main_rectangle_half_width_mm'];b=CONFIG['main_rectangle_half_depth_mm']
cx,cy=CONFIG['rear_floor_center_xy_mm']
small=CONFIG['NE_SW_chamfer_leg_mm'];large=CONFIG['NW_SE_chamfer_leg_mm']
A=a+b-small;B=a+b-large
uv=[((A+B)/2,(A-B)/2),((A-B)/2,(A+B)/2),(-(A+B)/2,-(A-B)/2),(-(A-B)/2,-(A+B)/2)]
wire=cq.Wire.makePolygon([cq.Vector(cx+u,cy+v,-1) for u,v in uv],close=True)
cutter=cq.Solid.extrudeLinear(wire,[],cq.Vector(0,0,7))
rear=r4['body-bottom-back'].intersect(cutter).clean()
front=rear.rotate((0,0,0),(0,0,1),180).translate((0,0,CONFIG['front_floor_height_offset_mm']))
r5={'body-bottom-back':rear,'body-bottom-front':front}
for pid,s in r5.items():export(pid,s)
# A single manufacturing source serves both assembled positions.
for folder,ext in [('step','step'),('stl-review','stl')]:
    shutil.copyfile(ROOT/folder/f'body-bottom-back.{ext}',ROOT/folder/f'body-bottom-common.{ext}')

corners=[
 {'name':'NE','corner_xy_mm':[a,2*b],'leg_mm':small,'cut_edge_xy_mm':[[a,2*b-small],[a-small,2*b]]},
 {'name':'SW','corner_xy_mm':[-a,0],'leg_mm':small,'cut_edge_xy_mm':[[-a,small],[-a+small,0]]},
 {'name':'NW','corner_xy_mm':[-a,2*b],'leg_mm':large,'cut_edge_xy_mm':[[-a,2*b-large],[-a+large,2*b]]},
 {'name':'SE','corner_xy_mm':[a,0],'leg_mm':large,'cut_edge_xy_mm':[[a,large],[a-large,0]]},
]
removed_volume=r4['body-bottom-back'].Volume()-rear.Volume()
removed_area=removed_volume/5
model=copy.deepcopy(R4_MODEL)
model['schema']='10box-v2-review/5';model['revision']=CONFIG['revision']
model['previousRevision']=R4_MODEL['revision'];model['baselineParts']=copy.deepcopy(R4_MODEL['parts'])
model['previousChecks']={'revision':R4_MODEL['revision'],'generator_checks':len(R4_MODEL['checks']),
                         'all_passed':all(c['passed'] for c in R4_MODEL['checks'])}
for pid in FLOORS:
    p=next(p for p in model['parts'] if p['id']==pid);key='r5-'+pid
    model['meshes'][key]=mesh(r5[pid])
    p.update(mesh=key,box=bounds(r5[pid]),volume=r5[pid].Volume(),material='10BOX V2 R5 / 5mm printed floor; review only',
             note='Four12/16mm corner chamfers for flat diagonal H2D placement. All9slots and4tabs retained. Same common print shape as the other floor.',
             change_from_r4='Removed four small corner triangles; no slot/tab/mount or case resizing.')
model['floorCutParameters']={
    'common_shape_id':'body-bottom-common','assembly_instances':FLOORS,'print_quantity':2,
    'coordinate_convention':'Rear floor Xwidth/Y0..144.99432/Z0..5; u=X,v=Y-72.49716',
    'main_rectangle_mm':[327.1,144.99432,5],'tab_tip_span_mm':336.8,
    'corners_rear':corners,'diagonal_halfplane_limits_mm':{'abs_u_plus_v':A,'abs_minus_u_plus_v':B},
    'removed_area_each_mm2':removed_area,'removed_volume_each_mm3':removed_volume,
    'removed_fraction_of_original_material_percent':removed_volume/r4['body-bottom-back'].Volume()*100,
    'retained_slots_each':9,'retained_tabs_each':4,'tab_insertion_mm_unchanged':4.7,
    'front_from_rear':{'rotation_axis':[0,0,1],'rotation_degrees':180,'translation_mm':[0,0,36]},
    'nominal_flat_print_pose':{'yaw_degrees':-45,'center_xy_mm':[162.5,160],
                               'source_center_xy_mm':[0,72.49716],'z_mm':[0,5],
                               'verification':'Exact exported mesh and printer-template verification handled by H2D project builder.'},
    'corner_support_note':'Intentional corner gaps remove some original corner-lip floor contact. All tab engagement and nine fastening regions remain; do not describe all former corner contacts as retained.'}
model['commonPrintParts']=[{'id':'body-bottom-common','step':'step/body-bottom-common.step',
                           'stl':'stl-review/body-bottom-common.stl','quantity':2,'assembly_ids':FLOORS}]
model['lidParameters']['body_floor_status']='R5 floors now use four corner chamfers and a reviewed flat diagonal H2D pose; no upright floor solution.'
model['limitations']=[
    'CAD and structural checks do not establish a sliced or successfully printed part; Studio toolpaths and physical fit remain pending.',
    'Floor corner chamfers intentionally create small triangular corner gaps and remove some original corner-lip bearing contact.',
    'Four floor tabs and nine screw slots per panel are unchanged. The same common print geometry serves both floor positions.',
    'The flat floor pose must use the verified single left-nozzle area and avoid the rear wipe exclusion; do not substitute the full two-nozzle bed union.',
    'The R4 flat lid, supported flanges, body dimensions, rail gap, mounting heights, other joints, spacers and stand remain unchanged.',
    'Original small source-fit overlaps remain inherited; these subtractive floor edits add no material interference.',
]

# Regenerate the joint crop from the actual candidate floor, even though the
# chamfers lie outside this unchanged tab region.
joint_clip=box([150,75,-7,175,115,20]);records=[]
for pid,s,cat in [('body-right',r4['body-right'],'sides'),('body-bottom-back',rear,'floor')]:
    clipped=s.intersect(joint_clip).clean();key='floor-joint-'+pid
    model['meshes'][key]=mesh(clipped)
    records.append({'id':key,'sourceId':pid,'name':pid,'cat':cat,'mesh':key,
                    'box':bounds(clipped),'explode':[1,0,0] if pid=='body-right' else [0,0,0],
                    'group':'detail','material':'Exact R5 CAD section','volume':clipped.Volume()})
model['jointScenes']['floor-joint']=records
rear_record=next(p for p in model['parts'] if p['id']=='body-bottom-back')
model['jointScenes']['floor-top']=[{**copy.deepcopy(rear_record),'id':'floor-top-body-bottom-back',
                                    'sourceId':'body-bottom-back','explode':[0,0,0]}]
receipts=[]
for p in sorted(PREVIOUS.rglob('*')):
    if p.is_file():receipts.append({'file':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,
                                    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
model['r4InputReceipts']=receipts

def write_model():
    model['checks']=checks
    (ROOT/'model_data.json').write_text(json.dumps(model,separators=(',',':')),encoding='utf8')
    keys=['revision','units','dimensions','jointParameters','mountParameters','ventParameters','widthParameters','lidParameters','lidLedgeDetail','floorCutParameters','commonPrintParts','limitations']
    (ROOT/'parameters.json').write_text(json.dumps({k:model[k] for k in keys},indent=2)+'\n')
    (ROOT/'geometry-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    (ROOT/'source-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    (ROOT/'joint_scenes.json').write_text(json.dumps({'scenes':model['jointScenes']},indent=2)+'\n')
write_model();print('MODEL_READY',ROOT/'model_data.json',flush=True)

for pid,s in r5.items():
    old=r4[pid];z=41 if pid.endswith('front') else 5
    evidence('valid connected floor '+pid,s.isValid() and len(s.Solids())==1,
             solid_count=len(s.Solids()),volume_mm3=s.Volume(),bounds_mm=bounds(s))
    evidence('floor envelope and thickness retained '+pid,np.max(np.abs(np.array(bounds(s))-bounds(old)))<1e-6,
             old_bounds_mm=bounds(old),new_bounds_mm=bounds(s))
    hs=hole_signature(s,z);old_hs=hole_signature(old,z)
    evidence('nine original slots exactly retained '+pid,len(hs)==9 and hs==old_hs,slot_count=len(hs))
    added=s.cut(old).Volume();removed=old.cut(s).Volume()
    evidence('only2000mm3 corner material removed '+pid,added<TOL and abs(removed-2000)<TOL,
             added_volume_mm3=added,removed_volume_mm3=removed,removed_area_mm2=removed/5)
    for sign in [-1,1]:
        for yc in CONFIG['rear_tab_y_centers_mm']:
            x0,x1=sorted([sign*CONFIG['tab_root_x_mm'],sign*CONFIG['tab_tip_x_mm']])
            t=box([x0,yc-10,0,x1,yc+10,5])
            if pid.endswith('front'):t=t.rotate((0,0,0),(0,0,1),180).translate((0,0,36))
            before=old.intersect(t);after=s.intersect(t)
            difference=before.cut(after).Volume()+after.cut(before).Volume()
            evidence('full tab retained '+pid+'/'+str(sign)+'/'+str(yc),difference<TOL and abs(after.Volume()-500)<TOL,
                     symmetric_difference_mm3=difference,tab_volume_mm3=after.Volume(),expected_mm3=500)
    for wall in WALLS:
        before=old.intersect(r4[wall]).Volume();after=s.intersect(r4[wall]).Volume()
        evidence('no added wall interference '+pid+'/'+wall,after<=before+TOL,
                 r4_overlap_mm3=before,r5_overlap_mm3=after)

aligned=front.rotate((0,0,0),(0,0,1),180).translate((0,0,-36))
delta1=aligned.cut(rear).Volume();delta2=rear.cut(aligned).Volume()
evidence('front and back are one common physical shape',delta1<TOL and delta2<TOL,
         alignment='Front rotate180degZ then translateZ-36mm',
         aligned_front_minus_back_mm3=delta1,back_minus_aligned_front_mm3=delta2,
         proper_rotation_determinant=1)
for c in corners:
    expected=c['leg_mm']*math.sqrt(2)
    matches=[]
    for f in top_faces(rear,5):
        for e in f.outerWire().Edges():
            vv=e.Vertices()
            if len(vv)!=2:continue
            p0,p1=np.array(vv[0].toTuple()[:2]),np.array(vv[1].toTuple()[:2])
            q0,q1=np.array(c['cut_edge_xy_mm'][0]),np.array(c['cut_edge_xy_mm'][1])
            if min(np.linalg.norm(p0-q0)+np.linalg.norm(p1-q1),np.linalg.norm(p0-q1)+np.linalg.norm(p1-q0))<1e-6:matches.append(e.Length())
    evidence('exact rear corner chamfer '+c['name'],len(matches)==1 and abs(matches[0]-expected)<1e-6,
             leg_mm=c['leg_mm'],expected_edge_length_mm=expected,measured_edge_lengths_mm=matches,
             endpoints_xy_mm=c['cut_edge_xy_mm'])

mesh_reports=[]
for pid in FLOORS:
    report=stl_integrity(ROOT/'stl-review'/f'{pid}.stl',r5[pid].Volume());mesh_reports.append(report)
    evidence('exported STL integrity '+pid,report['passed'],**{k:v for k,v in report.items() if k!='passed'})
(ROOT/'review-checks/stl-integrity.json').write_text(json.dumps({'scope':'Only the two changed standalone STL exports; exact binary bytes inspected independently of3MF.',
                                                               'reports':mesh_reports},indent=2)+'\n')
for folder,ext in [('step','step'),('stl-review','stl')]:
    evidence('common print export identical '+ext,
             (ROOT/folder/f'body-bottom-common.{ext}').read_bytes()==(ROOT/folder/f'body-bottom-back.{ext}').read_bytes())
    for p in sorted((ROOT/folder).glob('*.'+ext)):
        if p.stem in FLOORS+['body-bottom-common']:continue
        evidence('unchanged export '+folder+'/'+p.name,p.read_bytes()==(PREVIOUS/folder/p.name).read_bytes(),
                 sha256=hashlib.sha256(p.read_bytes()).hexdigest())
for p in model['parts']:
    if p['id'] in FLOORS:continue
    old=next(q for q in R4_MODEL['parts'] if q['id']==p['id'])
    evidence('unchanged preview part '+p['id'],p==old and model['meshes'][p['mesh']]==R4_MODEL['meshes'][old['mesh']])
model['floorCutParameters']['standalone_stl_integrity']={
    'passed':all(r['passed'] for r in mesh_reports),'weld_tolerance_mm':CONFIG['stl_vertex_weld_tolerance_mm'],
    'report':'review-checks/stl-integrity.json'}
write_model()
failures=[c for c in checks if not c['passed']]
print('GEOMETRY_DONE',len(checks),'checks,',len(failures),'failed',flush=True)
if failures:raise SystemExit(1)
