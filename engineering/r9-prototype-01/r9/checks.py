"""Nominal R9 assembly checkpoint. A flagged result never grants manufacturing approval."""
from __future__ import annotations

import json
from pathlib import Path

import cadquery as cq

from .common import export_step, sha256_file
from .types import BuildContext, Part

TOLERANCE_MM3 = 1e-3


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _shape(path: Path) -> cq.Shape:
    return cq.importers.importStep(str(path)).val()


def _bounds(shape: cq.Shape) -> tuple[tuple[float, float], ...]:
    b = shape.BoundingBox()
    return ((b.xmin, b.xmax), (b.ymin, b.ymax), (b.zmin, b.zmax))


def _bbox_gap(a: cq.Shape, b: cq.Shape) -> float:
    aa, bb = _bounds(a), _bounds(b)
    return max(max(y[0] - x[1], x[0] - y[1]) for x, y in zip(aa, bb))


def _volume(a: cq.Shape, b: cq.Shape) -> float:
    if _bbox_gap(a, b) > 0:
        return 0.0
    return a.intersect(b).Volume()


def _file(ctx: BuildContext, category: str, part_id: str, qty: int = 1) -> Path:
    return ctx.out / category / f'{part_id.lower()}-qty{qty}-mm.step'


def build(ctx: BuildContext) -> list[Part]:
    out = ctx.out / 'assembly'
    out.mkdir(parents=True, exist_ok=True)
    lid_manifest = _read(ctx.out / 'pa12/lid/manifest.json')
    guard_manifest = _read(ctx.out / 'pa12/guards/t1p2/manifest.json')
    body_manifest = _read(ctx.out / 'hardware-envelopes/body-manifest.json')
    slots = _read(ctx.out / 'aluminum/slot-checks.json')
    lid = {pid: _shape(_file(ctx, 'aluminum', pid) if pid.endswith('PLATE') else
                       ctx.out / 'pa12/lid' / f'{pid.lower()}-qty1-mm.step')
           for pid in lid_manifest['parts']}
    # Guard files are one geometry per mirrored pair. Reflect across X to
    # account for the second physical instance without duplicating exports.
    guards = {}
    for item in guard_manifest['parts']:
        pid = item['id']
        original = _shape(ctx.root / item['files'][0]['path'])
        guards[pid + '-A'] = original
        if item['quantity'] == 2:
            guards[pid + '-B'] = original.mirror('YZ')
    top_guards = {k: v for k, v in guards.items() if '-TOP-' in k}
    # Body plate STEP files are flat local patterns. Their localToAssembly
    # transforms are in the body manifest; omit them from this BREP scope.
    lid_frame = {k: v for k, v in lid.items() if 'FRAME' in k}
    contacts = []
    for lid_id, lid_shape in lid_frame.items():
        for guard_id, guard_shape in top_guards.items():
            volume = _volume(lid_shape, guard_shape)
            if volume > TOLERANCE_MM3:
                contacts.append({'a': lid_id, 'b': guard_id, 'volumeMm3': round(volume, 6)})
    seat_z = float(ctx.value('lid', 'frame_seat_z'))
    frozen_top = float(ctx.value('guards', 'top_edge_seated_guard_z'))
    actual_top = max(s.BoundingBox().zmax for s in top_guards.values())
    locator_x_gap = -float(ctx.value('lid', 'locator_x_overhang_from_opening'))
    lift_first = None
    # 1 mm increments, including the seated state. Stop at first physical
    # overlap; a positive clearance throughout remains a nominal CAD result.
    for rise in range(151):
        for lid_id, shape in lid_frame.items():
            moved = shape.translate((0, 0, rise))
            for guard_id, guard in top_guards.items():
                volume = _volume(moved, guard)
                if volume > TOLERANCE_MM3:
                    lift_first = {'riseMm': rise, 'a': lid_id, 'b': guard_id,
                                  'volumeMm3': round(volume, 6)}
                    break
            if lift_first:
                break
        if lift_first:
            break
    plate = lid['7U40-R9-LID-PLATE']
    knob_top = (float(ctx.value('body', 'case_height')) +
                float(ctx.value('lid', 'module_panel_thickness')) +
                float(ctx.value('lid', 'knob_envelope_height')))
    knob_gap = plate.BoundingBox().zmin - knob_top
    m3_bore_count = 8  # Four frame quarters, two assembly bores each.
    bearing = slots['failures']['bearingCoverage']
    guard_band = slots['failures']['guardContact']
    tool = slots['failures']['toolAccess']
    flags = []
    if contacts:
        flags.append('Lid frame intersects top guards at nominal seated position; resolve geometry before fit coupon.')
    if lift_first:
        flags.append('Nominal lid lift path intersects top guards; see firstContact.')
    if seat_z < frozen_top:
        flags.append('R8 frame seat 92.7 mm is below frozen guard top 93.4 mm; actual guard solid top differs from frozen interface. Resolve seat datum and fit.')
    if bearing:
        flags.append(f'{len(bearing)} wall slots fail bearing coverage with provisional 10 mm washer; OD >= {slots["criteria"]["bearingRequiredOdMm"]} mm is a candidate, not selected.')
    if guard_band:
        flags.append(f'{len(guard_band)} slots enter the nominal guard contact band.')
    if tool:
        flags.append(f'{len(tool)} M5 exterior tool envelopes conflict in S2 nominal check.')
    if knob_gap <= 0:
        flags.append('Provisional knob envelope reaches lid plate underside.')
    # Four isolated quarter frames carry the nominal two X-station straps at
    # front and rear edges. The continuous aluminum plate spans their seams;
    # no frame member is under the plate at each station across the full Y loop.
    strap_x = float(ctx.value('guards', 'top_edge_guard_exterior_x')) * 0.30
    band = [{'stationXmm': x, 'widthMm': 20.0,
             'contactSurfaces': ['front PA12 quarter-frame edge', 'rear PA12 quarter-frame edge',
                                 'aluminum lid plate between frame corners'],
             'continuousPA12Support': False} for x in (-strap_x, strap_x)]
    flags.append('Two schematic straps contact PA12 at front/rear edges, but span the aluminum plate between corner frames; plate-only contact and deflection remain unresolved.')
    not_validated = [
        'Full solid-pair collision coverage for transformed body plates, brackets, PCB, rail and hardware instances; local plate STEP patterns are not assembly transforms.',
        'Lift path against body, PCB, rail and knob solids; only actual top-guard solids checked.',
        'M3 driver cone/tool access: eight plate/frame bores are modeled, but driver and screw heads are not specified.',
        'M5 physical tool access and washer fit; S2 exterior envelope is nominal only.',
        'Adhesive retention, physical fit, strap load strength, module knob/cable envelope and transport testing.',
    ]
    report = {
        'schema': 'zudo-case-r9-assembly-checks-v1', 'revision': ctx.revision,
        'model': ctx.model, 'units': 'mm', 'status': 'unapproved_prototype',
        'intersectionThresholdMm3': TOLERANCE_MM3,
        'staticInterference': {'scope': 'lid PA12 frame versus main t1p2 top guards',
                               'contacts': contacts, 'passes': not contacts},
        'clearancesMm': {'locatorToGuardNominalX': round(locator_x_gap, 6),
                         'lidPlateUndersideToProvisionalKnobTop': round(knob_gap, 6),
                         'frameSeatToActualTopGuard': round(seat_z - actual_top, 6),
                         'frameSeatToFrozenGuardTop': round(seat_z - frozen_top, 6),
                         'locatorToRailEnvelope': None, 'locatorToHighestBracket': None},
        'liftPath': {'axis': '+Z', 'startMm': 0, 'endMm': 150, 'stepMm': 1,
                     'scope': 'PA12 lid frame versus main top guards',
                     'firstContact': lift_first, 'passes': lift_first is None},
        'access': {'m3PlateFrameBoreCount': m3_bore_count,
                   'm3DriverValidated': False, 'm5S2NominalToolFailures': tool,
                   'm5PhysicalValidated': False},
        'straps': {'status': 'schematic only', 'widthMm': 20, 'stations': band,
                   'plateOnlyContactExcluded': False},
        'slotsVsRealGuards': {'s2GuardBandFailures': guard_band,
                              'actualTopGuardBottomZMm': round(min(s.BoundingBox().zmin for s in top_guards.values()), 6),
                              'bearingCoverageFailures': bearing},
        'bodyManifestComponentCount': len(body_manifest['components']),
        'flags': flags, 'not_validated': not_validated,
        'productionApproved': False,
    }
    (out / 'assembly-checks.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    assembly = cq.Compound.makeCompound([*lid.values(), *top_guards.values()])
    assembly_path = out / '7u40-r9-reference-assembly-NOT-APPROVED.step'
    export_step(assembly, assembly_path)
    # Normalize insignificant OCC line-end whitespace for tracked STEP output.
    assembly_path.write_bytes(b'\n'.join(line.rstrip(b' \t') for line in assembly_path.read_bytes().split(b'\n')))
    if assembly_path.stat().st_size >= 25 * 1024 * 1024:
        raise ValueError('reference assembly STEP exceeds 25 MiB')
    (out / 'assembly.json').write_text(json.dumps({
        'revision': ctx.revision, 'model': ctx.model, 'units': 'mm',
        'status': 'partial reference only; unapproved',
        'file': {'path': str(assembly_path.relative_to(ctx.root)),
                 'sha256': sha256_file(assembly_path), 'bytes': assembly_path.stat().st_size},
        'included': ['lid plate', 'four PA12 lid corners', 'main top guards'],
        'excluded': ['body plates', 'PCB detail', 'rail', 'brackets', 'hardware'],
    }, indent=2) + '\n')
    return []
