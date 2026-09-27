/**
 * 台帳の状態契約。未見積の価格は null とし、0 で代用しない。現行価格には、
 * 実在する根拠ファイル、対象機種・版・数量・通貨・税送料条件、行合計を持つ
 * 実見積だけを使う。助手の旧概算は現行価格の根拠にならない。
 * 製作候補は path と SHA-256 で登録できるが、承認とは別状態。
 * 承認には承認者・日付・承認ファイルのハッシュ、G01〜G11 の完了根拠、
 * release-state・release_gate・機種別台帳の一致が必要。
 * release/ の実ファイルは承認済み一覧とハッシュが一致するときだけ許す。
 * この検査は台帳とバイト同一性の確認であり、製造適合や現物試験ではない。
 */
import { createHash } from 'node:crypto';
import { readFile, readdir, realpath } from 'node:fs/promises';
import path from 'node:path';

const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const money = value => Number.isSafeInteger(value) && value >= 0;
const modelsOf = value => value?.model ? [value.model] : Array.isArray(value?.models) ? value.models : [];
const scopeKey = value => JSON.stringify({ models: [...modelsOf(value)].sort(), revision: value?.revision });
const isHash = value => typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value);
const releasePath = 'engineering/release';

/** Validate a repository-relative evidence path and read its bytes without escaping root. */
async function bytesAt(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) return null;
  const full = path.resolve(root, relative);
  if (!full.startsWith(path.resolve(root) + path.sep)) return null;
  try {
    const resolvedRoot = await realpath(root), resolvedFile = await realpath(full);
    if (!resolvedFile.startsWith(resolvedRoot + path.sep)) return null;
    return await readFile(resolvedFile);
  } catch { return null; }
}

