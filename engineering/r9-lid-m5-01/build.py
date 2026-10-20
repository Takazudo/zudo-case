#!/usr/bin/env python3
"""Regenerate the isolated 7U40 R9-LID-M5-01 lid fastener candidate (issue #123).

  uv run --locked --project ../r9-prototype-01 python build.py [--out DIR]

Reads R9-FITFIX-01 and R9-ANODIZING-01 inputs read-only. Writes only to --out.
Not a manufacturing approval: production_approved stays false.
"""
from __future__ import annotations
import argparse, csv, json, math, os, platform, sys, time, zipfile
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import cadquery as cq
import ezdxf
import numpy as np
from lidm5.geometry import *
from lidm5.geometry import FIT, lid_parts_m5, nut_envelope, screw_envelope, QUARTERS
from lidm5.coupons import c2_m5, n1_ladder, c2_window
from lidm5.checks import (fastener_checks, unchanged_outside_boss, knob_zones, plate_holes, bore_axes,
                          measure_pocket, anti_rotation, insertion_path)
from fitfix import io
from fitfix.geometry import guard_parts, guard_instances, body_envelopes, clip
from fitfix.reference import load_reference
from fitfix.validation import validate_variant, pairs, overlap

REVISION = 'R9-LID-M5-01'
PREFIX = '7u40-r9m5-'
ANOD = ROOT.parent / 'r9-anodizing-01'
REPO = ROOT.parents[1]


def rel(path):
    return os.path.relpath(path, REPO).replace(os.sep, '/')


def r4(x):
    return round(float(x), 4)


def dxf_plate(path, width, height, m5_holes, hang_holes=(), radius=0.):
    """Outline + M5 functional holes + anodizing hang hole on separate layers."""
    old = ezdxf.options.write_fixed_meta_data_for_testing
    ezdxf.options.write_fixed_meta_data_for_testing = True
    try:
        doc = ezdxf.new('R2010'); doc.units = ezdxf.units.MM; msp = doc.modelspace()
        for layer in ('OUTLINE', 'M5_HOLES', 'HANG_HOLE_D4'):
            doc.layers.new(layer)
        if radius:
            r = radius; bulge = math.tan(math.pi / 8)
            contour = [(r, 0, 0, 0, 0), (width - r, 0, 0, 0, bulge), (width, r, 0, 0, 0),
                       (width, height - r, 0, 0, bulge), (width - r, height, 0, 0, 0),
                       (r, height, 0, 0, bulge), (0, height - r, 0, 0, 0), (0, r, 0, 0, bulge)]
        else:
            contour = [(0, 0), (width, 0), (width, height), (0, height)]
        msp.add_lwpolyline(contour, close=True, dxfattribs={'layer': 'OUTLINE'})
        for x, y, d in m5_holes:
            msp.add_circle((x, y), d / 2, dxfattribs={'layer': 'M5_HOLES'})
        for x, y, d in hang_holes:
            msp.add_circle((x, y), d / 2, dxfattribs={'layer': 'HANG_HOLE_D4'})
        doc.classes.add_required_classes(doc.dxfversion)
        doc.classes.classes = OrderedDict(sorted(doc.classes.classes.items()))
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)
    finally:
        ezdxf.options.write_fixed_meta_data_for_testing = old


def dxf_readback(path, step_path, layers):
    """DXF circles/outline must equal the reimported STEP holes and plan size."""
    doc = ezdxf.readfile(path)
    if doc.audit().has_errors or doc.units != 4:
        raise AssertionError(f'DXF audit failed: {path}')
    msp = doc.modelspace()
    outline = msp.query('LWPOLYLINE[layer=="OUTLINE"]')[0]
    pts = np.array([p[:2] for p in outline.get_points()])
    size = pts.max(axis=0) - pts.min(axis=0)
    shape = cq.importers.importStep(str(step_path)).val()
    bb = io.bounds(shape)
    if abs(size[0] - bb['size'][0]) > 1e-6 or abs(size[1] - bb['size'][1]) > 1e-6:
        raise AssertionError(f'DXF outline differs from STEP: {path}')
    step_holes = sorted((r4(x - bb['min'][0]), r4(y - bb['min'][1]), r4(d)) for (x, y), d in plate_holes(shape).items())
    dxf_holes = sorted((r4(c.dxf.center.x), r4(c.dxf.center.y), r4(2 * c.dxf.radius)) for c in msp.query('CIRCLE'))
    if step_holes != dxf_holes:
        raise AssertionError(f'DXF holes differ from STEP: {path}: {dxf_holes} vs {step_holes}')
    by_layer = {layer: sorted(r4(2 * c.dxf.radius) for c in msp.query(f'CIRCLE[layer=="{layer}"]')) for layer in layers}
    return dict(outline_mm=[r4(size[0]), r4(size[1])], holes=[list(h) for h in dxf_holes], diameters_by_layer=by_layer, matches_step=True)


def zip_subset(path, files, root):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(set(files)):
            info = zipfile.ZipInfo(f.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())


