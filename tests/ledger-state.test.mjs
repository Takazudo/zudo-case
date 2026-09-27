import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { checkProjectState } from '../scripts/lib/state-checks.mjs';

const sourceRoot = new URL('../', import.meta.url);
const read = async name => JSON.parse(await readFile(new URL(name, sourceRoot), 'utf8'));
const baseline = {
  spec: await read('project/current-spec.json'), release: await read('project/release-state.json'),
  quotes: await read('project/quote-records.json'), gates: await read('project/open-issues.json'),
};
const fixture = async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'zudo-state-'));
  await mkdir(path.join(root, 'engineering/release'), { recursive: true });
  await writeFile(path.join(root, 'engineering/release/README.md'), 'fixture');
  return { root, ...structuredClone(baseline) };
};
const check = f => checkProjectState(f);
const quote = async f => {
  await mkdir(path.join(f.root, 'evidence'));
  await writeFile(path.join(f.root, 'evidence/quote.txt'), 'supplier quote fixture');
  f.quotes.records.push({ id: 'Q-CURRENT', kind: 'supplier_quote', applies_to_current_release: true,
    component: 'total', model: '7u40', revision: 'R9', quantity: 1, currency: 'JPY',
    tax_status: '税込', shipping_included: true, source: 'evidence/quote.txt',
    rows: [{ part: '一式', row_jpy: 12345 }], total_jpy: 12345 });
  f.quotes.current_total_scope = { model: '7u40', revision: 'R9' };
  f.quotes.current_total_jpy = 12345;
};
const file = async (f, relative = 'engineering/candidate/test.step') => {
  const full = path.join(f.root, relative);
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, 'candidate fixture');
  return { path: relative, sha256: createHash('sha256').update('candidate fixture').digest('hex') };
};

test('current state passes', async () => assert.deepEqual(await check(await fixture()), []));
test('evidenced quote and matching total pass', async () => {
  const f = await fixture(); await quote(f); assert.deepEqual(await check(f), []);
});
test('synthetic total without qualifying record fails', async () => {
  const f = await fixture(); f.quotes.current_total_jpy = 12345;
  assert.match((await check(f)).join('\n'), /current_total_jpy/);
});
test('assistant estimate cannot justify current total', async () => {
  const f = await fixture(); f.quotes.current_total_jpy = 12345;
  f.quotes.records.push({ id: 'estimate', kind: 'prior_assistant_budget_not_quote', applies_to_current_release: true,
    total_jpy: 12345 });
  assert.match((await check(f)).join('\n'), /current_total_jpy/);
});
test('quote scope mismatch fails', async () => {
  const f = await fixture(); await quote(f); f.quotes.current_total_scope.revision = 'R10';
  assert.match((await check(f)).join('\n'), /current_total_jpy/);
});
test('unapproved candidate passes with verified hash', async () => {
  const f = await fixture(); f.release.candidate_files = [await file(f)];
  assert.deepEqual(await check(f), []);
});
test('approval without approval record fails', async () => {
  const f = await fixture(); f.release.production_approved = true;
  assert.match((await check(f)).join('\n'), /approval_record/);
});
test('approval with open G item fails', async () => {
  const f = await fixture(); f.release.production_approved = true;
  f.release.approval_record = { approver: 'fixture', date: '2026-09-27', approved_files: [] };
  assert.match((await check(f)).join('\n'), /G01/);
});
test('unlisted release file fails', async () => {
  const f = await fixture(); await file(f, 'engineering/release/unlisted.step');
  assert.match((await check(f)).join('\n'), /unlisted.step/);
});
test('release gate disagreement fails', async () => {
  const f = await fixture(); f.spec.release_gate.approved_for_production = true;
  assert.match((await check(f)).join('\n'), /release_gate/);
});

test('complete approval with matching ledgers and closed evidenced gates passes', async () => {
  const f = await fixture();
  const approvedFile = await file(f, 'engineering/release/approved.step');
  const evidence = await file(f, 'evidence/test-report.txt');
  f.release.published_release_files = [approvedFile];
  f.release.production_approved = true;
  f.release.approval_record = { approver: 'fixture approver', date: '2026-09-27',
    approved_files: [approvedFile], model_revisions: Object.fromEntries(Object.keys(f.spec.models).map(model => [model, 'R9'])) };
  f.spec.release_gate.approved_for_production = true;
  for (const model of Object.values(f.spec.models)) model.manufacturing_release = 'R9';
  for (const gate of f.gates) { gate.status = 'closed'; gate.result = { summary: 'fixture result', evidence: [evidence.path] }; }
  assert.deepEqual(await check(f), []);
});

test('closed G item without actual evidence fails', async () => {
  const f = await fixture();
  f.release.production_approved = true;
  f.release.approval_record = { approver: 'fixture', date: '2026-09-27', approved_files: [] };
  for (const gate of f.gates) { gate.status = 'closed'; gate.result = { summary: 'done', evidence: ['missing.txt'] }; }
  assert.match((await check(f)).join('\n'), /G01/);
});

test('nested release file not listed fails', async () => {
  const f = await fixture(); await file(f, 'engineering/release/nested/unlisted.step');
  assert.match((await check(f)).join('\n'), /nested\/unlisted.step/);
});

test('candidate hash mismatch fails', async () => {
  const f = await fixture(); f.release.candidate_files = [{ ...(await file(f)), sha256: '0'.repeat(64) }];
  assert.match((await check(f)).join('\n'), /candidate_files.*ハッシュ不一致/);
});

test('lid and band prices each require their own matching quote', async () => {
  const f = await fixture(); await quote(f);
  f.quotes.current_lid_price_jpy = 12345;
  f.quotes.current_lid_price_scope = { model: '7u40', revision: 'R9' };
  f.quotes.current_band_price_jpy = 12345;
  f.quotes.current_band_price_scope = { model: '7u40', revision: 'R9' };
  const errors = (await check(f)).join('\n');
  assert.match(errors, /current_lid_price_jpy/);
  assert.match(errors, /current_band_price_jpy/);
});
