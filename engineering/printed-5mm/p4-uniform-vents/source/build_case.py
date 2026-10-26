"""P2: 5mm printed-panel 7U40 design study. CadQuery / mm.
Run: python source/build.py. Outputs are prototypes, not qualified order data.
The same BReps drive meshes, STEP, STL and envelope checks.
"""
from pathlib import Path
import json, math, hashlib, sys, csv, shutil
import cadquery as cq
import numpy as np
import trimesh
from ventilation import validate, cut_wall
vent_reports=[]; unvented={}

ROOT=Path(__file__).resolve().parents[1]
P=json.loads((ROOT/'source/parameters.json').read_text())
validate(P)
B,L=P['body'],P['lid'];T=B['panel_thickness'];IW=B['inside_width'];ID=B['inside_depth']
W=IW+2*T;D=ID+2*T;H=T+B['wall_height'];XI=IW/2;YI=ID/2;SH=B['bracket_shim'];GAP=B['seam_gap']
SEAT=H;RB=H+L['rise_to_roof_underside'];RT=RB+L['roof_thickness'];LH=RT-H
PAIR=B['center_pair_offset_y']
XS=[-59.5,59.5];YS=[-126.5,-PAIR,PAIR,126.5];ZS=[40.,70.]
MOUNTY=[22.8453565-157.377228,90.111288-157.377228,157.37722-157.377228,224.6431425-157.377228,291.873764-157.377228]
MOUNTZ=68.1894265+(T-1.5)
FACES={'front':((0,-D/2,0),(1,0,0),(0,0,1),(0,-1,0)),
'back':((0,D/2,0),(-1,0,0),(0,0,1),(0,1,0)),
'right':((W/2,0,0),(0,1,0),(0,0,1),(1,0,0)),
'left':((-W/2,0,0),(0,-1,0),(0,0,1),(-1,0,0)),
'floor':((0,0,0),(1,0,0),(0,-1,0),(0,0,-1))}
meshes={}; scenes={}; parts=[]; breps={}; printed=[]; checks=[]; count=0
for folder in ('stl','step','evidence'):(ROOT/folder).mkdir(exist_ok=True)

def check(name,ok,**kw):
 checks.append(dict(check=name,passed=bool(ok),**kw))
 if not ok: raise ValueError(name+' '+str(kw))
def box(x0,x1,y0,y1,z0,z1):return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def fuse(sh):
 s=sh[0]
 for a in sh[1:]:s=s.fuse(a)
 return s.clean()
def disk(u,v,z0,z1,r,ri=0):
 s=cq.Solid.makeCylinder(r,z1-z0,cq.Vector(u,v,z0))
 return s.cut(cq.Solid.makeCylinder(ri,z1-z0+2,cq.Vector(u,v,z0-1))).clean() if ri else s

def rr(x0,x1,y0,y1,z0,z1,r=.6):
 s=cq.Workplane('XY').box(x1-x0,y1-y0,z1-z0,centered=(True,True,False))
 if r:s=s.edges('|Z').fillet(r)
 return s.val().translate(((x0+x1)/2,(y0+y1)/2,z0))
def slot(u,v,z0,z1,angle=0):return cq.Workplane('XY',origin=(u,v,z0)).slot2D(B['slot_length'],B['slot_width'],angle).extrude(z1-z0).val()
def moveface(s,f):
 o,u,v,n=FACES[f];return s.moved(cq.Plane(origin=o,xDir=u,normal=n).location)
def cap(u,v,z0,z1,angle=0):
 s=cq.Workplane('XY',origin=(u,v,z0)).slot2D(20,12,angle).extrude(z1-z0).val()
 return s.cut(disk(u,v,z0-1,z1+1,2.75)).clean()
def hexnut(u,v,z0,z1):
 r=8/math.sqrt(3);vs=[cq.Vector(u+r*math.cos(i*math.pi/3),v+r*math.sin(i*math.pi/3),z0) for i in range(6)]
 s=cq.Solid.extrudeLinear(cq.Wire.makePolygon(vs,close=True),[],cq.Vector(0,0,z1-z0))
 return s.cut(disk(u,v,z0-1,z1+1,2.5)).clean()
