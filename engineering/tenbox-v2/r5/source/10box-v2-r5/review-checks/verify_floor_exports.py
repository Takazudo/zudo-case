"""Independently inspect R5 floor exports against the shipped frozen R4 STEP.

Only the two changed floors are geometrically audited. Adjacent wall STEP
files are read to quantify the intended loss of corner-lip overlap. Other
parts are compared by bytes. This does not import the CAD generator/config,
the print-fit validator, or their validation results.
"""
from pathlib import Path
import hashlib
import json
import math
import cadquery as cq
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'10box-v2-r5/source-r4/step'
NEW=ROOT/'10box-v2-r5/step'
OUT=Path(__file__).resolve().parent
FLOORS=['body-bottom-front','body-bottom-back']
NEIGHBORS=['body-left','body-right','body-front','body-back']
checks=[]
hashes={}

def record(name,passed,**data):
    checks.append({'check':name,'passed':bool(passed),**data})
    print(('PASS ' if passed else 'FAIL ')+name,flush=True)

def bounds(shape):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(shape.wrapped,b,False,False)
    return np.array(b.Get(),dtype=float)

def box(b):
    b=np.asarray(b,dtype=float)
    return cq.Solid.makeBox(*(b[3:]-b[:3]),cq.Vector(*b[:3]))

def digest(path):
    value=hashlib.sha256(path.read_bytes()).hexdigest()
    hashes[path.relative_to(ROOT).as_posix()]=value
    return value

def load(folder,pid):
    path=folder/(pid+'.step');digest(path)
    return cq.importers.importStep(str(path)).val()

def difference(a,b):
    return float(a.cut(b).Volume()),float(b.cut(a).Volume())

def top(shape):
    z=bounds(shape)[5]
    faces=[f for f in shape.Faces() if f.normalAt().z>.999999 and abs(f.Center().z-z)<1e-6]
    assert len(faces)==1,'Expected one planar floor top face'
    return faces[0]

def center(shape):
    b=bounds(shape);return (b[:3]+b[3:])/2

def hole_prism(w):
    return cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,-5))

def approved_clip(before):
    # The four approved cuts are 12 mm at NE/SW and 16 mm at NW/SE
    # in either floor's own centered assembly XY coordinates. Use infinite
    # diagonal bands (represented by a sufficiently large diamond), not a
    # base-width octagon that would accidentally truncate the four tabs.
    b=bounds(before);yc=(b[1]+b[4])/2;hd=(b[4]-b[1])/2
    a=163.55+hd-12;bdiag=163.55+hd-16
    pts=[((p-q)/2,(p+q)/2+yc) for p,q in [(a,bdiag),(-a,bdiag),(-a,-bdiag),(a,-bdiag)]]
    clip=cq.Workplane('XY').workplane(offset=b[2]-1).polyline(pts).close().extrude(7).val()
    return clip,float(yc),float(a),float(bdiag)

def contact_projection(floor,lip):
    projected=lip.translate((0,0,bounds(floor)[5]-lip.Center().z))
    return float(top(floor).intersect(projected).Area())

