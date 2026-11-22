"""Incremental, reproducible 10BOX-v2 R8 review geometry from immutable R5 inputs.

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
import gzip

import cadquery as cq
import numpy as np
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'r5/source/10box-v2-r5'
RAIL_BASE = ROOT.parent / 'r5/source/research/zzmod/rail-3u60-geometry.json'
R7_MODEL = ROOT / 'reference/r7-model-data.json.gz'
R7_RECEIPT = ROOT / 'reference/r7-model-receipt.json'
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
    previous_bytes = gzip.decompress(R7_MODEL.read_bytes())
    previous_receipt = json.loads(R7_RECEIPT.read_text())
    if (hashlib.sha256(previous_bytes).hexdigest() != previous_receipt['uncompressed_sha256'] or
            len(previous_bytes) != previous_receipt['uncompressed_bytes'] or
            digest(R7_MODEL) != previous_receipt['sha256']):
        raise ValueError('The exact committed R7 comparison model does not match its receipt.')
    previous = json.loads(previous_bytes)
    data = copy.deepcopy(baseline)
    data.update(schema='10box-v2-review/8', revision=CFG['revision'], previousRevision=previous['revision'],
                production_approved=False, baselineParts=copy.deepcopy(baseline['parts']), checks=[], jointScenes={})
    data['comparison'] = {'name': 'Previous R7', 'bodyWidthMm': 337.4, 'frameToSideGapMm': 8,
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
        key = 'r8-' + pid
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
    # Measure the ordinary internal front-panel bracket openings from the exact
    # retained R5 ledges. Its approximately3.0069mm nominal3mm side allowance is
    # the spacing requested for the new side-panel ledges, not the R6 0.5mm gap.
    front_lip_solids=originals['body-front'].intersect(box([-170,-144.99,41.01,170,-141,46.1])).Solids()
    front_intervals=sorted((bounds(s)[0],bounds(s)[3]) for s in front_lip_solids)
    reference_gaps=[]
    for slot in floor_slots['body-bottom-front']:
        x,y,_=slot['center']
        if abs(x)>100:continue
        left=x-CFG['bracket_outer_mm'][2]/2;right=x+CFG['bracket_outer_mm'][2]/2
        before=[b for a,b in front_intervals if b<left]
        after=[a for a,b in front_intervals if a>right]
        if before and after:reference_gaps.extend([left-max(before),min(after)-right])
    evidence('side ledge clearance matches existing front bracket allowance',len(reference_gaps)==6 and
             all(abs(g-CFG['bracket_window_margin_mm'])<.02 for g in reference_gaps),
             reference_front_clearances_mm=reference_gaps,new_side_clearance_mm=CFG['bracket_window_margin_mm'])
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
    record_shape('body-bottom-back',common,note='R8 shared floor: four1.5mm-deep side bracket seats; exterior, tabs and nine through-slots retained.')
    front=common.rotate((0,0,0),(0,0,1),180).translate((0,0,36))
    record_shape('body-bottom-front',front,note='Same R8 common floor, rotated180° and raised36mm.')
    shapes['body-bottom-common']=common
    changed.update(['body-bottom-back','body-bottom-front','body-bottom-common'])
    data['floorSeatParameters']={'seats':seat_details,'side_floor_washer':False,'remaining_thickness_mm':3.5,
                                'purpose':'Provide room for stock t2 bracket feet and internal thin nuts beneath the native rail frames.'}
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
    mount_z = baseline['mountParameters']['mount_z_mm']+CFG['mounting_raise_mm']
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
        record_shape(pid, side, note='R8: corner lips removed; straight ledges and four floor-bracket slots added; R7 rail-mount bore positions remain fixed (+3.5 mm Z from R5). All16 original vents retained.')
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
            record_shape(pid, old.translate((0,shift,CFG['mounting_raise_mm'])), note='R7 8 mm spacer remains fixed with the enclosure mounting axis while the rail frame rises to its lower slot.')
            changed.add(pid)

    # Exact native rail references; changing placement never changes scale or aluminium outlines.
    rail_sources = json.loads(RAIL_BASE.read_text())
    frame_contour = rail_sources['panelContours']['frame3u']
    slot_centers = [sum((min(p[1] for p in hole), max(p[1] for p in hole)))/2
                    for hole in frame_contour['holes'][:2]]
    slot_spacing = slot_centers[1] - slot_centers[0]
    frame_raise = CFG['rail_plane_raise_mm']
    mounting_raise = CFG['mounting_raise_mm']
    evidence('lower slot selection follows the native source',
             CFG['frame_hole_index'] == 1 and
             all(m['frameHoleIndex'] == 1 for row in rail_sources['mounts'] for m in row) and
             abs(frame_raise-mounting_raise-slot_spacing) < 1e-9,
             frame_hole_index=CFG['frame_hole_index'], upper_slot_offset_mm=slot_centers[0],
             lower_slot_offset_mm=slot_centers[1], slot_center_spacing_mm=slot_spacing,
             frame_raise_from_r7_mm=frame_raise-mounting_raise)
    evidence('R7 enclosure mounting axes remain fixed',
             abs(mount_z-previous['mountParameters']['mount_z_mm']) < 1e-9 and
             np.allclose(new_mounts, previous['mountParameters']['mount_y_mm'], atol=1e-9, rtol=0),
             mount_z_mm=mount_z, mount_y_mm=new_mounts)
    rail_shapes = {}
    lower_slot_voids = {}
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
        pid='r8-rail-'+p['id']; key=pid
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
            if p['panel'] == 'frame3u':
                lower_slot_voids[pid] = transformed_panel({
                    'outer': frame_contour['holes'][CFG['frame_hole_index']], 'holes': [],
                    'thickness': frame_contour['thickness']}, mat)
    # Documented frame stack: head below padder,8mm spacer, outerwasher+nut6mm.
    for side,sgn in [('left',-1),('right',1)]:
        for i,y in enumerate(new_mounts):
            shaft=cylinder(2.5,(sgn*152.5,y,mount_z),(sgn,0,0),25)
            head=cylinder(6,(sgn*(152.5-1.4),y,mount_z),(sgn,0,0),1.4)
            pid=f'rail-bolt-{side}-{i+1}'
            record_shape(pid,shaft.fuse(head).clean(),name='Rail M5×25 reference / head below padder',cat='railHardware',group='rails',
                         note='Known1.4mm head height; Ø12mm diameter/M5×25 length are nominal reference envelopes. Threads omitted.',reference=True)
            washer_r=CFG['rail_outside_washer_outer_diameter_mm']/2
            washer_t=CFG['rail_outside_washer_thickness_mm']
            washer=cylinder(washer_r,(sgn*xo,y,mount_z),(sgn,0,0),washer_t).cut(
                cylinder(CFG['rail_outside_washer_inner_diameter_mm']/2,(sgn*(xo-1),y,mount_z),(sgn,0,0),washer_t+2)).clean()
            record_shape(f'rail-washer-{side}-{i+1}',washer,name='Outer rail washer OD10 ID5 t1',cat='railHardware',group='rails',
                         note='R8 rail-only OD10 washer requirement: clears lift-off lid while preserving the confirmed1mm washer/6mm outer washer-plus-nut stack. L-bracket washers stayOD15.',reference=True)
            rr=8/math.sqrt(3)
            w=cq.Wire.makePolygon([cq.Vector(rr*math.cos(k*math.pi/3),rr*math.sin(k*math.pi/3),0) for k in range(6)],close=True)
            nut=cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,5)).cut(cylinder(2.5,(0,0,-1),(0,0,1),7)).clean()
            nut=nut.rotate((0,0,0),(0,1,0),sgn*90).translate((sgn*(xo+1),y,mount_z))
            record_shape(f'rail-nut-{side}-{i+1}',nut,name='Outer rail M5 nut AF8 h5 reference',cat='railHardware',group='rails',reference=True)

    for p in data['parts']:
        if p['id'].startswith('rail-nut-'):
            p.update(fastenerRole='nut',nutSide='outside',fastenerAxis='rail-mount',attachmentWall='body-'+('left' if '-left-' in p['id'] else 'right'))
        elif p['id'].startswith('rail-bolt-'):
            p.update(fastenerRole='bolt',fastenerAxis='rail-mount')
        elif p['id'].startswith('rail-washer-'):
            p.update(fastenerRole='washer',fastenerAxis='rail-mount')

    rail_nuts=[p for p in data['parts'] if p['id'].startswith('rail-nut-')]
    evidence('rail-to-case outside-nut exception retained',len(rail_nuts)==8 and all(p.get('nutSide')=='outside' for p in rail_nuts),
             outside_nut_count=len(rail_nuts),confirmed_outer_washer_plus_nut_mm=6)
    evidence('upper rail mounts retain positive wall ligaments',72-(mount_z+5)>0 and
             72-(mount_z+CFG['rail_mount_hole_diameter_mm']/2)>2,
             spacer_top_edge_margin_mm=72-(mount_z+5),bore_top_ligament_mm=72-(mount_z+CFG['rail_mount_hole_diameter_mm']/2),
             mount_center_z_mm=mount_z,wall_top_z_mm=72)

    rail_washer_checks=[]
    lid_shapes={key:shape for key,shape in originals.items() if key.startswith('lid-')}
    for side,sgn in [('left',-1),('right',1)]:
        for i,y in enumerate(new_mounts):
            pid=f'rail-washer-{side}-{i+1}';washer=shapes[pid]
            rr=CFG['rail_outside_washer_outer_diameter_mm']/2
            clearance=min(washer.distance(lid) for lid in lid_shapes.values())
            # Only the lid's outer side face can reach the washer's inner bearing
            # plane. Project a thin strip of that face over the full washer width;
            # its lowest point moves upward throughout a straight lift-off.
            ax,bx=sorted([sgn*xo,sgn*(xo-.01)])
            strip=box([ax,y-rr,-100,bx,y+rr,200])
            sections=[lid.intersect(strip) for lid in lid_shapes.values() if overlaps(lid,strip)]
            sections=[section for section in sections if section.Volume()>1e-9]
            lowest=min(bounds(section)[2] for section in sections)
            washer_top=mount_z+rr
            lift_gap=lowest-washer_top
            entry={'part':pid,'closed_lid_clearance_mm':clearance,'vertical_lift_clearance_lower_bound_mm':lift_gap,
                   'washer_top_z_mm':washer_top,'projected_lid_lowest_z_mm':lowest,
                   'lift_motion':'straight upward translation from the closed position'}
            rail_washer_checks.append(entry)
            evidence('rail outside washer clears closed lid and vertical lift '+pid,clearance>.17 and lift_gap>.17,**entry)
            contact=cylinder(rr,(sgn*xo,y,mount_z),(-sgn,0,0),.01)
            area=contact.intersect(shapes['body-'+side]).Volume()/.01
            expected=math.pi*(rr**2-(CFG['rail_mount_hole_diameter_mm']/2)**2)
            evidence('rail outside washer fully seated on body '+pid,abs(area-expected)<.02,
                     contact_area_mm2=area,expected_annular_area_mm2=expected,body_top_margin_mm=72-washer_top)
    nut_corner_radius=8/math.sqrt(3)
    nut_support_margin=CFG['rail_outside_washer_outer_diameter_mm']/2-nut_corner_radius
    evidence('rail washer supports complete AF8 nut footprint',nut_support_margin>0,
             radial_margin_mm=nut_support_margin,nut_corner_diameter_mm=2*nut_corner_radius,
             washer_outer_diameter_mm=CFG['rail_outside_washer_outer_diameter_mm'])
    data['mountParameters']['outside_washer']={'count':8,'outer_diameter_mm':CFG['rail_outside_washer_outer_diameter_mm'],
        'inner_diameter_mm':CFG['rail_outside_washer_inner_diameter_mm'],'thickness_mm':CFG['rail_outside_washer_thickness_mm'],
        'nut_footprint_radial_margin_mm':nut_support_margin,'confirmed_washer_plus_nut_stack_mm':6,
        'status':'R8 nominal rail-only OD10 hardware requirement; diameter is not a user measurement.',
        'reason':'OD15 reference washers overlapped the retained lift-off lid bearing face; OD10 remains below the body rim.',
        'lid_clearances':rail_washer_checks}

    # Subsequent stages add source-compatible stock brackets and run exact collision checks.
    add_brackets(data, parts, shapes, originals, floor_slots, rail_shapes, record_shape, evidence, changed)

    # Raising the frames also brings them closer to the retained lid shell and
    # its fasteners. Check the actual frame/padder solids against the shell;
    # add_brackets checks every lid fastener against these same exact solids.
    frame_shell_conflicts=[]
    for pid,solid in rail_shapes.items():
        for other_id,other in shapes.items():
            if not other_id.startswith(('body-','lid-')) or other_id == 'body-bottom-common':
                continue
            if overlaps(solid,other):
                volume=solid.intersect(other).Volume()
                if volume>TOL:
                    frame_shell_conflicts.append({'frame':pid,'shell':other_id,'volume_mm3':volume})
    evidence('raised native frames and padders clear retained body and lid shell',
             not frame_shell_conflicts,collisions=frame_shell_conflicts)

    # Each selected M5 shaft passes through the real, unmodified frame slot.
    for side, sign in [('left',-1),('right',1)]:
        for i,y in enumerate(new_mounts):
            source_id=f'r8-rail-{"front" if y<0 else "rear"}-frame3u-{sign}-0'
            frame=rail_shapes[source_id]
            probe=cylinder(2.5,(-170,y,mount_z),(1,0,0),340)
            overlap=frame.intersect(probe).Volume()
            lower_coverage=lower_slot_voids[source_id].intersect(probe).Volume()
            expected_coverage=math.pi*2.5**2*frame_contour['thickness']
            evidence(f'rail M5 shaft passes through native lower slot {side}/{i+1}',
                     overlap<TOL and abs(lower_coverage-expected_coverage)<TOL,
                     frame_hole_index=1,overlap_mm3=overlap,lower_slot_coverage_mm3=lower_coverage,
                     expected_shaft_through_frame_mm3=expected_coverage,axis_y_z_mm=[y,mount_z])
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
    data['mountParameters']['previous_rail_panel_plane_z_mm']=previous['railSource']['panelPlaneZ']
    data['mountParameters']['previous_preview_rail_panel_plane_z_mm']=previous['railSource']['panelPlaneZ']
    data['mountParameters']['selected_frame_slot']='lower'
    data['mountParameters']['frame_hole_index']=1
    data['mountParameters']['previous_selected_frame_slot']='upper'
    data['mountParameters']['lower_frame_slot_offset_below_panel_plane_mm']=slot_centers[1]
    data['mountParameters']['slot_center_spacing_mm']=slot_spacing
    data['mountParameters']['frame_raise_from_r7_mm']=frame_raise-mounting_raise
    data['mountParameters']['fixed_r7_enclosure_mounting_axes']=True
    data['mountParameters']['front_frame_bottom_clearance_above_shallow_floor_mm']=1+CFG['rail_plane_raise_mm']
    data['mountParameters']['mount_raise_from_old_top_cap_center_mm']=mount_z-baseline['mountParameters']['old_tall_slot_top_cap_center_z_mm']
    data['mountParameters']['previous_mount_y_mm']=previous['mountParameters']['mount_y_mm']
    data['mountParameters']['frame_row_translation_mm']=row_shift
    data['railLayout'].update(panelPlaneZ=72+CFG['rail_plane_raise_mm'],rowCentersY=rail['row_centers_mm'],centralRail='nuts-double-v2-60hp.stl',railBodies=3)
    data['railSource']={'sha':rail['commit'],'panelPlaneZ':72+CFG['rail_plane_raise_mm'],'previousPanelPlaneZ':previous['railSource']['panelPlaneZ'],'physicalFitVerified':False,
                        'reference':'reference/rail-placement.json','rowTranslationMm':row_shift,'raiseZMm':CFG['rail_plane_raise_mm'],
                        'frameHoleIndex':1,'raiseFromR7Mm':slot_spacing}
    data['sideFixingParameters']={'slots':side_fixings,'ledges':ledges,'bracket_dimensions_mm':CFG['bracket_outer_mm'],
                                  'bracket_thickness_mm':CFG['bracket_thickness_mm'],'reference_front_clearances_mm':reference_gaps,'config':CFG}
    data['r8Changes']={'based_on':'R7','changed_printed_parts':[],
                      'changed_assembly_placements':[p['id'] for p in data['parts'] if p['id'].startswith('r8-rail-')],
                      'user_requests':['use native lower long slots for fixed enclosure screw axes',
                                       'raise complete rail/frame/padder assembly without moving printed parts or hardware',
                                       'preserve R7 bracket margins, inside nuts and complete fasteners'],
                      'frame_raise_from_r7_mm':slot_spacing}
    data['limitations']=['Nominal CAD review candidate; physical assembly and print validation are not performed.',
                          'Stock bracket hole inset follows the 7U nominal reference, not a measured hardware drawing.',
                          'The saved native double rail has the same small nominal end-hole residual as the 7U reference assembly.',
                          'Imported native rail meshes are preserved; full rail-mesh manufacturing validity is not claimed.']
    data['limitations'] += ['Rail mounting requires8 OD10/ID5/t1 outside washers;L-bracket washers remainOD15. This nominal diameter change preserves the confirmed6mm outerstack and avoids clamping the lift-off lid.',
                            'All52 L-bracket nuts are inside; only the8 retained rail-frame/case mounting nuts are outside.',
                            'All18 floor,8 sidewall and8 roof joints use the current7U h2.7 thin-nut reference;18 remaining wall joints use h4. Purchased hardware is unmeasured.',
                            'Outside head washers are t1; nuts bear directly on metal brackets without another under-nut washer.',
                            'Rail plane rises12.631103mm from R7 toZ88.131103 to engage lower slots. The unchanged lid offers19.868897mm above that plane; the earlier2mm panel+25mm knob assumption exceeds it by7.131103mm.']
    data['floorCutParameters'].pop('standalone_stl_integrity',None)
    data['floorCutParameters']['r8_bracket_seats']='Four shallow side seats per common floor, preserving the R5 outline, tabs and nine through-slots.'

    # Keep an exact R7 before view, with its own namespaced mesh keys. The
    # comparison cannot accidentally reuse an R8 mesh at an R7 placement.
    data['baselineParts']=copy.deepcopy(previous['parts'])
    for part in data['baselineParts']:
        old_key=part['mesh']; key='r7-before-'+old_key
        data['meshes'][key]=copy.deepcopy(previous['meshes'][old_key])
        part['mesh']=key
    old_parts={p['id']:p for p in previous['parts']}
    same_parts=[]
    for part in data['parts']:
        if part['id'].startswith('r8-rail-'):
            continue
        old=old_parts[part['id']]
        current_mesh=data['meshes'][part['mesh']]
        old_mesh=previous['meshes'][old['mesh']]
        same=(current_mesh['i']==old_mesh['i'] and
              len(current_mesh['p'])==len(old_mesh['p']) and
              np.allclose(current_mesh['p'],old_mesh['p'],atol=1e-9,rtol=0) and
              np.allclose(part['box'],old['box'],atol=1e-9,rtol=0) and
              part.get('staticOffset',[0,0,0])==old.get('staticOffset',[0,0,0]))
        same_parts.append({'part':part['id'],'passed':bool(same)})
    evidence('all non-rail R7 geometry and placements unchanged',
             len(same_parts)==273 and all(p['passed'] for p in same_parts),
             compared_parts=len(same_parts),parts=same_parts,
             scope='All printed parts, spacers, brackets and fasteners; only the 11 rail/frame/padder placements change.')
    rail_placements=[]
    for part in data['parts']:
        if not part['id'].startswith('r8-rail-'):continue
        old=old_parts[part['id'].replace('r8-rail-','r7-rail-',1)]
        current_mesh=data['meshes'][part['mesh']]
        old_mesh=previous['meshes'][old['mesh']]
        delta=np.asarray(current_mesh['p']).reshape(-1,3)-np.asarray(old_mesh['p']).reshape(-1,3)
        # Both saved world meshes round independently to 0.000001 mm. Their
        # subtraction can therefore differ by one least-significant unit.
        rounding_error=float(np.abs(delta-[0,0,slot_spacing]).max())
        same=(current_mesh['i']==old_mesh['i'] and rounding_error<=1.0001e-6)
        rail_placements.append({'part':part['id'],'passed':bool(same),'translation_mm':[0,0,slot_spacing],
                                'maximum_saved_mesh_rounding_error_mm':rounding_error,
                                'saved_world_vertex_precision_mm':0.000001})
    evidence('all 11 native rail parts move only by the measured slot spacing',
             len(rail_placements)==11 and all(p['passed'] for p in rail_placements),parts=rail_placements)
    data['r8Changes']['unchanged_non_rail_part_count']=len(same_parts)
    data['previewMetadata']={'baselineRevision':'R7','r7RailPlaneZ':previous['railSource']['panelPlaneZ'],
                             'railPlaneRaiseFromR7Mm':slot_spacing,'lidRoofUndersideZ':108,
                             'baselineModelSha256':previous_receipt['uncompressed_sha256'],
                             'physicalFitVerified':False}
    detail_ids={'body-right','body-bottom-front','spacer-right-1','rail-bolt-right-1',
                'rail-washer-right-1','rail-nut-right-1','bracket-front-9',
                'r8-rail-front-frame3u-1-0','r8-rail-front-pad3u-1-1'}
    def lower_detail(part):
        return part['id'].replace('r7-rail-','r8-rail-',1) in detail_ids or part.get('attachmentBracket')=='bracket-front-9'
    data['jointScenes']['lower-slot']=[copy.deepcopy(p) for p in data['parts'] if lower_detail(p)]
    data['baselineJointScenes']={'lower-slot':[copy.deepcopy(p) for p in data['baselineParts'] if lower_detail(p)],
                                 'side-fixing':copy.deepcopy(data['jointScenes']['side-fixing'])}
    data['previewMetadata']['lowerSlotFocusMm']=[157,new_mounts[0],mount_z]
    for pid in sorted(changed):
        shape=shapes[pid]
        cq.exporters.export(shape,str(out/'step'/f'{pid}.step'))
        cq.exporters.export(shape,str(out/'stl-review'/f'{pid}.stl'),tolerance=CFG['tessellation_linear_tolerance_mm'],angularTolerance=CFG['tessellation_angular_tolerance_rad'])
        read=cq.importers.importStep(str(out/'step'/f'{pid}.step')).val()
        evidence('STEP readback '+pid,read.isValid() and abs(read.Volume()-shape.Volume())<max(TOL,shape.Volume()*1e-8))
    for pid in originals:
        if pid not in changed:
            evidence('unchanged STEP bytes '+pid,digest(BASE/'step'/f'{pid}.step')==digest(out/'step'/f'{pid}.step'))
    source_files=[R7_MODEL,R7_RECEIPT,BASE/'model_data.json',ROOT/'design-config.json',ROOT/'build_geometry.py',RAIL_BASE,ROOT/'reference/rail-placement.json',
                  ROOT.parents[1]/'r11-build-feedback-04/source/reference/washer-reference.json',
                  ROOT.parents[1]/'r11-build-feedback-04/source/parameters.json',
                  ROOT.parents[1]/'r11-build-feedback-04/source/revision/body.py']
    source_files+=sorted((BASE/'step').glob('*.step'))+sorted((ROOT/'reference').glob('*.stl'))
    receipts=[{'file':str(p.relative_to(ROOT.parents[2])),'bytes':p.stat().st_size,'sha256':digest(p)} for p in source_files]
    data['r8InputReceipts']=receipts
    (out/'model_data.json').write_text(json.dumps(data,separators=(',',':'),ensure_ascii=False))
    (out/'geometry-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    (out/'parameters.json').write_text(json.dumps({k:v for k,v in data.items() if k in ['revision','units','production_approved','dimensions','mountParameters','ventParameters','sideFixingParameters','floorSeatParameters','bracketParameters','railLayout','railSource','r8Changes','lidClearance','previewMetadata','comparison','limitations']},indent=2)+'\n')
    (out/'source-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    failed=[c['check'] for c in checks if not c['passed']]
    print(json.dumps({'out':str(out),'checks':len(checks),'failed':failed,'production_approved':False}),flush=True)
    if failed:
        raise SystemExit(1)


def add_brackets(data, parts, shapes, originals, floor_slots, rail_shapes, record_shape, evidence, changed):
    """Model both fastening legs, with all L-bracket nuts on the inside.

    Nut envelopes and direct nut-to-metal seating follow the current 7U source.
    Its h2.7 thin nut is used at floor/roof and constrained side-wall joints;
    the eighteen remaining wall joints use the h4 regular reference nut.
    """
    bt = CFG['bracket_thickness_mm']
    leg, width = CFG['bracket_outer_mm'][0], CFG['bracket_outer_mm'][2]
    r, inset, pad = CFG['bracket_hole_diameter_mm']/2, CFG['bracket_hole_inset_mm'], CFG['bracket_wall_pad_mm']
    bracket_rows, lid_rows, fasteners = [], [], []
    reference_path = ROOT.parents[1]/'r11-build-feedback-04/source/parameters.json'
    reference = json.loads(reference_path.read_text())
    evidence('7U nut and washer reference retained',
             CFG['bracket_thin_nut_height_mm'] == reference['hardware']['thin_nut_height'] and
             CFG['bracket_regular_nut_height_mm'] == reference['hardware']['nut_height'] and
             CFG['bracket_nut_across_flats_mm'] == reference['hardware']['nut_across_flats'] and
             CFG['outside_bracket_washer_mm'] == reference['washers']['thickness'],
             source=str(reference_path.relative_to(ROOT.parents[2])), thin_nut_height_mm=2.7,
             regular_nut_height_mm=4, dimensions_status=reference['hardware']['dimensions_status'])

    def pad_solid(center, normal, thickness=1):
        return cylinder(7.5,center,normal,thickness).cut(
            cylinder(2.5,tuple(np.asarray(center)-np.asarray(normal)),normal,thickness+2)).clean()

    def hex_nut(center, normal, height):
        center, normal = np.array(center,float), np.array(normal,float)
        u = np.array([0.,1.,0.]) if abs(normal[0]) > .5 else np.array([1.,0.,0.])
        v = np.cross(normal,u)
        radius = CFG['bracket_nut_across_flats_mm']/math.sqrt(3)
        wire = cq.Wire.makePolygon([cq.Vector(*(center+radius*(u*math.cos(k*math.pi/3)+v*math.sin(k*math.pi/3)))) for k in range(6)],close=True)
        solid = cq.Solid.extrudeLinear(wire,[],cq.Vector(*(normal*height)))
        return solid.cut(cylinder(2.5,tuple(center-normal),normal,height+2)).clean()

    def attach(pid, bracket, wall, axis=None, role=None, nut_side=None):
        parts[pid].update(attachmentGroup='brackets', attachmentBracket=bracket, attachmentWall=wall)
        if axis: parts[pid]['fastenerAxis']=axis
        if role: parts[pid]['fastenerRole']=role
        if nut_side: parts[pid]['nutSide']=nut_side

    def fasten(bracket, wall, axis, exterior, normal, inner_seat, length, nut_height, group):
        """Outside washer/head; screw points inward; nut bears on metal directly."""
        exterior, normal, inner_seat = map(lambda a:np.array(a,float),(exterior,normal,inner_seat))
        washer_t = CFG['outside_bracket_washer_mm']
        bearing = exterior-normal*washer_t
        shaft = cylinder(2.5,bearing,normal,length)
        head = cylinder(CFG['floor_screw_head_diameter_mm']/2,bearing-normal*CFG['floor_screw_head_height_mm'],normal,CFG['floor_screw_head_height_mm'])
        pid = axis+'-bolt-'+bracket
        record_shape(pid,shaft.fuse(head).clean(),name=f'Outside M5×{length:g} head / inside thread',cat='hardware',group=group,
                     note='Nominal M5 envelope; 1.4mm head, Ø12mm head. The outside washer bears on the printed panel. Threads omitted.',reference=True)
        attach(pid,bracket,wall,axis,'bolt')
        wid=axis+'-outside-washer-'+bracket
        record_shape(wid,pad_solid(bearing,normal,washer_t),name='Outside washer / OD15 ID5 t1',cat='washers',group=group,reference=True)
        attach(wid,bracket,wall,axis,'washer')
        nid=axis+'-inside-nut-'+bracket
        record_shape(nid,hex_nut(inner_seat,normal,nut_height),name=f'Inside M5 nut / AF8 h{nut_height:g}',cat='hardware',group=group,
                     note='Current7U nominal thin/regular nut reference; directly seated on metal bracket, without an extra under-nut washer. Purchased hardware unmeasured.',reference=True)
        attach(nid,bracket,wall,axis,'nut','inside')
        grip=float(np.dot(inner_seat-bearing,normal))
        engaged=max(0.,min(nut_height,length-grip))
        projection=length-grip-nut_height
        row={'id':axis+'-'+bracket,'bracket':bracket,'wall':wall,'axis':axis,'group':group,
             'exterior_xyz_mm':exterior.tolist(),'inward_normal':normal.tolist(),'head_bearing_xyz_mm':bearing.tolist(),
             'nut_seat_xyz_mm':inner_seat.tolist(),'shaft_tip_xyz_mm':(bearing+normal*length).tolist(),
             'nut_side':'inside','head_side':'outside','nominal_screw_length_mm':length,'nut_height_mm':nut_height,
             'grip_mm':grip,'thread_engagement_mm':engaged,'thread_projection_mm':projection,
             'outside_washer_mm':washer_t,'extra_under_nut_washer':False,
             'parts':[pid,wid,nid]}
        fasteners.append(row)
        evidence('full nut engagement '+row['id'],engaged>=nut_height-1e-7 and projection>=-.000001,
                 engagement_mm=engaged,nut_height_mm=nut_height,projection_mm=projection,nominal_screw_length_mm=length)

    for floor_id, top in [('body-bottom-front',41),('body-bottom-back',5)]:
        for i,slot in enumerate(floor_slots[floor_id]):
            x,y,_=slot['center']; is_side=abs(x)>140
            sign=1 if (x if is_side else y)>0 else -1
            wall='body-'+(('right' if sign>0 else 'left') if is_side else ('back' if sign>0 else 'front'))
            floor_pad=0 if is_side else CFG['bracket_floor_pad_mm']
            recess=CFG['side_bracket_floor_recess_mm'] if is_side else 0
            z0=top+floor_pad-recess
            wall_face=(CFG['side_inner_x_mm'] if is_side else 145)-pad
            aa,bb=sorted([sign*wall_face,sign*(wall_face-leg)])
            cc,dd=sorted([sign*wall_face,sign*(wall_face-bt)])
            normal=(-sign,0,0) if is_side else (0,-sign,0)
            if is_side:
                solid=box([aa,y-width/2,z0,bb,y+width/2,z0+bt]).fuse(box([cc,y-width/2,z0,dd,y+width/2,z0+leg])).clean()
                hole_x=sign*(wall_face-inset)
                solid=solid.cut(cylinder(r,(hole_x,y,z0-1),(0,0,1),bt+2)).cut(cylinder(r,(-170,y,z0+inset),(1,0,0),340)).clean()
                axis_floor=[hole_x,y,top]; axis_wall=[sign*(CFG['side_inner_x_mm']+2.5),y,z0+inset]
                outside_wall=[sign*CFG['side_outer_x_mm'],y,z0+inset]
                inside_wall=[sign*(wall_face-bt),y,z0+inset]
            else:
                solid=box([x-width/2,aa,z0,x+width/2,bb,z0+bt]).fuse(box([x-width/2,cc,z0,x+width/2,dd,z0+leg])).clean()
                hole_y=sign*(wall_face-inset)
                solid=solid.cut(cylinder(r,(x,hole_y,z0-1),(0,0,1),bt+2)).cut(cylinder(r,(x,-155,z0+inset),(0,1,0),310)).clean()
                axis_floor=[x,hole_y,top]; axis_wall=[x,sign*147.5,z0+inset]
                outside_wall=[x,sign*150,z0+inset]
                inside_wall=[x,sign*(wall_face-bt),z0+inset]
            pid=f'bracket-{floor_id.removeprefix("body-bottom-")}-{i+1}'
            record_shape(pid,solid,name='Stock L bracket / '+floor_id,cat='brackets',group='body',
                         note='7U stock20×20×16mm reference, t2; nominal hole inset10mm. Physical hardware fit not verified.',reference=True)
            attach(pid,pid,wall)
            bracket_rows.append({'id':pid,'wall':wall,'floor':floor_id,'floor_axis_mm':axis_floor,'wall_axis_mm':axis_wall,
                                 'nut_side':'inside','side_ledge_clearance_mm':CFG['bracket_window_margin_mm'] if is_side else None})
            pad_center=[sign*(CFG['side_inner_x_mm']-pad),y,z0+inset] if is_side else [x,sign*(145-pad),z0+inset]
            pad_id='pad-wall-'+pid
            record_shape(pad_id,pad_solid(pad_center,(sign,0,0) if is_side else (0,sign,0),pad),
                         name='Protective wall washer between plastic and bracket / t1',cat='washers',group='body',reference=True)
            attach(pad_id,pid,wall,'wall','protective-washer')
            if is_side:
                sb=bounds(solid)
                contact=solid.intersect(box([sb[0]-.1,sb[1]-.1,z0,sb[3]+.1,sb[4]+.1,z0+.01])).translate((0,0,-.01))
                area=contact.intersect(shapes[floor_id]).Volume()/.01
                evidence('recessed bracket foot seated '+pid,area>250,contact_area_mm2=area,
                         floor_seat_z_mm=z0,remaining_floor_mm=5-recess)
            else:
                pad_id='pad-floor-'+pid
                record_shape(pad_id,pad_solid((axis_floor[0],axis_floor[1],top),(0,0,1),floor_pad),
                             name='Protective floor washer between plastic and bracket / t1',cat='washers',group='body',reference=True)
                attach(pad_id,pid,wall,'floor','protective-washer')
            fx,fy=axis_floor[:2]
            nut_h=CFG['bracket_thin_nut_height_mm'] if is_side else CFG['bracket_regular_nut_height_mm']
            floor_length=CFG['side_floor_screw_length_mm'] if is_side else CFG['end_floor_screw_length_mm']
            fasten(pid,wall,'floor',(fx,fy,top-5),(0,0,1),(fx,fy,z0+bt),floor_length,CFG['bracket_thin_nut_height_mm'],'body')
            wall_length=CFG['side_wall_screw_length_mm'] if is_side else CFG['end_wall_screw_length_mm']
            fasten(pid,wall,'wall',outside_wall,normal,inside_wall,wall_length,nut_h,'body')
            floor_probe=cylinder(2.5,(fx,fy,top-5.1),(0,0,1),5.2)
            wall_probe=cylinder(2.5,(-170,axis_wall[1],axis_wall[2]),(1,0,0),340) if is_side else cylinder(2.5,(axis_wall[0],-155,axis_wall[2]),(0,1,0),310)
            evidence('bracket screw clears floor slot '+pid,originals[floor_id].intersect(floor_probe).Volume()<TOL)
            evidence('bracket screw clears wall slot '+pid,shapes[wall].intersect(wall_probe).Volume()<TOL)

    roof=originals['lid-top-single']; roof_z=108
    for i,slot in enumerate(top_slots(roof,113)):
        x,y,_=slot['center']; is_side=abs(x)>140; sgn=1 if (x if is_side else y)>0 else -1
        face=(163.7 if is_side else 145)-pad; z1=roof_z-CFG['bracket_floor_pad_mm']
        aa,bb=sorted([sgn*face,sgn*(face-leg)]); cc,dd=sorted([sgn*face,sgn*(face-bt)])
        normal=(-sgn,0,0) if is_side else (0,-sgn,0)
        if is_side:
            solid=box([aa,y-width/2,z1-bt,bb,y+width/2,z1]).fuse(box([cc,y-width/2,z1-leg,dd,y+width/2,z1])).clean()
            solid=solid.cut(cylinder(r,(sgn*(face-inset),y,z1-bt-1),(0,0,1),bt+2)).cut(cylinder(r,(-170,y,z1-inset),(1,0,0),340)).clean()
            outside_wall=(sgn*CFG['side_outer_x_mm'],y,z1-inset)
            inside_wall=(sgn*(face-bt),y,z1-inset)
        else:
            solid=box([x-width/2,aa,z1-bt,x+width/2,bb,z1]).fuse(box([x-width/2,cc,z1-leg,x+width/2,dd,z1])).clean()
            solid=solid.cut(cylinder(r,(x,sgn*(face-inset),z1-bt-1),(0,0,1),bt+2)).cut(cylinder(r,(x,-155,z1-inset),(0,1,0),310)).clean()
            outside_wall=(x,sgn*150,z1-inset)
            inside_wall=(x,sgn*(face-bt),z1-inset)
        pid=f'bracket-lid-{i+1}'
        wall='lid-'+(('right' if sgn>0 else 'left') if is_side else ('back' if sgn>0 else 'front'))
        record_shape(pid,solid,name='Stock L bracket / lid',cat='brackets',group='lid',note='7U stock bracket reference; lid group.',reference=True)
        attach(pid,pid,wall)
        wall_center=(sgn*(163.7-pad),y,z1-inset) if is_side else (x,sgn*(145-pad),z1-inset)
        pad_id='pad-wall-'+pid
        record_shape(pad_id,pad_solid(wall_center,(sgn,0,0) if is_side else (0,sgn,0),pad),
                     name='Protective lid wall washer / t1',cat='washers',group='lid',reference=True)
        attach(pad_id,pid,wall,'wall','protective-washer')
        roof_axis=(sgn*(face-inset),y,z1) if is_side else (x,sgn*(face-inset),z1)
        pad_id='pad-roof-'+pid
        record_shape(pad_id,pad_solid(roof_axis,(0,0,1),CFG['bracket_floor_pad_mm']),
                     name='Protective roof washer / t1',cat='washers',group='lid',reference=True)
        attach(pad_id,pid,wall,'roof','protective-washer')
        fx,fy=roof_axis[:2]
        fasten(pid,wall,'roof',(fx,fy,113),(0,0,-1),(fx,fy,z1-bt),CFG['lid_roof_screw_length_mm'],CFG['bracket_thin_nut_height_mm'],'lid')
        fasten(pid,wall,'wall',outside_wall,normal,inside_wall,CFG['lid_wall_screw_length_mm'],CFG['bracket_regular_nut_height_mm'],'lid')
        lid_rows.append({'id':pid,'wall':wall,'roof':'lid-top-single','nut_side':'inside'})
        wall_probe=cylinder(2.5,(-170,y,z1-inset),(1,0,0),340) if is_side else cylinder(2.5,(x,-155,z1-inset),(0,1,0),310)
        roof_probe=cylinder(2.5,(fx,fy,107.9),(0,0,1),5.2)
        evidence('bracket screw clears lid slots '+pid,originals[wall].intersect(wall_probe).Volume()<TOL and roof.intersect(roof_probe).Volume()<TOL)

    data['bracketParameters']={'body_count':18,'lid_count':8,'total':26,'mounts':bracket_rows,'lid_mounts':lid_rows,
        'nominal_hardware_only':True,'fasteners':fasteners,'fastener_count':52,'inside_nut_count':52,
        'thin_nut_count':sum(row['nut_height_mm']==2.7 for row in fasteners),'regular_nut_count':sum(row['nut_height_mm']==4 for row in fasteners),
        'nut_orientation':'All L-bracket nuts inside. Rail-frame/case connection nuts remain outside.',
        'thin_nut_locations':'All18 body-floor joints,8 side-wall joints and8 lid-roof joints;34 h2.7 nuts.',
        'washer_arrangement':'Outside OD15/ID5/t1 head washer; retained protective pad between plastic and bracket where modeled; nut bears directly on metal.',
        'hardware_source':'engineering/r11-build-feedback-04/source/parameters.json and source/revision/body.py',
        'floor_fasteners':{'count':18,'direction':'Outside heads, inside nuts','side_length_mm':10,'end_length_mm':12,
                           'side_nut_height_mm':2.7,'end_nut_height_mm':2.7},
        'remaining_assumptions':'M5 screw/head/nut envelopes and bracket hole inset are nominal7U source values, not purchased-hardware measurements.'}
    evidence('complete bracket hardware and inside nuts',len(fasteners)==52 and all(row['nut_side']=='inside' for row in fasteners)
             and data['bracketParameters']['thin_nut_count']==34 and data['bracketParameters']['regular_nut_count']==18,
             fastener_count=len(fasteners),inside_nuts=52,thin_nuts=34,regular_nuts=18)

    hardware=[p for p in data['parts'] if p['cat'] in ('brackets','washers','hardware','railHardware')]
    for p in hardware:
        solid=shapes[p['id']]
        candidates={k:s for k,s in shapes.items() if k.startswith(('body-','lid-','spacer-')) and k not in ('body-bottom-common','spacer-8mm-reference')}
        candidates.update(rail_shapes)
        collision=[]
        for name,other in candidates.items():
            if overlaps(solid,other):
                volume=solid.intersect(other).Volume()
                if volume>TOL:collision.append({'part':name,'volume_mm3':volume})
        evidence('reference hardware clearance '+p['id'],not collision,collisions=collision)
        solid_bounds=bounds(solid); stand_hits=[]
        for stand in [q for q in data['parts'] if q.get('group')=='stand']:
            bb=stand['box']
            if all(min(solid_bounds[k+3],bb[k+3])-max(solid_bounds[k],bb[k])>1e-6 for k in range(3)):stand_hits.append(stand['id'])
        evidence('reference hardware clears original stand '+p['id'],not stand_hits,overlapping_source_bounds=stand_hits)
    # Record actual outer-washer support next to the preserved vents. Positive
    # contact is geometric evidence only, not a strength or tightening result.
    vent_voids=[]
    for vent in data['ventParameters']['side_layout']:
        y,z,w,h,rr=(vent[k] for k in ('y','z','width','height','radius'))
        vv=box([-180,y-w/2+rr,z-h/2,180,y+w/2-rr,z+h/2]).fuse(
            box([-180,y-w/2,z-h/2+rr,180,y+w/2,z+h/2-rr]))
        for cy in (y-w/2+rr,y+w/2-rr):
            for cz in (z-h/2+rr,z+h/2-rr):vv=vv.fuse(cylinder(rr,(-180,cy,cz),(1,0,0),360))
        vent_voids.append(vv.clean())
    bearing_rows=[]
    for row in fasteners:
        if row['axis']!='wall' or row['wall'] not in ('body-left','body-right'):continue
        xyz=np.array(row['exterior_xyz_mm']);normal=np.array(row['inward_normal'])
        probe=cylinder(7.5,xyz,normal,.01)
        area=probe.intersect(shapes[row['wall']]).Volume()/.01
        intended_slot=side_slot(-180,180,xyz[1],xyz[2])
        expected=probe.cut(intended_slot).Volume()/.01
        head_start=np.array(row['head_bearing_xyz_mm'])-normal*CFG['floor_screw_head_height_mm']
        head=cylinder(CFG['floor_screw_head_diameter_mm']/2,head_start,normal,CFG['floor_screw_head_height_mm'])
        head_gap=min(head.distance(vent) for vent in vent_voids)
        entry={'fastener':row['id'],'washer_contact_area_mm2':area,'slot_only_contact_area_mm2':expected,
               'support_fraction':area/expected,'head_to_nearest_vent_mm':head_gap,
               'partial_vent_overlap':area<expected-.01,'strength_validated':False}
        bearing_rows.append(entry)
        evidence('side wall washer contact and head vent clearance '+row['id'],area>0 and head_gap>0,**entry)
    data['bracketParameters']['side_wall_washer_bearing']=bearing_rows
    data['bracketParameters']['side_wall_washer_bearing_note']='Two shallow-side washers overlap a preserved vent edge by3.43% of the slot-only contact area. Heads remain clear; geometric contact is not strength validation.'

    # Native rail STLs are not converted or repaired. Absence of an intersection
    # with their complete source bounds proves all reference hardware clear of
    # those meshes, including the concave L legs whose own bounds overlap them.
    native_rails=[p for p in data['parts'] if p['cat']=='rails' and p['id'].startswith('r8-rail-')]
    native_envelopes={p['id']:box(p['box']) for p in native_rails}
    native_hits=[]
    for p in hardware:
        for rid,envelope in native_envelopes.items():
            solid=shapes[p['id']]
            if not overlaps(solid,envelope):continue
            volume=solid.intersect(envelope).Volume()
            if volume>TOL:native_hits.append({'hardware':p['id'],'rail':rid,'envelope_overlap_mm3':volume})
    evidence('reference hardware clears complete native rail envelopes',not native_hits,native_rail_count=len(native_rails),collisions=native_hits)

    # Include orthogonal nuts on the same L and adjacent rail-mount stacks.
    hardware_collisions=[]; tested_pairs=0
    for i,p in enumerate(hardware):
        for q in hardware[i+1:]:
            a,b=shapes[p['id']],shapes[q['id']]
            if not overlaps(a,b):continue
            tested_pairs+=1
            volume=a.intersect(b).Volume()
            if volume>TOL:hardware_collisions.append({'parts':[p['id'],q['id']],'volume_mm3':volume})
    evidence('all reference hardware pairs clear',not hardware_collisions,tested_overlapping_bounds_pairs=tested_pairs,collisions=hardware_collisions)
    # A nut may stop at any rotational angle when tightened. The swept union
    # of the hexagonal outline is its circumscribed cylinder, not one convenient
    # flat-up mesh. Check that conservative solid against perpendicular hardware
    # and frame/padder solids as well as checking the displayed nut geometry.
    nut_envelopes={}
    for row in fasteners:
        normal=np.array(row['inward_normal'],float)
        seat=np.array(row['nut_seat_xyz_mm'],float)
        envelope=cylinder(CFG['bracket_nut_across_flats_mm']/math.sqrt(3),seat,normal,row['nut_height_mm']).cut(
            cylinder(2.5,seat-normal,normal,row['nut_height_mm']+2)).clean()
        nut_envelopes[row['id']]=envelope
        conflicts=[]
        for p in hardware:
            if p.get('attachmentBracket')!=row['bracket'] or p['id']==row['parts'][2]:continue
            other=shapes[p['id']]
            if overlaps(envelope,other):
                volume=envelope.intersect(other).Volume()
                if volume>TOL:conflicts.append({'part':p['id'],'volume_mm3':volume})
        for pid,other in {**rail_shapes,**{k:v for k,v in shapes.items() if k.startswith('spacer-') and k!='spacer-8mm-reference'}}.items():
            if overlaps(envelope,other):
                volume=envelope.intersect(other).Volume()
                if volume>TOL:conflicts.append({'part':pid,'volume_mm3':volume})
        evidence('nut rotational envelope clears '+row['id'],not conflicts,collisions=conflicts)
    pairs=[]
    for bracket in bracket_rows+lid_rows:
        rows=[row for row in fasteners if row['bracket']==bracket['id']]
        a,b=(nut_envelopes[row['id']] for row in rows)
        gap=a.distance(b)
        overlap=a.intersect(b).Volume() if overlaps(a,b) else 0
        pairs.append({'bracket':bracket['id'],'minimum_distance_mm':gap,'overlap_mm3':overlap})
    evidence('orthogonal nuts retain clearance at every rotation',all(row['minimum_distance_mm']>.6 and row['overlap_mm3']<TOL for row in pairs),
             minimum_distance_mm=min(row['minimum_distance_mm'] for row in pairs),pairs=pairs)
    data['bracketParameters']['rotating_nut_pair_clearance_mm']=min(row['minimum_distance_mm'] for row in pairs)
    floor_bolts=[p for p in hardware if p['id'].startswith('floor-bolt-bracket-front-') and abs((p['box'][0]+p['box'][3])/2)>140]
    distances=[shapes[p['id']].distance(s) for p in floor_bolts for s in rail_shapes.values()]
    evidence('shallow floor screw-tip-to-frame clearance',min(distances)>.49,minimum_distance_mm=min(distances),
             rail_plane_z_mm=72+CFG['rail_plane_raise_mm'],thin_nut_height_mm=2.7)
    wall_bolts=[p for p in hardware if p['id'].startswith('wall-bolt-bracket-front-') and p.get('attachmentWall') in ('body-left','body-right')]
    distances=[shapes[p['id']].distance(s) for p in wall_bolts for s in rail_shapes.values()]
    evidence('side wall screw-tip-to-frame clearance',min(distances)>1.99,minimum_distance_mm=min(distances))
    available_height=108-(72+CFG['rail_plane_raise_mm'])
    knob_clearance=available_height-27
    data['lidClearance']={'roof_underside_z_mm':108,'rail_plane_z_mm':72+CFG['rail_plane_raise_mm'],
                          'available_height_mm':available_height,'assumed_panel_and_knob_height_mm':27,
                          'nominal_clearance_mm':knob_clearance,'shortfall_mm':max(0,-knob_clearance),
                          'assumed_envelope_fits':knob_clearance>=0,'lid_geometry_changed':False,
                          'status':'Known retained-lid limitation, not a physical fit validation.'}
    evidence('retained lid height shortfall is explicitly recorded',
             abs(available_height-19.868897)<1e-8 and abs(knob_clearance+7.131103)<1e-8,
             module_panel_and_knob_assumption_mm=27,roof_underside_mm=108,
             available_height_mm=available_height,nominal_clearance_mm=knob_clearance,
             assumed_envelope_fits=False)
    clip=box([137,-125,30,172,-25,68]); scene=[]
    for pid,solid in shapes.items():
        if pid not in parts or not (pid in ('body-right','body-bottom-front') or 'bracket-front-' in pid):continue
        if not overlaps(solid,clip):continue
        cut=solid.intersect(clip).clean()
        if cut.Volume()<TOL:continue
        key='side-fixing-'+pid; data['meshes'][key]=mesh(cut)
        row=copy.deepcopy(parts[pid]);row.update(id=key,sourceId=pid,mesh=key,box=bounds(cut),explode=[0,0,0]);scene.append(row)
    data['jointScenes']['side-fixing']=scene

if __name__=='__main__':
    main()