def mesh(s):
 v,t=s.tessellate(.09,.22);a={'p':[round(x,5) for vv in v for x in vv.toTuple()],'i':[int(x) for tt in t for x in tt]}
 k=hashlib.sha1(json.dumps(a,separators=(',',':')).encode()).hexdigest()[:16];meshes[k]=a;return k

def record(s,id,name,cat,*,note='',ex=(0,0,0),group='body',local=None,angle=0,material='',printit=False):
 s=s.clean();check('valid solid '+id,s.isValid() and len(s.Solids())==1 and s.Volume()>0)
 bb=s.BoundingBox();row=dict(id=id,name=name,cat=cat,mesh=mesh(s),box=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax],note=note,explode=list(ex),group=group,material=material or ('ASA / home print' if printit else 'reference / not printed'),volume=round(s.Volume(),3),solids=1)
 parts.append(row);breps[id]=s
 if printit:
  orient=local if local is not None else s
  bb=orient.BoundingBox();orient=orient.translate((-bb.xmin,-bb.ymin,-bb.zmin))
  ob=orient.BoundingBox();dim=[ob.xlen,ob.ylen,ob.zlen]
  placed=orient.rotate((0,0,0),(0,0,1),angle);pb=placed.BoundingBox();placed=placed.translate((-pb.xmin,-pb.ymin,-pb.zmin))
  pb=placed.BoundingBox();dims=[pb.xlen,pb.ylen,pb.zlen];brim=P['printer']['brim_allowance_each_side'];xy=[dims[0]+2*brim,dims[1]+2*brim]
  fit=xy[0]<=325+1e-6 and xy[1]<=320+1e-6 and dims[2]<=325
  check('flat placement with 5mm brim '+id,fit,footprint=[round(x,4) for x in xy])
  check('part edge <=350 '+id,max(dim)<=350+1e-6,dimensions=dim)
  cq.exporters.export(placed,str(ROOT/'stl'/f'{id}.stl'),tolerance=.025,angularTolerance=.15)
  cq.exporters.export(s,str(ROOT/'step'/f'{id}.step'))
  m=trimesh.load(ROOT/'stl'/f'{id}.stl',force='mesh');check('readback STL '+id,m.is_watertight and m.is_winding_consistent and m.volume>0)
  read=cq.importers.importStep(str(ROOT/'step'/f'{id}.step')).val();check('readback STEP '+id,read.isValid() and abs(read.Volume()-s.Volume())<max(1e-3,s.Volume()*1e-6))
  plan={'id':id,'name':name,'native_print_dimensions_mm':[round(x,4) for x in dim],'rotation_degrees':angle,'bed_footprint_mm':[round(x,4) for x in dims], 'with_5mm_brim_mm':[round(x,4) for x in xy], 'fits_single_nozzle_rect':fit,'quantity':1,'file':f'stl/{id}.stl','volume_mm3':round(s.Volume(),3),'note':note}
  row['print']=plan;printed.append(plan)
  # Centre actual oriented STL geometry in the true single-nozzle rectangle.
  centered=placed.translate((-dims[0]/2,-dims[1]/2,.2))
  cb=centered.BoundingBox();pp=dict(row);pp.update(id='bed-'+id,mesh=mesh(centered),box=[cb.xmin,cb.ymin,cb.zmin,cb.xmax,cb.ymax,cb.zmax],explode=[0,0,0],group='bed')
  scenes['bed-'+id]=[pp]
 return row

# Equal floor halves; paired lower brackets are placed either side of the centered seam.
flo=rr(-W/2,W/2,-D/2,D/2,0,T,.6)
fh=[]
for sy in (-1,1):
 for x in XS:fh.append((x,sy*(YI-10),90))
for sx in(-1,1):
 for y in YS:fh.append((sx*(XI-10),y,0))
for x,y,a in fh:flo=flo.cut(slot(x,y,-1,T+1,a))
sy=B['floor_split_y']
for j,(y0,y1) in enumerate([(-D/2,sy-GAP/2),(sy+GAP/2,D/2)]):
 s=flo.intersect(box(-W,W,y0,y1,-1,T+1)).clean();record(s,f'floor-{j+1}',f'Floor half {j+1}','floor',note='5mm. Equal 236.4 x 170.35mm halves; centered 0.3mm seam. Two independent side brackets at Y=-25/+25mm. No joining strip or strip holes.',ex=(0,(-1 if j==0 else 1)*1.0,-.5),printit=True)
