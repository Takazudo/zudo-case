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
  const state = structuredClone(baseline);
  state.release.candidate_files = [];
  state.release.current_lid_manufacturing = null;
  return { root, ...state };
};
const check = f => checkProjectState(f);
const quote = async f => {
  await mkdir(path.join(f.root, 'evidence'), { recursive: true });
  await writeFile(path.join(f.root, 'evidence/quote.txt'), 'supplier quote fixture');
  f.quotes.records.push({ id: 'Q-CURRENT', kind: 'supplier_quote', applies_to_current_release: true,
    component: 'total', model: '7u40', revision: 'R9', quantity: 1, price_basis: 'lot_total', currency: 'JPY',
    tax_status: '税込', shipping_included: true, source: 'evidence/quote.txt',
    rows: [{ part: '一式', row_jpy: 12345 }], total_jpy: 12345 });
  f.quotes.current_total_scope = { model: '7u40', revision: 'R9', quantity: 1, price_basis: 'lot_total',
    tax_status: '税込', shipping_included: true, quote_ids: ['Q-CURRENT'] };
  f.quotes.current_total_jpy = 12345;
};
const file = async (f, relative = 'engineering/candidate/test.step') => {
  const full = path.join(f.root, relative);
  await mkdir(path.dirname(full), { recursive: true });
  await writeFile(full, 'candidate fixture');
  return { path: relative, sha256: createHash('sha256').update('candidate fixture').digest('hex') };
};
const lidCandidate = async (f, part, overrides = {}) => ({
  ...(await file(f, `engineering/candidate/${part}.step`)),
  id: `LID-7U40-R9-${part.toUpperCase()}`, component: 'lid', model: '7u40', revision: 'R9', ...overrides,
});
const designateLid = (f, candidates) => {
  f.release.current_lid_manufacturing = {
    model: '7u40', revision: 'R9', candidate_ids: candidates.map(candidate => candidate.id),
  };
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
const secondQuote = f => {
  const record = { ...structuredClone(f.quotes.records.at(-1)), id: 'Q-SECOND',
    rows: [{ part: '別部品', row_jpy: 8000 }], total_jpy: 8000 };
  f.quotes.records.push(record);
  return record;
};
const selectBoth = f => {
  f.quotes.current_total_scope.quote_ids.push('Q-SECOND');
  f.quotes.current_total_scope.coverage_note = '各1台分の本体と蓋を別見積として採用。重複なし。';
  f.quotes.current_total_jpy += 8000;
};

test('selected disjoint quotes with matching conditions and coverage note pass', async () => {
  const f = await fixture(); await quote(f); secondQuote(f); selectBoth(f);
  assert.deepEqual(await check(f), []);
});
for (const [field, value] of [['quantity', 10], ['tax_status', '税別'],
  ['price_basis', 'per_unit'], ['shipping_included', false]]) {
  test(`selected quote ${field} mismatch fails`, async () => {
    const f = await fixture(); await quote(f);
    f.quotes.records.at(-1).total_jpy = 10000;
    f.quotes.records.at(-1).rows[0].row_jpy = 10000;
    f.quotes.current_total_jpy = 10000;
    const other = secondQuote(f); other[field] = value;
    if (field === 'quantity') {
      other.total_jpy = other.rows[0].row_jpy = 80000;
    }
    selectBoth(f);
    f.quotes.current_total_jpy = 10000 + other.total_jpy;
    assert.match((await check(f)).join('\n'), new RegExp(`${field}.*不一致`));
  });
}
test('unselected competing quote is excluded from total', async () => {
  const f = await fixture(); await quote(f); secondQuote(f);
  assert.deepEqual(await check(f), []);
  f.quotes.current_total_jpy += 8000;
  assert.match((await check(f)).join('\n'), /total_jpy合計と不一致/);
});
for (const [name, ids] of [['unknown', ['missing']], ['duplicate', ['Q-CURRENT', 'Q-CURRENT']],
  ['historical', ['Q-R3-001']], ['estimate', ['E-R6-BODY']]]) {
  test(`${name} selected quote_ids fails`, async () => {
    const f = await fixture(); await quote(f); f.quotes.current_total_scope.quote_ids = ids;
    f.quotes.current_total_scope.coverage_note = 'fixture';
    assert.match((await check(f)).join('\n'), /quote_ids/);
  });
}
for (const [name, mutate, pattern] of [
  ['wrong component', r => r.component = 'lid', /同じcomponent/],
  ['invalid current record', r => r.source = 'missing.txt', /有効な現行見積/],
  ['wrong model set', r => r.model = '7u60', /model\/modelsが範囲と不一致/],
]) {
  test(`selection rejects ${name}`, async () => {
    const f = await fixture(); await quote(f); mutate(f.quotes.records.at(-1));
    assert.match((await check(f)).join('\n'), pattern);
  });
}
test('duplicate record id including historical record fails', async () => {
  const f = await fixture(); await quote(f); f.quotes.records.at(-1).id = 'Q-R3-001';
  assert.match((await check(f)).join('\n'), /idが重複/);
});
test('null total permits valid unselected quotes and absent or null scope', async () => {
  const f = await fixture(); await quote(f); secondQuote(f);
  f.quotes.current_total_jpy = null;
  delete f.quotes.current_total_scope;
  assert.deepEqual(await check(f), []);
  f.quotes.current_total_scope = null;
  assert.deepEqual(await check(f), []);
  f.quotes.current_total_scope = { model: '7u40' };
  assert.match((await check(f)).join('\n'), /価格がnullなら範囲もnull/);
});
for (const [name, change, pattern] of [
  ['coverage note', f => delete f.quotes.current_total_scope.coverage_note, /coverage_note/],
  ['duplicate part', f => f.quotes.records.at(-1).rows[0].part = '一式', /rows\[\]\.partが重複/],
]) {
  test(`multi-quote selection without ${name} fails`, async () => {
    const f = await fixture(); await quote(f); secondQuote(f); selectBoth(f); change(f);
    assert.match((await check(f)).join('\n'), pattern);
  });
}
for (const target of ['record', 'scope']) {
  test(`both model and models in ${target} fail`, async () => {
    const f = await fixture(); await quote(f);
    (target === 'record' ? f.quotes.records.at(-1) : f.quotes.current_total_scope).models = ['7u40'];
    assert.match((await check(f)).join('\n'), /model\/models/);
  });
}
test('model sets match regardless of order or singular representation', async () => {
  const f = await fixture(); await quote(f);
  const record = f.quotes.records.at(-1), scope = f.quotes.current_total_scope;
  delete record.model; record.models = ['7u40'];
  assert.deepEqual(await check(f), []);
  delete scope.model; scope.models = ['7u60', '7u40']; record.models = ['7u40', '7u60'];
  assert.deepEqual(await check(f), []);
});
for (const [field, invalid] of [['id', ' '], ['price_basis', 'unit'], ['quantity', 0],
  ['tax_status', ' '], ['shipping_included', 'yes']]) {
  test(`current record requires valid ${field}`, async () => {
    const f = await fixture(); await quote(f); f.quotes.records.at(-1)[field] = invalid;
    assert.match((await check(f)).join('\n'), new RegExp(field));
  });
}
for (const [field, invalid] of [['quantity', 1.5], ['price_basis', 'unit'], ['tax_status', ' '],
  ['shipping_included', 'yes'], ['quote_ids', []], ['quote_ids', [' ']], ['quote_ids', [123]]]) {
  test(`non-null scope requires valid ${field}`, async () => {
    const f = await fixture(); await quote(f); f.quotes.current_total_scope[field] = invalid;
    assert.match((await check(f)).join('\n'), new RegExp(field));
  });
}
for (const [component, prefix] of [['lid', 'current_lid_price'], ['band', 'current_band_price']]) {
  test(`${component} uses explicit selection and condition matching`, async () => {
    const f = await fixture(); await quote(f); const record = f.quotes.records.at(-1);
    record.component = component;
    f.quotes[`${prefix}_jpy`] = f.quotes.current_total_jpy;
    f.quotes[`${prefix}_scope`] = f.quotes.current_total_scope;
    f.quotes.current_total_jpy = null; delete f.quotes.current_total_scope;
    assert.deepEqual(await check(f), []);
    f.quotes[`${prefix}_scope`].quantity = 10;
    assert.match((await check(f)).join('\n'), new RegExp(`${prefix}_jpy.*quantity.*不一致`));
    f.quotes[`${prefix}_jpy`] = null; delete f.quotes[`${prefix}_scope`];
    assert.deepEqual(await check(f), []);
  });
}

test('unapproved candidate passes with verified hash', async () => {
  const f = await fixture(); f.release.candidate_files = [await file(f)];
  assert.deepEqual(await check(f), []);
});
test('null current lid designation passes', async () => {
  const f = await fixture();
  assert.equal(f.release.current_lid_manufacturing, null);
  assert.deepEqual(await check(f), []);
});
for (const [name, value] of [['path string', 'engineering/candidate/missing.step'], ['number', 12345]]) {
  test(`invalid current lid designation ${name} fails`, async () => {
    const f = await fixture(); f.release.candidate_files = [];
    f.release.current_lid_manufacturing = value;
    assert.match((await check(f)).join('\n'), /current_lid_manufacturing.*オブジェクト/);
  });
}
test('unregistered current lid candidate ID fails', async () => {
  const f = await fixture();
  const candidate = await lidCandidate(f, 'plate'); f.release.candidate_files = [candidate];
  f.release.current_lid_manufacturing = { model: '7u40', revision: 'R9', candidate_ids: ['LID-OTHER'] };
  assert.match((await check(f)).join('\n'), /不明なID LID-OTHER/);
});
test('valid unapproved lid designation may reference plate and frame candidates', async () => {
  const f = await fixture();
  const candidates = [await lidCandidate(f, 'plate'), await lidCandidate(f, 'frame')];
  f.release.candidate_files = candidates; designateLid(f, candidates);
  assert.equal(f.release.production_approved, false);
  assert.equal(f.spec.release_gate.approved_for_production, false);
  assert.ok(Object.values(f.spec.models).every(model => model.manufacturing_release === null));
  assert.ok(f.gates.every(gate => gate.status === 'open'));
  assert.deepEqual(await check(f), []);
});
test('lid model sets match across order and singular/array representations', async () => {
  const f = await fixture();
  const candidate = await lidCandidate(f, 'multi');
  delete candidate.model; candidate.models = ['7u60', '7u40'];
  f.release.candidate_files = [candidate];
  f.release.current_lid_manufacturing = { models: ['7u40', '7u60'], revision: 'R9', candidate_ids: [candidate.id] };
  assert.deepEqual(await check(f), []);

  const g = await fixture();
  const singular = await lidCandidate(g, 'singular'); g.release.candidate_files = [singular];
  g.release.current_lid_manufacturing = { models: ['7u40'], revision: 'R9', candidate_ids: [singular.id] };
  assert.deepEqual(await check(g), []);
});
for (const [name, candidateOverrides, designationOverrides, pattern] of [
  ['wrong model', {}, { model: '7u60' }, /model\/modelsが指定と不一致/],
  ['wrong revision', {}, { revision: 'R10' }, /revisionが指定と不一致/],
  ['wrong component', { component: 'body' }, {}, /componentはlidが必要/],
]) {
  test(`current lid candidate with ${name} fails`, async () => {
    const f = await fixture();
    const candidate = await lidCandidate(f, 'plate', candidateOverrides);
    f.release.candidate_files = [candidate];
    f.release.current_lid_manufacturing = {
      model: '7u40', revision: 'R9', candidate_ids: [candidate.id], ...designationOverrides,
    };
    assert.match((await check(f)).join('\n'), pattern);
  });
}
test('empty current lid candidate_ids fails', async () => {
  const f = await fixture();
  f.release.current_lid_manufacturing = { model: '7u40', revision: 'R9', candidate_ids: [] };
  assert.match((await check(f)).join('\n'), /candidate_idsは空でない一意/);
});
test('duplicate current lid candidate_ids fail', async () => {
  const f = await fixture();
  const candidate = await lidCandidate(f, 'plate'); f.release.candidate_files = [candidate];
  f.release.current_lid_manufacturing = { model: '7u40', revision: 'R9', candidate_ids: [candidate.id, candidate.id] };
  assert.match((await check(f)).join('\n'), /candidate_idsは空でない一意/);
});
for (const [name, candidateIds] of [['empty string', ['']], ['nonstring', [12345]]]) {
  test(`current lid candidate_ids rejects ${name}`, async () => {
    const f = await fixture();
    f.release.current_lid_manufacturing = { model: '7u40', revision: 'R9', candidate_ids: candidateIds };
    assert.match((await check(f)).join('\n'), /candidate_idsは空でない一意/);
  });
}
test('duplicate candidate file IDs fail', async () => {
  const f = await fixture();
  const first = await lidCandidate(f, 'plate');
  const second = await lidCandidate(f, 'frame', { id: first.id });
  f.release.candidate_files = [first, second]; designateLid(f, [first]);
  assert.match((await check(f)).join('\n'), /candidate_files.*idが重複/);
});
test('designated lid candidate still requires its registered file hash', async () => {
  const f = await fixture(); const candidate = await lidCandidate(f, 'plate');
  candidate.sha256 = '0'.repeat(64); f.release.candidate_files = [candidate]; designateLid(f, [candidate]);
  assert.match((await check(f)).join('\n'), /candidate_files.*ハッシュ不一致/);
});
for (const [name, mutate, pattern] of [
  ['both model fields in candidate metadata', candidate => candidate.models = ['7u40'], /candidate_files.*model\/models/],
  ['unknown model in candidate metadata', candidate => candidate.model = 'unknown', /candidate_files.*model\/models/],
  ['nonstring model in candidate metadata', candidate => candidate.model = 123, /candidate_files.*model\/models/],
]) {
  test(`${name} fails`, async () => {
    const f = await fixture(); const candidate = await lidCandidate(f, 'invalid'); mutate(candidate);
    f.release.candidate_files = [candidate];
    assert.match((await check(f)).join('\n'), pattern);
  });
}
for (const [name, value] of [['empty', ' '], ['nonstring', 12345]]) {
  test(`${name} candidate ID fails`, async () => {
    const f = await fixture(); const candidate = await lidCandidate(f, 'invalid', { id: value });
    f.release.candidate_files = [candidate];
    assert.match((await check(f)).join('\n'), /candidate_files.*idは空でない文字列が必要/);
  });
}
for (const [field, value, pattern] of [
  ['component', ' ', /componentが必要/], ['component', 123, /componentが必要/],
  ['revision', ' ', /revisionが必要/], ['revision', 123, /revisionが必要/],
]) {
  test(`ID-bearing candidate requires a non-empty string ${field}`, async () => {
    const f = await fixture(); const candidate = await lidCandidate(f, 'invalid', { [field]: value });
    f.release.candidate_files = [candidate];
    assert.match((await check(f)).join('\n'), pattern);
  });
}
for (const [name, designation, pattern] of [
  ['both model fields', candidate => ({ model: '7u40', models: ['7u40'], revision: 'R9', candidate_ids: [candidate.id] }), /current_lid_manufacturing.*model\/models/],
  ['unknown model', candidate => ({ model: 'unknown', revision: 'R9', candidate_ids: [candidate.id] }), /current_lid_manufacturing.*model\/models/],
]) {
  test(`current lid designation with ${name} fails`, async () => {
    const f = await fixture(); const candidate = await lidCandidate(f, 'valid');
    f.release.candidate_files = [candidate]; f.release.current_lid_manufacturing = designation(candidate);
    assert.match((await check(f)).join('\n'), pattern);
  });
}
for (const [field, pattern] of [['component', /componentが必要/], ['model', /model\/models/], ['revision', /revisionが必要/]]) {
  test(`ID-bearing candidate requires ${field}`, async () => {
    const f = await fixture(); const candidate = await lidCandidate(f, 'plate');
    delete candidate[field]; f.release.candidate_files = [candidate];
    assert.match((await check(f)).join('\n'), pattern);
  });
}
test('lid designation does not permit an unlisted engineering release file', async () => {
  const f = await fixture();
  const candidate = await lidCandidate(f, 'plate'); f.release.candidate_files = [candidate]; designateLid(f, [candidate]);
  await file(f, 'engineering/release/unlisted-lid.step');
  assert.match((await check(f)).join('\n'), /unlisted-lid.step/);
});
test('lid designation without an approval record cannot approve production', async () => {
  const f = await fixture();
  const candidate = await lidCandidate(f, 'plate'); f.release.candidate_files = [candidate]; designateLid(f, [candidate]);
  f.release.production_approved = true;
  assert.match((await check(f)).join('\n'), /approval_record/);
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