/** Check quote, candidate, approval, and cross-ledger transitions. Returns Japanese error messages. */
export async function checkProjectState({ root, spec, release, quotes, gates }) {
  const errors = [];
  const fail = message => errors.push(message);
  const fields = [
    ['current_total_jpy', 'current_total_scope', 'total'],
    ['current_lid_price_jpy', 'current_lid_price_scope', 'lid'],
    ['current_band_price_jpy', 'current_band_price_scope', 'band'],
  ];
  const qualifying = { total: [], lid: [], band: [] };
  for (const record of quotes.records ?? []) {
    if (Array.isArray(record.rows) && money(record.total_jpy) && record.rows.every(row => money(row.row_jpy)) &&
      record.rows.reduce((sum, row) => sum + row.row_jpy, 0) !== record.total_jpy) fail(`見積 ${record.id ?? '(IDなし)'}: 行合計とtotal_jpyが不一致`);
    if (record.applies_to_current_release !== true) continue;
    const label = `見積 ${record.id ?? '(IDなし)'}`;
    if (!['supplier_quote', 'user_quote_screenshot'].includes(record.kind)) {
      fail(`${label}: 現行価格に旧概算・未確認記録を使えません`); continue;
    }
    if (!Object.hasOwn(qualifying, record.component)) { fail(`${label}: componentが不正`); continue; }
    let valid = true;
    const requireField = (condition, field) => { if (!condition) { fail(`${label}: ${field}が必要`); valid = false; } };
    const models = modelsOf(record);
    requireField(models.length > 0 && models.every(x => typeof x === 'string' && Object.hasOwn(spec.models, x)) && new Set(models).size === models.length, 'model/models');
    requireField(typeof record.revision === 'string' && record.revision.trim().length > 0, 'revision');
    requireField(Number.isSafeInteger(record.quantity) && record.quantity > 0, 'quantity');
    requireField(record.currency === quotes.currency && typeof record.currency === 'string', 'currency');
    requireField(typeof record.tax_status === 'string' && record.tax_status.trim().length > 0, 'tax_status');
    requireField(typeof record.shipping_included === 'boolean', 'shipping_included');
    requireField(await bytesAt(root, record.source) !== null, 'source');
    requireField(Array.isArray(record.rows) && record.rows.length > 0 && record.rows.every(row => money(row.row_jpy)), 'rows[].row_jpy');
    requireField(money(record.total_jpy) && Array.isArray(record.rows) && record.rows.reduce((sum, row) => sum + row.row_jpy, 0) === record.total_jpy, 'total_jpy/行合計');
    if (valid) qualifying[record.component].push(record);
  }
  for (const [amountField, scopeField, component] of fields) {
    const amount = quotes[amountField], scope = quotes[scopeField];
    if (amount === null) {
      if (qualifying[component].length) fail(`${amountField}: 有効な現行見積があるため合計を記録してください`);
      if (scope != null) fail(`${scopeField}: 価格がnullなら範囲もnullにしてください`);
      continue;
    }
    if (!money(amount) || amount === 0) fail(`${amountField}: 正の円額が必要（未見積はnull）`);
    if (!isObject(scope) || !modelsOf(scope).length || typeof scope.revision !== 'string' || !scope.revision.trim()) {
      fail(`${amountField}: ${scopeField}に機種と版が必要`); continue;
    }
    const matching = qualifying[component].filter(record => scopeKey(record) === scopeKey(scope));
    if (!matching.length || matching.length !== qualifying[component].length || matching.reduce((sum, record) => sum + record.total_jpy, 0) !== amount) {
      fail(`${amountField}: 同じ機種・版の有効な見積行合計と一致しません`);
    }
  }

  const approved = release.production_approved === true;
  if (typeof release.production_approved !== 'boolean') fail('release-state.production_approvedは真偽値が必要');
  if (spec.release_gate?.approved_for_production !== release.production_approved) fail('release_gateとrelease-stateの製造承認状態が不一致');
  for (const [model, data] of Object.entries(spec.models ?? {})) {
    if (approved ? typeof data.manufacturing_release !== 'string' || !data.manufacturing_release.trim() || data.manufacturing_release !== release.approval_record?.model_revisions?.[model] : data.manufacturing_release !== null) {
      fail(`${model}: manufacturing_releaseと製造承認状態が不一致`);
    }
  }
  const stl = spec.release_gate?.approved_stl_files, dxf = spec.release_gate?.approved_dxf_files;
  if (!Array.isArray(stl) || !Array.isArray(dxf)) fail('release_gate: 承認済みファイル一覧は配列が必要');
  else if (!approved && (stl.length || dxf.length)) fail('release_gate: 未承認時はSTL/DXF一覧を空にしてください');
  if (spec.release_gate?.latest_preview_is_manufacturing_data !== false) {
    fail('release_gate: R8プレビューを製作データとして扱えません');
  }
  const candidate = release.candidate_files ?? [];
  const published = release.published_release_files ?? [];
  if (!Array.isArray(candidate) || !Array.isArray(published)) fail('candidate_files/published_release_filesは配列が必要');
  const checked = async (entries, label) => {
    const seen = new Set();
    for (const entry of entries) {
      if (!isObject(entry) || typeof entry.path !== 'string' || !isHash(entry.sha256)) { fail(`${label}: pathとsha256が必要`); continue; }
      if (seen.has(entry.path)) fail(`${label}: 重複 ${entry.path}`);
      seen.add(entry.path);
      const bytes = await bytesAt(root, entry.path);
      if (!bytes || createHash('sha256').update(bytes).digest('hex') !== entry.sha256.toLowerCase()) fail(`${label}: ファイルなし・ハッシュ不一致 ${entry.path}`);
    }
  };
  if (Array.isArray(candidate)) await checked(candidate, 'candidate_files');
  if (Array.isArray(published)) await checked(published, 'published_release_files');
  if (!approved && Array.isArray(published) && published.length) fail('published_release_files: 製造承認が必要');
  const approval = release.approval_record;
  if (approved) {
    if (!isObject(approval) || !isObject(approval.model_revisions) || typeof approval.approver !== 'string' || !approval.approver.trim() ||
      typeof approval.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(approval.date) ||
      !Array.isArray(approval.approved_files) || !approval.approved_files.length) fail('approval_record: 承認者・日付・承認ファイル一覧が必要');
    else {
      await checked(approval.approved_files, 'approval_record.approved_files');
      const keyed = entries => entries.map(x => `${x.path}:${x.sha256}`).sort().join('|');
      if (!Array.isArray(published) || keyed(approval.approved_files) !== keyed(published)) fail('approval_recordとpublished_release_filesが不一致');
      const paths = new Set(Array.isArray(published) ? published.map(x => x.path) : []);
      for (const p of [...(stl ?? []), ...(dxf ?? [])]) if (!paths.has(p)) fail(`release_gate: 承認一覧にないファイル ${p}`);
    }
    const byId = new Map((gates ?? []).map(g => [g.id, g]));
    for (let i = 1; i <= 11; i++) {
      const id = `G${String(i).padStart(2, '0')}`, gate = byId.get(id);
      if (!gate || gate.status !== 'closed' || !isObject(gate.result) || typeof gate.result.summary !== 'string' || !gate.result.summary.trim() ||
        !Array.isArray(gate.result.evidence) || !gate.result.evidence.length ||
        !(await Promise.all(gate.result.evidence.map(item => bytesAt(root, item)))).every(Boolean)) fail(`${id}: closed・結果・実在する根拠ファイルが必要`);
    }
  } else if (approval != null) fail('approval_record: 未承認時に承認記録を置けません');
  async function inspectRelease(dir, relativeDir) {
    let entries;
    try { entries = await readdir(dir, { withFileTypes: true }); }
    catch { fail(`engineering/releaseが読めません: ${relativeDir}`); return; }
    for (const entry of entries) {
      const relative = `${relativeDir}/${entry.name}`;
      if (entry.isDirectory()) { await inspectRelease(path.join(dir, entry.name), relative); continue; }
      if (relative === `${releasePath}/README.md`) continue;
      if (!approved || !entry.isFile() || !listed.has(relative)) fail(`engineering/release: 未承認・未登録ファイル ${relative}`);
    }
  }
  const listed = new Set(Array.isArray(published) ? published.map(x => x.path) : []);
  await inspectRelease(path.join(root, releasePath), releasePath);
  if (approved && Array.isArray(published) && Array.isArray(stl) && Array.isArray(dxf)) {
    const expected = ext => published.filter(x => typeof x.path === 'string' && x.path.toLowerCase().endsWith(ext)).map(x => x.path).sort();
    if (JSON.stringify([...stl].sort()) !== JSON.stringify(expected('.stl')) || JSON.stringify([...dxf].sort()) !== JSON.stringify(expected('.dxf'))) fail('release_gate: STL/DXF一覧と公開ファイルが不一致');
  }
  if (Array.isArray(published)) for (const entry of published) {
    if (typeof entry.path !== 'string' || !entry.path.startsWith(`${releasePath}/`)) fail(`published_release_files: release/内のパスが必要 ${entry.path}`);
  }
  return errors;
}