# Four 5mm side walls. Round printed silhouette replaces separate PA12 guards.
wall_holes={}
for f in('front','back','right','left'):
 half=XI if f in('front','back') else D/2
 s=rr(-half,half,T,H,-T,0,.6)
 rows=[(u,T+10,90,'lower') for u in(XS if f in('front','back') else YS)]
 rows += [(sgn*((XI if f in('front','back') else YI)-10),z,0,'corner') for z in ZS for sgn in(-1,1)]
 if f in('right','left'):rows += [(y if f=='right' else -y,MOUNTZ,None,'rail') for y in MOUNTY]
 for u,v,a,kind in rows:s=s.cut(disk(u,v,-T-1,1,2.75) if a is None else slot(u,v,-T-1,1,a))
 wall_holes[f]=rows;v=FACES[f][3]
 unvented[f]={'mesh':mesh(moveface(s,f)),'volume':round(s.Volume(),3)}
 s,report=cut_wall(s,f,rows,P,check);vent_reports.append(report)
 # Outer face down; native print XY is U/V.
 flat=s.rotate((0,0,0),(1,0,0),180)
 record(moveface(s,f),'wall-'+f,f'{f.title()} wall — 5mm','panels',local=flat,angle=45 if f in('right','left') else 0,ex=[n*1.3 for n in v],note='Original interior kept. 341mm sides print flat at 45 degrees; not upright.',printit=True)
# Existing metal brackets, translated inward by the retained 1mm protective pads.
for f in('front','back','right','left'):
 for k,u in enumerate(XS if f in('front','back') else YS):
  vv=T+SH;nn=-T-SH
  s=fuse([box(u-8,u+8,vv,vv+20,nn-2,nn),box(u-8,u+8,vv,vv+2,nn-20,nn)])
  s=s.cut(disk(u,vv+10,nn-3,nn+1,2.75));s=s.cut(cq.Solid.makeCylinder(2.75,4,cq.Vector(u,vv-1,nn-10),cq.Vector(0,1,0)))
  record(moveface(s,f),f'bracket-lower-{f}-{k}','Stock L bracket 20 x 20 x 16','brackets',ex=[n*.7 for n in FACES[f][3]],material='Stock metal; t2, omitted bend radius')
for sx in(-1,1):
 for syc in(-1,1):
  xx=sx*(XI-SH);yy=syc*(YI-SH)
  for k,z in enumerate(ZS):
   xa,xb=sorted((xx,xx-sx*20));ya,yb=sorted((yy,yy-syc*2));xc,xd=sorted((xx,xx-sx*2));yc,yd=sorted((yy,yy-syc*20))
   s=fuse([box(xa,xb,ya,yb,z-8,z+8),box(xc,xd,yc,yd,z-8,z+8)])
   s=s.cut(cq.Solid.makeCylinder(2.75,25,cq.Vector(xx-sx*10,yy-12,z),cq.Vector(0,1,0))).cut(cq.Solid.makeCylinder(2.75,25,cq.Vector(xx-12,yy-syc*10,z),cq.Vector(1,0,0)))
   record(s,f'bracket-corner-{sx}-{syc}-{k}','Stock corner L bracket','brackets',ex=(sx*.7,syc*.7,0),material='Stock metal; t2')
# Washers and symbolic fasteners: actual thicknesses, threads omitted.
for f,rows in wall_holes.items():
 for k,(u0,v0,a,kind) in enumerate(rows):
  if kind=='rail':continue
  u=u0-math.copysign(SH,u0) if kind=='corner' else u0;v=v0+SH if kind=='lower' else v0
  for tag,n0,n1,cat in [('inner',-T-SH,-T,'washers'),('outer',0,1,'washers')]:
   s=cap(u,v,n0,n1,a);record(moveface(s,f),f'{tag}-{f}-{k}',f'{tag.title()} protective pad t1','washers',note='Home-print ASA / nominal. Round Ø5.5 bore. Printed-panel variant has no guard ears.',ex=[n*(1.6 if tag=='outer' else .9) for n in FACES[f][3]])
  shaft=disk(u,v,-T-SH-2,8,2.5);head=disk(u,v,-T-SH-3.4,-T-SH-2,6)
  record(moveface(fuse([shaft,head]),f),f'bolt-{f}-{k}','M5 body bolt — length to be selected','hardware',ex=[-n*.2 for n in FACES[f][3]],material='Metal; schematic shank/low head')
  record(moveface(hexnut(u,v,1,6),f),f'nut-{f}-{k}','M5 lock nut AF8 x h5','hardware',ex=[n*2 for n in FACES[f][3]],material='Metal; nut envelope only')
