import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, mkdtempSync, mkdirSync, symlinkSync, copyFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {checkR11Contract, readZip, sha256} from '../scripts/lib/r11-contract.mjs';
import {runSync, verifyReceipt, verifyPackages, POINTER_FILES, POINTER_KEY, PRIVATE_DETAIL} from '../scripts/sync-r11.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const R11 = 'engineering/r11-build-feedback-04';
const read = p => readFileSync(path.join(root, p));
const json = p => JSON.parse(read(p));
const RECEIVED_SHA256 = '4c74dd94e84ecebee8ac8d714cb5ba60f0ff479667c8c7f4ed4c75790463fcad';

test('accepted R11-04 contract holds for the imported source', () => {
  assert.deepEqual(checkR11Contract(root), []);
});

test('package roles and member counts', async () => {
  const m = json(R11 + '/packages-manifest.json');
  assert.deepEqual(m.packages.map(p => p.role), ['source', 'pa12', 'aluminum', 'home-print']);
  const count = (names, ext) => names.filter(n => n.endsWith(ext)).length;
  const names = async role => (await readZip(read(`public/downloads/candidate/R11-BUILD-FEEDBACK-04-${role}.zip`))).map(e => e.name);
  const pa12 = await names('pa12');
  assert.equal(count(pa12, '.step'), 20);
  assert.equal(count(pa12, '.stl'), 20);
  assert.ok(pa12.includes('START-HERE.md') && pa12.includes('pa12-size-audit.csv'));
  const alu = await names('aluminum');
  assert.deepEqual([count(alu, '.step'), count(alu, '.stl'), count(alu, '.dxf')], [6, 6, 6]);
  assert.ok(alu.includes('START-HERE.md') && alu.includes('panel-hole-map.csv'));
  const home = await names('home-print');
  assert.deepEqual(home, ['START-HERE.md', 'home-print/round-washer.step', 'home-print/round-washer.stl']);
});

test('source zip repackages source/ with private details generalized; the received archive stays identified by hash', async () => {
  const receipt = json(R11 + '/SOURCE-RECEIPT.json');
  const m = json(R11 + '/packages-manifest.json').packages.find(p => p.role === 'source');
  const blob = read('public/downloads/candidate/R11-BUILD-FEEDBACK-04-source.zip');
  assert.equal(receipt.received_archive.sha256, RECEIVED_SHA256);
  assert.equal(receipt.received_archive.published, false);
  assert.equal(m.received_archive_sha256, RECEIVED_SHA256);
  assert.equal(m.verbatim_received_archive, false);
  assert.notEqual(sha256(blob), RECEIVED_SHA256);
  assert.equal(sha256(blob), m.sha256);
  assert.equal(blob.length, m.bytes);
  assert.equal(receipt.members.length, 238);
  const generalized = receipt.members.filter(x => x.generalized);
  assert.deepEqual(generalized.map(x => x.path).sort(), ['README.md', 'research/hanging-hole-audit.json', 'research/hanging-hole-audit.md']);
  for (const g of generalized) assert.ok(/^[0-9a-f]{64}$/.test(g.received_sha256) && g.received_sha256 !== g.sha256, g.path);
  const entries = await readZip(blob);
  assert.equal(entries.length, 238);
  for (const e of entries) {
    const member = receipt.members.find(x => receipt.received_archive.root + x.path === e.name);
    assert.ok(member, e.name);
    assert.equal(sha256(e.data), member.sha256, e.name);
    assert.doesNotMatch(e.data.toString('latin1'), PRIVATE_DETAIL, e.name);
  }
  assert.doesNotMatch(JSON.stringify(receipt), /codex-artifacts|Dropbox/);
});

test('a private mailbox link in the published source copy is reported', async () => {
  assert.ok(PRIVATE_DETAIL.test('https://mail.google.com/mail/u/0/#all/0123456789abcdef'));
  assert.ok(PRIVATE_DETAIL.test('/codex-artifacts/zudo-case/x/'));
  assert.ok(!PRIVATE_DETAIL.test('mailbox message; reference withheld in the published copy'));
});

