#!/usr/bin/env python3
"""Sample a constructive, hardware-free sliding sequence for the R11 body.

This reads the current exact body CAD; it does not alter geometry. The report
checks positive-volume intersections at stated translation samples. It is not
a continuous sweep proof, a tolerance study, a tool-access qualification, or a
physical assembly trial. Nominal bearing-face contact is allowed.

Prepare each wall's middle spans separately, form the two side subassemblies,
insert the front/back and floor into the left side, then close with the right
side along X. Bolts, nuts, loose washers, L brackets, feet, rails and lid are
absent during these motions and must be installed afterward.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LINEAR_TOLERANCE = 1e-6
VOLUME_TOLERANCE = 1e-5


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: digest(ROOT / name) for name in (
        'parameters.json', 'revision/core.py', 'revision/body.py',
        'revision/assembly_path_check.py')}


def translation_samples(moving, fixed, boxes, axis, sign, start, step):
    """Regular samples, denser near closure, plus bounding-box entry events."""
    distances = {0.0, float(start)}
    distances.update(min(start, k * step) for k in range(math.ceil(start / step) + 1))
    distances.update(d for d in (.05, .1, .2, .25, .5, .75, 1, 1.5, 2, 3, 4, 5,
                                  7.5, 10, 12, 15, 20) if d <= start)
    for a in moving:
        for b in fixed:
            ba, bb = boxes[a], boxes[b]
            # First/last possible overlap along the motion axis. This does
            # not claim to detect every internal feature's critical event.
            for event in ((bb[axis + 3] - ba[axis]) / sign,
                          (bb[axis] - ba[axis + 3]) / sign):
                for delta in (-.05, 0.0, .05):
                    value = event + delta
                    if 0 <= value <= start:
                        distances.add(value)
    return sorted({round(d, 7) for d in distances}, reverse=True)


def positive_bbox_overlap(a, b):
    return all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > LINEAR_TOLERANCE
               for k in range(3))


def plan():
    stages = []

    def add(ident, moving, fixed, axis, sign, start, text, context):
        stages.append(dict(id=ident, moving=moving, fixed=fixed,
                           axis=axis, outward_sign=sign, start_distance_mm=start,
                           instruction=text, context=context))

    # These four preparations take place separately on the workbench. Each
    # check is represented in the final assembly datum for easy reproducibility.
    walls = {}
    for face in ('left', 'right', 'front', 'back'):
        panel = 'panel-' + face
        top, bottom = 'body-top-' + face, 'body-bottom-' + face
        add('preload-top-' + face, [top], [panel], 2, 1, 120,
            'Lower the top middle span onto this separate wall panel.',
            'Independent wall subassembly; other walls are not present.')
        add('preload-bottom-' + face, [bottom], [panel, top], 2, -1, 120,
            'Raise the bottom middle span onto the separate wall; floor absent.',
            'Independent wall subassembly; other walls are not present.')
        walls[face] = [panel, top, bottom]

    side_groups = {}
    for face, sx in (('left', -1), ('right', 1)):
        fixed = list(walls[face])
        for sy, end in ((-1, 'front'), (1, 'back')):
            corner = f'body-corner-{sx}-{sy}'
            add(f'corner-onto-{face}-{end}', [corner], list(fixed), 1, sy, 120,
                'Slide the corner onto the side-panel end along Y.',
                'Independent side subassembly; front/back/floor panels absent.')
            fixed.append(corner)
        side_groups[face] = fixed

    fixed = list(side_groups['left'])
    for face in ('front', 'back'):
        add('insert-' + face, list(walls[face]), list(fixed), 0, 1, 260,
            'Slide the prepared wall into the left corners from the open right side.',
            'Right-side subassembly is set aside; floor and all hardware absent.')
        fixed += walls[face]
    add('insert-floor', ['panel-floor'], list(fixed), 0, 1, 260,
        'Slide the floor along X through the open lower channels.',
        'Right-side subassembly and all floor bolts are absent.')
    fixed.append('panel-floor')
    add('close-right-side', side_groups['right'], fixed, 0, 1, 260,
        'Move the right-side subassembly inward along minus X, capturing the free panel ends.',
        'No L brackets, bolts, nuts, washers, rails, feet or lid are present.')
    return stages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step-mm', type=float, default=5,
                        help='Regular translation sampling interval; extra closure/event samples are always included.')
    parser.add_argument('--out', type=Path, default=ROOT / 'out' / 'assembly-path-check.json')
    parser.add_argument('--stage', action='append', default=[],
                        help='Optional stage ID filter for diagnosing an approach; a filtered run is not a complete route pass.')
    args = parser.parse_args()
    if not 0 < args.step_mm <= 10:
        parser.error('--step-mm must be greater than zero and at most 10')
    start_time = time.time()
    before = source_hashes()
    sys.path.insert(0, str(ROOT))
    from revision.body import body_nylon, panel_shape
    from revision.core import FACES, P, bounds, world

    print('Building current body panels and nylon connectors for path inspection…', flush=True)
    items = body_nylon()
    items += [dict(id='panel-' + face, shape=world(panel_shape(face), face)) for face in FACES]
    shapes = {part['id']: part['shape'] for part in items}
    boxes = {ident: bounds(shape) for ident, shape in shapes.items()}
    assert len(shapes) == 17, 'Expected twelve body nylon parts and five sheets'
    stages = plan()
    known_ids = {stage['id'] for stage in stages}
    if set(args.stage) - known_ids:
        parser.error('Unknown stage IDs: ' + ', '.join(sorted(set(args.stage) - known_ids)))
    if args.stage:
        stages = [stage for stage in stages if stage['id'] in args.stage]
    results = []
    total_booleans = total_samples = 0
    for stage in stages:
        axis, sign = stage['axis'], stage['outward_sign']
        distances = translation_samples(stage['moving'], stage['fixed'], boxes,
                                        axis, sign, stage['start_distance_mm'], args.step_mm)
        failures = {}
        count = 0
        for distance in distances:
            vector = [0.0, 0.0, 0.0]
            vector[axis] = sign * distance
            for a in stage['moving']:
                moved_bounds = [v + vector[k % 3] for k, v in enumerate(boxes[a])]
                candidates = [b for b in stage['fixed'] if positive_bbox_overlap(moved_bounds, boxes[b])]
                if not candidates:
                    continue
                moving_shape = shapes[a].translate(tuple(vector))
                for b in candidates:
                    count += 1
                    common = moving_shape.intersect(shapes[b])
                    volume = common.Volume()
                    if volume <= VOLUME_TOLERANCE:
                        continue
                    key = (a, b)
                    failure = failures.setdefault(key, dict(moving=a, fixed=b,
                        first_distance_mm=distance, last_distance_mm=distance,
                        collision_samples=0, maximum_overlap_mm3=0.0,
                        worst_translation_mm=None, worst_overlap_bounds_mm=None))
                    failure['last_distance_mm'] = distance
                    failure['collision_samples'] += 1
                    if volume > failure['maximum_overlap_mm3']:
                        failure.update(maximum_overlap_mm3=volume,
                                       worst_translation_mm=vector,
                                       worst_overlap_bounds_mm=bounds(common))
        total_samples += len(distances)
        total_booleans += count
        result = dict(stage, samples_mm=distances, sample_count=len(distances),
                      exact_intersection_checks=count, passed=not failures,
                      collisions=list(failures.values()))
        results.append(result)
        print(json.dumps(dict(stage=stage['id'], passed=result['passed'],
                              samples=len(distances), checks=count,
                              collision_pairs=len(failures))), flush=True)
    after = source_hashes()
    unchanged = before == after
    report = dict(revision=P['revision'], production_approved=False,
                  method='Sampled exact BRep intersections along stated independent translations',
                  complete_route=not args.stage,
                  passed=not args.stage and unchanged and all(row['passed'] for row in results),
                  selected_stages_passed=all(row['passed'] for row in results),
                  source_unchanged_during_run=unchanged,
                  input_hashes=before, final_input_hashes=after,
                  regular_sampling_mm=args.step_mm,
                  linear_tolerance_mm=LINEAR_TOLERANCE,
                  positive_volume_threshold_mm3=VOLUME_TOLERANCE,
                  body_parts=sorted(shapes), stages=results,
                  sampled_positions=total_samples,
                  exact_intersection_checks=total_booleans,
                  elapsed_seconds=time.time()-start_time,
                  excluded_during_sliding=['L brackets', 'bolts', 'nuts', 'loose washers',
                                           'feet', 'original rail/PCB unit', 'lid'],
                  subsequent_operations=[
                      'Place L brackets from the still-open interior after all panels are seated.',
                      'Fit lower wall nuts before the paired floor nuts; retain prescribed thin nuts.',
                      'Fit remaining body hardware and the independent rail unit afterward.'],
                  limits=[
                      'Discrete positions, not a continuous swept-volume proof between samples.',
                      'Nominal geometry only; zero-volume bearing-face contact is allowed.',
                      'No printed tolerance, coating, friction, elastic deformation, holding-jig or hand/tool model.',
                      'Post-closure bracket/tool insertion and tightening are not path-qualified by this report.',
                      'A complete route pass requires every listed independent preparation and closure stage.'])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], complete_route=report['complete_route'],
                          source_unchanged=unchanged, stages=len(results),
                          sampled_positions=total_samples, exact_intersections=total_booleans,
                          elapsed_seconds=report['elapsed_seconds'], output=str(args.out))), flush=True)
    return 0 if report['selected_stages_passed'] and unchanged else 1


if __name__ == '__main__':
    raise SystemExit(main())