# Bottom junction hardware includes internal protection and the underside slot cover.
for k,(x0,y0,a) in enumerate(fh):
 x=x0-math.copysign(SH,x0) if a==0 else x0;y=y0-math.copysign(SH,y0) if a==90 else y0
 for tag,z0,z1 in [('inside',T,T+1),('outside',-1,0)]:record(cap(x,y,z0,z1,a),f'floor-pad-{tag}-{k}','Floor protective pad t1','washers',ex=(0,0,-1 if tag=='outside' else .2))
 record(fuse([disk(x,y,-2.4,-1,6),disk(x,y,-1,17,2.5)]),f'floor-bolt-{k}','M5 bottom low-head bolt','hardware',ex=(0,0,-1),material='Metal; schematic')
 record(disk(x,y,8,9,5,2.75),f'floor-round-pad-{k}','Retained bracket-side washer','washers')
 record(hexnut(x,y,9,14),f'floor-nut-{k}','M5 bottom lock nut','hardware',material='Metal')
# P2: no floor seam strip, dedicated holes, bolts, nuts or washers.
# Feet: reference parts, not exported as ASA (use existing rubber feet).
for sx in(-1,1):
 for syc in(-1,1):record(disk(sx*(W/2-20),syc*(D/2-20),-5,0,6),f'foot-{sx}-{syc}','Rubber foot — 5mm reference','feet',note='Existing/purchased rubber. Not an ASA print recommendation.',material='Rubber reference',ex=(0,0,-1))
# Lid edge: the uploaded 5+5 stepped plate principle with a separated inward tongue.
# Local n positive outward: print outer face down by flipping to positive thickness.
lid_mounts={};ledge_segments={}
for f in('front','back','right','left'):
 half=XI if f in('front','back') else D/2
 mounts=XS if f in('front','back') else [-D/4,D/4]
 lid_mounts[f]=mounts
 s=rr(-half,half,H,RT,-5,0,.6)
 # Tongues clear the adjacent side tongues at corners, 0.3mm from the body inner face.
 tongue_half=half-(6 if f in('front','back') else 10.6)
 t0=-T-L['locator_clearance_per_side']-L['locator_thickness'];t1=-T-L['locator_clearance_per_side']
 # Locator root bridges the 0.3mm relief above the body rim, not below it.
 tongue=box(-tongue_half,tongue_half,H-L['locator_engagement'],H+5,t0,t1)
 bridge=box(-tongue_half,tongue_half,H,H+5,t0,-T+.1)
 s=fuse([s,tongue,bridge])
 # Segmented ledge at roof underside. Leave tool/bracket windows at fastening sites.
 intervals=[(-half+8,half-8)]
 for u in mounts:
  nxt=[]
  for a,b in intervals:
   if u-11>a:nxt.append((a,min(b,u-11)))
   if u+11<b:nxt.append((max(a,u+11),b))
  intervals=[(a,b) for a,b in nxt if b-a>.1]
 for a,b in intervals:s=s.fuse(box(a,b,RB-5,RB,-8,-5))
 for u in mounts:s=s.cut(slot(u,RB-10,-11,1,90))
 flat=s.rotate((0,0,0),(1,0,0),180)
 record(moveface(s,f),'lid-edge-'+f,f'{f.title()} stepped lid edge','lidEdges',local=flat,angle=45 if f in('right','left') else 0,group='lid',ex=[n for n in FACES[f][3]],note='Reference-inspired 5mm wall + 5mm inward locator, 7.5mm engagement, 0.3mm side clearance, segmented 3mm ledge. Local support required under the offset locator when printed outside-face down.',printit=True)
 for k,u in enumerate(mounts):
  # Optional thin shim retained behind lid brackets too.
  n=-T-SH
  br=fuse([box(u-8,u+8,RB-20,RB,n-2,n),box(u-8,u+8,RB-2,RB,n-20,n)])
  br=br.cut(disk(u,RB-10,n-3,n+1,2.75)).cut(cq.Solid.makeCylinder(2.75,4,cq.Vector(u,RB-3,n-10),cq.Vector(0,1,0)))
  record(moveface(br,f),f'lid-bracket-{f}-{k}','Lid edge / top stock L bracket','brackets',group='lid',material='Metal; existing 20x20x16 t2',ex=[n*.5 for n in FACES[f][3]])
  record(moveface(cap(u,RB-10,-6,-5,90),f),f'lid-shim-{f}-{k}','Lid bracket shim t1','washers',group='lid')
  record(moveface(cap(u,RB-10,0,1,90),f),f'lid-cap-{f}-{k}','Lid side outer pad t1','washers',group='lid')
  record(moveface(fuse([disk(u,RB-10,-9.4,-8,6),disk(u,RB-10,-8,8,2.5)]),f),f'lid-bolt-{f}-{k}','Lid side M5 bolt','hardware',group='lid',material='Metal; schematic')
  record(moveface(hexnut(u,RB-10,1,6),f),f'lid-nut-{f}-{k}','Lid side M5 nut','hardware',group='lid',material='Metal')
