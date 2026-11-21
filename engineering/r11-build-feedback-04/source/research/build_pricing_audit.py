"""Rebuild the evidence-only JLC pricing audit; never changes CAD or places orders."""
from pathlib import Path
import hashlib
import json
import math

HERE = Path(__file__).resolve().parent
REV = HERE.parent
OLD = REV / 'reference/r11-03-baseline/parts-manifest.json'
NEW = REV / 'out/parts-manifest.json'
HISTORICAL = REV / 'reference/r10-cart-2026-10-26.json'

for required in (OLD, NEW, HISTORICAL):
    if not required.is_file():
        raise SystemExit(f'Required saved input is missing: {required.relative_to(REV)}. '
                         'Finish the R11-04 export before generating the pricing report.')

sources = [
    dict(id='S1', title='3D Printing Special Charges Case', url='https://jlc3dp.com/help/article/3d-printing-special-charges-case', updated='2026-09-04', verified='2026-11-22', refs=['turn190675618view0'], claim='Longest bounding-box dimension >=250 mm: indicative surcharge starts at USD 8 per part, plus 1-2 business days. Complex or special-shaped structures have a separate indicative surcharge. Engineer review determines final charges.'),
    dict(id='S2', title='PA12-HP Nylon', url='https://jlc3dp.com/help/article/pa12-hp-nylon', updated='2026-07-30', verified='2026-11-22', refs=['turn190675618view1'], claim='MJF PA12 advertised from USD 1.00. Listed wall thickness 1 mm; maximum size 370 x 276 x 360 mm. The page does not give a volume or envelope threshold guaranteeing the starting price.'),
    dict(id='S3', title="What's the price of your 3D printing parts", url="https://jlc3dp.com/help/article/what's-the-price-of-your-3d-printing-parts", updated='2023-12-20', verified='2026-11-22', refs=['turn190675618view2'], claim='Part volume, process, material and quantity affect pricing. Model upload is the documented route to an automatic quote; no numeric minimum-price formula is provided.'),
    dict(id='S4', title='Online 3D Printing Instant Quote', url='https://jlc3dp.com/3d-printing-quote', updated=None, refs=['turn904054663view0'], claim='The public signed-out calculator offers model upload and then material/quantity selection. No R11 model was uploaded during this audit.'),
    dict(id='S5', title='JLC3DP Launches New 3D Printing Pricing Strategy', url='https://jlc3dp.com/news/drastic-material-price-cuts-and-adjusted-post-processing-service-fees', updated='2025-12-26', refs=['turn130814167view0'], claim='Article header says Dec 26, 2025; body states an Aug 13, 2025 effective announcement of MJF-PA12 USD 0.275/g excluding tax. Historical announced rate only, not a current all-in quote or a complete pricing formula.'),
    dict(id='S6', title='Pricing Updates for Selected Materials and Finishing Services', url='https://jlc3dp.com/news/materials-finishing-pricing-update-july2026', updated='2026-07-24', refs=['turn130814167view1'], claim='This update lists PAC-HP Nylon and PA12-CF Plastic, not MJF PA12-HP. It directs customers to the live calculator for current material and finishing prices.'),
]

denial = ('This uploads a nonpublic CAD/STL artifact to JLC3DP, an external supplier, '
          'which is sensitive data egress; the user authorized a pricing audit but did '
          'not explicitly authorize sending this specific file to that destination, '
          'and the action creates an external copy beyond read-only inspection.')

old = json.loads(OLD.read_text())
old_parts = {p['id']: p for p in old['parts'] if p['category'] == 'pa12'}
new = json.loads(NEW.read_text())
current = {p['id']: p for p in new['parts'] if p['category'] == 'pa12'}
assert old['revision'] == 'R11-BUILD-FEEDBACK-03', old['revision']
assert new['revision'] == 'R11-BUILD-FEEDBACK-04', new['revision']
assert len(current) == 20 and set(current) == set(old_parts), 'Expected the same 20 PA12 part IDs.'
basis = 'Exported R11-BUILD-FEEDBACK-04 exact CAD dimensions and material volumes, compared with the saved R11-03 baseline; all 20 STL file hashes verified against the export manifest.'
old_washer = next(p for p in old['parts'] if p['id'] == 'round-washer')
new_washer = next(p for p in new['parts'] if p['id'] == 'round-washer')

