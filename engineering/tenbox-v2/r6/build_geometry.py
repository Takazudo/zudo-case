"""Incremental, reproducible 10BOX-v2 R6 review geometry from immutable R5 inputs.

The sidewall cuts and support ledges are exact CAD, and all assemblies consume
the same output meshes as the STEP/STL exports. Native rail meshes are rigidly
placed, never rescaled. Production approval and physical verification stay false.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import shutil
import struct

import cadquery as cq
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'r5/source/10box-v2-r5'
RAIL_BASE = ROOT.parent / 'r5/source/research/zzmod/rail-3u60-geometry.json'
CFG = json.loads((ROOT / 'design-config.json').read_text())
TOL = CFG['validation_volume_tolerance_mm3']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, b, False, False)
    return list(b.Get())


def box(v):
    return cq.Solid.makeBox(*(v[i + 3] - v[i] for i in range(3)), cq.Vector(*v[:3]))


def mesh(shape):
    vv, ff = shape.tessellate(CFG['tessellation_linear_tolerance_mm'], CFG['tessellation_angular_tolerance_rad'])
    return {'p': [round(a, 6) for v in vv for a in v.toTuple()],
            'i': [int(a) for f in ff for a in f]}


def cylinder(radius, origin, vector, length):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*vector))


def side_slot(x0, x1, y, z):
    w = CFG['side_bracket_slot_width_mm']
    travel = CFG['side_bracket_slot_height_mm'] - w
    mid = box([x0, y - w / 2, z - travel / 2, x1, y + w / 2, z + travel / 2])
    for dz in [-travel / 2, travel / 2]:
        mid = mid.fuse(cylinder(w / 2, (x0, y, z + dz), (1, 0, 0), x1 - x0))
    return mid.clean()


def top_slots(shape, top):
    result = []
    for face in shape.Faces():
        if face.normalAt().z < .99 or abs(face.Center().z - top) > 1e-5:
            continue
        for wire in face.innerWires():
            b = bounds(wire)
            result.append({'center': [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, top], 'bounds': b})
    return sorted(result, key=lambda a: a['center'])


def binary_stl(path):
    raw = path.read_bytes()
    n = struct.unpack_from('<I', raw, 80)[0]
    if len(raw) != 84 + 50 * n:
        raise ValueError('Expected complete binary STL: ' + str(path))
    dt = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
    points = np.frombuffer(raw, dtype=dt, count=n, offset=84)['vertices'].astype(float).reshape(-1, 3)
    vertices, inverse = np.unique(points, axis=0, return_inverse=True)
    return vertices, inverse.reshape(-1, 3)


def transformed_mesh(vertices, indices, matrix):
    mat = np.asarray(matrix, float)
    pts = (np.c_[vertices, np.ones(len(vertices))] @ mat.T)[:, :3]
    ind = indices[:, [0, 2, 1]] if np.linalg.det(mat[:3, :3]) < 0 else indices
    return {'p': np.round(pts, 6).ravel().tolist(), 'i': ind.ravel().tolist()}, np.r_[pts.min(axis=0), pts.max(axis=0)].tolist()


def transformed_panel(contour, matrix):
    mat = np.asarray(matrix, float)
    def wire(points):
        pts = (np.c_[np.asarray(points), np.zeros(len(points)), np.ones(len(points))] @ mat.T)[:, :3]
        return cq.Wire.makePolygon([cq.Vector(*p) for p in pts], close=True)
    vector = mat[:3, 2] * contour['thickness']
    return cq.Solid.extrudeLinear(wire(contour['outer']), [wire(h) for h in contour['holes']], cq.Vector(*vector))


def overlaps(a, b):
    aa, bb = bounds(a), bounds(b)
    return all(min(aa[k+3], bb[k+3]) - max(aa[k], bb[k]) > 1e-7 for k in range(3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise SystemExit('Choose an absent output directory; immutable source files are never overwritten.')
    out.mkdir(parents=True)
    for folder in ('step', 'stl-review'):
        shutil.copytree(BASE / folder, out / folder)
    baseline = json.loads((BASE / 'model_data.json').read_text())
    data = copy.deepcopy(baseline)
    data.update(schema='10box-v2-review/6', revision=CFG['revision'], previousRevision=baseline['revision'],
                production_approved=False, baselineParts=copy.deepcopy(baseline['parts']), checks=[], jointScenes={})
    data['comparison'] = {'name': 'Previous R5', 'bodyWidthMm': 337.4, 'frameToSideGapMm': 8,
                          'roofPanels': 1, 'roofWidthMm': 317, 'floorCornersClipped': True}
    shapes = {}
    originals = {}
    for path in (BASE / 'step').glob('*.step'):
        originals[path.stem] = cq.importers.importStep(str(path)).val()
    shapes.update(originals)
    parts = {p['id']: p for p in data['parts']}
    checks = data['checks']
    changed = set()

    def evidence(name, passed, **details):
        checks.append({'check': name, 'passed': bool(passed), **details})
        print(('PASS ' if passed else 'FAIL ') + name, flush=True)

    def record_shape(pid, shape, *, name=None, cat=None, group='body', note='', reference=False):
        shapes[pid] = shape
        key = 'r6-' + pid
        data['meshes'][key] = mesh(shape)
        if pid in parts:
            part = parts[pid]
        else:
            part = {'id': pid, 'name': name or pid, 'cat': cat, 'group': group, 'explode': [0, 0, 0]}
            parts[pid] = part
            data['parts'].append(part)
        part.update(mesh=key, box=bounds(shape), volume=shape.Volume(), sourceId=pid, note=note)
        if cat is not None:
            part.update(cat=cat, group=group, material='Stock metal bracket reference; nominal t2 mm' if cat == 'brackets' else 'Reference hardware')
        if reference:
            part['reference'] = True
        evidence('valid connected solid ' + pid, shape.isValid() and len(shape.Solids()) == 1,
                 solids=len(shape.Solids()), volume_mm3=shape.Volume())

    floor_slots = {pid: top_slots(originals[pid], z) for pid, z in [('body-bottom-front', 41), ('body-bottom-back', 5)]}
    # Four matching seats in the common floor provide room under the shallow
    # row's aluminium side frames. Both positions still use one physical part.
    seat_details=[]
    common=originals['body-bottom-back']
    for slot in floor_slots['body-bottom-back']:
        x,y,top=slot['center']
        if abs(x)<140:continue
        sign=1 if x>0 else -1
        wall_face=CFG['side_inner_x_mm']-CFG['bracket_wall_pad_mm']
        aa,bb=sorted([sign*wall_face,sign*(wall_face-CFG['bracket_outer_mm'][0])])
        clearance=CFG['bracket_seat_clearance_mm']
        b=[aa-clearance,y-CFG['bracket_outer_mm'][2]/2-clearance,top-CFG['side_bracket_floor_recess_mm'],
           bb+clearance,y+CFG['bracket_outer_mm'][2]/2+clearance,top+.1]
        common=common.cut(box(b)).clean()
        seat_details.append({'floor':'body-bottom-common','bounds_mm':b,'depth_mm':CFG['side_bracket_floor_recess_mm'],
                             'remaining_floor_mm':5-CFG['side_bracket_floor_recess_mm']})
    record_shape('body-bottom-back',common,note='R6 shared floor: four1.5mm-deep side bracket seats; exterior, tabs and nine through-slots retained.')
    front=common.rotate((0,0,0),(0,0,1),180).translate((0,0,36))
    record_shape('body-bottom-front',front,note='Same R6 common floor, rotated180° and raised36mm.')
    shapes['body-bottom-common']=common
    changed.update(['body-bottom-back','body-bottom-front','body-bottom-common'])
    data['floorSeatParameters']={'seats':seat_details,'side_floor_washer':False,'remaining_thickness_mm':3.5,
                                'purpose':'Provide room for stock t2 bracket feet and1.4mm low-profile screw heads under the raised native rail frames.'}
    evidence('one shared floor after seat changes',front.rotate((0,0,0),(0,0,1),180).translate((0,0,-36)).cut(common).Volume()<TOL)
    bottom_slab=box([-170,-1,-.1,170,146,5-CFG['side_bracket_floor_recess_mm']])
    evidence('floor lower thickness and through-slots retained',
             originals['body-bottom-back'].intersect(bottom_slab).cut(common).Volume()<TOL,
             unchanged_thickness_mm=5-CFG['side_bracket_floor_recess_mm'])
    side_fixings = []
    ledges = []
    rail = json.loads((ROOT / 'reference/rail-placement.json').read_text())
    old_mounts = baseline['mountParameters']['mount_y_mm']
    row_shift = rail['row_translation_mm']
    new_mounts = [y + row_shift[0 if y < 0 else 1] for y in old_mounts]
    mount_z = baseline['mountParameters']['mount_z_mm']+CFG['rail_plane_raise_mm']
    xi, xo = CFG['side_inner_x_mm'], CFG['side_outer_x_mm']

    for pid, sign in [('body-left', -1), ('body-right', 1)]:
        old = originals[pid]
        # Delete only material projecting inside the original flat inner face.
        cutter = box([-xi, -160, -5, -xi+10, 160, 75]) if sign < 0 else box([xi-10, -160, -5, xi, 160, 75])
        side = old.cut(cutter).clean()
        removed_shape=old.cut(side)
        removed=removed_shape.Volume()
        removed_regions=[bounds(s) for s in removed_shape.Solids()]
        corner_only=len(removed_regions)==4 and all((abs((b[1]+b[4])/2)<12 or abs((b[1]+b[4])/2)>138) for b in removed_regions)
        evidence('four original corner lips removed '+pid,corner_only,removed_volume_mm3=removed,removed_regions_mm=removed_regions)
        x0, x1 = sorted([sign * xi, sign * (xi - CFG['side_ledge_projection_mm'])])
        # Add ledges in the supported straight-edge zone between bracket windows.
        for floor_id, top in [('body-bottom-front', 41), ('body-bottom-back', 5)]:
            slots = [s for s in floor_slots[floor_id] if s['center'][0] * sign > 140]
            ys = sorted(s['center'][1] for s in slots)
            half = CFG['bracket_outer_mm'][2] / 2 + CFG['bracket_window_margin_mm']
            y0, y1 = ys[0] + half, ys[1] - half
            z0 = top + CFG['side_ledge_floor_clearance_mm']
            lip_box = [x0 - (.1 if sign < 0 else 0), y0, z0,
                       x1 + (.1 if sign > 0 else 0), y1, z0 + CFG['side_ledge_height_mm']]
            lip = box(lip_box)
            side = side.fuse(lip).clean()
            ledges.append({'wall': pid, 'floor': floor_id, 'bounds_mm': lip_box, 'projection_mm': CFG['side_ledge_projection_mm'],
                           'floor_clearance_mm': CFG['side_ledge_floor_clearance_mm'], 'window_edge_clearance_mm': CFG['bracket_window_margin_mm']})
            footprint = box([min(sign*xi, sign*(xi-CFG['side_ledge_projection_mm'])), y0, top-.1,
                             max(sign*xi, sign*(xi-CFG['side_ledge_projection_mm'])), y1, top])
            bearing_area = originals[floor_id].intersect(footprint).Volume() / .1
            evidence('ledge lies above intact floor ' + pid + '/' + floor_id, bearing_area > (y1-y0)*2.7,
                     projected_floor_area_mm2=bearing_area)
            for slot in slots:
                y = slot['center'][1]
                z = top + CFG['side_bracket_slot_axis_above_floor_mm'] - CFG['side_bracket_floor_recess_mm']
                hole = side_slot(-xo-1, xo+1, y, z)
                side = side.cut(hole).clean()
                side_fixings.append({'wall': pid, 'floor': floor_id, 'center_xyz_mm': [sign*(xi+2.5), y, z],
                                     'slot_size_mm': [CFG['side_bracket_slot_width_mm'], CFG['side_bracket_slot_height_mm']]})
        # Fill and re-drill the existing circular frame mounting bores for new row positions.
        wall_x0, wall_x1 = sorted([sign*xi, sign*xo])
        for old_y in old_mounts:
            plug = cylinder(CFG['rail_mount_hole_diameter_mm']/2 + .001, (wall_x0, old_y, baseline['mountParameters']['mount_z_mm']), (1,0,0), wall_x1-wall_x0)
            side = side.fuse(plug).clean()
        for y in new_mounts:
            side = side.cut(cylinder(CFG['rail_mount_hole_diameter_mm']/2, (wall_x0-1,y,mount_z), (1,0,0), wall_x1-wall_x0+2)).clean()
        record_shape(pid, side, note='R6: corner lips removed; straight ledges and four floor-bracket slots added; rail-mount bores move with the shared double-rail assembly (+2 mm Z). All16 original vents retained.')
        changed.add(pid)
        old_bounds=bounds(old);new_bounds=bounds(side)
        external_indices=[0,1,2,4,5] if sign<0 else [1,2,3,4,5]
        evidence('sidewall outside envelope retained ' + pid, np.allclose(np.asarray(new_bounds)[external_indices],np.asarray(old_bounds)[external_indices],atol=1e-6),
                 old_bounds_mm=old_bounds, new_bounds_mm=new_bounds)

    # Existing spacer bodies are rigid translations with unchanged 8 mm length.
    for pid, old in list(originals.items()):
        if pid.startswith('spacer-') and pid != 'spacer-8mm-reference':
            y = (bounds(old)[1]+bounds(old)[4])/2
            index=min(range(len(old_mounts)),key=lambda i:abs(y-old_mounts[i]))
            shift = new_mounts[index]-old_mounts[index]
            record_shape(pid, old.translate((0,shift,CFG['rail_plane_raise_mm'])), note='Unchanged 8 mm spacer, moved with its original aluminium rail frame.')
            changed.add(pid)

    # Exact native rail references; changing placement never changes scale or aluminium outlines.
    rail_sources = json.loads(RAIL_BASE.read_text())
    rail_shapes = {}
    for p in rail['parts']:
        if p.get('panel'):
            src = rail_sources['geometries'][p['panel']]
            vv = np.asarray(src['positions'], float).reshape(-1,3)
            ff = np.asarray(src['indices'], int).reshape(-1,3)
        else:
            vv, ff = binary_stl(ROOT / 'reference' / p['asset'])
        mat = np.array(p['matrix'],float)
        mat[2,3]+=CFG['rail_plane_raise_mm']
        m, b = transformed_mesh(vv,ff,mat)
        pid='r6-rail-'+p['id']; key=pid
        data['meshes'][key]=m
        category='railPCB' if p.get('panel')=='frame3u' else 'railPads' if p.get('panel')=='pad3u' else 'rails'
        row={'id':pid,'sourceId':pid,'name':p['id'],'cat':category,'group':'rails','mesh':key,'box':b,
             'explode':[0,0,.7],'reference':True,'material':'Original source rail/frame geometry',
             'note':'Rigid native source placement; source aluminium side-frame outline is unchanged.'}
        data['parts'].append(row);parts[pid]=row
        evidence('rigid unscaled source placement '+pid,np.allclose(np.asarray(mat)[:3,:3].T@np.asarray(mat)[:3,:3],np.eye(3),atol=1e-8))
        if p.get('panel'):
            solid=transformed_panel(rail_sources['panelContours'][p['panel']],mat)
            rail_shapes[pid]=solid
            evidence('valid exact source panel '+pid,solid.isValid() and len(solid.Solids())==1)
    # R5 rail references are preserved only in the comparison assembly.
    for row, depth in enumerate([-70,70]):
        for k,p in enumerate(rail_sources['nylonParts']):
            src=rail_sources['geometries'][p.get('asset') or p['panel']]
            vv=np.asarray(src['positions'],float).reshape(-1,3);ff=np.asarray(src['indices'],int).reshape(-1,3)
            native=np.asarray(p['matrix'],float).reshape(4,4,order='F')
            frame=np.array([[1,0,0,0],[0,-1,0,depth],[0,0,1,72],[0,0,0,1]])
            m,b=transformed_mesh(vv,ff,frame@native);pid=f'r5-rail-{row}-{k}'
            data['meshes'][pid]=m
            data['baselineParts'].append({'id':pid,'sourceId':pid,'name':f'R5 row {row} {p["id"]}','cat':'railPCB' if p['category']=='panel' else 'rails','group':'rails','mesh':pid,'box':b,'explode':[0,0,.7]})

    # Documented frame stack: head below padder,8mm spacer, outerwasher+nut6mm.
    for side,sgn in [('left',-1),('right',1)]:
        for i,y in enumerate(new_mounts):
            shaft=cylinder(2.5,(sgn*152.5,y,mount_z),(sgn,0,0),25)
            head=cylinder(6,(sgn*(152.5-1.4),y,mount_z),(sgn,0,0),1.4)
            pid=f'rail-bolt-{side}-{i+1}'
            record_shape(pid,shaft.fuse(head).clean(),name='Rail M5×25 reference / head below padder',cat='railHardware',group='rails',
                         note='Known1.4mm head height; Ø12mm diameter/M5×25 length are nominal reference envelopes. Threads omitted.',reference=True)
            washer=cylinder(7.5,(sgn*xo,y,mount_z),(sgn,0,0),1).cut(cylinder(2.5,(sgn*(xo-1),y,mount_z),(sgn,0,0),3)).clean()
            record_shape(f'rail-washer-{side}-{i+1}',washer,name='Outer rail washer OD15 ID5 t1',cat='railHardware',group='rails',reference=True)
            rr=8/math.sqrt(3)
            w=cq.Wire.makePolygon([cq.Vector(rr*math.cos(k*math.pi/3),rr*math.sin(k*math.pi/3),0) for k in range(6)],close=True)
            nut=cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,5)).cut(cylinder(2.5,(0,0,-1),(0,0,1),7)).clean()
            nut=nut.rotate((0,0,0),(0,1,0),sgn*90).translate((sgn*(xo+1),y,mount_z))
            record_shape(f'rail-nut-{side}-{i+1}',nut,name='Outer rail M5 nut AF8 h5 reference',cat='railHardware',group='rails',reference=True)

    # Subsequent stages add source-compatible stock brackets and run exact collision checks.
    add_brackets(data, parts, shapes, originals, floor_slots, rail_shapes, record_shape, evidence, changed)

    # Each selected M5 shaft passes through the real, unmodified frame slot.
    for side, sign in [('left',-1),('right',1)]:
        for i,y in enumerate(new_mounts):
            source_id=f'r6-rail-{"front" if y<0 else "rear"}-frame3u-{sign}-0'
            frame=rail_shapes[source_id]
            probe=cylinder(2.5,(-170,y,mount_z),(1,0,0),340)
            overlap=frame.intersect(probe).Volume()
            evidence(f'rail M5 shaft clears native slot {side}/{i+1}',overlap<TOL,overlap_mm3=overlap,axis_y_z_mm=[y,mount_z])
            # The end face of an OD10 spacer must be fully backed by printed wall,
            # apart from the intended Ø5.5 through-hole.
            wall=shapes['body-'+side]
            axis_x=sign*xi
            x0=min(axis_x,axis_x+sign*.01)
            contact=cylinder(5,(x0,y,mount_z),(1,0,0),.01)
            area=contact.intersect(wall).Volume()/.01
            expected=math.pi*(5**2-(CFG['rail_mount_hole_diameter_mm']/2)**2)
            evidence(f'rail spacer seated on solid wall {side}/{i+1}',abs(area-expected)<.02,
                     contact_area_mm2=area,expected_annular_area_mm2=expected)

    data['mountParameters']['mount_y_mm']=new_mounts
    data['mountParameters']['mount_z_mm']=mount_z
    data['mountParameters']['rail_panel_plane_z_mm']=72+CFG['rail_plane_raise_mm']
    data['mountParameters']['previous_rail_panel_plane_z_mm']=72
    data['mountParameters']['previous_preview_rail_panel_plane_z_mm']=72
    data['mountParameters']['front_frame_bottom_clearance_above_shallow_floor_mm']=1+CFG['rail_plane_raise_mm']
    data['mountParameters']['mount_raise_from_old_top_cap_center_mm']=mount_z-baseline['mountParameters']['old_tall_slot_top_cap_center_z_mm']
    data['mountParameters']['previous_mount_y_mm']=old_mounts
    data['mountParameters']['frame_row_translation_mm']=row_shift
    data['railLayout'].update(panelPlaneZ=72+CFG['rail_plane_raise_mm'],rowCentersY=rail['row_centers_mm'],centralRail='nuts-double-v2-60hp.stl',railBodies=3)
    data['railSource']={'sha':rail['commit'],'panelPlaneZ':72+CFG['rail_plane_raise_mm'],'previousPanelPlaneZ':72,'physicalFitVerified':False,
                        'reference':'reference/rail-placement.json','rowTranslationMm':row_shift,'raiseZMm':CFG['rail_plane_raise_mm']}
    data['sideFixingParameters']={'slots':side_fixings,'ledges':ledges,'bracket_dimensions_mm':CFG['bracket_outer_mm'],
                                  'bracket_thickness_mm':CFG['bracket_thickness_mm'],'config':CFG}
    data['r6Changes']={'changed_printed_parts':sorted(p for p in changed if not p.startswith('spacer-')),
                      'changed_assembly_placements':sorted(p for p in changed if p.startswith('spacer-')),
                      'user_requests':['one double center rail','relocated side floor fixers','sidewall bracket slots and actual bracket references']}
    data['limitations']=['Nominal CAD review candidate; physical assembly and print validation are not performed.',
                          'Stock bracket hole inset follows the 7U nominal reference, not a measured hardware drawing.',
                          'The saved native double rail has the same small nominal end-hole residual as the 7U reference assembly.',
                          'Imported native rail meshes are preserved; full rail-mesh manufacturing validity is not claimed.']
    data['limitations'] += ['Floor screws install from inside before the rail assemblies; their1.4mm low-profile heads are inside and washer+nut6mm stack is outside.',
                            'Ø12mm head diameter and M5×16 shaft length are nominal reference envelopes, not measured purchased hardware.',
                            'Rail plane rises2mm toZ74 for real floor-screw head clearance. Assumed2mm module panel+25mm knob leaves7mm below the unchanged lid.']
    data['floorCutParameters'].pop('standalone_stl_integrity',None)
    data['floorCutParameters']['r6_bracket_seats']='Four shallow side seats per common floor, preserving the R5 outline, tabs and nine through-slots.'
    for pid in sorted(changed):
        shape=shapes[pid]
        cq.exporters.export(shape,str(out/'step'/f'{pid}.step'))
        cq.exporters.export(shape,str(out/'stl-review'/f'{pid}.stl'),tolerance=CFG['tessellation_linear_tolerance_mm'],angularTolerance=CFG['tessellation_angular_tolerance_rad'])
        read=cq.importers.importStep(str(out/'step'/f'{pid}.step')).val()
        evidence('STEP readback '+pid,read.isValid() and abs(read.Volume()-shape.Volume())<max(TOL,shape.Volume()*1e-8))
    for pid in originals:
        if pid not in changed:
            evidence('unchanged STEP bytes '+pid,digest(BASE/'step'/f'{pid}.step')==digest(out/'step'/f'{pid}.step'))
    source_files=[BASE/'model_data.json',ROOT/'design-config.json',ROOT/'build_geometry.py',RAIL_BASE,ROOT/'reference/rail-placement.json',
                  ROOT.parents[1]/'r11-build-feedback-04/source/reference/washer-reference.json']
    source_files+=sorted((BASE/'step').glob('*.step'))+sorted((ROOT/'reference').glob('*.stl'))
    receipts=[{'file':str(p.relative_to(ROOT.parents[2])),'bytes':p.stat().st_size,'sha256':digest(p)} for p in source_files]
    data['r6InputReceipts']=receipts
    (out/'model_data.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False))
    (out/'geometry-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    (out/'parameters.json').write_text(json.dumps({k:v for k,v in data.items() if k in ['revision','units','production_approved','dimensions','mountParameters','ventParameters','sideFixingParameters','floorSeatParameters','bracketParameters','railLayout','railSource','r6Changes','limitations']},indent=2)+'\n')
    (out/'source-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    failed=[c['check'] for c in checks if not c['passed']]
    print(json.dumps({'out':str(out),'checks':len(checks),'failed':failed,'production_approved':False}),flush=True)
    if failed:
        raise SystemExit(1)


def add_brackets(data, parts, shapes, originals, floor_slots, rail_shapes, record_shape, evidence, changed):
    """Add the same nominal 20x20x16, t2 stock bracket family used by 7U."""
    bt=CFG['bracket_thickness_mm'];leg=CFG['bracket_outer_mm'][0];width=CFG['bracket_outer_mm'][2]
    r=CFG['bracket_hole_diameter_mm']/2;inset=CFG['bracket_hole_inset_mm'];pad=CFG['bracket_wall_pad_mm']
    bracket_rows=[]
    def pad_solid(center, normal, slot_direction, thickness=1):
        # Exact current7U washer dimensions from its saved reference record:
        # OD15 / ID5 / t1. A round washer avoids intruding into the floor seat.
        base=cylinder(7.5,center,normal,thickness)
        return base.cut(cylinder(2.5,tuple(np.asarray(center)-np.asarray(normal)),normal,thickness+2)).clean()
    def hex_nut(x,y,z0,height):
        radius=CFG['outside_floor_nut_across_flats_mm']/math.sqrt(3)
        w=cq.Wire.makePolygon([cq.Vector(x+radius*math.cos(k*math.pi/3),y+radius*math.sin(k*math.pi/3),z0) for k in range(6)],close=True)
        solid=cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,height))
        return solid.cut(cylinder(2.5,(x,y,z0-1),(0,0,1),height+2)).clean()
    for floor_id, top in [('body-bottom-front',41),('body-bottom-back',5)]:
        for i,slot in enumerate(floor_slots[floor_id]):
            x,y,_=slot['center'];is_side=abs(x)>140
            sign=1 if (x if is_side else y)>0 else -1
            wall='body-'+(('right' if sign>0 else 'left') if is_side else ('back' if sign>0 else 'front'))
            floor_pad=0 if is_side else CFG['bracket_floor_pad_mm']
            recess=CFG['side_bracket_floor_recess_mm'] if is_side else 0
            z0=top+floor_pad-recess
            wall_face=(CFG['side_inner_x_mm'] if is_side else 145)-pad
            aa,bb=sorted([sign*wall_face,sign*(wall_face-leg)])
            cc,dd=sorted([sign*wall_face,sign*(wall_face-bt)])
            if is_side:
                solid=box([aa,y-width/2,z0,bb,y+width/2,z0+bt]).fuse(box([cc,y-width/2,z0,dd,y+width/2,z0+leg])).clean()
                hole_x=sign*(wall_face-inset)
                solid=solid.cut(cylinder(r,(hole_x,y,z0-1),(0,0,1),bt+2)).cut(cylinder(r,(-170,y,z0+inset),(1,0,0),340)).clean()
                axis_floor=[hole_x,y,top];axis_wall=[sign*(CFG['side_inner_x_mm']+2.5),y,z0+inset]
            else:
                solid=box([x-width/2,aa,z0,x+width/2,bb,z0+bt]).fuse(box([x-width/2,cc,z0,x+width/2,dd,z0+leg])).clean()
                hole_y=sign*(wall_face-inset)
                solid=solid.cut(cylinder(r,(x,hole_y,z0-1),(0,0,1),bt+2)).cut(cylinder(r,(x,-155,z0+inset),(0,1,0),310)).clean()
                axis_floor=[x,hole_y,top];axis_wall=[x,sign*147.5,z0+inset]
            pid=f'bracket-{floor_id.removeprefix("body-bottom-")}-{i+1}'
            record_shape(pid,solid,name='Stock L bracket / '+floor_id,cat='brackets',group='body',
                         note='7U stock 20×20×16 mm reference, t2; nominal hole inset10 mm. Physical hardware fit not verified.',reference=True)
            bracket_rows.append({'id':pid,'wall':wall,'floor':floor_id,'floor_axis_mm':axis_floor,'wall_axis_mm':axis_wall})
            pad_center=[sign*(CFG['side_inner_x_mm']-pad),y,z0+inset] if is_side else [x,sign*(145-pad),z0+inset]
            wall_pad=pad_solid(pad_center,(sign,0,0) if is_side else (0,sign,0),(0,0,1),pad)
            record_shape('pad-wall-'+pid,wall_pad,name='7U reference protective wall washer t1',cat='washers',group='body',
                         note='Current7U washer reference: OD15 / ID5 / t1; stored source geometry verified by the R11 reference receipt.',reference=True)
            if is_side:
                # Exact contact area under the recessed metal foot, excluding the through-slot.
                sb=bounds(solid)
                contact=solid.intersect(box([sb[0]-.1,sb[1]-.1,z0,sb[3]+.1,sb[4]+.1,z0+.01])).translate((0,0,-.01))
                area=contact.intersect(shapes[floor_id]).Volume()/.01
                evidence('recessed bracket foot seated '+pid,area>250,contact_area_mm2=area,
                         floor_seat_z_mm=z0,remaining_floor_mm=5-recess)
            else:
                floor_pad_shape=pad_solid((axis_floor[0],axis_floor[1],top),(0,0,1),(0,1,0),floor_pad)
                record_shape('pad-floor-'+pid,floor_pad_shape,name='7U reference protective floor pad t1',cat='washers',group='body',reference=True)
            # Low-profile head stays inside, washer/nut outside, installed before rails.
            fx,fy=axis_floor[:2];foot_top=z0+bt
            shaft=cylinder(2.5,(fx,fy,foot_top-CFG['floor_screw_length_mm']),(0,0,1),CFG['floor_screw_length_mm'])
            head=cylinder(CFG['floor_screw_head_diameter_mm']/2,(fx,fy,foot_top),(0,0,1),CFG['floor_screw_head_height_mm'])
            bolt=shaft.fuse(head).clean()
            record_shape('floor-bolt-'+pid,bolt,name='Inside low-profile M5 head / nominal M5×16',cat='hardware',group='body',
                         note='1.4mm head inside; Ø12mm and16mm shaft are reference assumptions. Install before rail frames. Threads omitted.',reference=True)
            floor_bottom=top-5
            washer=pad_solid((fx,fy,floor_bottom-1),(0,0,1),(1,0,0),1)
            record_shape('floor-outside-washer-'+pid,washer,name='Outside floor washer / OD15 ID5 t1',cat='hardware',group='body',reference=True)
            nut=hex_nut(fx,fy,floor_bottom-6,5)
            record_shape('floor-outside-nut-'+pid,nut,name='Outside floor M5 nut / AF8 h5 reference',cat='hardware',group='body',reference=True)
            bracket_rows[-1].update(screw_head_inside=True,head_top_z_mm=foot_top+CFG['floor_screw_head_height_mm'],
                                    outside_stack_mm=6,nominal_screw_length_mm=CFG['floor_screw_length_mm'])
            # Verify an M5 shank, not merely an intersecting hole center.
            floor_probe=cylinder(2.5,(axis_floor[0],axis_floor[1],top-5.1),(0,0,1),5.2)
            wall_probe=cylinder(2.5,(-170,axis_wall[1],axis_wall[2]),(1,0,0),340) if is_side else cylinder(2.5,(axis_wall[0],-155,axis_wall[2]),(0,1,0),310)
            evidence('bracket screw clears floor slot '+pid,originals[floor_id].intersect(floor_probe).Volume()<TOL)
            evidence('bracket screw clears wall slot '+pid,shapes[wall].intersect(wall_probe).Volume()<TOL)
    # Separate lid brackets remain part of the lid group for visibility and lifting.
    roof=originals['lid-top-single'];roof_z=108
    for i,slot in enumerate(top_slots(roof,113)):
        x,y,_=slot['center'];is_side=abs(x)>140;sgn=1 if (x if is_side else y)>0 else -1
        face=(163.7 if is_side else 145)-pad;z1=roof_z-CFG['bracket_floor_pad_mm']
        aa,bb=sorted([sgn*face,sgn*(face-leg)]);cc,dd=sorted([sgn*face,sgn*(face-bt)])
        if is_side:
            solid=box([aa,y-width/2,z1-bt,bb,y+width/2,z1]).fuse(box([cc,y-width/2,z1-leg,dd,y+width/2,z1])).clean()
            solid=solid.cut(cylinder(r,(sgn*(face-inset),y,z1-bt-1),(0,0,1),bt+2)).cut(cylinder(r,(-170,y,z1-inset),(1,0,0),340)).clean()
        else:
            solid=box([x-width/2,aa,z1-bt,x+width/2,bb,z1]).fuse(box([x-width/2,cc,z1-leg,x+width/2,dd,z1])).clean()
            solid=solid.cut(cylinder(r,(x,sgn*(face-inset),z1-bt-1),(0,0,1),bt+2)).cut(cylinder(r,(x,-155,z1-inset),(0,1,0),310)).clean()
        pid=f'bracket-lid-{i+1}'
        record_shape(pid,solid,name='Stock L bracket / lid',cat='brackets',group='lid',note='7U stock bracket reference; lid group.',reference=True)
        wall_center=(sgn*(163.7-pad),y,z1-inset) if is_side else (x,sgn*(145-pad),z1-inset)
        wp=pad_solid(wall_center,(sgn,0,0) if is_side else (0,sgn,0),(0,0,1),pad)
        record_shape('pad-wall-'+pid,wp,name='7U reference protective lid wall pad t1',cat='washers',group='lid',reference=True)
        roof_axis=(sgn*(face-inset),y,z1) if is_side else (x,sgn*(face-inset),z1)
        rp=pad_solid(roof_axis,(0,0,1),(1,0,0) if is_side else (0,1,0),CFG['bracket_floor_pad_mm'])
        record_shape('pad-roof-'+pid,rp,name='7U reference protective roof pad t1',cat='washers',group='lid',reference=True)
        # Verify actual screw axes through unchanged lid slots, including adjustment travel.
        wall_probe=cylinder(2.5,(-170,y,z1-inset),(1,0,0),340) if is_side else cylinder(2.5,(x,-155,z1-inset),(0,1,0),310)
        lid_wall='lid-'+(('right' if sgn>0 else 'left') if is_side else ('back' if sgn>0 else 'front'))
        roof_probe=cylinder(2.5,(roof_axis[0],roof_axis[1],107.9),(0,0,1),5.2)
        evidence('bracket screw clears lid slots '+pid,originals[lid_wall].intersect(wall_probe).Volume()<TOL and roof.intersect(roof_probe).Volume()<TOL)
    data['bracketParameters']={'body_count':18,'lid_count':8,'total':26,'mounts':bracket_rows,'nominal_hardware_only':True,
                              'floor_fasteners':{'count':18,'direction':'Low-profile head inside, washer+nut outside; assemble before rails',
                              'head_height_mm':1.4,'head_diameter_mm':12,'nominal_shaft_length_mm':16,'outside_stack_mm':6}}
    for p in data['parts']:
        if p['cat'] in ('washers','hardware'):p['attachmentGroup']='brackets'
    hardware=[p for p in data['parts'] if p['cat'] in ('brackets','washers','hardware','railHardware')]
    for p in hardware:
        solid=shapes[p['id']]
        candidates={k:s for k,s in shapes.items() if k.startswith(('body-','lid-','spacer-')) and k not in ('body-bottom-common','spacer-8mm-reference')}
        if p['group']!='lid': candidates.update(rail_shapes)
        collision=[]
        for name,other in candidates.items():
            if overlaps(solid,other):
                volume=solid.intersect(other).Volume()
                if volume>TOL:collision.append({'part':name,'volume_mm3':volume})
        evidence('reference hardware clearance '+p['id'],not collision,collisions=collision)
        # Original stand is a source mesh; disjoint exact source bounds prove clearance.
        solid_bounds=bounds(solid);stand_hits=[]
        for stand in [q for q in data['parts'] if q.get('group')=='stand']:
            bb=stand['box']
            if all(min(solid_bounds[k+3],bb[k+3])-max(solid_bounds[k],bb[k])>1e-6 for k in range(3)):
                stand_hits.append(stand['id'])
        evidence('reference hardware clears original stand '+p['id'],not stand_hits,overlapping_source_bounds=stand_hits)
    heads=[p for p in hardware if p['id'].startswith('floor-bolt-bracket-front-') and abs((p['box'][0]+p['box'][3])/2)>140]
    distances=[shapes[p['id']].distance(s) for p in heads for s in rail_shapes.values()]
    evidence('shallow floor head-to-frame clearance',min(distances)>.99,minimum_distance_mm=min(distances),
             head_height_mm=1.4,rail_plane_z_mm=72+CFG['rail_plane_raise_mm'])
    evidence('lid knob assumption retained',108-(72+CFG['rail_plane_raise_mm']+27)>=7,
             module_panel_and_knob_assumption_mm=27,roof_underside_mm=108,nominal_clearance_mm=108-(72+CFG['rail_plane_raise_mm']+27))
    # A clipped actual-CAD view, independent of camera-only clipping in the viewer.
    clip=box([137,-125,30,171,-25,66]);scene=[]
    for pid,solid in shapes.items():
        if pid not in parts or not (pid in ('body-right','body-bottom-front') or 'bracket-front-' in pid):continue
        if not overlaps(solid,clip):continue
        cut=solid.intersect(clip).clean()
        if cut.Volume()<TOL:continue
        key='side-fixing-'+pid;data['meshes'][key]=mesh(cut)
        row=copy.deepcopy(parts[pid]);row.update(id=key,sourceId=pid,mesh=key,box=bounds(cut),explode=[0,0,0]);scene.append(row)
    data['jointScenes']['side-fixing']=scene


if __name__=='__main__':
    main()