def guard_identity(b, g, comparison_wall):
    """Regenerated guards must equal the R9-FITFIX-01 STEP solids: body/guards stay as ordered.

    STL bytes are platform-tessellated, so the comparison is on the B-rep:
    the symmetric difference with the saved STEP must vanish.
    """
    rows = []
    for tag, gg in (('t1p2', g), ('t1p0', replace(g, wall=comparison_wall))):
        for p in guard_parts(b, gg, tag):
            old = FIT / 'out' / f'pa12/{tag}/guards' / f'7u40-r9f-{p.id}-qty{p.quantity}-mm.step'
            saved = cq.importers.importStep(str(old)).val()
            diff = p.shape.cut(saved).Volume() + saved.cut(p.shape).Volume()
            rows.append(dict(path=rel(old), sha256=io.digest(old), symmetric_difference_mm3=diff, identical=diff < 1e-4))
    return dict(method='regenerated solid vs saved R9-FITFIX-01 STEP, symmetric difference volume', files=rows,
                passed=all(r['identical'] for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=ROOT / 'out')
    ap.add_argument('--reference-root', type=Path, default=ROOT.parent / 'r6-body')
    args = ap.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    io.REVISION = REVISION
    started = time.monotonic()
    P = load(); D = P['data']
    b, g, l, m = P['body'], P['guard'], P['lid'], P['m5']
    src = D['nut_source']; asm = D['assumptions']
    nut = dict(af_min=src['across_flats_min'], af_max=D['design_envelope']['nut_across_flats'],
               af_photo=src['product_photo_across_flats'], h_min=src['height_min'], h_max=D['design_envelope']['nut_height'],
               pitch=src['pitch'], corner_ratio=asm['nut_corner_ratio_e_over_s'])
    r6, entries = load_reference(args.reference_root)
    hardware = [Part(e['id'], r6.SHAPES[e['id']], group='reference-hardware') for e in entries
                if e['id'] in r6.SHAPES and e.get('role') != 'aluminumPanel']
    rails = []
    for e in entries:
        if e.get('role') == 'rail':
            v = np.array(e['positions']).reshape(-1, 3); lo = v.min(axis=0); hi = v.max(axis=0)
            rails.append(Part(e['id'], box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]), group='reference-rail-envelope'))
    assert len(rails) == 6
    knobs = knob_zones(b, l, rails)
    fixed = body_envelopes(b)

    manifest, meshchecks, bom = [], [], []
    def export(part, folder, variant, order_quantity=None, stl=True):
        folder = out / folder; folder.mkdir(parents=True, exist_ok=True)
        stem = f'{PREFIX}{part.id}-qty{part.quantity}-mm'; st = folder / (stem + '.step'); sl = folder / (stem + '.stl')
        io.step(part.shape, st)
        reimport = cq.importers.importStep(str(st)).val()
        assert reimport.isValid() and len(reimport.Solids()) == 1
        assert abs(reimport.Volume() - part.shape.Volume()) < max(.001, part.shape.Volume() * 1e-8)
        files = [st]
        if stl:
            io.stl(part.shape, sl); meshchecks.append(dict(path=sl.relative_to(out).as_posix(), **io.inspect_stl(sl, part.shape)))
            files.append(sl)
        row = dict(part=part.id, variant=variant, material=part.material, group=part.group,
                   per_set_quantity=part.quantity, order_quantity=part.quantity if order_quantity is None else order_quantity,
                   dimensions_mm=[r4(x) for x in io.bounds(part.shape)['size']], volume_mm3=r4(part.shape.Volume()),
                   stl=sl.relative_to(out).as_posix() if stl else '', step=st.relative_to(out).as_posix(), status='candidate-not-approved')
        bom.append(row); return row

    scene_src = json.loads((FIT / 'out/scene.json').read_text())
    scene = dict(revision=REVISION, status='UNAPPROVED / M5 lid fastener candidate', body=vars(b),
                 reference=scene_src['reference'], variants={}, coupons={},
                 m5summary=f'M5: 通し穴φ{m.through_hole} / 六角対辺{m.pocket_af} / 有効深さ{m.pocket_effective_depth} / 天板端→軸{m.plate_edge_to_axis}')
    report = dict(scope='Nominal CAD and file readback only. No torque, strength, creep, fit, transport or physical test.',
                  revision=REVISION, base_revision=D['base_revision'], production_approved=False,
                  variants={}, coupons={}, physical_results=None)
    dims = dict(revision=REVISION, source=src, design_envelope=D['design_envelope'], adopted=D['m5'],
                adopted_reasons=D['adopted_reasons'], assumptions=asm, m3_before={k: l[k] for k in ('assembly_hole', 'nut_af', 'boss_depth', 'nut_roof', 'screw_inset')},
                variants={})
    mapping = []

    def fastener_meshes(sites, roof_z, ptop, length=10):
        meshes = []
        for s in sites:
            env = screw_envelope(s['x'], s['y'], ptop, length, asm['head_diameter_max'], asm['head_height_max'], asm['screw_major_diameter'])
            meshes.append(io.mesh_record(env['head'].fuse(env['shank']).clean(), f"m5-screw-L{length}-assumed-{s['frame']}-{s['site']}", 'fastener'))
            meshes.append(io.mesh_record(nut_envelope(s['x'], s['y'], roof_z, nut['af_max'], nut['h_max'], s['hex_angle']), f"m5-nut-envelope-{s['frame']}-{s['site']}", 'nut'))
        return meshes

    for tag, gg in (('t1p2', g), ('t1p0', replace(g, wall=P['comparison_wall']))):
        print('Build', tag, flush=True)
        guards = guard_instances(guard_parts(b, gg, tag))
        parts, holes, sites = lid_parts_m5(b, gg, l, m)
        i = interface(b, gg, l)
        frames = [p for p in parts if p.group == 'lid']; plate = next(p for p in parts if p.group == 'lid-metal')
        for p in frames:
            export(p, f'pa12/{tag}/lid', tag)
        r = export(plate, f'aluminum/{tag}', tag)
        w, d, t = i['lid_plate_mm']
        dx = out / f'aluminum/{tag}/{PREFIX}lid-plate-qty1-mm.dxf'
        dxf_plate(dx, w, d, [(x + w / 2, y + d / 2, m.through_hole) for x, y in holes], radius=l['plate_corner_radius'])
        r['dxf'] = dx.relative_to(out).as_posix()
        r['dxf_readback'] = dxf_readback(dx, out / r['step'], ('M5_HOLES', 'HANG_HOLE_D4'))
        # Frame bores and plate holes from the generated solids.
        axes = sorted(a for f in frames for a in bore_axes(f.shape, m.through_hole / 2))
        plate_m5 = sorted(k for k, v in plate_holes(plate.shape).items() if abs(v - m.through_hole) < 1e-6)
        alignment = dict(frame_bores=len(axes), plate_holes=len(plate_m5), matched=axes == plate_m5 and len(axes) == 8,
                         axes=[list(a) for a in axes])
        base = validate_variant(b, gg, l, guards, parts, hardware, rails)
        stationary = guards + fixed + hardware + rails
        fchecks = fastener_checks(b, gg, l, m, frames, plate.shape, sites, stationary, knobs, nut, asm)
        knob_lid = pairs(parts, knobs)
        unchanged = unchanged_outside_boss(b, gg, l, m)
        if tag == 't1p2':
            min_wall_t1p2 = min(s['min_wall_true'] for s in fchecks)
        checks_ok = (base['passed'] and alignment['matched'] and unchanged['passed'] and knob_lid['passed'] and
                     all(not s['head_collisions'] and not s['driver_column_collisions'] and not s['nut_envelope_collisions']
                         and s['insertion']['passed'] and s['plate_hole_present']
                         and s['anti_rotation']['max_nut_seated_overlap_mm3'] < 1e-6
                         and s['anti_rotation']['min_sharp']['locks'] and s['anti_rotation']['min_truncated']['locks']
                         and s['effective_depth'] >= nut['h_max'] and s['roof_thickness'] >= 1.5 - TOLM
                         and s['min_wall_true'] >= 1.5 - TOLM and s['head_margin_on_plate'] >= 0
                         and min(abs(a - m.pocket_af) for a in s['across_flats_measured']) < 1e-3
                         for s in fchecks))
        ok_lengths = sorted({(row['length'], row['washer']) for s in fchecks for row in s['screws']
                             if all(any(rr['length'] == row['length'] and rr['washer'] == row['washer'] and rr['passed'] for rr in ss['screws']) for ss in fchecks)})
        report['variants'][tag] = dict(passed=checks_ok, base_fitfix_checks=base, hole_alignment=alignment,
                                       lid_vs_assumed_knob_zones=knob_lid, unchanged_outside_m5_boss=unchanged,
                                       fastener_sites=fchecks, screw_lengths_passing_all_sites=[dict(length=a, washer=w_) for a, w_ in ok_lengths])
        print('Validation', tag, checks_ok, base['failed_checks'], flush=True)
        def summary(key):
            vals = [s[key] for s in fchecks]
            return dict(min=r4(min(vals)), max=r4(max(vals)))
        by_site = {}
        for s in fchecks:
            by_site.setdefault(s['site'], []).append(s)
        dims['variants'][tag] = dict(
            interface={k: (r4(v) if isinstance(v, float) else [r4(x) for x in v] if isinstance(v, list) else v) for k, v in i.items()},
            plate_mm=[r4(x) for x in i['lid_plate_mm']], m5_sites=8, hole_alignment_matched=alignment['matched'],
            by_edge={site: dict(
                frames=[s['frame'] for s in rows],
                across_flats_measured=dict(min=r4(min(min(s['across_flats_measured']) for s in rows)), max=r4(max(max(s['across_flats_measured']) for s in rows))),
                effective_depth=dict(min=r4(min(s['effective_depth'] for s in rows))),
                roof_thickness=dict(min=r4(min(s['roof_thickness'] for s in rows))),
                min_wall_true=dict(min=r4(min(s['min_wall_true'] for s in rows))),
                wall_to_outer_face=dict(min=r4(min(s['wall_to_outer_face'] for s in rows))),
                wall_to_interior=dict(min=r4(min(s['wall_to_interior'] for s in rows))),
                boss_bottom_z=r4(rows[0]['boss_bottom_z']),
                plate_edge_ligament=dict(min=r4(min(s['plate_edge_ligament'] for s in rows))),
                plate_edge_to_axis=dict(min=r4(min(s['plate_edge_to_axis'] for s in rows))),
                head_margin_on_plate=dict(min=r4(min(s['head_margin_on_plate'] for s in rows))),
                head_clearance_to_frames=dict(min=r4(min(s['head_clearance_to_frames'] for s in rows))),
                axis_xy_first=[r4(x) for x in rows[0]['axis_xy']],
            ) for site, rows in by_site.items()},
            lid_frame_volume_cm3=r4(sum(p.shape.Volume() for p in frames) / 1000),
            screw_lengths_passing_all_sites=report['variants'][tag]['screw_lengths_passing_all_sites'])
        roof_z = fchecks[0]['roof_underside_z']
        scene['variants'][tag] = dict(interface=i, meshes=[io.mesh_record(p.shape, p.id, 'guards') for p in guards] +
                                      [io.mesh_record(p.shape, p.id, 'lid' if p.group == 'lid' else 'lidMetal') for p in parts] +
                                      fastener_meshes(sites, roof_z, i['plate_top_z_mm']))
        io.write_json(out / f'interface-{tag}.json', i)
        # Reference-only assembly: lid parts + fastener envelopes (not order items).
        asm_shapes = [p.shape for p in parts]
        for s in sites:
            env = screw_envelope(s['x'], s['y'], i['plate_top_z_mm'], 10, asm['head_diameter_max'], asm['head_height_max'], asm['screw_major_diameter'])
            asm_shapes += [env['head'], env['shank'], nut_envelope(s['x'], s['y'], roof_z, nut['af_max'], nut['h_max'], s['hex_angle'])]
        io.step(cq.Compound.makeCompound(asm_shapes), out / f'assembly/{tag}-lid-m5-with-assumed-fasteners-REFERENCE.step')
        # Detail views for the preview: real full-lid geometry around one front and one side site.
        for s in (x for x in sites if x['frame'] == 'lid-frame-fr'):
            key = f"LID-{tag.upper()}-{s['site'].upper()}"
            cx, cy = s['x'], s['y']
            win = lambda sh: clip(sh, cx - 16, cx + 16, cy - 16, cy + 16, 60, 140)
            meshes = []
            for p in guards + fixed + frames + [plate]:
                try:
                    piece = win(p.shape)
                except ValueError:
                    continue
                grp = 'guards' if p in guards else 'metal' if p in fixed else 'lid' if p.group == 'lid' else 'lidMetal'
                meshes.append(io.mesh_record(piece, p.id, grp))
            meshes += fastener_meshes([s], roof_z, i['plate_top_z_mm'])
            normal = s['normal']
            scene['coupons'][key] = dict(meshes=meshes, description=f'{tag} 全体フタの{"前辺" if s["site"]=="front" else "側辺"}M5部（表示用切出し）',
                                         section=dict(normal=[abs(normal[1]), abs(normal[0]), 0], constant=-(cx if normal[1] else cy)),
                                         info=f'{key}\n全体フタから切り出した表示\nM5軸 X{cx:.2f} Y{cy:.2f}\nナット受け Z{roof_z:.2f}\nネジ・ナットは仮定包絡')

    # Old -> new map for the lid. Body and guards are unchanged and reused by hash.
    for tag in ('t1p2', 't1p0'):
        for q, _, _ in QUARTERS:
            for ext in ('stl', 'step'):
                old = FIT / 'out' / f'pa12/{tag}/lid/7u40-r9f-lid-frame-{q}-qty1-mm.{ext}'
                mapping.append(dict(change='replaced: M3 bore/nut pocket/boss -> M5', part=f'lid-frame-{q}', variant=tag,
                                    old_path=rel(old), old_sha256=io.digest(old), new_path=f'pa12/{tag}/lid/{PREFIX}lid-frame-{q}-qty1-mm.{ext}'))
        for ext in ('step', 'dxf', 'stl'):
            old = FIT / 'out' / f'aluminum/{tag}/7u40-r9f-lid-plate-qty1-mm.{ext}'
            mapping.append(dict(change='replaced: 8x M3 3.4 holes -> 8x M5 5.5 holes at new positions' if ext != 'stl' else 'retired: plate STL is not an aluminum order file; new STEP/DXF/STL generated',
                                part='lid-plate', variant=tag, old_path=rel(old), old_sha256=io.digest(old),
                                new_path=f'aluminum/{tag}/{PREFIX}lid-plate-qty1-mm.{ext}'))

    print('Coupons', flush=True)
    c2 = c2_m5(b, g, l, m, P['hang_hole'])
    guards12 = guard_instances(guard_parts(b, g, 't1p2'))
    for c in c2:
        rows, meshes = [], []
        for p in c['parts']:
            r = export(p, 'coupons/c2-m5', 'coupon')
            if p.group == 'coupon-metal':
                bb = io.bounds(p.shape)
                hx, hy = c['hang_hole']['x'], c['hang_hole']['y']
                dx = out / 'coupons/c2-m5' / f'{PREFIX}{p.id}-qty1-mm.dxf'
                dxf_plate(dx, bb['size'][0], bb['size'][1], [(c['site']['x'] - bb['min'][0], c['site']['y'] - bb['min'][1], m.through_hole)],
                          [(hx - bb['min'][0], hy - bb['min'][1], c['hang_hole']['diameter'])])
                r['dxf'] = dx.relative_to(out).as_posix()
                r['dxf_readback'] = dxf_readback(dx, out / r['step'], ('M5_HOLES', 'HANG_HOLE_D4'))
                r['dxf_origin_assembly_mm'] = [r4(x) for x in bb['min']]
            rows.append(r)
            meshes.append(io.mesh_record(p.shape, p.id, 'lidMetal' if p.group == 'coupon-metal' else 'lid'))
        plate = c['plate']
        frame = c['parts'][0].shape
        roof = measure_pocket(frame, dict(c['site'], frame=c['parts'][0].id), m, c['interface']['plate_bottom_z_mm'])
        for p in c['reuse_parts']:
            meshes.append(io.mesh_record(p.shape, p.id, 'metal' if 'wall' in p.id else 'guards'))
        s = dict(c['site'], frame=c['parts'][0].id)
        meshes += fastener_meshes([s], roof['roof_underside_z'], c['interface']['plate_top_z_mm'])
        # Hang hole vs frame contact footprint and boss, measured on solids.
        hang = cq.Solid.makeCylinder(c['hang_hole']['diameter'] / 2, 60, cq.Vector(c['hang_hole']['x'], c['hang_hole']['y'], 80))
        hang_clear = hang.distance(frame)
        check = pairs([c['parts'][0], Part('c2-m5-plate', plate), *c['reuse_parts']])
        ar = anti_rotation(frame, s, roof['roof_underside_z'], nut, m)
        ins = insertion_path(frame, s, roof['roof_underside_z'], roof['boss_bottom_z'], nut, 12)
        ok = (check['passed'] and hang_clear >= 1.5 and ar['min_truncated']['locks'] and ins['passed']
              and abs(roof['effective_depth'] - m.pocket_effective_depth) < 1e-3 and abs(roof['min_wall_true'] - min_wall_t1p2) < 1e-3)
        report['coupons'][c['id']] = dict(passed=ok, pairs=check, pocket=roof, anti_rotation=ar, insertion=ins,
                                          hang_hole=dict(**c['hang_hole'], clearance_to_frame_projection_mm=hang_clear,
                                                         m5_hole_xy=[c['site']['x'], c['site']['y']]),
                                          same_as_full_lid=dict(min_wall=min_wall_t1p2, effective_depth=m.pocket_effective_depth))
        serial = {k: v for k, v in c.items() if k not in ('parts', 'reuse_parts', 'plate', 'site')}
        serial['parts'] = rows
        serial['reuse'] = [dict(part=p.id, source=rel(FIT / 'out/coupons/c2-01' / f'7u40-r9f-{p.id}-qty1-mm.step'),
                                sha256=io.digest(FIT / 'out/coupons/c2-01' / f'7u40-r9f-{p.id}-qty1-mm.step')) for p in c['reuse_parts']]
        io.write_json(out / 'coupons/c2-m5' / f"{c['id'].lower()}-manifest.json", serial)
        scene['coupons'][c['id']] = dict(meshes=meshes, description=c['purpose'],
                                         section=dict(normal=[1, 0, 0], constant=-c['site']['x']),
                                         info=f"{c['id']}\n位置決めすきま {c['locator_clearance_mm']} mm\nM5通し穴φ{m.through_hole} / 六角{m.pocket_af}\n天板はC2-M5-01の1枚を共用\n壁・ガードはR9-FITFIX-01のC2を再利用\n現物結果は未記入")
        print('Coupon', c['id'], ok, flush=True)
        n = int(c['id'][-2:])
        for ext in ('stl', 'step'):
            old = FIT / 'out' / f'coupons/c2-0{n}/7u40-r9f-c2-0{n}-frame-qty1-mm.{ext}'
            mapping.append(dict(change='replaced: C2 frame with M5 boss', part=f'c2-m5-{n:02d}-frame', variant='coupon', old_path=rel(old),
                                old_sha256=io.digest(old), new_path=f'coupons/c2-m5/{PREFIX}c2-m5-{n:02d}-frame-qty1-mm.{ext}'))
    for old in (FIT / 'out/coupons/c2-01/7u40-r9f-c2-01-plate-qty1-mm.step', FIT / 'out/coupons/c2-01/7u40-r9f-c2-01-plate-qty1-mm.dxf',
                ANOD / 'out/step/7u40-r9a-c2-01-plate-qty1-mm.step', ANOD / 'out/dxf/7u40-r9a-c2-01-plate-qty1-mm.dxf'):
        mapping.append(dict(change='replaced: C2 plate M3 3.4 -> M5 5.5 at the new axis; R9-ANODIZING-01 hang hole d4 kept at the same UV',
                            part='c2-m5-plate', variant='coupon', old_path=rel(old), old_sha256=io.digest(old),
                            new_path=f'coupons/c2-m5/{PREFIX}c2-m5-plate-qty1-mm.{old.suffix[1:]}'))
    for pid in ('wall', 'guard'):
        for ext in ('step', 'stl'):
            old = FIT / 'out/coupons/c2-01' / f'7u40-r9f-c2-01-{pid}-qty1-mm.{ext}'
            mapping.append(dict(change='unchanged: reuse the ordered C2 piece', part=f'c2-01-{pid}', variant='coupon',
                                old_path=rel(old), old_sha256=io.digest(old), new_path=''))
    n1, centers, top = n1_ladder(m, P['ladder'])
    export(n1, 'coupons/n1', 'coupon')
    n1_rows = []
    for c in centers:
        s = dict(x=c['x'], y=c['y'], hex_angle=0.0, normal=(0, -1), frame='n1', site=f"af{c['af']}")
        mm = replace(m, pocket_af=c['af'])
        pocket = measure_pocket(n1.shape, s, mm, top)
        ar = anti_rotation(n1.shape, s, pocket['roof_underside_z'], nut, mm)
        n1_rows.append(dict(af=c['af'], pocket=pocket, anti_rotation=ar))
    report['coupons']['N1'] = dict(passed=all(abs(r['pocket']['effective_depth'] - m.pocket_effective_depth) < 1e-3 for r in n1_rows),
                                   pockets=n1_rows, purpose='Physical across-flats ladder 8.3/8.4/8.5; only the AF differs from the lid definition')
    io.write_json(out / 'coupons/n1/manifest.json', dict(id='N1', ladder=P['ladder'], centers=centers, roof_contact_z=top,
                                                        purpose=report['coupons']['N1']['purpose'], physical_results=None))
    n1m = [io.mesh_record(n1.shape, n1.id, 'lid')]
    for c in centers:
        n1m.append(io.mesh_record(nut_envelope(c['x'], 0, top - m.nut_roof, nut['af_max'], nut['h_max'], 0.0), f"m5-nut-envelope-af{c['af']}", 'nut'))
    scene['coupons']['N1'] = dict(meshes=n1m, description='M5ナット収納ラダー（対辺8.3/8.4/8.5）', section=dict(normal=[0, 1, 0], constant=0),
                                  info='N1\n六角対辺 8.3 / 8.4 / 8.5\n通し穴・屋根・深さはフタと同じ\nナットの挿入感と回り止めを比較\n現物結果は未記入')

    report['guard_and_body_identity'] = guard_identity(b, g, P['comparison_wall'])
    report['passed'] = (all(v['passed'] for v in report['variants'].values()) and all(v['passed'] for v in report['coupons'].values())
                        and report['guard_and_body_identity']['passed'])
    report['mesh_step_checks'] = meshchecks
    report['unverified'] = [
        'Actual screw head diameter/height, washer and length: variable assumptions in parameters.json',
        'Actual nut corner shape and printed pocket size after MJF; N1 ladder is for this',
        'Tightening torque, PA12 creep under the lock nut, nylon insert prevailing torque',
        'Physical seat/locator fit of the new frames; strap routing over the protruding heads',
        'Continuous motion between sampled insertion/lift positions',
        'Knob envelope (rise30/panel2/knob25) is the provisional R9 assumption, not every module',
        'Manufacturing tolerances, warpage, anodizing, L-bracket field check (#102), guard adhesive (separate issues)']
    io.write_json(out / 'validation.json', report)

    # Dimension table (Japanese) from measured values.
    io.write_json(out / 'dimensions.json', dims)
    md = dimension_markdown(dims, report)
    (out / 'DIMENSIONS.md').write_text(md, encoding='utf-8')

    # Hardware BOM rows: assumptions, not generated parts.
    lengths = report['variants']['t1p2']['screw_lengths_passing_all_sites']
    for tag in ('t1p2', 't1p0'):
        bom.append(dict(part='m5-screw', variant=tag, material='M5 screw (ZB40 family). Length candidate below', group='hardware', per_set_quantity=8, order_quantity=8,
                        dimensions_mm=None, volume_mm3=None, stl='', step='', status='assumption-not-identified',
                        note='Recommended 10 mm without washer; see dimensions.json screw_lengths_passing_all_sites'))
        bom.append(dict(part='m5-nylon-lock-nut', variant=tag, material='M5 nylon insert lock nut, s 7.68-8.0, h 4.7-5.0 (table)', group='hardware',
                        per_set_quantity=8, order_quantity=8, dimensions_mm=None, volume_mm3=None, stl='', step='', status='catalogue-table-not-measured'))
    bom.append(dict(part='m5-screw+nut (C2-M5 + N1 trials)', variant='coupon', material='M5 screw + M5 nylon lock nut', group='hardware',
                    per_set_quantity=4, order_quantity=4, dimensions_mm=None, volume_mm3=None, stl='', step='', status='assumption-not-identified',
                    note='1 set for the shared C2-M5 plate, 3 nuts for N1'))
    for tag in ('t1p2', 't1p0'):
        for name in (f'7u40-{tag}-pa12-NOT-APPROVED.zip', f'7u40-{tag}-aluminum-NOT-APPROVED.zip'):
            path = FIT / 'out' / name
            bom.append(dict(part=f'R9-FITFIX-01 {name}', variant=tag, material='unchanged body plates + guards (reuse). Its lid frames/plate are superseded by this revision',
                            group='unchanged-reference', per_set_quantity=None, order_quantity=0, dimensions_mm=None, volume_mm3=None,
                            stl='', step=rel(path), status=f'sha256 {io.digest(path)}'))
    io.write_json(out / 'BOM.json', bom)
    with (out / 'BOM.csv').open('w', newline='', encoding='utf-8-sig') as f:
        wr = csv.DictWriter(f, fieldnames=['variant', 'part', 'material', 'group', 'per_set_quantity', 'order_quantity', 'volume_mm3', 'stl', 'step', 'dxf', 'status', 'note'], extrasaction='ignore')
        wr.writeheader(); wr.writerows(bom)

    notice = out / 'NOT-APPROVED.txt'
    notice.write_text('UNAPPROVED PROTOTYPE R9-LID-M5-01 - mm - each STL/STEP is one part; use the order table.\n'
                      'Only the lid frames and lid plates change. Body plates and guards stay R9-FITFIX-01.\n'
                      'M5 screw length/head and nut are assumptions; see DIMENSIONS.md. Not a manufacturing approval.\n', encoding='utf-8')
    def order_table(name, rows):
        path = out / 'order-tables' / name; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='', encoding='utf-8-sig') as f:
            wr = csv.DictWriter(f, fieldnames=['part', 'material', 'order_quantity', 'stl', 'step', 'dxf'], extrasaction='ignore')
            wr.writeheader(); wr.writerows(rows)
        return path
    for tag in ('t1p2', 't1p0'):
        rows = [r for r in bom if r['variant'] == tag and r['group'] == 'lid']
        table = order_table(f'lid-m5-pa12-{tag}.csv', rows)
        zip_subset(out / f'7u40-{tag}-lid-m5-pa12-NOT-APPROVED.zip', [out / r['stl'] for r in rows] + [table, notice, out / 'DIMENSIONS.md'], out)
        rows = [r for r in bom if r['variant'] == tag and r['group'] == 'lid-metal']
        table = order_table(f'lid-m5-aluminum-{tag}.csv', rows)
        zip_subset(out / f'7u40-{tag}-lid-m5-aluminum-NOT-APPROVED.zip', [out / r[k] for r in rows for k in ('step', 'dxf')] + [table, notice, out / 'DIMENSIONS.md'], out)
    rows = [r for r in bom if r['variant'] == 'coupon' and r['group'] == 'coupon']
    table = order_table('m5-coupons-pa12.csv', rows)
    zip_subset(out / 'm5-coupons-pa12-NOT-APPROVED.zip', [out / r['stl'] for r in rows] + [table, notice, out / 'DIMENSIONS.md'], out)
    rows = [r for r in bom if r['variant'] == 'coupon' and r['group'] == 'coupon-metal']
    table = order_table('m5-coupons-metal.csv', rows)
    zip_subset(out / 'm5-coupons-metal-NOT-APPROVED.zip', [out / r[k] for r in rows for k in ('step', 'dxf')] + [table, notice, out / 'DIMENSIONS.md'], out)

    for row in mapping:
        if row['new_path']:
            row['new_sha256'] = io.digest(out / row['new_path'])
            row['new_path'] = f"{rel(ROOT)}/out/{row['new_path']}"  # canonical, also for --out
        else:
            row['new_path'], row['new_sha256'] = row['old_path'], row['old_sha256']
    io.write_json(out / 'old-to-new.json', mapping)
    with (out / 'old-to-new.csv').open('w', newline='', encoding='utf-8') as f:
        wr = csv.DictWriter(f, fieldnames=['change', 'part', 'variant', 'old_path', 'old_sha256', 'new_path', 'new_sha256'])
        wr.writeheader(); wr.writerows(mapping)

    from lidm5.preview import make_preview
    make_preview(scene, FIT / 'vendor/three-bundle.js', out / 'preview.html')

    env = {'python': sys.version.split()[0], 'cadquery': cq.__version__, 'ezdxf': ezdxf.__version__, 'numpy': np.__version__,
           'platform': platform.platform(), 'repository_python_cq_range_compatible': sys.version_info[:2] == (3, 12) and cq.__version__.startswith('2.7.'),
           'seconds': round(time.monotonic() - started, 2)}
    io.write_json(out / 'environment.json', env)
    files = []
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name not in ('outputs-manifest.json', 'environment.json'):
            files.append(dict(path=path.relative_to(out).as_posix(), sha256=io.digest(path), bytes=path.stat().st_size))
    inputs = []
    for source in sorted([ROOT / 'build.py', ROOT / 'parameters.json', *ROOT.glob('lidm5/*.py'),
                          FIT / 'parameters.json', *FIT.glob('fitfix/*.py'), FIT / 'vendor/three-bundle.js', FIT / 'out/scene.json',
                          ANOD / 'parameters.json', ROOT.parent / 'r9-prototype-01/uv.lock']):
        inputs.append(dict(path=os.path.relpath(source, ROOT).replace(os.sep, '/'), sha256=io.digest(source)))
    io.write_json(out / 'outputs-manifest.json', dict(revision=REVISION, base_revision=D['base_revision'],
                                                      implementation_base_commit=D['implementation_base_commit'],
                                                      production_approved=False, inputs=inputs, files=files))
    print('DONE', len(files), 'files; passed=', report['passed'], 'seconds=', env['seconds'], flush=True)
    if not report['passed']:
        raise SystemExit(1)


