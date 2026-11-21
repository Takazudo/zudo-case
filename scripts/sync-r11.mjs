// Verify the imported R11-BUILD-FEEDBACK-04 revision and synchronize its public copies and
// the active 7U40 selection `current_metal_7u40_candidate` in project/release-state.json.
// `--check` verifies without writing and fails on any drift. Only that key is ever written.
// The legacy `current_fullset_candidate` (R10-FULLSET-01, owned by sync-fullset.mjs and
// asserted by preserved family verifiers) and project/current-spec.json (hashed by the
// R9 package manifest) are deliberately left untouched.
import {readFileSync, writeFileSync, readdirSync, mkdirSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {checkR11Contract, deriveR11Facts, readZip, sha256, R11_DIR, R11_SOURCE, R11_REVISION} from './lib/r11-contract.mjs';

export const POINTER_FILES = ['project/release-state.json'];
export const POINTER_KEY = 'current_metal_7u40_candidate';
const URL_DIR = '/downloads/candidate';
const PUBLIC_DIR = 'public/downloads/candidate';
export const PUBLIC_COPIES = [
  {target: 'public/previews/r11-build-feedback-04.html', source: R11_SOURCE + '/out/preview.html'},
  {target: 'public/images/metal-case/r11-build-feedback-04/lid-guides.png', source: R11_SOURCE + '/out/preview-renders/lidguides.png'},
  {target: 'public/images/metal-case/r11-build-feedback-04/lid-side-fit.png', source: R11_SOURCE + '/out/preview-renders/lidfit-exploded.png'},
];

function listFiles(dir, base = dir) {
  const out = [];
  for (const e of readdirSync(dir, {withFileTypes: true})) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...listFiles(p, base)); else out.push(path.relative(base, p).split(path.sep).join('/'));
  }
  return out;
}

export function verifyReceipt(root, receipt) {
  const errors = [];
  const dir = path.join(root, R11_SOURCE);
  const listed = new Set();
  for (const m of receipt.members) {
    listed.add(m.path);
    try {
      const b = readFileSync(path.join(dir, m.path));
      if (b.length !== m.bytes || sha256(b) !== m.sha256) errors.push(`source/${m.path}: bytes/sha256 differ from SOURCE-RECEIPT`);
    } catch (e) { errors.push(`source/${m.path}: missing (${e.code || e.message})`); }
  }
  if (receipt.members.length !== receipt.received_archive.member_count) errors.push('SOURCE-RECEIPT member_count mismatch');
  try { for (const f of listFiles(dir)) if (!listed.has(f)) errors.push(`source/${f}: not in SOURCE-RECEIPT`); }
  catch (e) { errors.push(`source/ unreadable: ${e.message}`); }
  return errors;
}

export async function verifyPackages(root, receipt, pkgManifest) {
  const errors = [];
  const rev = p => path.join(root, R11_DIR, p);
  const gen = readFileSync(rev(pkgManifest.generator.path));
  if (sha256(gen) !== pkgManifest.generator.sha256) errors.push('package.py changed since packages-manifest.json was generated; rerun it');
  const roles = pkgManifest.packages.map(p => p.role);
  if (JSON.stringify(roles) !== JSON.stringify(['source', 'pa12', 'aluminum', 'home-print'])) errors.push('package roles: ' + roles);
  for (const pkg of pkgManifest.packages) {
    const expectedPublic = `${PUBLIC_DIR}/${R11_REVISION}-${pkg.role}.zip`;
    if (pkg.public_path !== expectedPublic || pkg.url !== expectedPublic.replace(/^public/, '')) errors.push(`${pkg.role}: unexpected public path`);
    if (pkg.role === 'source') {
      if (pkg.verbatim_received_archive !== true || pkg.sha256 !== receipt.received_archive.sha256 || pkg.bytes !== receipt.received_archive.bytes)
        errors.push('source package is not the verbatim received archive');
      continue;
    }
    let blob;
    try { blob = readFileSync(rev(pkg.path)); } catch (e) { errors.push(`${pkg.path}: missing`); continue; }
    if (blob.length !== pkg.bytes || sha256(blob) !== pkg.sha256) { errors.push(`${pkg.path}: bytes/sha256 differ from packages-manifest`); continue; }
    const entries = await readZip(blob);
    const names = entries.map(e => e.name);
    if (JSON.stringify(names) !== JSON.stringify(pkg.members.map(m => m.name))) errors.push(`${pkg.path}: member list differs from packages-manifest`);
    for (const m of pkg.members) {
      const e = entries.find(x => x.name === m.name);
      if (!e || sha256(e.data) !== m.sha256) { errors.push(`${pkg.path}:${m.name}: content differs from manifest`); continue; }
      if (m.source.startsWith('source/out/')) {
        const s = readFileSync(rev(m.source));
        if (sha256(s) !== m.sha256) errors.push(`${pkg.path}:${m.name}: differs from ${m.source}`);
      } else if (m.name !== 'START-HERE.md') errors.push(`${pkg.path}:${m.name}: member not sourced from source/out/`);
    }
  }
  return errors;
}