# Inset 5mm roof: two halves to fit actual single-nozzle build area.
RW=IW-2*L['roof_edge_clearance'];RD=ID-2*L['roof_edge_clearance']
roof=rr(-RW/2,RW/2,-RD/2,RD/2,RB,RT,.6)
roofholes=[]
for f,mounts in lid_mounts.items():
 for u in mounts:
  o,a,v,n=FACES[f];pt=[o[i]+a[i]*u+n[i]*(-T-SH-10) for i in range(3)];x,y=pt[:2];roofholes.append((x,y));roof=roof.cut(disk(x,y,RB-1,RT+1,2.75))
for j,(y0,y1) in enumerate([(-RD/2,-GAP/2),(GAP/2,RD/2)]):
 s=roof.intersect(box(-W,W,y0,y1,RB-1,RT+1)).clean();record(s,f'lid-top-{j+1}',f'Lid top half {j+1} — 5mm','lidRoof',group='lid',ex=(0,-.6 if j==0 else .6,1),note='5mm roof rests on the segmented ledges and bolts to stock L brackets. Two independent halves; no joining strip or strip holes.',printit=True)
for k,(x,y) in enumerate(roofholes):
 record(fuse([disk(x,y,RT+1,RT+2.4,6),disk(x,y,RT+1-16,RT+1,2.5)]),f'roof-bolt-{k}','M5 x16 lid-to-bracket candidate','hardware',group='lid',material='Metal')
 record(disk(x,y,RT,RT+1,5,2.75),f'roof-pad-{k}','Lid top washer','washers',group='lid')
 record(hexnut(x,y,RB-8,RB-3),f'roof-nut-{k}','M5 lock nut beneath roof bracket','hardware',group='lid',material='Metal')
 record(disk(x,y,RB-3,RB-2,5,2.75),f'roof-underpad-{k}','Lid bracket-side washer','washers',group='lid')
# P2: no roof seam strip, dedicated holes, bolts, nuts or washers.
# Reference envelope only: no invented detailed rail/PCB shape.
record(box(-105.2,105.2,-157.377228,157.377228,63,93),'frame-envelope','Existing rail / PCB outer envelope','frame',note='210.4 x314.754456 reference envelope; actual source mesh not imported. Not a manufactured replacement.',material='Reference only',ex=(0,0,1))
# Print existing washer types once each, not every mesh instance.
# These are optional reproductions; user can reuse purchased nylon washers instead.
for name,shape in [('pad-horizontal',cap(0,0,0,1,0)),('pad-vertical',cap(0,0,0,1,90)),('washer-round',disk(0,0,0,1,5,2.75))]:
 # Keep isolated print parts out of assembly by remembering and removing the display record.
 row=record(shape,name,name.replace('-',' ').title(),'washers',printit=True,note='ASA washer prototype. Parameterized; replaceable at home. Not a nylon-material equivalence.');parts.remove(row)