def main():
    before={pid:load(BASE,pid) for pid in FLOORS}
    after={pid:load(NEW,pid) for pid in FLOORS}
    neighbors={pid:load(NEW,pid) for pid in NEIGHBORS}
    unchanged=[]
    for p in sorted(BASE.glob('*.step')):
        if p.stem in FLOORS:continue
        q=NEW/p.name
        same=q.is_file() and digest(p)==digest(q)
        unchanged.append({'part':p.stem,'byte_identical':same})
    record('all other active STEP files remain byte-identical to frozen R4',
           bool(unchanged) and all(r['byte_identical'] for r in unchanged),parts=unchanged)
    floor_results={}
    for pid in FLOORS:
        old=before[pid];new=after[pid];nb=bounds(new);ob=bounds(old)
        record(pid+' is one valid connected solid',new.isValid() and len(new.Solids())==1,
               valid=new.isValid(),solid_count=len(new.Solids()),volume_mm3=float(new.Volume()))
        record(pid+' keeps assembly bounds and 5 mm thickness',np.max(np.abs(nb-ob))<1e-7 and abs(nb[5]-nb[2]-5)<1e-7,
               before_bounds_mm=ob.tolist(),after_bounds_mm=nb.tolist(),dimensions_mm=(nb[3:]-nb[:3]).tolist())
        clip,yc,a,bdiag=approved_clip(old)
        expected=old.intersect(clip).clean()
        extra,missing=difference(new,expected)
        record(pid+' differs only by the approved 12/16 mm corner cuts',extra+missing<1e-5,
               unexpected_volume_mm3=extra,missing_volume_mm3=missing,
               clipping_bands={'u':'assembly X','v':f'assembly Y minus {yc:.5f}',
                               'absolute_u_plus_v_max_mm':a,'absolute_minus_u_plus_v_max_mm':bdiag})
        added=new.cut(old).Volume();removed=old.cut(new)
        record(pid+' adds no material and removes exactly 2000 cubic mm',added<1e-5 and abs(removed.Volume()-2000)<1e-5,
               added_mm3=float(added),removed_mm3=float(removed.Volume()),
               removed_material_fraction=float(removed.Volume()/old.Volume()))
        corners=[]
        for corner in removed.Solids():
            cb=bounds(corner);leg_x=cb[3]-cb[0];leg_y=cb[4]-cb[1]
            corners.append({'bounds_mm':cb.tolist(),'edge_legs_mm':[float(leg_x),float(leg_y)],
                            'triangle_opening_area_mm2':float(corner.Volume()/5),
                            'diagonal_edge_length_mm':float(math.hypot(leg_x,leg_y)),
                            'removed_volume_mm3':float(corner.Volume()),
                            'location':'outer end' if abs(center(corner)[1])>abs(yc) else 'center step'})
        areas=sorted(r['triangle_opening_area_mm2'] for r in corners)
        record(pid+' has exactly four triangular floor openings',len(corners)==4 and np.max(np.abs(np.array(areas)-[72,72,128,128]))<1e-6,
               corners=corners,total_opening_area_mm2=float(sum(areas)))

        old_holes=top(old).innerWires();new_holes=top(new).innerWires();remaining=list(new_holes)
        slot_rows=[];slots_ok=len(old_holes)==len(new_holes)==9
        if slots_ok:
            for w in old_holes:
                match=min(remaining,key=lambda q:np.linalg.norm(center(q)-center(w)));remaining.remove(match)
                axis_delta=float(np.linalg.norm(center(match)-center(w)))
                added_profile,lost_profile=difference(hole_prism(match),hole_prism(w))
                slots_ok=slots_ok and axis_delta<1e-6 and added_profile+lost_profile<1e-6
                c=center(match);bb=bounds(match);verts=np.array([v.toTuple() for v in match.Vertices()])
                p=verts[:,0]+verts[:,1]-yc;q=-verts[:,0]+verts[:,1]-yc
                web=min(a-p.max(),a+p.min(),bdiag-q.max(),bdiag+q.min())/math.sqrt(2)
                cp=c[0]+c[1]-yc;cqv=-c[0]+c[1]-yc
                washer_clear=min(a-abs(cp),bdiag-abs(cqv))/math.sqrt(2)-5
                dx,dy=bb[3]-bb[0],bb[4]-bb[1]
                travel=(max(dx,dy)-min(dx,dy))/2
                axis=0 if dx>dy else 1
                washer_rows=[]
                for offset in [-travel,0,travel]:
                    wc=c.copy();wc[axis]+=offset
                    base=cq.Vector(wc[0],wc[1],nb[5]-.01)
                    ring=cq.Solid.makeCylinder(5,.01,base).cut(cq.Solid.makeCylinder(2.75,.01,base))
                    oa=old.intersect(ring).Volume()/.01;na=new.intersect(ring).Volume()/.01
                    washer_rows.append({'nominal_slot_travel_offset_mm':float(offset),
                                        'original_contact_area_mm2':float(oa),'revised_contact_area_mm2':float(na)})
                region=box([c[0]-10,c[1]-10,nb[2],c[0]+10,c[1]+10,nb[5]])
                local_extra,local_lost=difference(new.intersect(region),old.intersect(region))
                slot_rows.append({'center_mm':c.tolist(),'bounds_mm':bb.tolist(),'axis_change_mm':axis_delta,
                                  'profile_extra_mm3':added_profile,'profile_lost_mm3':lost_profile,
                                  'new_diagonal_edge_web_mm':float(web),
                                  'nominal_OD10_washer_diagonal_clearance_mm':float(washer_clear),
                                  'OD10_full_nominal_slot_travel_diagonal_clearance_mm':float(washer_clear-travel/math.sqrt(2)),
                                  'washer_contact_samples':washer_rows,
                                  'local_20x20_mounting_region_extra_mm3':local_extra,
                                  'local_20x20_mounting_region_lost_mm3':local_lost})
        record(pid+' retains all nine closed slot profiles and axes',slots_ok,
               original_slot_count=len(old_holes),revised_slot_count=len(new_holes),slots=slot_rows)
        record(pid+' retains the material within each 20 x 20 mm local fixing region',
               len(slot_rows)==9 and all(r['local_20x20_mounting_region_extra_mm3']+r['local_20x20_mounting_region_lost_mm3']<1e-5 for r in slot_rows),
               region_size_mm=[20,20,5],scope='Local geometry retention; no bracket hardware dimensions assumed.')
        record(pid+' preserves nominal OD10 washer land through nominal slot travel',
               len(slot_rows)==9 and all(r['OD10_full_nominal_slot_travel_diagonal_clearance_mm']>12 and
                   all(abs(x['original_contact_area_mm2']-x['revised_contact_area_mm2'])<1e-5 for x in r['washer_contact_samples']) for r in slot_rows),
               minimum_diagonal_clearance_mm=float(min(r['OD10_full_nominal_slot_travel_diagonal_clearance_mm'] for r in slot_rows)),
               washer_dimensions_mm={'outer_diameter':10,'inner_diameter':5.5},
               scope='Nominal geometric envelope; physical hardware and strength are not qualified.')

        tab_rows=[]
        ysign=-1 if pid.endswith('front') else 1
        for xsign in [-1,1]:
            for y0,y1 in [(45,65),(85,105)]:
                tx=sorted([xsign*163.55,xsign*168.4]);ty=sorted([ysign*y0,ysign*y1])
                region=box([tx[0],ty[0],nb[2],tx[1],ty[1],nb[5]])
                a_tab=old.intersect(region);b_tab=new.intersect(region)
                ae,al=difference(b_tab,a_tab)
                # The 5 mm inner root region is retained as well as the tab tip.
                rx=sorted([xsign*158.55,xsign*163.55])
                root_region=box([rx[0],ty[0],nb[2],rx[1],ty[1],nb[5]])
                re,rl=difference(new.intersect(root_region),old.intersect(root_region))
                tab_rows.append({'bounds_mm':bounds(b_tab).tolist(),'volume_mm3':float(b_tab.Volume()),
                                 'tab_extra_mm3':ae,'tab_lost_mm3':al,
                                 'inner_5mm_root_extra_mm3':re,'inner_5mm_root_lost_mm3':rl})
        record(pid+' retains all four tab profiles and their inner roots',len(tab_rows)==4 and
               all(abs(r['volume_mm3']-485)<1e-6 and sum(r[k] for k in ['tab_extra_mm3','tab_lost_mm3','inner_5mm_root_extra_mm3','inner_5mm_root_lost_mm3'])<1e-5 for r in tab_rows),tabs=tab_rows)

        contacts=[];intersections=[]
        for wall_id,wall in neighbors.items():
            ov=old.intersect(wall).Volume();nv=new.intersect(wall).Volume()
            intersections.append({'neighbor':wall_id,'old_overlap_mm3':float(ov),'new_overlap_mm3':float(nv)})
            for f in wall.Faces():
                fb=bounds(f)
                if not(f.normalAt().z<-.999999 and abs(f.Center().z-nb[5])<.05 and f.Area()>5 and
                       fb[1]>=nb[1]-.01 and fb[4]<=nb[4]+.01):continue
                oa=contact_projection(old,f);na=contact_projection(new,f)
                contacts.append({'neighbor':wall_id,'lip_bounds_mm':fb.tolist(),
                                 'lip_bottom_relative_to_floor_top_mm':float(fb[2]-nb[5]),
                                 'original_projected_overlap_mm2':oa,'revised_projected_overlap_mm2':na,
                                 'projected_overlap_lost_mm2':oa-na,
                                 'location':'middle end lip' if wall_id in ['body-front','body-back'] and abs(f.Center().x)<130 else 'corner lip'})
        record(pid+' introduces no additional intersection with neighboring walls',
               all(r['new_overlap_mm3']<=r['old_overlap_mm3']+1e-5 for r in intersections),intersections=intersections)
        middle=[r for r in contacts if r['location']=='middle end lip']
        record(pid+' retains all four middle end-lip overlaps',len(middle)==4 and all(abs(r['projected_overlap_lost_mm2'])<1e-5 for r in middle),contacts=middle)
        end_corners=[r for r in contacts if r['neighbor'] in ['body-front','body-back'] and r['location']=='corner lip']
        record(pid+' retains partial overlap with both end-panel corner lips',len(end_corners)==2 and all(r['revised_projected_overlap_mm2']>45 for r in end_corners),contacts=end_corners)
        # Contact loss at the deliberately opened corners is disclosed, not
        # misclassified as a test failure or concealed behind unchanged tabs.
        floor_results[pid]={'bounds_mm':nb.tolist(),'volume_mm3':float(new.Volume()),
                           'corners':corners,'removed_area_mm2':float(removed.Volume()/5),
                           'removed_material_fraction':float(removed.Volume()/old.Volume()),
                           'slots':slot_rows,'tabs':tab_rows,'corner_and_end_lip_overlaps':contacts,
                           'neighbor_intersections':intersections}

    rotated=after['body-bottom-back'].rotate((0,0,0),(0,0,1),180).translate((0,0,36))
    extra,missing=difference(after['body-bottom-front'],rotated)
    record('front and back are one common part under 180 degree Z rotation plus 36 mm height',extra+missing<1e-5,
           extra_mm3=extra,missing_mm3=missing,rotation_z_degrees=180,height_offset_mm=36)
    wall_width=bounds(neighbors['body-right'])[3]-bounds(neighbors['body-left'])[0]
    record('337.4 mm exterior width and existing side-frame datums are unchanged',
           abs(wall_width-337.4)<1e-7 and all(r['byte_identical'] for r in unchanged if r['part'] in NEIGHBORS),
           outside_width_mm=float(wall_width),scope='Body side/end STEP bytes and floor assembly coordinates unchanged.')

    report={'scope':'Independent R5 exported STEP audit of only the changed floor panels and their existing corner interfaces. No printer reach, sliced-toolpath, material-strength, or physical-print qualification.',
            'passed':sum(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),
            'floors':floor_results,'unchanged_parts':unchanged,'step_sha256':hashes,'checks':checks}
    (OUT/'independent-floor-export-review.json').write_text(json.dumps(report,indent=2)+'\n')
    min_web=min(r['new_diagonal_edge_web_mm'] for p in floor_results.values() for r in p['slots'])
    min_washer=min(r['nominal_OD10_washer_diagonal_clearance_mm'] for p in floor_results.values() for r in p['slots'])
    min_travel=min(r['OD10_full_nominal_slot_travel_diagonal_clearance_mm'] for p in floor_results.values() for r in p['slots'])
    summary=f'''# R5 clipped floors — independent exported STEP review

**{report['passed']}/{len(checks)} checks passed.** The verifier reads the candidate floor STEP exports and the frozen R4 STEP files shipped in `10box-v2-r5/source-r4/step`. It does not import the model generator, candidate parameters, or their validation reports.

| Feature | Independent result |
| --- | --- |
| Floor solids | One valid connected solid each, 5 mm thick |
| New cuts | Four through-thickness 45° corner chamfers per floor; two 12 mm legs and two 16 mm legs |
| Scope of geometry edits | Exactly the four approved corner triangles; no added material |
| Original assembly bounds | 336.8 × 144.99432 × 5 mm, unchanged |
| Floor heights | Rear Z0–5; front Z36–41, unchanged |
| Fixing slots | Nine original closed profiles and axes retained per floor |
| Local fixing material | Every 20 × 20 mm region centered on an original slot is unchanged |
| 凸 tabs | Four original 4.85 × 20 × 5 mm tabs and their inner 5 mm roots retained per floor |
| Front/rear equivalence | Same solid under 180° Z rotation and 36 mm height offset |
| Other parts | All other active STEP files byte-identical to frozen R4 |
| Exterior case width | 337.4 mm, unchanged; original side/frame datums preserved |

## Corner openings and existing lips

Each floor loses **400 mm² of projected area / 2,000 mm³ of material**: two triangular openings of 72 mm² and two of 128 mm². The openings extend 12 or 16 mm along each adjoining original edge, with diagonal edges of 16.97056 or 22.62742 mm. There are two outer-end openings and two center-step openings per floor. These are intentional openings through the floor, not closed corner joints.

The cuts reduce overlap with the small existing corner retaining lips. Both outer side lips lose their floor overlap; the center-side lips retain only small partial areas. Both end-panel corner lips retain more than 45 mm² projected overlap, and the four middle end lips remain unchanged. Exact per-lip before/after areas and the inherited source height offsets are recorded in the JSON. Projection overlap is not a claim of exact physical contact: the source lips have small positive or negative Z offsets relative to the floor top.

The side tab/receiver regions and all fixing regions remain unchanged. The changed floors introduce no additional intersection with the neighboring walls. The intentionally removed corner contacts should not be described as fully preserved.

## Fixing clearance

The closest retained slot profile is **{min_web:.6f} mm** from a new diagonal edge. A nominal OD10/ID5.5 washer has at least **{min_washer:.6f} mm** clearance to the new diagonal at the slot center, or **{min_travel:.6f} mm** through the nominal slot-center travel. Its contact area is unchanged at the center and both nominal travel ends. These measurements describe geometry; they do not select actual hardware or qualify fastening strength.

Run `python analysis/r5/verify_floor_exports.py` from the package root to reproduce this report. Printer placement and nozzle-area checks are separate; this review does not establish slicing or physical printing success.
'''
    (OUT/'independent-floor-export-review.md').write_text(summary)
    print(json.dumps({'passed':report['passed'],'failed':report['failed']}),flush=True)
    if report['failed']:raise SystemExit(1)

if __name__=='__main__':main()
