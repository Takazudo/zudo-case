import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, cpSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
const root = new URL('../', import.meta.url).pathname;

test('lid M5 check rejects changed CAD, public copy, generator and designation drift; fitfix check still passes', () => {
  const tmp = mkdtempSync(path.join(tmpdir(), 'lid-m5-ledger-'));
  try {
    for (const p of ['scripts/sync-lid-m5.mjs', 'scripts/sync-fitfix.mjs', 'project/current-spec.json', 'project/release-state.json',
      'project/artifact-manifest.json', 'engineering/r9-lid-m5-01', 'engineering/r9-fitfix-01', 'engineering/r9-anodizing-01/parameters.json',
      'engineering/r9-prototype-01/uv.lock', 'engineering/r9-prototype-01/out/aluminum', 'public/previews/r9-fitfix-01.html',
      'public/previews/r9-lid-m5-01.html', 'public/downloads/candidate']) {
      mkdirSync(path.dirname(path.join(tmp, p)), { recursive: true });
      cpSync(path.join(root, p), path.join(tmp, p), { recursive: true, filter: p => !p.includes('__pycache__') });
    }
    const run = script => spawnSync(process.execPath, [script, '--check'], { cwd: tmp, encoding: 'utf8' });
    let result = run('scripts/sync-lid-m5.mjs'); assert.equal(result.status, 0, result.stderr);
    result = run('scripts/sync-fitfix.mjs'); assert.equal(result.status, 0, result.stderr);
    const manifest = JSON.parse(readFileSync(path.join(tmp, 'engineering/r9-lid-m5-01/out/outputs-manifest.json')));
    for (const p of [
      `engineering/r9-lid-m5-01/out/${manifest.files.find(x => x.path.endsWith('.stl')).path}`,
      `engineering/r9-lid-m5-01/out/${manifest.files.find(x => x.path.endsWith('.dxf')).path}`,
      'public/previews/r9-lid-m5-01.html',
      'engineering/r9-lid-m5-01/parameters.json',
      'engineering/r9-lid-m5-01/lidm5/geometry.py',
      'engineering/r9-fitfix-01/fitfix/geometry.py',
    ]) {
      const full = path.join(tmp, p), original = readFileSync(full);
      writeFileSync(full, Buffer.concat([original, Buffer.from('\nchanged')]));
      assert.notEqual(run('scripts/sync-lid-m5.mjs').status, 0, p);
      assert.equal(readFileSync(full).length, original.length + 8, 'check must not repair mutation');
      writeFileSync(full, original);
    }
    const full = path.join(tmp, 'project/release-state.json'), original = readFileSync(full);
    const state = JSON.parse(original); state.current_lid_manufacturing.revision = 'R9-LID-M5-01';
    writeFileSync(full, JSON.stringify(state, null, 2) + '\n'); assert.notEqual(run('scripts/sync-lid-m5.mjs').status, 0);
    const approved = JSON.parse(original); approved.lid_revision_candidates[0].production_approved = true;
    writeFileSync(full, JSON.stringify(approved, null, 2) + '\n'); assert.notEqual(run('scripts/sync-lid-m5.mjs').status, 0);
  } finally { rmSync(tmp, { recursive: true, force: true }); }
});