# Diagnostic beds and reference mesh.
scenes['assembly']=parts
scenes['lid']=[p for p in parts if p['group']=='lid']
# Section through a short piece of the long side, away from bracket windows.
clip=box(W/2-30,W/2+10,45,69,H-12,RT+4)
section=[]
for id in ('wall-right','lid-edge-right','lid-top-2'):
 s=breps[id].intersect(clip).clean()
 if s.Volume()>1e-6:
  oldlen=len(parts);r=record(s,'section-'+id,id.replace('-',' '), 'panels' if id=='wall-right' else 'lidEdges' if 'edge' in id else 'lidRoof',group='lid' if id.startswith('lid') else 'body',note='Actual local BRep cut, same geometry as the complete case.');section.append(r);parts.pop()
scenes['edge']=section
# Floor view includes its actual twelve brackets and the lower wall strips.
scenes['seams']=[p for p in parts if p['id'].startswith('floor-') or p['id'].startswith('bracket-lower-')]
for f in ('front','back','right','left'):
 for k in range(len(XS if f in ('front','back') else YS)):
  scenes['seams'].extend(p for p in parts if p['id'] in [f'{tag}-{f}-{k}' for tag in ('inner','outer','bolt','nut')])
 s=breps['wall-'+f].intersect(box(-W,W,-D,D,T,T+25)).clean()
 row=record(s,'lower-wall-'+f,'Lower '+f+' wall (actual section)','panels',note='Actual wall cut for viewing; not a separate print part.',ex=[n*1.3 for n in FACES[f][3]])
 scenes['seams'].append(row);parts.pop()
# Close-up of the real right-side paired supports. Nothing is invented for this view.
scenes['pair']=[]
pair_clip=box(XI-36,W/2+12,-50,50,-5,T+28)
for p in list(parts):
 if p['group']!='body' or p['cat']=='frame':continue
 bb=p['box'];cb=pair_clip.BoundingBox()
 if any(min(bb[i+3],(cb.xmax,cb.ymax,cb.zmax)[i])-max(bb[i],(cb.xmin,cb.ymin,cb.zmin)[i])<=1e-6 for i in range(3)):continue
 s=breps[p['id']].intersect(pair_clip).clean()
 if s.Volume()<1e-6:continue
 row=record(s,'pair-'+p['id'],p['name']+' (local cut)',p['cat'],note='Clipped from the same complete-case solid; not a separate print.',ex=p['explode'],material=p['material'])
 scenes['pair'].append(row);parts.pop()
# The supplied STL is displayed unmodified, not a re-created image.
m=trimesh.load(ROOT/'reference/lid-edge.stl',force='mesh');reference_report={'interpreted_units':'mm','dimensions_mm':m.extents.tolist(),'bounds':m.bounds.tolist(),'watertight':bool(m.is_watertight),'sha256':hashlib.sha256((ROOT/'reference/lid-edge.stl').read_bytes()).hexdigest(),'principal_layer_coordinates_mm':np.unique(np.round(m.vertices[:,2],4)).tolist(),'interpretation':'5mm main plate, offset 5mm locator lip and segmented ledge. Concept adapted, not stretched.'}
v=m.vertices-m.bounds.mean(axis=0);refkey='reference-lid-edge';meshes[refkey]={'p':np.round(v,5).reshape(-1).tolist(),'i':m.faces.reshape(-1).tolist()}
scenes['reference']=[{'id':'reference-stl','name':'Your original lid-edge.stl','cat':'reference','mesh':refkey,'box':np.r_[v.min(axis=0),v.max(axis=0)].tolist(),'note':'Original mesh. Dimensions 317.408 x48.500 x10mm (interpreting STL units as mm). Not stretched to the new case.','explode':[0,0,0],'group':'reference','material':'Uploaded reference','volume':m.volume,'solids':1}]
# Actual bed rectangle is a thin reference solid, distinct from the 350mm combined extent.
bed=box(-162.5,162.5,-160,160,-2,0);bedbb=bed.BoundingBox();bedrow={'id':'h2d-bed','name':'H2D single-nozzle XY: 325 x320','cat':'bed','mesh':mesh(bed),'box':[-162.5,-160,-2,162.5,160,0],'note':'Rectangular advertised build envelope. Check actual slicer keepouts, nozzle mode and supports.','explode':[0,0,0],'group':'bed','material':'Reference','volume':208000,'solids':1}
for key in list(scenes):
 if key.startswith('bed-'):scenes[key].insert(0,bedrow)