TOLM = 1e-3


def dimension_markdown(dims, report):
    a, s, e = dims['adopted'], dims['source'], dims['design_envelope']
    m3 = dims['m3_before']
    L = []
    L.append('# R9-LID-M5-01 寸法表（生成値）\n')
    L.append('`build.py` が生成形状から計測して書き出す。手で編集しない。公称CADの値で、現物の実測・締付試験ではない。\n')
    L.append('## ナット資料値（ユーザー添付の商品寸法表 M5行）\n')
    L.append('| 項目 | 値 mm |\n|---|---:|')
    L.append(f"| ピッチ | {s['pitch']} |\n| 全高 h | {s['height_min']}〜{s['height_max']} |\n| 金属六角部の高さ m | min {s['metal_hex_height_min']} |\n| 対辺 s | {s['across_flats_min']}〜{s['across_flats_max']} |\n| 商品写真の表示 | {s['product_photo_across_flats']} |\n| 設計包絡 | 対辺{e['nut_across_flats']}・全高{e['nut_height']} |\n")
    L.append('## 採用寸法（M3から変更）\n')
    L.append('| 項目 | 旧M3 | 開始候補 | 採用 |\n|---|---:|---:|---:|')
    L.append(f"| 通し穴 | φ{m3['assembly_hole']} | φ5.5 | φ{a['through_hole']} |")
    L.append(f"| 六角収納部の対辺 | {m3['nut_af']} | 8.5 | **{a['pocket_af']}** |")
    L.append(f"| 収納部の有効深さ | {m3['boss_depth'] - m3['nut_roof']:.1f} | 5.5 | {a['pocket_effective_depth']} |")
    L.append(f"| ナット上側の樹脂（屋根） | {m3['nut_roof']} | 1.5以上 | {a['nut_roof']} |")
    L.append(f"| ボス深さ | {m3['boss_depth']} | 7.0以上 | {a['pocket_effective_depth'] + a['nut_roof']:.1f} |")
    L.append(f"| 収納部周囲の最小樹脂（目標） | — | 1.5以上 | {a['nut_wall_min']} |")
    L.append(f"| 天板端→ネジ軸 | 3.9 | — | {a['plate_edge_to_axis']} |")
    L.append(f"| 組立箇所 | 8 | 8 | 8 |\n")
    L.append('## 生成形状からの計測値\n')
    L.append('| 案 | 辺 | 対辺 実測 | 有効深さ | 屋根 | 最小肉厚（頂点含む） | 外面側の肉 | 天板穴の残り幅 | 天板端→軸 | 頭φ10仮定の天板上余裕 | 頭と枠のすきま | ボス下面Z |')
    L.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for tag, v in dims['variants'].items():
        for site, r in v['by_edge'].items():
            L.append(f"| {tag} | {'前後辺' if site == 'front' else '左右辺'}（{len(r['frames'])}箇所） | {r['across_flats_measured']['min']:.3f} | {r['effective_depth']['min']:.3f} | {r['roof_thickness']['min']:.3f} | {r['min_wall_true']['min']:.3f} | {r['wall_to_outer_face']['min']:.3f} | {r['plate_edge_ligament']['min']:.3f} | {r['plate_edge_to_axis']['min']:.3f} | {r['head_margin_on_plate']['min']:.3f} | {r['head_clearance_to_frames']['min']:.3f} | {r['boss_bottom_z']:.2f} |")
    L.append('')
    L.append('## 回り止め（公称）\n')
    L.append('| 案 | ナット | 角の半径 | 収納部の内接半径 | 30°回転で干渉 | 回転の遊び |\n|---|---|---:|---:|---|---:|')
    for tag, v in report['variants'].items():
        ar = v['fastener_sites'][0]['anti_rotation']
        for key, label in (('min_sharp', '最小対辺7.68・角が鋭い'), ('min_truncated', '最小対辺7.68・角を面取り(e/s=1.099)'), ('photo_truncated', '写真7.83・角を面取り')):
            r = ar[key]
            free = '—' if r['free_rotation_deg'] is None else f"{r['free_rotation_deg']:.1f}°"
            L.append(f"| {tag} | {label} | {r['corner_radius']:.3f} | {r['pocket_inscribed_radius']:.3f} | {'する' if r['locks'] else 'しない'} | {free} |")
    L.append('')
    L.append('## ネジ長さ候補（仮定: 頭φ10×高さ5、座金なし／座金t1.0）\n')
    L.append('| 長さ | 座金 | ナイロン部の先へ出る量（h4.7〜5.0） | 全8箇所で成立 |\n|---:|---|---:|---|')
    ok = {(x['length'], x['washer']) for x in report['variants']['t1p2']['screw_lengths_passing_all_sites']}
    for row in report['variants']['t1p2']['fastener_sites'][0]['screws']:
        pr = row['protrusion_beyond_nut_min_max']
        L.append(f"| {row['length']} | {'あり' if row['washer'] else 'なし'} | {min(pr.values()):.2f}〜{max(pr.values()):.2f} | {'はい' if (row['length'], row['washer']) in ok else 'いいえ'} |")
    L.append('\n成立条件: ナイロン部の先へ2ピッチ（1.6mm）以上出る、ネジ先端がガード・本体・金具・レール・仮定ノブ域に入らない。')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    main()