test('sync is idempotent and only writes the active 7U40 selection', async () => {
  const tmp = mkdtempSync(path.join(tmpdir(), 'r11-sync-'));
  try {
    symlinkSync(path.join(root, 'engineering'), path.join(tmp, 'engineering'));
    symlinkSync(path.join(root, 'public'), path.join(tmp, 'public'));
    mkdirSync(path.join(tmp, 'project'));
    for (const p of POINTER_FILES) copyFileSync(path.join(root, p), path.join(tmp, p));
    const before = Object.fromEntries(POINTER_FILES.map(p => { const d = JSON.parse(readFileSync(path.join(tmp, p))); delete d[POINTER_KEY]; return [p, d]; }));
    // Start from a ledger without the active key, as on main before the import.
    for (const p of POINTER_FILES) writeFileSync(path.join(tmp, p), JSON.stringify(before[p], null, 2) + '\n');
    const first = await runSync({root: tmp, check: false});
    assert.deepEqual(first.errors, []);
    const snapshot = POINTER_FILES.map(p => readFileSync(path.join(tmp, p)));
    const second = await runSync({root: tmp, check: false});
    assert.deepEqual(second, {errors: [], changed: []});
    POINTER_FILES.forEach((p, i) => assert.ok(readFileSync(path.join(tmp, p)).equals(snapshot[i]), p));
    assert.deepEqual((await runSync({root: tmp, check: true})).errors, []);
    for (const p of POINTER_FILES) {
      const doc = JSON.parse(readFileSync(path.join(tmp, p)));
      const keys = Object.keys(before[p]);
      keys.splice(keys.indexOf('current_fullset_candidate') + 1, 0, POINTER_KEY);
      assert.deepEqual(Object.keys(doc), keys, p + ' key order');
      for (const k of Object.keys(doc)) if (k !== POINTER_KEY) assert.deepEqual(doc[k], before[p][k], `${p}:${k}`);
      assert.equal(doc.current_fullset_candidate.revision, 'R10-FULLSET-01', 'legacy R10 pointer untouched');
      const c = doc[POINTER_KEY];
      assert.equal(c.revision, 'R11-BUILD-FEEDBACK-04');
      assert.equal(c.production_approved, false);
      assert.deepEqual(c.quantities, {aluminum: 6, pa12: 20, pa12_body: 12, pa12_lid: 8, washer_models: 1, washer_instances: 64, l_brackets: 16});
      assert.deepEqual(c.sheet_cutouts, {body_slots: 40, rail_round_holes: 10, lid_round_holes: 8, total: 58});
      assert.deepEqual(c.pa12_volume_cm3, {body: 87.7351, lid: 120.2104, total: 207.9455});
      assert.deepEqual(c.prices, {current_total_jpy: null, status: 'unquoted'});
      assert.equal(c.received_archive.sha256, RECEIVED_SHA256);
    }
  } finally {
    rmSync(tmp, {recursive: true, force: true});
  }
});

test('active 7U40 selection is R11 while the legacy R10 pointers and current-spec stay untouched', () => {
  const release = json('project/release-state.json');
  assert.equal(release[POINTER_KEY].revision, 'R11-BUILD-FEEDBACK-04');
  assert.equal(release.current_fullset_candidate.revision, 'R10-FULLSET-01');
  const spec = json('project/current-spec.json');
  assert.equal(spec.current_fullset_candidate.revision, 'R10-FULLSET-01');
  assert.equal(spec[POINTER_KEY], undefined);
  const selection = json('project/current-selection.json').selections.find(s => s.project === 'metal-case' && s.model === '7u40');
  assert.equal(selection.revision, release[POINTER_KEY].revision);
  assert.deepEqual(selection.registry, {file: 'project/release-state.json', key: POINTER_KEY});
});

test('a tampered receipt member hash is reported', () => {
  const receipt = json(R11 + '/SOURCE-RECEIPT.json');
  assert.deepEqual(verifyReceipt(root, receipt), []);
  const target = receipt.members.find(m => m.path === 'out/pa12/lid-corner-fl.stl');
  target.sha256 = '0'.repeat(64);
  const errors = verifyReceipt(root, receipt);
  assert.equal(errors.length, 1);
  assert.match(errors[0], /out\/pa12\/lid-corner-fl\.stl/);
});

test('a tampered package member hash is reported', async () => {
  const receipt = json(R11 + '/SOURCE-RECEIPT.json');
  const m = json(R11 + '/packages-manifest.json');
  m.packages.find(p => p.role === 'aluminum').members[1].sha256 = 'f'.repeat(64);
  const errors = await verifyPackages(root, receipt, m);
  assert.ok(errors.some(e => e.includes('R11-BUILD-FEEDBACK-04-aluminum.zip')), errors.join('\n'));
});
