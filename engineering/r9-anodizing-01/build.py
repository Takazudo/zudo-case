"""Isolated anodizing revision; original generators and order packages stay immutable."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FIT = ROOT.parent / 'r9-fitfix-01'
R9 = ROOT.parent / 'r9-prototype-01'
sys.path[:0] = [str(FIT), str(R9)]

import cadquery as cq
import ezdxf
from fitfix import io
from fitfix.coupons import coupon_families
from fitfix.geometry import Body, Guard, vertical_corner
from r9.coupons import _build_c3, _c3_joint_records
from r9.body import _geometry_records, _make_bracket_solid
from r9.types import BuildContext

TOL = 1e-5


def require(ok, message):
    if not ok:
        raise ValueError(message)


def file_record(path):
    return dict(path=path.relative_to(REPO).as_posix(), sha256=io.digest(path), bytes=path.stat().st_size)


def source_parts():
    params = json.loads((FIT / 'parameters.json').read_text())
    families = coupon_families(Body(**params['body']), Guard(**{
        k: v for k, v in params['guard'].items() if k != 'comparison_wall'}), params['lid'])
    corner = vertical_corner(Body(**params['body']), Guard(**{k:v for k,v in params['guard'].items() if k != 'comparison_wall'}))
    by_id = {p.id: p for c in families for p in c['parts']}
    plan = json.loads((FIT / 'order-prep/order-plan.json').read_text())
    parts = []
    for item in plan['aluminum_base']['parts']:
        name = item['part']
        family = next(c for c in families if any(p.id == name for p in c['parts']))
        neighbors = [(p.id, p.shape) for p in family['parts'] if p.id != name]
        if name.startswith('c2-'):
            neighbors += [(p.id, p.shape) for c in families if c['id'] in ('C2-02', 'C2-03')
                          for p in c['parts'] if p.id.endswith('-frame')]
        if name.startswith('c5-'):
            neighbors.append(('full-case-vertical-corner-guard', corner))
        parts.append(dict(id=name, shape=by_id[name].shape, neighbors=neighbors,
                          old={k: FIT / 'out' / item[k] for k in ('step', 'dxf', 'stl')}))
    params = {p.stem: json.loads(p.read_text()) for p in (R9 / 'params').glob('*.json')}
    context = BuildContext(R9, R9 / 'out', params)
    sources, design, brackets, _, _ = _geometry_records(context)
    for part in parts:
        if part['id'] == 'c1-metal-edge':
            continue
        b, axis, uv = frame(part['shape'])
        for definition in brackets:
            hardware = _make_bracket_solid(definition)
            hb = io.bounds(hardware)
            if hb['min'][axis] <= b['max'][axis]+2 and hb['max'][axis] >= b['min'][axis]-2:
                part['neighbors'].append(('case-'+definition['id'], hardware))
    params['derived_bracket_width'] = design['bracket_outer'][2]
    c3, records, sources = _build_c3(context)
    selected, _ = _c3_joint_records(context)
    for p in c3:
        name = p.id.lower().removeprefix('7u40-r9-cpn-')
        spec, hole = next((s,h) for s,h in selected if (s.part_type == 'bottom') == name.endswith('-bottom'))
        parts.append(dict(id=name, shape=p.solid, neighbors=[],
                          case_matrix=spec.primary_matrix, case_origin_u=hole.center_local_mm[0]-params['coupons']['c3_plate_width']['value']/2,
                          old={k: R9 / 'out/coupons' / f'{p.id.lower()}-qty1-mm.{k}' for k in ('step', 'dxf')}))
    inputs = [FIT / 'parameters.json', FIT / 'order-prep/order-plan.json',
              FIT / 'order-prep/TEST-PLAN.md', FIT / 'order-prep/ALUMINUM-RFQ.txt',
              FIT / 'order-prep/PA12-RFQ.txt', R9 / 'uv.lock', R9 / 'pyproject.toml',
              *sorted((FIT / 'fitfix').glob('*.py')), *sorted((R9 / 'r9').glob('*.py')),
              *sorted((R9 / 'params').glob('*.json')), *sources['paths'].values()]
    inputs += [FIT/'out/fit-coupons-metal-NOT-APPROVED.zip', FIT/'out/fit-coupons-pa12-NOT-APPROVED.zip', REPO/'public/downloads/candidate/fit-test-order-pack-DRAFT.zip']
    return parts, sorted(set(inputs)), params


def frame(shape):
    b = io.bounds(shape)
    axis = min(range(3), key=lambda i: b['size'][i])
    uv = [i for i in range(3) if i != axis]
    require(abs(b['size'][axis] - 1.5) < TOL, 'not 1.5 mm sheet')
    return b, axis, uv


def local_to_world(shape, b, uv):
    if uv == [0, 2]:
        return shape.rotate((0, 0, 0), (1, 0, 0), 90).translate((b['min'][0], b['max'][1], b['min'][2]))
    if uv == [1, 2]:
        return shape.rotate((0, 0, 0), (1, 1, 1), 120).translate(b['min'])
    return shape.translate(b['min'])


def hole_tool(shape, center, diameter):
    b, axis, uv = frame(shape)
    local = cq.Solid.makeCylinder(diameter / 2, 3.5, cq.Vector(*center, -1))
    return local_to_world(local, b, uv)


def symmetric_difference(a, b):
    return a.cut(b).Volume() + b.cut(a).Volume()


def rectangle_distance(center, rect):
    x, y = center
    x0, y0, x1, y1 = rect
    return math.hypot(max(x0-x, 0, x-x1), max(y0-y, 0, y-y1))


def keepouts(part, params):
    b, axis, uv = frame(part['shape'])
    w, h = (b['size'][i] for i in uv)
    zones = []
    for name, shape in part['neighbors']:
        nb = io.bounds(shape)
        rect = [nb['min'][uv[0]]-b['min'][uv[0]], nb['min'][uv[1]]-b['min'][uv[1]],
                nb['max'][uv[0]]-b['min'][uv[0]], nb['max'][uv[1]]-b['min'][uv[1]]]
        zones.append(dict(id=name, rectangle_uv_mm=rect, basis='conservative projection of regenerated neighboring BREP bounds'))
    if part['id'] == 'c1-metal-edge':
        zones.append(dict(id='all-c1-guard-contact', rectangle_uv_mm=[0, h-5, w, h],
                          basis='shared 5 mm cover; all seven C1 comparisons and split positions'))
    if part['id'].startswith('c3-'):
        bw = params['derived_bracket_width']
        longest = max(params['slots']['slot_length']['value'], *params['coupons']['c3_slot_length_variants']['value'])
        travel = (longest-params['slots']['slot_width']['value'])/2
        bearing = longest+2*travel+2*params['slots']['bearing_overlap']['value']
        require(bw >= max(bearing, params['body']['nylon_outer_diameter']['value']), 'C3 bearing envelope exceeds protected bracket band')
        zones.append(dict(id='bracket-and-swept-washer', rectangle_uv_mm=[w/2-bw/2, 0, w/2+bw/2, h],
                          basis='full-depth 16 mm bracket band; also encloses OD13.5 washer/head swept +/-1.5 mm in V'))
        zones.append(dict(id='joint-and-guard-edge', rectangle_uv_mm=[0, 0, w, 5],
                          basis='conservative 5 mm lower-edge guard/contact band'))
    return zones


def validate_change(original, revised, center, diameter, zones, minimum=1):
    require(3.5 <= diameter <= 5, 'diameter outside supplier range')
    b, axis, uv = frame(original)
    w, h = (b['size'][i] for i in uv)
    r = diameter / 2
    ligament = min(center[0], w-center[0], center[1], h-center[1])-r
    require(ligament >= minimum-TOL, 'edge ligament below minimum')
    clearances = [dict(id=z['id'], clearance_mm=rectangle_distance(center, z['rectangle_uv_mm'])-r) for z in zones]
    require(all(c['clearance_mm'] > TOL for c in clearances), 'hole intersects protected region')
    tool = hole_tool(original, center, diameter)
    removed = original.cut(revised)
    expected = tool.intersect(original)
    require(revised.isValid() and len(revised.Solids()) == 1, 'invalid revised solid')
    require(revised.cut(original).Volume() < TOL, 'material added')
    expected_volume = math.pi*r*r*1.5
    require(abs(removed.Volume()-expected_volume) < TOL, 'hole not one full through cylinder or overlaps old feature')
    require(symmetric_difference(removed, expected) < TOL, 'functional geometry changed outside hanging hole')
    require(max(abs(x-y) for k in ('min', 'max') for x, y in zip(b[k], io.bounds(revised)[k])) < TOL, 'outline changed')
    return dict(edge_ligament_mm=ligament, protected_clearances=clearances,
                removed_volume_mm3=removed.Volume(), expected_removed_volume_mm3=expected_volume,
                functional_geometry_unchanged=True)


def dxf_shape(path):
    """Reconstruct all delivered DXF closed wires, including original slot arcs."""
    doc = ezdxf.readfile(path)
    require(doc.units == 4 and not doc.audit().has_errors, 'DXF units/audit failed')
    groups = {}
    for e in doc.modelspace():
        layer = e.dxf.layer
        groups.setdefault(layer, [])
        if e.dxftype() == 'LWPOLYLINE':
            require(e.closed and not any(abs(p[4]) > TOL for p in e.get_points()), 'unexpected outline/bulge')
            pts = [cq.Vector(p[0], p[1], 0) for p in e.get_points()]
            groups[layer].extend(cq.Edge.makeLine(a, b) for a, b in zip(pts, pts[1:]+pts[:1]))
        elif e.dxftype() == 'CIRCLE':
            groups[layer].append(cq.Edge.makeCircle(e.dxf.radius, cq.Vector(*e.dxf.center)))
        elif e.dxftype() == 'LINE':
            groups[layer].append(cq.Edge.makeLine(cq.Vector(*e.dxf.start), cq.Vector(*e.dxf.end)))
        elif e.dxftype() == 'ARC':
            groups[layer].append(cq.Edge.makeCircle(e.dxf.radius, cq.Vector(*e.dxf.center),
                                                   angle1=e.dxf.start_angle, angle2=e.dxf.end_angle))
        else:
            raise ValueError(f'unexpected DXF entity {e.dxftype()}')
    require('OUTLINE' in groups, 'missing DXF outline')
    outer = cq.Wire.assembleEdges(groups.pop('OUTLINE'))
    inner = []
    for edges in groups.values():
        inner.extend(cq.Wire.combine(edges, tol=1e-7))
    return cq.Solid.extrudeLinear(outer, inner, cq.Vector(0, 0, 1.5))


def export_dxf(old, new, center, diameter):
    previous = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        doc = ezdxf.readfile(old)
        require('HANGING' not in doc.layers, 'baseline already contains hanging layer')
        doc.layers.new('HANGING')
        doc.modelspace().add_circle(center, diameter/2, dxfattribs={'layer': 'HANGING'})
        doc.saveas(new)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = previous


def svg_entities(path, offset, scale, height):
    def pt(p):
        return (offset[0]+p[0]*scale, offset[1]+(height-p[1])*scale)
    result = []
    for e in ezdxf.readfile(path).modelspace():
        color = '#c62828' if e.dxf.layer == 'HANGING' else '#162b3c'
        if e.dxftype() == 'CIRCLE':
            x, y = pt(e.dxf.center)
            result.append(f'<circle cx="{x}" cy="{y}" r="{e.dxf.radius*scale}" fill="none" stroke="{color}" stroke-width="2"/>')
        elif e.dxftype() == 'LWPOLYLINE':
            points = ' '.join(f'{x},{y}' for x, y in [pt(p) for p in e.get_points()])
            result.append(f'<polygon points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        elif e.dxftype() == 'LINE':
            a, b = pt(e.dxf.start), pt(e.dxf.end)
            result.append(f'<path d="M {a[0]} {a[1]} L {b[0]} {b[1]}" fill="none" stroke="{color}" stroke-width="2"/>')
        elif e.dxftype() == 'ARC':
            start, end = e.dxf.start_angle, e.dxf.end_angle
            delta = (end-start) % 360
            points = [pt((e.dxf.center.x+e.dxf.radius*math.cos(math.radians(start+delta*i/32)),
                          e.dxf.center.y+e.dxf.radius*math.sin(math.radians(start+delta*i/32)))) for i in range(33)]
            result.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="2"/>')
    return ''.join(result)


def diagram(part, new_dxf, zones, center, diameter, check, target):
    b, axis, uv = frame(part['shape'])
    w, h = (b['size'][i] for i in uv)
    scale = min(290/w, 230/h)
    content = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="460" viewBox="0 0 800 460">',
               '<rect width="800" height="460" fill="white"/>',
               '<g font-family="sans-serif" fill="#162b3c">',
               f'<text x="25" y="30" font-size="22">{part["id"]} | {w:g} x {h:g} x 1.5 mm</text>',
               '<text x="25" y="58">Original / BEFORE</text><text x="420" y="58">R9-ANODIZING-01 / AFTER</text>']
    for x, path in [(35,part['old']['dxf']), (430,new_dxf)]:
        for z in zones:
            x0,y0,x1,y1 = z['rectangle_uv_mm']
            x0,y0,x1,y1=max(0,x0),max(0,y0),min(w,x1),min(h,y1)
            if x1>x0 and y1>y0:
                content.append(f'<rect x="{x+x0*scale}" y="{85+(h-y1)*scale}" width="{(x1-x0)*scale}" height="{(y1-y0)*scale}" fill="#eab663" opacity=".30"/>')
        content.append(svg_entities(path,(x,85),scale,h))
        content.append(f'<text x="{x}" y="{105+h*scale}" font-size="12">(0,0) lower-left; U right, V up</text>')
    content += [f'<text x="25" y="355">New hole: diameter {diameter:g}; center U={center[0]:g}, V={center[1]:g} mm</text>',
                f'<text x="25" y="380">Nearest plate-edge ligament: {check["edge_ligament_mm"]:.2f} mm (hole edge to plate edge)</text>',
                '<text x="25" y="405">Amber: protected neighbor/contact projections; red: dedicated hanging hole.</text>',
                '<text x="25" y="430">Actual delivered DXF geometry; see manifest for export and case coordinates / clearances.</text></g></svg>']
    target.write_text('\n'.join(content)+'\n')


def deterministic_zip(target, paths, root):
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(paths):
            info=zipfile.ZipInfo(p.relative_to(root).as_posix(),date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,p.read_bytes())


def build(out):
    config = json.loads((ROOT/'parameters.json').read_text())
    parts, inputs, params = source_parts()
    require(len(parts)==13 and set(config['centers_uv_mm'])=={p['id'] for p in parts}, '13-part coverage failed')
    for folder in ('step','dxf','reference-stl','review'):
        (out/folder).mkdir(parents=True,exist_ok=True)
    io.REVISION=config['revision']
    records=[]
    for part in parts:
        name=part['id']; shape=part['shape']; center=config['centers_uv_mm'][name]; diameter=config['diameter_mm']
        baseline=cq.importers.importStep(str(part['old']['step'])).val()
        require(symmetric_difference(shape,baseline)<TOL, f'{name}: regenerated source differs from original STEP')
        b,axis,uv=frame(shape)
        require(symmetric_difference(shape,local_to_world(dxf_shape(part['old']['dxf']),b,uv))<TOL, f'{name}: original DXF mismatch')
        zones=keepouts(part,params)
        revised=shape.cut(hole_tool(shape,center,diameter)).clean()
        check=validate_change(shape,revised,center,diameter,zones,config['minimum_edge_ligament_mm'])
        stem=f'7u40-r9a-{name}-qty1-mm'
        new={k:out/folder/f'{stem}.{k}' for k,folder in [('step','step'),('dxf','dxf'),('stl','reference-stl')]}
        io.step(revised,new['step']); io.stl(revised,new['stl'])
        export_dxf(part['old']['dxf'],new['dxf'],center,diameter)
        back=cq.importers.importStep(str(new['step'])).val()
        require(symmetric_difference(revised,back)<TOL, f'{name}: STEP readback differs')
        flat=local_to_world(dxf_shape(new['dxf']),b,uv)
        require(symmetric_difference(back,flat)<TOL, f'{name}: STEP/DXF readback differs')
        circles=ezdxf.readfile(new['dxf']).modelspace().query('CIRCLE[layer=="HANGING"]')
        require(len(circles)==1 and abs(circles[0].dxf.radius-diameter/2)<TOL,'hanging hole count/diameter')
        check['stl']=io.inspect_stl(new['stl'],revised)
        check['step_dxf_symmetric_difference_mm3']=symmetric_difference(back,flat)
        xyz=list(b['min'])
        for i,v in zip(uv,center):xyz[i]+=v
        xyz[axis]+=0.75
        case_xyz=xyz
        if 'case_matrix' in part:
            local=[part['case_origin_u']+center[0],center[1],0.75,1]
            case_xyz=[sum(v*x for v,x in zip(row,local)) for row in part['case_matrix'][:3]]
        record=dict(id=name,quantity=1,dimensions_mm=[b['size'][i] for i in uv]+[1.5],
                    hole_center_uv_mm=center,hole_center_exported_step_mm=xyz,hole_center_case_mm=case_xyz,diameter_mm=diameter,
                    flat_axes_in_exported_step=uv,thickness_axis_in_exported_step=axis,origin_exported_step_mm=b['min'],keepouts=zones,checks=check,
                    old_files=[file_record(p) for p in part['old'].values()],
                    new_files=[dict(path=p.relative_to(out).as_posix(),sha256=io.digest(p),bytes=p.stat().st_size) for p in new.values()],
                    mapping=[dict(old=part['old'][k].relative_to(REPO).as_posix() if k in part['old'] else None,
                                  new=p.relative_to(out).as_posix(),format=k) for k,p in new.items()])
        diagram(part,new['dxf'],zones,center,diameter,check,out/'review'/f'{name}.svg')
        records.append(record)
        print(name, 'PASS', 'ligament',round(check['edge_ligament_mm'],3),flush=True)
    inputs += [ROOT/'parameters.json',ROOT/'build.py']
    original_inputs=sorted({p for item in parts for p in item['old'].values()} | {p for p in inputs if p.suffix == '.zip'} | {FIT/'order-prep/order-plan.json'})
    for p in original_inputs:
        relative=p.relative_to(REPO).as_posix()
        pinned=subprocess.run(['git','show',f'{config["original_order_commit"]}:{relative}'],cwd=REPO,capture_output=True,check=True).stdout
        require(p.read_bytes()==pinned,f'original order input changed: {relative}')
    plan = json.loads((FIT/'order-prep/order-plan.json').read_text())
    package_members=[]
    with zipfile.ZipFile(REPO/'public/downloads/candidate/fit-test-order-pack-DRAFT.zip') as package:
        for attachment in plan['attachments']:
            payload=package.read(attachment['file'])
            require(hashlib.sha256(payload).hexdigest()==attachment['sha256'], 'original attachment digest mismatch')
            require(len(payload)==attachment['bytes'], 'original attachment size mismatch')
            package_members.append(attachment)
    manifest=dict(revision=config['revision'],original_order_commit=config['original_order_commit'],
                  implementation_base=config['implementation_base'],units='mm',material='A5052',finish='black anodized',
                  production_approved=False,order_uploaded=False,parts=records,
                  original_order_package_members=package_members,
                  inputs=[file_record(p) for p in sorted(set(inputs))],
                  original_inputs_verified_against_pinned_commit=[file_record(p) for p in original_inputs],
                  environment=dict(python=platform.python_version(),cadquery=cq.__version__,ezdxf=ezdxf.__version__),
                  limitations=['Nominal CAD verification, no physical manufacturing/strength/fit guarantee.',
                               'Hardware is the repository provisional envelope; actual washer and tool selection remains unverified.',
                               'No supplier upload, order modification or manufacturing approval.'])
    io.write_json(out/'manifest.json',manifest)
    with (out/'replacement-map.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator="\n");writer.writerow(['part','quantity','old_file','old_sha256','new_file','new_sha256'])
        for row in records:
            for m in row['mapping']:
                old=next((x['sha256'] for x in row['old_files'] if x['path']==m['old']),'REFERENCE ONLY')
                new=next(x['sha256'] for x in row['new_files'] if x['path']==m['new'])
                writer.writerow([row['id'],1,m['old'] or 'new reference STL',old,m['new'],new])
    (out/'NOTICE.txt').write_text('R9-ANODIZING-01: 13 aluminum plates, quantity 1 each.\nSTEP and DXF are paired descriptions of the SAME 13 items. Units mm, A5052 t1.5 black anodized.\nOne dedicated diameter 4 mm hanging hole per plate. Original functional holes/slots remain.\nReference STL files are not the aluminum manufacturing inputs. PA12 order unchanged.\nNo manufacturing approval or supplier upload is implied. See manifest.json and review diagrams.\n')
    deterministic_zip(out/'r9-anodizing-01-aluminum-13-NOT-APPROVED.zip',
                      list((out/'step').glob('*'))+list((out/'dxf').glob('*'))+[out/'NOTICE.txt',out/'replacement-map.csv',out/'manifest.json'],out)
    deterministic_zip(out/'r9-anodizing-01-review.zip',list((out/'review').glob('*'))+list((out/'reference-stl').glob('*'))+[out/'manifest.json'],out)
    io.write_json(out/'checksums.json',dict(files=[dict(path=p.relative_to(out).as_posix(),sha256=io.digest(p),bytes=p.stat().st_size)
                  for p in sorted(out.rglob('*')) if p.is_file() and p.name!='checksums.json']))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'out')
    args=parser.parse_args()
    build(args.out.resolve())
