"""7U40 lift-off lid: aluminum top and four integral PA12 locating corners."""
from __future__ import annotations
import math
import json
from .common import sha256_file
import cadquery as cq
from .common import export_step, export_stl
from .types import BuildContext, Part

MIRRORS = ('top_edge_guard_opening_x','top_edge_guard_opening_y','top_edge_guard_exterior_x','top_edge_guard_exterior_y','top_edge_seated_guard_z','top_edge_adhesive_allowance')

def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))

def fused(shapes):
    result=shapes[0]
    for shape in shapes[1:]: result=result.fuse(shape)
    result=result.clean()
    if not result.isValid() or len(result.Solids())!=1: raise ValueError('invalid PA12 quarter')
    return result

def hex_prism(x,y,z0,z1,af):
    r=af/math.sqrt(3)
    wire=cq.Wire.makePolygon([cq.Vector(x+r*math.cos(i*math.pi/3),y+r*math.sin(i*math.pi/3),z0) for i in range(6)],close=True)
    return cq.Solid.extrudeLinear(wire,[],cq.Vector(0,0,z1-z0))

def make_quarter(ox,oy,tab_xmax,tab_y,v):
    wall=v['frame_wall'];seat=v['frame_seat_z'];pz=v['plate_bottom_z'];lip=v['lip_top_z'];seam=v['frame_seam']/2;ledge=v['ledge_depth']
    front=(ox*v['front_screw_fraction'],-oy+v['screw_inset']);side=(ox-v['screw_inset'],-oy*v['side_screw_fraction'])
    tab=box(seam,tab_xmax,tab_y,tab_y+v['locator_thickness'],v['locator_bottom_z'],seat+v['blade_bridge_height'])
    bottom=v['locator_bottom_z']
    edges=[e for e in tab.Edges() if abs(e.BoundingBox().zmin-bottom)<1e-6 and abs(e.BoundingBox().zmax-bottom)<1e-6]
    tab=tab.fillet(v['locator_lead_radius'],edges).clean()
    s=fused([box(seam,ox,-oy,-oy+wall,seat,lip),box(ox-wall,ox,-oy+wall,-seam,seat,lip),
      box(seam,ox,-oy,-oy+ledge,pz-v['ledge_thickness'],pz),box(ox-ledge,ox,-oy+ledge,-seam,pz-v['ledge_thickness'],pz),
      box(front[0]-7,front[0]+7,-oy,-oy+11,pz-v['boss_depth'],pz),
      box(ox-11,ox,side[1]-7,side[1]+7,pz-v['boss_depth'],pz),
      box(seam,tab_xmax,-oy,tab_y+v['locator_thickness'],seat,seat+v['blade_bridge_height']),tab])
    for x,y in (front,side):
        bore=cq.Solid.makeCylinder(v['assembly_bore_diameter']/2,v['boss_depth']+2,cq.Vector(x,y,pz-v['boss_depth']-1))
        pocket=hex_prism(x,y,pz-v['boss_depth']-.2,pz-v['nut_roof_thickness'],v['nut_pocket_af'])
        s=s.cut(bore).cut(pocket).clean()
    if not s.isValid() or len(s.Solids())!=1: raise ValueError('invalid M3 assembly boss')
    return s,(front,side)

def outline(px,py,r):
    b=math.tan(math.pi/8)
    # Lower-left DXF origin; 5-tuples carry true quarter-circle bulges.
    return ((r,0,0,0,0),(2*px-r,0,0,0,b),(2*px,r,0,0,0),(2*px,2*py-r,0,0,b),
            (2*px-r,2*py,0,0,0),(r,2*py,0,0,b),(0,2*py-r,0,0,0),(0,r,0,0,b))