# Assembly interference tests on purpose-made printed structure and bracket envelopes.
struct=[p for p in parts if p['cat'] in ('panels','floor','lidEdges','lidRoof','brackets')]
collisions=[]
for i,a in enumerate(struct):
 for b in struct[i+1:]:
  aa=a['box'];bb=b['box']
  if any(min(aa[j+3],bb[j+3])-max(aa[j],bb[j])<1e-5 for j in range(3)):continue
  vol=breps[a['id']].intersect(breps[b['id']]).Volume()
  if vol>1e-4:collisions.append([a['id'],b['id'],round(vol,6)])
check('printed structure and bracket nominal overlap',not collisions,collisions=collisions)
# Locator removal: sample upward from assembled through full clearance.
lifts=[]
body=[p for p in parts if p['group']=='body' and p['cat'] in ('panels','floor','brackets')]
lidedges=[p for p in parts if p['cat']=='lidEdges']
for dz in [0,.5,1,2,4,6,7.5,8,10,15]:
 hit=0
 for a in lidedges:
  aa=a['box'];sa=breps[a['id']].translate((0,0,dz))
  for b in body:
   bb=b['box']
   if any(min(aa[j+3]+(dz if j==2 else 0),bb[j+3])-max(aa[j]+(dz if j==2 else 0),bb[j])<1e-5 for j in range(3)):continue
   hit+=sa.intersect(breps[b['id']]).Volume()
 lifts.append({'lift':dz,'overlap_mm3':hit})
check('sampled straight lid lift path',all(r['overlap_mm3']<1e-4 for r in lifts),samples=lifts)
check('body keeps interior',[round(W-2*T,6),round(D-2*T,6),round(H-T,6)]==[IW,ID,B['wall_height']])
check('stock bracket count',len([p for p in parts if p['cat']=='brackets'])==28)
# Lid clearance against an explicitly assumed knob zone (not every module).
knob=box(-102,102,-150,150,H,H+27)
kh=[]
for p in parts:
 if p['group']!='lid': continue
 vol=breps[p['id']].intersect(knob).Volume()
 if vol>1e-4:kh.append([p['id'],vol])
check('lid vs assumed 27mm knob zone',not kh,collisions=kh,scope='x +-102 / y +-150 / z rim..rim+27; not source detailed modules')
# Optional home-print reproduction quantities: two pad files are orientation aliases.
for p in printed:
 if p['id'] in ('pad-horizontal','pad-vertical'):p['quantity']=48
 if p['id']=='washer-round':p['quantity']=28
# P2 feedback-specific geometry regression.
check('P2 no seam-strip parts or hardware',all('splice' not in p['id'] and p['cat']!='splices' for p in parts))
check('P2 centered floor split',abs(sy)<1e-9)
f1,f2=breps['floor-1'],breps['floor-2']
b1,b2=f1.BoundingBox(),f2.BoundingBox()
check('P2 equal floor panel sizes',all(abs(a-b)<1e-6 for a,b in zip([b1.xlen,b1.ylen,b1.zlen],[b2.xlen,b2.ylen,b2.zlen])),size_mm=[b1.xlen,b1.ylen,b1.zlen])
check('P2 floor halves same volume',abs(f1.Volume()-f2.Volume())<1e-5)
f2r=f2.rotate((0,0,0),(0,0,1),180)
check('P2 floor halves identical after 180 degree rotation',f1.cut(f2r).Volume()+f2r.cut(f1).Volume()<1e-5)
check('P2 floor seam gap',abs(b2.ymin-b1.ymax-GAP)<1e-6,gap_mm=b2.ymin-b1.ymax)
check('P2 twelve floor bracket slots',len(fh)==12)
for f in ('right','left'):
 lower=[row for row in wall_holes[f] if row[3]=='lower']
 check('P2 four lower fastenings '+f,[v[0] for v in lower]==YS,positions_mm=YS)
 check('P2 no central lower wall hole '+f,all(abs(v[0])>1e-6 for v in lower))
 rail=[row for row in wall_holes[f] if row[3]=='rail']
 check('P2 preserves central rail mount '+f,len(rail)==5 and any(abs(row[0])<1e-4 for row in rail))
 for k,y in enumerate(YS):
  if abs(y)!=PAIR:continue
  s=breps[f'bracket-lower-{f}-{k}'];bb=s.BoundingBox()
  check(f'P2 support sits entirely on one floor half {f}/{y}',bb.ymax<-GAP/2 if (y if f=='right' else -y)<0 else bb.ymin>GAP/2,range_mm=[bb.ymin,bb.ymax])
