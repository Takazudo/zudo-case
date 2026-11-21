"""Exact component, bearing-surface and paired-fastener checks for R11."""
from .core import P, T, box, bounds, disk, slot, world
from .lid import validate_lid
from .review_inner_ears import review_inner_ears, localized_outer_lap_contacts
from .review_lid_locators import review_lid_locators


def validate_all(parts, body_meta, lid_meta):
    ids={p['id']:p for p in parts}
    bb={p['id']:bounds(p['shape']) for p in parts}
    intersections=[]; tested=0
    for i,a in enumerate(parts):
        for b in parts[i+1:]:
            ba,bc=bb[a['id']],bb[b['id']]
            if any(min(ba[k+3],bc[k+3])-max(ba[k],bc[k])<=1e-5 for k in range(3)):continue
            tested+=1
            v=a['shape'].intersect(b['shape']).Volume()
            if v>1e-5:intersections.append(dict(a=a['id'],b=b['id'],volume_mm3=v))
    # The new inside contacts cannot stand in for an absent outside lap.
    # Both tests are local to the actual screw and its stated stack plane.
    laps=localized_outer_lap_contacts(parts,body_meta)
    inner_review=review_inner_ears(parts,body_meta,lid_meta)
    locator_review=review_lid_locators(parts,body_meta,lid_meta)
    bearing=inner_review['load_paths']['bearing_contacts']
    nylon=[p for p in parts if p['cat'] in ('corner','span')]
    brackets=[p for p in parts if p['cat']=='brackets']
    slots=body_meta['hole_table']
    slot_checks=[]
    for r in slots:
        if r['angle'] is None:continue
        du,dv=r['inward']
        # The nearest endpoint stays at its former global position, including
        # the proposed datum of each newly added/relocated slot.
        oldnear=[r['u']-du*r['old_length']/2,r['v']-dv*r['old_length']/2]
        newnear=[r['uc']-du*r['length']/2,r['vc']-dv*r['length']/2]
        error=max(abs(a-b) for a,b in zip(oldnear,newnear))
        slot_checks.append(dict(id=r['id'],endpoint_error_mm=error,extension_mm=r['length']-r['old_length']))
    removed_holes=[]
    for r in body_meta['removed_center_slots']:
        probe=world(slot(r['uc'],r['vc'],r['length'],r['width'],-T,0,r['angle']),r['face'])
        occupied=ids['panel-'+r['face']]['shape'].intersect(probe).Volume()
        removed_holes.append(dict(face=r['face'],kind='removed_center_slot',uv=[r['uc'],r['vc']],
                                  expected_filled_volume_mm3=probe.Volume(),filled_volume_mm3=occupied))
    for r in body_meta['removed_hanging_holes']:
        probe=world(disk(*r['uv'],-T,0,r['diameter_mm']/2),r['face'])
        occupied=ids['panel-'+r['face']]['shape'].intersect(probe).Volume()
        removed_holes.append(dict(face=r['face'],kind='removed_hanging_hole',uv=r['uv'],
                                  expected_filled_volume_mm3=probe.Volume(),filled_volume_mm3=occupied))
    fences=[]
    for f in ('left','right'):
        # This material was absent while the centre L bracket needed a relief.
        probe=world(box(-8,8,T+1,T+P['locators']['panel_edge_gap']+4,-2.6,-1.6),f)
        occupied=ids['body-bottom-'+f]['shape'].intersect(probe).Volume()
        fences.append(dict(face=f,expected_volume_mm3=probe.Volume(),occupied_volume_mm3=occupied))
    lid=validate_lid([p for p in parts if p['cat'].startswith('lid')],lid_meta)
    expected=P['expected_counts']
    rail_holes=[r for r in slots if r['kind']=='rail']
    stacks=body_meta['hardware_stacks']
    counts=dict(new_components=len(parts),body_screw_sites=len(stacks),body_slots=len(slot_checks),
                body_round_rail_holes=len(rail_holes),body_brackets=len(brackets),body_nylon_parts=len(nylon),
                lid_nylon_parts=sum(p['cat']=='lidFrame' for p in parts),
                body_thin_nuts=sum(abs(r['nut_height_mm']-P['hardware']['thin_nut_height'])<1e-6 for r in stacks),
                body_other_nuts=sum(abs(r['nut_height_mm']-P['hardware']['nut_height'])<1e-6 for r in stacks),
                loose_washers=sum(p.get('role')=='washer' for p in parts),
                body_lap_pairs=len(laps),body_bearing_contacts=len(bearing),
                lid_plate_bolt_holes=len(lid_meta['plate_holes_xy']),
                dedicated_hanging_holes=sum(r['kind']=='hang' for r in slots)+int(bool(lid_meta.get('hanging_hole'))),
                all_sheet_holes=len(slots)+len(lid_meta['plate_holes_xy'])+int(bool(lid_meta.get('hanging_hole'))))
    checks=dict(
        every_component_valid_single_solid=all(p['shape'].isValid() and len(p['shape'].Solids())==1 for p in parts),
        no_component_positive_overlap=not intersections,
        all_expected_component_and_hole_counts_match=all(counts[k]==expected[k] for k in counts),
        all_16_body_lap_pairs_contact=len(laps)==16 and all(r['gap_mm']<1e-6 and r['contact_area_mm2']>1 for r in laps),
        all_expected_body_bearing_contacts_present=len(bearing)==expected['body_bearing_contacts'] and all(r['total_contact_area_mm2']>1 for r in bearing),
        integral_inside_ears_and_r11_03_delta_pass=inner_review['passed'],
        four_sided_lid_locators_and_straight_lift_pass=locator_review['passed'],
        all_40_slots_extend_5mm_one_way=len(slot_checks)==40 and all(r['endpoint_error_mm']<1e-8 and r['extension_mm']==5 for r in slot_checks),
        ten_original_rail_holes_remain_round=len(rail_holes)==10 and all(r['angle'] is None and r['width']==5.5 for r in rail_holes),
        four_center_slots_and_five_body_hanging_holes_filled=len(removed_holes)==9 and all(abs(r['filled_volume_mm3']-r['expected_filled_volume_mm3'])<1e-6 for r in removed_holes),
        both_side_center_locating_fences_restored=all(abs(r['occupied_volume_mm3']-r['expected_volume_mm3'])<1e-6 for r in fences),
        lid_checks_pass=lid['passed'])
    return dict(passed=all(checks.values()),checks=checks,component_count=len(parts),
                counts=counts,expected_counts=expected,
                pairwise_intersection_tests=tested,collisions=intersections,body_lap_contacts=laps,
                body_fastener_bearing_contacts=bearing,slot_extension_checks=slot_checks,lid=lid,
                removed_hole_fill_checks=removed_holes,center_locating_fence_checks=fences,
                inner_ear_review=inner_review,lid_locator_review=locator_review,
                scope='Nominal CAD geometry only. Original frame clearance is a separate reference check; no physical, load, fatigue or print-process test.')