def build(ctx:BuildContext)->list[Part]:
    for key in MIRRORS:
        if ctx.value('guards',key)!=ctx.value('lid',key): raise ValueError(f'top-edge interface mismatch: {key}')
    keys=('frame_wall','frame_seat_z','plate_bottom_z','plate_top_z','lip_top_z','plate_thickness','plate_edge_gap','plate_corner_radius','frame_seam','ledge_depth','ledge_thickness','boss_depth','front_screw_fraction','side_screw_fraction','screw_inset','blade_bridge_height','locator_bottom_z','locator_lead_radius','assembly_bore_diameter','nut_pocket_af','nut_roof_thickness','assembly_hole_diameter','locator_thickness')
    v={k:ctx.value('lid',k) for k in keys}
    if abs(v['plate_top_z']-v['plate_bottom_z']-v['plate_thickness'])>1e-8: raise ValueError('plate Z mismatch')
    ox=ctx.value('guards','top_edge_guard_exterior_x')/2;oy=ctx.value('guards','top_edge_guard_exterior_y')/2
    px=ox-v['frame_wall']-v['plate_edge_gap'];py=oy-v['frame_wall']-v['plate_edge_gap']
    clearance=ctx.value('lid','top_edge_lid_locator_clearance')
    tab_y=-ctx.value('guards','top_edge_guard_opening_y')/2+clearance
    tab_xmax=ctx.value('guards','top_edge_guard_opening_x')/2+ctx.value('lid','locator_x_overhang_from_opening')
    quarter,screws=make_quarter(ox,oy,tab_xmax,tab_y,v)
    transforms=(('FR',lambda s:s,lambda p:p),('FL',lambda s:s.mirror('YZ'),lambda p:(-p[0],p[1])),
                ('BL',lambda s:s.rotate((0,0,0),(0,0,1),180),lambda p:(-p[0],-p[1])),
                ('BR',lambda s:s.mirror('YZ').rotate((0,0,0),(0,0,1),180),lambda p:(p[0],-p[1])))
    parts=[];holes=[];deliverables=[]
    for label,transform,point in transforms:
        part=Part(f'7U40-R9-PA12-LID-FRAME-{label}',transform(quarter),'pa12','black PA12-HP',1,())
        parts.append(part)
        # The scaffold exports only to category roots; keep lid handoff files in a specific folder.
        stem=f'{part.id.lower()}-qty1-mm';dest=ctx.out/'pa12'/'lid'
        for kind, exporter in (('step',export_step),('stl',export_stl)):
            path=dest/f'{stem}.{kind}';exporter(part.solid,path)
            deliverables.append({'partId':part.id,'path':str(path.relative_to(ctx.root)),
                                 'sha256':sha256_file(path),'bytes':path.stat().st_size})
        holes.extend(point(p) for p in screws)
    plate=(cq.Workplane('XY').box(2*px,2*py,v['plate_thickness'],centered=(True,True,False))
           .edges('|Z').fillet(v['plate_corner_radius']).val().translate(cq.Vector(0,0,v['plate_bottom_z'])))
    dxf_holes=[]
    for x,y in holes:
        cutter=cq.Solid.makeCylinder(v['assembly_hole_diameter']/2,v['plate_thickness']+2,cq.Vector(x,y,v['plate_bottom_z']-1))
        plate=plate.cut(cutter).clean();dxf_holes.append((x+px,y+py,v['assembly_hole_diameter']/2))
    if not plate.isValid() or len(plate.Solids())!=1: raise ValueError('invalid aluminum lid plate')
    parts.insert(0,Part('7U40-R9-LID-PLATE',plate,'aluminum','A5052 black anodized candidate',1,('step','dxf','stl'),outline(px,py,v['plate_corner_radius']),tuple(dxf_holes)))
    manifest={'revision':ctx.revision,'model':ctx.model,'module':'lid','status':'prototype-only; not approved for manufacture',
              'sourceMemberHashes':{key:ctx.value('lid',key) for key in ('r7_build_lids_sha256','r7_lid_parameters_sha256')},
              'parts':[part.id for part in parts],'deliverables':deliverables,
              'fitOpenIssues':['R8 seat 92.7 mm versus guard interface seated top 93.4 mm',
                               'adhesive allowance unset; no physical fit or knob envelope confirmation']}
    path=ctx.out/'pa12'/'lid'/'manifest.json'
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    return parts