export async function verifySourceZip(root, receipt) {
  const errors = [];
  const p = path.join(root, PUBLIC_DIR, `${R11_REVISION}-source.zip`);
  let blob;
  try { blob = readFileSync(p); } catch { return [`${PUBLIC_DIR}/${R11_REVISION}-source.zip: missing`]; }
  if (blob.length !== receipt.received_archive.bytes || sha256(blob) !== receipt.received_archive.sha256)
    return [`${PUBLIC_DIR}/${R11_REVISION}-source.zip: not the verbatim received archive`];
  const byPath = new Map(receipt.members.map(m => [m.path, m]));
  const entries = await readZip(blob);
  if (entries.length !== receipt.members.length) errors.push('source zip member count differs from receipt');
  for (const e of entries) {
    const rel = e.name.startsWith(receipt.received_archive.root) ? e.name.slice(receipt.received_archive.root.length) : null;
    const m = rel && byPath.get(rel);
    if (!m || sha256(e.data) !== m.sha256) errors.push(`source zip member ${e.name} differs from SOURCE-RECEIPT`);
  }
  return errors;
}

export function buildPointer(root, receipt, pkgManifest) {
  const f = deriveR11Facts(root);
  const url = role => pkgManifest.packages.find(p => p.role === role).url;
  const priceStatuses = [...new Set(f.auditCsv.map(r => r.price_status))];
  return {
    revision: f.revision,
    model: f.model,
    base_revision: f.base_revision,
    status: f.status,
    production_approved: f.production_approved,
    source: R11_DIR + '/',
    received_archive: {sha256: receipt.received_archive.sha256, bytes: receipt.received_archive.bytes},
    manifest_path: R11_SOURCE + '/out/parts-manifest.json',
    manifest_sha256: sha256(f.manifestBytes),
    preview: '/previews/r11-build-feedback-04.html',
    packages: {source: url('source'), pa12: url('pa12'), aluminum: url('aluminum'), 'home-print': url('home-print')},
    quantities: {
      aluminum: f.counts.aluminum, pa12: f.counts.pa12, pa12_body: f.counts.pa12_body, pa12_lid: f.counts.pa12_lid,
      washer_models: f.counts.washer_models, washer_instances: f.washer_instances, l_brackets: f.l_brackets,
    },
    sheet_cutouts: f.sheet_cutouts,
    body_slot_mm: f.body_slot_mm,
    pa12_volume_cm3: f.pa12_volume_cm3,
    prices: {current_total_jpy: f.audit.total_price, status: priceStatuses.length === 1 ? priceStatuses[0] : 'mixed'},
    current_doc: 'metal-case/design/r11-build-feedback-04.mdx',
  };
}

const encode = x => JSON.stringify(x, null, 2) + '\n';

// Returns {errors, changed}. In check mode nothing is written.
export async function runSync({root, check}) {
  const errors = [];
  const changed = [];
  const read = p => readFileSync(path.join(root, p));
  const receipt = JSON.parse(read(R11_DIR + '/SOURCE-RECEIPT.json'));
  const pkgManifest = JSON.parse(read(R11_DIR + '/packages-manifest.json'));
  errors.push(...verifyReceipt(root, receipt));
  errors.push(...checkR11Contract(root));
  errors.push(...await verifyPackages(root, receipt, pkgManifest));
  errors.push(...await verifySourceZip(root, receipt));
  if (errors.length) return {errors, changed};

  const copies = [...PUBLIC_COPIES, ...pkgManifest.packages.filter(p => p.role !== 'source')
    .map(p => ({target: p.public_path, source: R11_DIR + '/' + p.path}))];
  const put = (target, bytes) => {
    let current = null;
    try { current = read(target); } catch {}
    if (current && current.equals(bytes)) return;
    if (check) { errors.push(`drift: ${target}`); return; }
    mkdirSync(path.dirname(path.join(root, target)), {recursive: true});
    writeFileSync(path.join(root, target), bytes);
    changed.push(target);
  };
  for (const c of copies) put(c.target, read(c.source));

  const pointer = buildPointer(root, receipt, pkgManifest);
  for (const p of POINTER_FILES) {
    const doc = JSON.parse(read(p));
    let next = doc;
    if (Object.hasOwn(doc, POINTER_KEY)) next[POINTER_KEY] = pointer;
    else {
      // Insert the active selection right after the legacy R10 pointer, keeping all other keys.
      next = {};
      for (const [k, v] of Object.entries(doc)) { next[k] = v; if (k === 'current_fullset_candidate') next[POINTER_KEY] = pointer; }
      if (!Object.hasOwn(next, POINTER_KEY)) next[POINTER_KEY] = pointer;
    }
    put(p, Buffer.from(encode(next)));
  }
  return {errors, changed};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const check = process.argv.includes('--check');
  const root = fileURLToPath(new URL('../', import.meta.url));
  const {errors, changed} = await runSync({root, check});
  if (errors.length) {
    console.error(errors.join('\n'));
    console.error(`R11-BUILD-FEEDBACK-04 ${check ? 'check' : 'sync'} failed (${errors.length} problem(s)).`);
    process.exitCode = 1;
  } else {
    console.log(`R11-BUILD-FEEDBACK-04 ${check ? 'verified' : 'synchronized'}${changed.length ? ': updated ' + changed.join(', ') : ''}. Nominal data/hash check only; not physical validation or manufacturing approval.`);
  }
}