rows = []
for part_id, p in current.items():
    dims = p['dimensions_mm']
    stl = REV / 'out' / p['files']['stl']['path']
    if not stl.is_file():
        raise SystemExit(f'Required STL is missing: {stl.relative_to(REV)}')
    stl_hash = hashlib.sha256(stl.read_bytes()).hexdigest()
    assert stl_hash == p['files']['stl']['sha256'], f'Export hash mismatch: {part_id}'
    rows.append(dict(
        id=part_id, quantity=p['quantity'], dimensions_mm=[round(x, 8) for x in dims],
        longest_mm=max(dims), material_volume_cm3=p['volume_mm3'] / 1000,
        prior_r11_03_volume_cm3=old_parts[part_id]['volume_mm3'] / 1000,
        envelope_volume_cm3=math.prod(dims) / 1000,
        material_volume_change_cm3=(p['volume_mm3']-old_parts[part_id]['volume_mm3'])/1000,
        published_250mm_size_screen='pass' if max(dims) < 250 else 'fail',
        starting_price_tier='unconfirmed', price=None, currency=None,
        material='PA12-HP Nylon', technology='MJF', finish='Dyeing-Dyed Black',
        intended_stl_path=str(stl.relative_to(REV)),
        file_exists=True,
        stl_sha256=stl_hash,
        uploaded=False,
    ))

historic = json.loads(HISTORICAL.read_text())
historical = [dict(id=p['part_id'], dimensions_mm=p['dimensions_mm'], displayed_price_jpy=p['displayed_price_jpy'], quantity=p['quantity'])
              for p in historic['parts'] if '/pa12/' in p['file']]
