import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
// R9-LID-M5-01 (#123): register the M5 lid candidate beside R9-FITFIX-01.
// It never changes current_lid_manufacturing, the fitfix outputs or any approval.
const root = fileURLToPath(new URL('../', import.meta.url));
const base = 'engineering/r9-lid-m5-01', out = `${base}/out`, revision = 'R9-LID-M5-01', baseRevision = 'R9-FITFIX-01';
const check = process.argv.includes('--check');
if (process.argv.slice(2).some(x => x !== '--check')) throw Error('Usage: node scripts/sync-lid-m5.mjs [--check]');
const bytes = p => readFileSync(path.join(root, p));
const json = p => JSON.parse(bytes(p));
const hash = b => createHash('sha256').update(b).digest('hex');
const encode = x => JSON.stringify(x, null, 2) + '\n';
function put(p, b) {
  if (check) { if (!bytes(p).equals(Buffer.from(b))) throw Error(`Lid M5 drift: ${p}`); }
  else { mkdirSync(path.dirname(path.join(root, p)), { recursive: true }); writeFileSync(path.join(root, p), b); }
}
const manifest = json(`${out}/outputs-manifest.json`), validation = json(`${out}/validation.json`), env = json(`${out}/environment.json`);
if (manifest.revision !== revision || manifest.base_revision !== baseRevision || manifest.production_approved !== false ||
  validation.passed !== true || validation.production_approved !== false || !env.repository_python_cq_range_compatible) {
  throw Error('Full locked-compatible unapproved R9-LID-M5-01 generation required');
}
for (const f of manifest.inputs) if (hash(bytes(path.posix.join(base, f.path))) !== f.sha256) throw Error(`Stale generator input: ${f.path}`);
const artifacts = [], candidates = [];
function register(p, b, component) {
  if (b.length > 25 * 1024 * 1024) throw Error(`Artifact exceeds 25 MiB: ${p}`);
  const sha256 = hash(b); artifacts.push({ path: p, bytes: b.length, sha256, status: 'candidate-not-approved' });
  if (component) candidates.push({ id: `R9M5-${p.replace(/[^a-z0-9]+/gi, '-').toUpperCase()}`, component, model: '7u40', revision, path: p, sha256 });
}
const labels = {
  '7u40-t1p2-lid-m5-pa12-NOT-APPROVED.zip': 'M5フタ枠4個PA12（1.2mm案）',
  '7u40-t1p0-lid-m5-pa12-NOT-APPROVED.zip': 'M5フタ枠4個PA12（1.0mm案）',
  '7u40-t1p2-lid-m5-aluminum-NOT-APPROVED.zip': 'M5天板アルミ（1.2mm案）',
  '7u40-t1p0-lid-m5-aluminum-NOT-APPROVED.zip': 'M5天板アルミ（1.0mm案）',
  'm5-coupons-pa12-NOT-APPROVED.zip': 'C2-M5枠3種＋N1ラダーPA12',
  'm5-coupons-metal-NOT-APPROVED.zip': 'C2-M5天板アルミ',
};
const links = [];
for (const f of manifest.files) {
  const p = `${out}/${f.path}`, b = bytes(p);
  if (b.length !== f.bytes || hash(b) !== f.sha256) throw Error(`Changed output: ${p}`);
  const geometry = /\.(stl|step|dxf)$/.test(p);
  const component = !geometry || f.path.startsWith('assembly/') ? null : f.path.startsWith('coupons/') ? 'coupon' : 'lid';
  register(p, b, component);
  if (f.path === 'preview.html' || f.path.endsWith('.zip')) {
    const pub = f.path === 'preview.html' ? 'public/previews/r9-lid-m5-01.html' : `public/downloads/candidate/r9-lid-m5-01-${f.path}`;
    put(pub, b); register(pub, b, f.path.endsWith('.zip') ? 'package' : 'preview');
    links.push({ path: pub.replace(/^public/, ''), label: f.path === 'preview.html' ? 'R9-LID-M5-01プレビュー' : labels[f.path] });
  }
}
register(`${out}/outputs-manifest.json`, bytes(`${out}/outputs-manifest.json`));
register(`${out}/environment.json`, bytes(`${out}/environment.json`));
if (links.some(x => !x.label)) throw Error('Unlabelled M5 package');

// Candidate entries sit just before the R9-FITFIX-01 block, which sync-fitfix keeps last.
const release = json('project/release-state.json');
const others = release.candidate_files.filter(x => x.revision !== revision);
const at = others.findIndex(x => x.revision === baseRevision);
release.candidate_files = at < 0 ? [...others, ...candidates] : [...others.slice(0, at), ...candidates, ...others.slice(at)];
if (release.current_lid_manufacturing?.revision !== baseRevision) throw Error('Current lid designation must remain R9-FITFIX-01 until a physical decision');
const lidIds = candidates.filter(x => x.component === 'lid').map(x => x.id);
release.lid_revision_candidates = [
  ...(release.lid_revision_candidates ?? []).filter(x => x.revision !== revision),
  { model: '7u40', revision, base_revision: baseRevision, issue: 123, designated_current: false, production_approved: false,
    combination: { body_plates: `${baseRevision} (unchanged)`, guards: `${baseRevision} (unchanged)`, lid_frames_and_plates: revision },
    candidate_ids: lidIds,
    note: 'M5 screw + nylon lock nut for plate/frame assembly only. No lid-to-body lock. Physical fit and nut test pending; current_lid_manufacturing stays R9-FITFIX-01.' },
];
put('project/release-state.json', encode(release));

const ledger = json('project/artifact-manifest.json');
const remaining = new Map(artifacts.map(x => [x.path, x]));
ledger.files = ledger.files.flatMap(x => {
  const owned = x.path.startsWith(`${out}/`) || x.path.includes('/r9-lid-m5-01');
  if (!owned) return [x];
  const replacement = remaining.get(x.path); remaining.delete(x.path);
  return replacement ? [replacement] : [];
});
// New entries go before the fit-test packet record, which prepare-fit-test-order keeps last.
const packet = ledger.files.findIndex(x => x.path === 'public/downloads/candidate/fit-test-order-pack-DRAFT.zip');
if (packet < 0) ledger.files.push(...remaining.values()); else ledger.files.splice(packet, 0, ...remaining.values());
put('project/artifact-manifest.json', encode(ledger));

const spec = json('project/current-spec.json'), dims = json(`${out}/dimensions.json`);
const site = dims.variants.t1p2.by_edge;
spec.models['7u40'].lid_m5_candidate = {
  revision, base_revision: baseRevision, issue: 123, status: 'unapproved candidate; physical nut/fit test pending',
  scope: 'lid plate-to-PA12-frame assembly fastener only; body plates and guards unchanged',
  m5_adopted_mm: dims.adopted,
  measured_min_mm: {
    nut_wall: Math.min(site.front.min_wall_true.min, site.side.min_wall_true.min),
    effective_depth: Math.min(site.front.effective_depth.min, site.side.effective_depth.min),
    plate_edge_ligament: Math.min(site.front.plate_edge_ligament.min, site.side.plate_edge_ligament.min),
  },
  screw_length_candidates_mm: dims.variants.t1p2.screw_lengths_passing_all_sites,
  links, bom_path: `${out}/BOM.json`, dimensions_path: `${out}/DIMENSIONS.md`, old_to_new_path: `${out}/old-to-new.csv`,
};
put('project/current-spec.json', encode(spec));
console.log(`Lid M5 ${check ? 'verified' : 'synchronized'}: ${candidates.length} candidates, ${artifacts.length} artifacts.`);