# Former strip through holes must now be filled, not left as stray mounting holes.
for x in (-60,60):
 for y in (10,30):
  check(f'P2 old floor strip bore removed {x}/{y}',any(s.isInside(cq.Vector(x,y,T/2),1e-6) for s in (f1,f2)))
 for y in (-10,10):
  check(f'P2 old roof strip bore removed {x}/{y}',any(breps[k].isInside(cq.Vector(x,y,(RB+RT)/2),1e-6) for k in ('lid-top-1','lid-top-2')))
# New fasteners must pass through both the wall slots and bracket holes.
for f in ('right','left'):
 for k in (1,2):
  bolt=breps[f'bolt-{f}-{k}'];br=breps[f'bracket-lower-{f}-{k}'];wall=breps['wall-'+f]
  check(f'P2 new wall fastener alignment {f}/{k}',bolt.intersect(br).Volume()+bolt.intersect(wall).Volume()<1e-5)
check('P2 structural printed count',len([x for x in printed if x['id'] not in ('pad-horizontal','pad-vertical','washer-round')])==12)

# Report whole slab unprintability on single nozzle, not a false 350mm limit pass.
angles=np.linspace(0,math.pi/2,9001)
fits=lambda a,b:any((a*math.cos(th)+b*math.sin(th)+10<=325 and a*math.sin(th)+b*math.cos(th)+10<=320) for th in angles)
check('whole floor needs split for flat single-nozzle print',not fits(W,D))
check('whole lid top needs split for flat single-nozzle print',not fits(RW,RD))
checks.append({'check':'all detailed rail/PCB, warpage, print strength, transport','status':'NOT VERIFIED: rail mesh absent; envelope shown only. Bambu Studio slicing not performed.'})
model={'ventilation':vent_reports,'unvented':unvented,'revision':P['revision'],'units':'mm','meshes':meshes,'scenes':scenes,'parts':printed,'checks':checks,'reference':reference_report,'parameters':P,
'dimensions':{'body_outside':[W,D,H],'body_inside':[IW,ID,H-T],'roof_inside':[RW,RD,5],'lid_seat':H,'roof_underside':RB,'roof_top':RT,'height_including_roof_washer_and_head':RT+2.4,'floor_half_size':[W,(D-GAP)/2,T],'floor_split_y':sy,'paired_support_y':[-PAIR,PAIR],'body_brackets':20,'lid_brackets':8,'knob_assumption_top':H+27,'roof_nominal_knob_clearance':L['rise_to_roof_underside']-27,'largest_part_edge':max(max(p['native_print_dimensions_mm']) for p in printed)}}
(ROOT/'source/model.json').write_text(json.dumps(model,separators=(',',':')))
(ROOT/'evidence/geometry-checks.json').write_text(json.dumps(checks,indent=2));(ROOT/'evidence/reference-inspection.json').write_text(json.dumps(reference_report,indent=2));(ROOT/'evidence/print-bed-checks.json').write_text(json.dumps(printed,indent=2))
with (ROOT/'PRINT-PARTS.csv').open('w') as f:
 writer=csv.writer(f);writer.writerow(['Part','Quantity','Native flat size mm','Rotation deg','Footprint with 5mm brim','STL','Notes'])
 for r in printed:writer.writerow([r['id'],r['quantity'],r['native_print_dimensions_mm'],r['rotation_degrees'],r['with_5mm_brim_mm'],r['file'],r['note']])
print('DONE',len(parts),'assembly parts,',len(printed),'print files,',len(checks),'checks',flush=True)
