import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, cpSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
const root = new URL('../',import.meta.url).pathname;

test('fitfix check rejects changed CAD, public copy, generator, parity and active designation without writing', () => {
  const tmp=mkdtempSync(path.join(tmpdir(),'fitfix-ledger-'));
  try {
    for(const p of ['scripts/sync-fitfix.mjs','project/current-spec.json','project/release-state.json','project/artifact-manifest.json','engineering/r9-fitfix-01','engineering/r9-prototype-01/uv.lock','engineering/r9-prototype-01/out/aluminum','public/previews/r9-fitfix-01.html','public/downloads/candidate']) {
      mkdirSync(path.dirname(path.join(tmp,p)),{recursive:true});
      cpSync(path.join(root,p),path.join(tmp,p),{recursive:true,filter:p=>!p.includes('__pycache__')});
    }
    const run=()=>spawnSync(process.execPath,['scripts/sync-fitfix.mjs','--check'],{cwd:tmp,encoding:'utf8'});
    let result=run(); assert.equal(result.status,0,result.stderr);
    const manifest=JSON.parse(readFileSync(path.join(tmp,'engineering/r9-fitfix-01/out/outputs-manifest.json')));
    for(const p of [
      `engineering/r9-fitfix-01/out/${manifest.files.find(x=>x.path.endsWith('.stl')).path}`,
      'public/previews/r9-fitfix-01.html',
      'engineering/r9-fitfix-01/parameters.json',
      'engineering/r9-prototype-01/out/aluminum/7u40-r9-al-bottom-qty1-mm.dxf',
    ]) {
      const full=path.join(tmp,p), original=readFileSync(full);
      writeFileSync(full,Buffer.concat([original,Buffer.from('\nchanged')]));
      assert.notEqual(run().status,0,p);
      assert.equal(readFileSync(full).length,original.length+8,'check must not repair mutation');
      writeFileSync(full,original);
    }
    const full=path.join(tmp,'project/release-state.json');
    const state=JSON.parse(readFileSync(full)); state.current_lid_manufacturing.revision='R9-PROTOTYPE-01';
    writeFileSync(full,JSON.stringify(state)); assert.notEqual(run().status,0);
  } finally { rmSync(tmp,{recursive:true,force:true}); }
});