body_sum = sum(r['material_volume_cm3'] for r in rows if r['id'].startswith('body-'))
lid_sum = sum(r['material_volume_cm3'] for r in rows if r['id'].startswith('lid-'))
body_old_sum = sum(r['prior_r11_03_volume_cm3'] for r in rows if r['id'].startswith('body-'))
lid_old_sum = sum(r['prior_r11_03_volume_cm3'] for r in rows if r['id'].startswith('lid-'))
body_changed = sum(abs(r['material_volume_change_cm3']) > 1e-6 for r in rows if r['id'].startswith('body-'))
lid_changed = sum(abs(r['material_volume_change_cm3']) > 1e-6 for r in rows if r['id'].startswith('lid-'))
longest = max(r['longest_mm'] for r in rows)
size_pass_count = sum(r['published_250mm_size_screen'] == 'pass' for r in rows)
assert old_washer['quantity'] == new_washer['quantity'] == 64, 'R11-04 must retain the 64 R11-03 loose washers.'
expected_changed = {'lid-corner-fl', 'lid-corner-fr', 'lid-corner-bl', 'lid-corner-br', 'lid-middle-left', 'lid-middle-right'}
actual_changed = {r['id'] for r in rows if abs(r['material_volume_change_cm3']) > 1e-6}
assert body_changed == 0 and lid_changed == 6 and actual_changed == expected_changed, 'Expected only four lid corners and two side lid middle spans to gain material.'
assert all(r['material_volume_change_cm3'] > 0 for r in rows if r['id'] in expected_changed), 'The side locator revision must add material to its six intended pieces.'
corner_id = 'body-corner--1--1'
corner_row = next(r for r in rows if r['id'] == corner_id)
inputs = [dict(path=str(p.relative_to(REV)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
          for p in (OLD, NEW, HISTORICAL)]

data = dict(
    audit_date='2026-11-22', revision='R11-BUILD-FEEDBACK-04', production_approved=False,
    scope='All 20 supplier PA12 parts; loose ASA washers and purchased rubber feet are outside the JLC PA12 quote.',
    geometry_basis=basis, inputs=inputs,
    rules=dict(large_part_surcharge_longest_axis_mm=250, comparison='>=',
               indicated_surcharge_start_usd=8, starting_pa12_price_usd=1,
               starting_price_volume_threshold_cm3=None, starting_price_envelope_threshold_cm3=None,
               starting_price_dimension_threshold_mm=None, full_formula_published=False,
               note='Pass at <250 mm is not proof of the USD 1 starting tier. Shape-review surcharges remain unassessed.'),
    parts=rows,
    totals=dict(pa12_parts=len(rows), material_volume_cm3=body_sum+lid_sum,
                body_material_volume_cm3=body_sum, lid_material_volume_cm3=lid_sum,
                prior_r11_03_material_volume_cm3=body_old_sum+lid_old_sum,
                material_volume_change_cm3=body_sum+lid_sum-body_old_sum-lid_old_sum,
                price=None, currency=None, tax=None, shipping=None),
    revision_changes=dict(body_pieces_with_material_change=body_changed, lid_pieces_with_material_change=lid_changed,
                          changed_part_ids=sorted(actual_changed),
                          added_locator_edges=['left', 'right'], retained_locator_edges=['front', 'back'],
                          locator_engagement_mm=12, locator_thickness_mm=2, locator_clearance_mm=.7,
                          new_side_hardware_reliefs=4, all_locator_hardware_reliefs=8,
                          hardware_or_washer_quantity_change=0),
    carried_forward_body=dict(bracketed_integral_inside_seats=32, existing_top_integral_inside_seats=8,
                              top_inside_loose_washers_retained=8,
                              loose_inside_washers_removed_in_r11_03=32),
    automatic_quote=dict(status='not_authorized',
                         prior_attempt_status='blocked_by_automatic_approval_review_before_upload',
                         supplier_upload_authorized=False, r11_04_upload_attempted=False,
                         attempted_file='R11-01 body-top-right.stl', destination=sources[3]['url'],
                         exact_rejection_reason=denial, uploaded_count=0, order_submitted=False,
                         cart_saved=False, message_sent=False, payment_made=False,
                         next_permission='Upload the 20 R11-04 PA12 STL files listed in parts to JLC3DP solely for automatic price calculation using MJF PA12-HP Nylon, Dyed Black, quantity 1 each; no order, supplier message or payment.'),
    historical_r10=dict(source=str(HISTORICAL.relative_to(REV)), date='2026-10-26',
                       price_kind='displayed_cart_line_prices_not_final_supplier_reviewed_quote',
                       settings=historic['settings']['pa12'], parts=historical,
                       body_total_jpy=2872, lid_total_jpy=5068, total_jpy=7940,
                       tax_status='unknown', shipping_included=False),
    excluded=dict(round_washer=dict(dimensions_mm=new_washer['dimensions_mm'], bore_mm=5, material='home-print black ASA',
                                   volume_cm3=new_washer['volume_mm3']/1000,
                                   r11_03_quantity=old_washer['quantity'], r11_04_quantity=new_washer['quantity'],
                                   body_outside_quantity=40, lid_wall_quantity=16, body_inside_quantity=8, price=None,
                                   note='Quantities and geometry taken from the saved baseline and current export manifests.'),
                  feet=dict(quantity=4, material='purchased rubber feet / preview guide',
                            price=None, note='The current feet are guidance geometry, not one of the 20 exported PA12 pieces.')),
    sources=sources,
)
(HERE/'jlc-pa12-pricing-audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

fmt = lambda ds: ' × '.join(f'{v:g}' for v in ds)
lines = [
    '# R11-04 PA12 pricing audit', '',
    '**Status: no current R11 supplier quote. All prices remain unknown (`null`).**', '',
    f'Checked 2026-11-22. {size_pass_count} of {len(rows)} nylon parts pass the published 250 mm large-part size screen. '
    'That screen does **not** establish eligibility for the advertised USD 1 starting price. '
    'No numeric volume, envelope-volume, or dimension rule guaranteeing that starting tier '
    'was found in the official material page, special-charge rules, price FAQ, or pricing updates reviewed here.', '',
    '## Evidence and limits', '',
    '- [S1 — Current special charges](%s), updated 2026-09-04: a longest bounding-box axis of 250 mm or more incurs an indicative surcharge starting at USD 8 per part, with 1–2 additional business days. Complex structures have a separate review-based surcharge. All fees and lead times remain subject to engineer review.' % sources[0]['url'],
    '- [S2 — PA12-HP Nylon](%s), updated 2026-07-30: MJF starts at USD 1, with listed wall thickness 1 mm and a maximum build size of 370 × 276 × 360 mm. The maximum build size is a manufacturing limit, not a low-price tier.' % sources[1]['url'],
    '- [S3 — Price FAQ](%s): volume, process, material, and quantity affect price. The official advice is to upload the actual model for a quote. It publishes no complete formula or guaranteed minimum-price eligibility limits.' % sources[2]['url'],
    '- [S5 — Historical rate announcement](%s) announced USD 0.275/g for MJF-PA12, excluding tax, effective 2025-08-13. Its page header is 2025-12-26. This historical rate is not used to invent a current quote, finishing charge, density assumption, minimum, or total.' % sources[4]['url'],
    '- [S6 — July 2026 update](%s) changes PAC-HP Nylon and PA12-CF Plastic among other products. Those are different materials/processes from MJF PA12-HP; the reductions cannot be applied to this case.' % sources[5]['url'], '',
    '## Every supplier PA12 part', '',
    basis, '',
    'Envelope volume below is simply the product of the three bounding-box dimensions. '
    '**It is not an asserted JLC billing metric.** Material volume is the exact CAD solid volume. '
    'All parts are quantity 1, MJF PA12-HP Nylon with Dyed Black finishing for the intended quote. '
    'All 20 also fit within the published maximum build size.', '',
    '| Part | Dimensions (mm) | Material (cm³) | R11-03 material (cm³) | Envelope (cm³) | 250 mm screen | USD 1 tier / price |',
    '|---|---|---:|---:|---:|---|---|',
]
for r in rows:
    lines.append(f"| `{r['id']}` | {fmt(r['dimensions_mm'])} | {r['material_volume_cm3']:.4f} | {r['prior_r11_03_volume_cm3']:.4f} | {r['envelope_volume_cm3']:.3f} | {r['published_250mm_size_screen'].upper()} | Unconfirmed / unknown |")
lines += [
    '', f'Total material: **{body_sum+lid_sum:.4f} cm³** ({body_sum:.4f} cm³ body; {lid_sum:.4f} cm³ lid). '
    f'The longest parts are {longest:g} mm, leaving {250-longest:g} mm below the published 250 mm surcharge trigger.', '',
    '### Material effect of the four-sided lid guides', '',
    'R11-04 adds the inside locating skirts to the left and right lid edges, matching the existing '
    'front/back concept: 12 mm engagement, 2 mm wall thickness and 0.7 mm nominal clearance to the body guard. '
    'Four new side reliefs clear the body upper washers and nuts. The change adds material to four lid '
    'corner pieces and two side lid middle spans; the two front/back lid middle spans and all twelve body '
    'pieces retain their R11-03 geometry.', '',
    f'Body nylon remains **{body_sum:.6f} cm³**. Lid nylon changes from '
    f'**{lid_old_sum:.6f} to {lid_sum:.6f} cm³** (**{lid_sum-lid_old_sum:+.6f} cm³**). '
    f'Total PA12 changes by **{body_sum+lid_sum-body_old_sum-lid_old_sum:+.6f} cm³** '
    f'(**{100*(body_sum+lid_sum-body_old_sum-lid_old_sum)/(body_old_sum+lid_old_sum):.2f}%**). '
    'These are CAD material measurements, not a supplier price prediction. The part count stays at twenty; '
    'the body inner-ear design and 64 loose washers are retained from R11-03.', '',
    '## What previous real price records establish', '',
    'The saved [R10 cart record](../reference/r10-cart-2026-10-26.json) '
    'records 20 PA12-HP MJF, Dyed Black, quantity-1 lines on 2026-10-26. Body nylon totaled **JPY 2,872**, '
    'lid nylon **JPY 5,068**, total **JPY 7,940**. These were displayed cart prices, not final supplier-reviewed '
    'quote or invoice amounts; shipping was excluded and tax treatment was unknown.', '',
    '| Old R10 part group | Qty | Dimensions (mm) | Displayed JPY per part |',
    '|---|---:|---|---:|',
    '| Upper corner guards | 4 | 115.55 × 167.85 × 6 | 226 |',
    '| Vertical corner guards | 4 | 22.5 × 22.5 × 80.5 | 164 |',
    '| Front/back lower half spans | 4 | 114.45 × 6 × 24 | 164 |',
    '| Side lower half spans | 4 | 6 or 7 × 169.75 × 24 | 164 |',
    '| Lid quadrants | 4 | 115.6 × 167.9 × 43.8 | 1,267 |', '',
    'A roughly 169.75 mm lower span and a roughly 167.9 mm lid part had very different displayed prices. '
    'This directly rules out using length alone as a reliable predictor of the low-price tier. These prices '
    'cannot be transferred to the new geometry. The older R3 JPY 2,264 record is for twelve 1.2 mm guards, '
    'and does not price the current body or lid. The revision history documents thinner/narrower guards and '
    'long-edge splitting in R3, but does not establish an official 200 mm or other unpublished pricing boundary.', '',
    '## Smallest justified design changes', '',
    '1. Keep the long spans continuous for now. No current part crosses the published 250 mm trigger. '
    'Splitting a 210 mm part solely to avoid that trigger provides no proven saving and adds more parts and overlap material.',
    '2. Retain the four-sided lid guides and the established body inside seats. They are requested locating '
    'features. Removing them solely to reduce material would undo the adopted assembly concept. '
    'Their actual price effect requires the model-specific calculator.',
    '3. If a live quote shows material volume is dominant, trim unloaded ledges or wall area while retaining the '
    'washer bearing areas, fastened laps, locator function, and intended nominal wall thickness. Narrowing a part '
    'does not fix a longest-axis violation; here there is no such violation.',
    '4. If actual model-specific quote evidence shows envelope or handling charges dominate, compare the '
    f'continuous corners first: a body corner occupies about {corner_row["envelope_volume_cm3"]:.1f} cm³ of '
    f'bounding box but contains about {corner_row["material_volume_cm3"]:.2f} cm³ of nylon. '
    'This is a candidate for quote comparison, not proof that JLC bills that empty space.',
    '5. Only introduce another split if the actual before/after quote justifies it. Put any new seam at a '
    'deliberately fastened shared hole, as required by the user; do not restore free butt joints. No pricing '
    'evidence currently requires retaining the unused Y=0 station for a split.', '',
    '## Loose washers and feet', '',
    f'The Ø15 / Ø5 / t1 washer is a separate home-print black ASA item, **{new_washer["volume_mm3"]/1000:.6f} cm³ each**, not a JLC PA12 '
    f'part. The saved export manifests record {old_washer["quantity"]} for R11-03 and **{new_washer["quantity"]} for R11-04**: '
    '**40 outside body washers + 8 upper inside body washers + 16 lid-wall washers**. '
    'The four rubber feet are purchased-part/preview guidance, not exported PA12 print parts. No supplier '
    'prices are invented for either category.', '',
    '## Supplier upload remains unapproved', '',
    'No R11-04 upload was attempted. The user has not approved transmitting these CAD files to JLC. '
    'In the preceding audit, the [public JLC calculator](%s) loaded in the cloud browser and exposed its model upload control. '
    'The local browser extension was unavailable. The attempted upload of the R11-01 '
    '`body-top-right.stl` was rejected by automatic approval review **before the upload occurred**. '
    'The reason returned was:' % sources[3]['url'], '',
    '> '+denial, '',
    'The rejection was not bypassed. **Zero R11 files were uploaded.** No order, cart save, supplier message, '
    'or payment was performed. The live calculator tab was preserved for review. Explicit permission is '
    'needed to send the following 20 R11-04 STL files to JLC3DP solely to obtain automatic MJF PA12-HP, '
    'Dyed Black, quantity-1 prices. That permission would not include order submission, external messages, '
    'payment, or acceptance of any new terms.', '',
    '### Exact intended upload set', '',
    'Paths are relative to the R11-04 bundle root. All files exist; their SHA-256 hashes are recorded in the companion JSON report.', '',
]
lines += [f"- `{r['intended_stl_path']}`" for r in rows]
lines += ['', 'When uploads are authorized, record file hashes, material/finish, quantity, currency, '
          'line price, tax/shipping status, and any manual-review/surcharge flag before comparing variants. '
          'A low starting price or a successful size screen must never be substituted for that record.', '',
          '## Reproducible saved inputs', '',
          'Run `python research/build_pricing_audit.py` from the R11-04 bundle root after the CAD export completes. '
          'The generator requires the final export manifest, every listed STL, and the two saved reference JSON files. '
          'It verifies STL hashes before writing this report and makes no network requests. It uses no sibling repository or scratch paths.', '']
lines += [f'- `{p["path"]}` — SHA-256 `{p["sha256"]}`' for p in inputs]
(HERE/'jlc-pa12-pricing-audit.md').write_text('\n'.join(lines))
print(json.dumps({'report':str(HERE/'jlc-pa12-pricing-audit.md'), 'json':str(HERE/'jlc-pa12-pricing-audit.json'), 'basis':'exported_r11_04', 'part_count':len(rows), 'volume_cm3':body_sum+lid_sum}, indent=2))
