// Accepted contract for the imported R11-BUILD-FEEDBACK-04 7U40 metal-case revision.
// Values are read from the imported source JSON/CSV under
// engineering/r11-build-feedback-04/source/ and asserted against the accepted numbers.
// This is a data-consistency check of the received CAD review candidate, not a
// physical, strength or manufacturing validation.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';

export const R11_DIR = 'engineering/r11-build-feedback-04';
export const R11_SOURCE = R11_DIR + '/source';
export const R11_REVISION = 'R11-BUILD-FEEDBACK-04';

export const sha256 = b => createHash('sha256').update(b).digest('hex');
const round4 = x => Math.round(x * 1e4) / 1e4;

export function parseCsv(text) {
  const [head, ...rows] = text.trim().split(/\r?\n/).map(l => l.split(','));
  return rows.map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

// Reads the source data and derives the facts that the pointer and the contract use.
export function deriveR11Facts(root) {
  const src = p => path.join(root, R11_SOURCE, p);
  const raw = p => readFileSync(src(p));
  const json = p => JSON.parse(raw(p));
  const manifestBytes = raw('out/parts-manifest.json');
  const manifest = JSON.parse(manifestBytes);
  const params = json('parameters.json');
  const validation = json('out/validation.json');
  const delta = json('out/revision-delta.json');
  const audit = json('out/pa12-size-audit.json');
  const lidReview = json('out/lid-locator-review.json');
  const scene = json('out/scene.json');
  const holes = parseCsv(raw('out/panel-hole-map.csv').toString('utf8'));
  const auditCsv = parseCsv(raw('out/pa12-size-audit.csv').toString('utf8'));

  const parts = manifest.parts;
  const pa12 = parts.filter(p => p.category === 'pa12');
  const body = pa12.filter(p => p.id.startsWith('body-'));
  const lid = pa12.filter(p => p.id.startsWith('lid-'));
  const sheets = parts.filter(p => p.category === 'aluminum');
  const washers = parts.filter(p => p.category === 'home-print');
  const vol = list => list.reduce((n, p) => n + p.volume_mm3 * p.quantity, 0) / 1000;
  const fileRefs = parts.flatMap(p => Object.entries(p.files).map(([kind, ref]) => ({kind, ...ref})));

  // Washer breakdown: outer washers are the distinct washer-out-* ids in the body bearing
  // stacks; retained inner washers are the body stacks whose inner washer was not replaced
  // by an integral ear; lid-wall washers are the lid metadata count.
  const outerIds = new Set(), innerIds = new Set();
  for (const c of validation.body_fastener_bearing_contacts)
    for (const id of [...c.a, ...c.b]) {
      if (id.startsWith('washer-out-')) outerIds.add(id);
      if (id.startsWith('washer-in-')) innerIds.add(id);
    }
  const stacks = scene.body_metadata.hardware_stacks;

  const holesBy = (panel, shape) => holes.filter(h => h.panel_id === panel && h.shape === shape).length;
  const slots = holes.filter(h => h.shape === 'slot');
  const rounds = holes.filter(h => h.shape === 'round');
  const changed = delta.parts.filter(p => p.old_step_sha256 !== p.new_step_sha256).map(p => p.id).sort();

  return {
    manifest, manifestBytes, params, validation, delta, audit, lidReview, scene, holes, auditCsv,
    revision: manifest.revision, model: manifest.model, status: manifest.status,
    production_approved: manifest.production_approved,
    base_revision: params.base_revision, base_commit: params.base_commit,
    counts: {
      part_models: parts.length, pa12: pa12.length, pa12_body: body.length, pa12_lid: lid.length,
      aluminum: sheets.length, washer_models: washers.length,
      step: fileRefs.filter(f => f.kind === 'step').length,
      stl: fileRefs.filter(f => f.kind === 'stl').length,
      dxf: fileRefs.filter(f => f.kind === 'dxf').length,
    },
    pa12_quantities: pa12.map(p => p.quantity), sheet_quantities: sheets.map(p => p.quantity),
    washer_instances: washers.reduce((n, p) => n + p.quantity, 0),
    washer_breakdown: {
      outside_body: outerIds.size,
      outside_body_sites: stacks.length,
      upper_inside_body: innerIds.size,
      upper_inside_body_stacks: stacks.filter(s => s.inner_washer_replaced === false).length,
      upper_inside_body_param: params.inside_ears.retained_top_inner_washers,
      lid_wall: scene.lid_metadata.counts.round_washers,
    },
    sheet_cutouts: {
      body_slots: slots.length, rail_round_holes: rounds.filter(h => h.panel_id !== 'lid-plate').length,
      lid_round_holes: rounds.filter(h => h.panel_id === 'lid-plate').length, total: holes.length,
    },
    per_sheet: Object.fromEntries(['panel-front', 'panel-back', 'panel-floor', 'panel-left', 'panel-right', 'lid-plate']
      .map(id => [id, {slot: holesBy(id, 'slot'), round: holesBy(id, 'round')}])),
    slot_sizes: [...new Set(slots.map(h => `${Number(h.total_length_mm)}x${Number(h.width_or_diameter_mm)}`))],
    body_slot_mm: [params.slots.new_length, params.slots.width],
    l_brackets: validation.counts.body_brackets,
    thin_nuts: validation.counts.body_thin_nuts, other_nuts: validation.counts.body_other_nuts,
    max_pa12_mm: Math.max(...pa12.flatMap(p => p.dimensions_mm)),
    pa12_volume_cm3: {body: round4(vol(body)), lid: round4(vol(lid)), total: round4(vol(pa12))},
    envelope: params.body,
    floor_dims: sheets.find(p => p.id === 'panel-floor')?.dimensions_mm,
    changed_vs_previous: changed,
    file_refs: fileRefs,
  };
}

export function checkR11Contract(root) {
  const errors = [];
  const eq = (label, actual, expected) => {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
      errors.push(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  };
  let f;
  try { f = deriveR11Facts(root); } catch (e) { return [`R11 source unreadable: ${e.message}`]; }
  const {manifest, params, validation: v, delta, audit, lidReview} = f;

  // Identity and approval state.
  eq('revision', f.revision, R11_REVISION);
  eq('parameters.revision', params.revision, R11_REVISION);
  eq('model', f.model, '7u40');
  eq('parameters.model', params.model, '7u40');
  eq('status', f.status, 'CAD_REVIEW_CANDIDATE_NOT_PHYSICALLY_VERIFIED');
  eq('production_approved', f.production_approved, false);
  eq('parameters.production_approved', params.production_approved, false);
  eq('every part production_approved', manifest.parts.every(p => p.production_approved === false), true);
  eq('base_revision', f.base_revision, 'R10-FULLSET-01');
  eq('base_commit', f.base_commit, 'b7a9e3cd1fba3a12fa8a625ab4f0f43d4a06674a');

  // Models and files: 27 = 20 PA12 (12 body + 8 lid) + 6 aluminum + 1 washer model.
  eq('model counts', f.counts, {part_models: 27, pa12: 20, pa12_body: 12, pa12_lid: 8, aluminum: 6, washer_models: 1, step: 27, stl: 27, dxf: 6});
  eq('manifest.counts', manifest.counts, {nylon_parts: 20, sheetmetal_parts: 6, washer_models: 1, washer_instances: 64, part_models: 27, files: {step: 27, stl: 27, dxf: 6}});
  eq('PA12 quantity 1 each', f.pa12_quantities.every(q => q === 1), true);
  eq('sheet quantity 1 each', f.sheet_quantities.every(q => q === 1), true);
  eq('validation body/lid nylon parts', [v.counts.body_nylon_parts, v.counts.lid_nylon_parts], [12, 8]);

  // Washers: 64 = 40 outside body + 8 upper inside body + 16 lid-wall.
  eq('washer instances (parts-manifest quantity)', f.washer_instances, 64);
  eq('validation loose_washers', v.counts.loose_washers, 64);
  eq('revision-delta new_washers', delta.new_washers, 64);
  const w = f.washer_breakdown;
  eq('outside body washers (validation washer-out ids)', w.outside_body, 40);
  eq('body fastener stacks (scene)', w.outside_body_sites, 40);
  eq('upper inside body washers (validation washer-in ids)', w.upper_inside_body, 8);
  eq('upper inside body washers (scene stacks without integral ear)', w.upper_inside_body_stacks, 8);
  eq('parameters.inside_ears.retained_top_inner_washers', w.upper_inside_body_param, 8);
  eq('revision-delta retained_top_inside_washers', delta.retained_top_inside_washers, 8);
  eq('lid-wall washers (scene lid_metadata.counts.round_washers)', w.lid_wall, 16);
  eq('washer breakdown sum', w.outside_body + w.upper_inside_body + w.lid_wall, f.washer_instances);

  // Sheet cutouts from panel-hole-map.csv: 58 = 40 slots + 10 rail round + 8 lid round.
  eq('sheet cutouts', f.sheet_cutouts, {body_slots: 40, rail_round_holes: 10, lid_round_holes: 8, total: 58});
  eq('per-sheet cutouts', f.per_sheet, {
    'panel-front': {slot: 8, round: 0}, 'panel-back': {slot: 8, round: 0}, 'panel-floor': {slot: 8, round: 0},
    'panel-left': {slot: 8, round: 5}, 'panel-right': {slot: 8, round: 5}, 'lid-plate': {slot: 0, round: 8},
  });
  eq('slot size in hole map (length x width)', f.slot_sizes, ['15.5x5.5']);
  eq('body slot mm (parameters.slots)', f.body_slot_mm, [15.5, 5.5]);
  eq('validation hole counts', [v.counts.body_slots, v.counts.body_round_rail_holes, v.counts.lid_plate_bolt_holes, v.counts.all_sheet_holes, v.counts.dedicated_hanging_holes], [40, 10, 8, 58, 0]);
  eq('revision-delta remaining_panel_cutouts', delta.remaining_panel_cutouts, 58);

  // Hardware.
  eq('metal L brackets', f.l_brackets, 16);
  eq('nuts thin/other', [f.thin_nuts, f.other_nuts], [16, 24]);
  eq('validation counts equal expected_counts', Object.keys(v.expected_counts).every(k => k === 'perpendicular_nut_pairs' || v.counts[k] === v.expected_counts[k]), true);

  // PA12 size and volume.
  eq('max PA12 dimension mm', f.max_pa12_mm, 210);
  eq('pa12-size-audit maximum_axis_mm', audit.maximum_axis_mm, 210);
  eq('PA12 volume cm3 (body/lid/total)', f.pa12_volume_cm3, {body: 87.7351, lid: 120.2104, total: 207.9455});
  eq('pa12-size-audit total cm3', round4(audit.total_solid_volume_cm3), 207.9455);

  // Envelope.
  eq('metal envelope (parameters.body)', f.envelope, {width: 229.4, depth: 334, height: 91, metal: 1.5});
  eq('floor sheet dims', f.floor_dims, [229.4, 334, 1.5]);

  // Revision delta vs R11-03.
  eq('previous revision', delta.previous_revision, 'R11-BUILD-FEEDBACK-03');
  eq('revision-delta passed', delta.passed, true);
  eq('changed parts vs R11-03', f.changed_vs_previous, ['lid-corner-bl', 'lid-corner-br', 'lid-corner-fl', 'lid-corner-fr', 'lid-middle-left', 'lid-middle-right']);
  const unchangedMiddles = delta.parts.filter(p => ['lid-middle-front', 'lid-middle-back'].includes(p.id) && p.old_step_sha256 === p.new_step_sha256 && p.added_solid_mm3 === 0 && p.removed_solid_mm3 === 0).length;
  eq('front/back lid middle spans unchanged', unchangedMiddles, 2);
  eq('revised/unchanged nylon parts', [delta.revised_nylon_parts, delta.unchanged_nylon_parts], [6, 14]);
  eq('revision-delta current_manifest_sha256', delta.current_manifest_sha256, sha256(f.manifestBytes));
  eq('pa12-size-audit source_manifest_sha256', audit.source_manifest_sha256, sha256(f.manifestBytes));

  // Saved nominal reports and prices.
  eq('validation.passed', v.passed, true);
  eq('lid locator review passed / range', [lidReview.passed, lidReview.straight_lift_off.translation_range_mm], [true, [0, 12.5]]);
  eq('PA12 prices null', audit.total_price === null && audit.parts.every(p => p.quoted_price === null), true);
  eq('PA12 size-audit CSV price status', [...new Set(f.auditCsv.map(r => r.price_status))], ['unquoted']);

  // Every out/ file listed in the parts manifest (plus the assembly shell) matches its hash.
  const refs = [...f.file_refs, manifest.assembly_shell.file];
  for (const ref of refs) {
    try {
      const b = readFileSync(path.join(root, R11_SOURCE, 'out', ref.path));
      if (b.length !== ref.bytes || sha256(b) !== ref.sha256) errors.push(`out/${ref.path}: hash/bytes differ from parts-manifest`);
    } catch (e) { errors.push(`out/${ref.path}: unreadable (${e.code || e.message})`); }
  }
  eq('hash-checked out/ files', refs.length, 61);
  return errors;
}

// Minimal ZIP reader (no ZIP64) used to compare package members with their sources.
export async function readZip(buf) {
  const {inflateRawSync} = await import('node:zlib');
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw Error('ZIP end record not found');
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const entries = [];
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw Error('bad ZIP central header');
    const method = buf.readUInt16LE(p + 10), csize = buf.readUInt32LE(p + 20), usize = buf.readUInt32LE(p + 24);
    const nlen = buf.readUInt16LE(p + 28), xlen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.subarray(p + 46, p + 46 + nlen).toString('utf8');
    p += 46 + nlen + xlen + clen;
    const start = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
    const raw = buf.subarray(start, start + csize);
    const data = method === 0 ? Buffer.from(raw) : method === 8 ? inflateRawSync(raw) : null;
    if (!data || data.length !== usize) throw Error('unsupported or corrupt ZIP member: ' + name);
    entries.push({name, data});
  }
  return entries;
}
