import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const base = 'engineering/r9-fitfix-01', out = `${base}/out`, revision = 'R9-FITFIX-01';
const check = process.argv.includes('--check');
if (process.argv.slice(2).some(x => x !== '--check')) throw Error('Usage: node scripts/sync-fitfix.mjs [--check]');
const bytes = p => readFileSync(path.join(root,p));
const json = p => JSON.parse(bytes(p));
const hash = b => createHash('sha256').update(b).digest('hex');
const encode = x => JSON.stringify(x,null,2)+'\n';
function put(p,b) {
  if (check) { if (!bytes(p).equals(Buffer.from(b))) throw Error(`Fitfix drift: ${p}`); }
  else { mkdirSync(path.dirname(path.join(root,p)),{recursive:true}); writeFileSync(path.join(root,p),b); }
}
const manifest=json(`${out}/outputs-manifest.json`), validation=json(`${out}/validation.json`), env=json(`${out}/environment.json`);
if (manifest.revision !== revision || manifest.production_approved !== false || validation.passed !== true || !validation.reference_hardware_included || !env.repository_python_cq_range_compatible) throw Error('Full locked-compatible unapproved generation required');
const parity=json(`${base}/verification/body-patterns.json`);
if (parity.passed !== true || parity.patterns.length !== 3 || parity.patterns.some(p=>!p.matched)) throw Error('Body DXF parity required');
for(const row of parity.patterns) for(const f of [row.upstream,row.fixed]) if(hash(bytes(f.path))!==f.sha256) throw Error(`Stale parity evidence: ${f.path}`);
for (const f of manifest.inputs) if(hash(bytes(`${base}/${f.path}`))!==f.sha256) throw Error(`Stale generator: ${f.path}`);
let artifacts=[], candidates=[];
function register(p,b,component) {
  if(b.length>25*1024*1024) throw Error(`Artifact exceeds 25 MiB: ${p}`);
  const sha256=hash(b); artifacts.push({path:p,bytes:b.length,sha256,status:'candidate-not-approved'});
  if(component) candidates.push({id:`R9F-${p.replace(/[^a-z0-9]+/gi,'-').toUpperCase()}`,component,model:'7u40',revision,path:p,sha256});
}
for(const f of manifest.files) {
  const p=`${out}/${f.path}`, b=bytes(p);
  if(b.length!==f.bytes || hash(b)!==f.sha256) throw Error(`Changed output: ${p}`);
  const geometry=/\.(stl|step|dxf)$/.test(p);
  const component= !geometry || f.path.startsWith('assembly/') ? null : f.path.startsWith('coupons/')?'coupon': f.path.includes('/lid/')||/^aluminum\/t1p/.test(f.path)?'lid':f.path.includes('/guards/')?'guard':'body-plate';
  register(p,b,component);
  if(f.path==='preview.html' || f.path.endsWith('.zip')) {
    const pub=f.path==='preview.html'?'public/previews/r9-fitfix-01.html':`public/downloads/candidate/r9-fitfix-01-${f.path}`;
    put(pub,b); register(pub,b,f.path.endsWith('.zip')?'package':'preview');
  }
}
register(`${out}/outputs-manifest.json`,bytes(`${out}/outputs-manifest.json`));
register(`${out}/environment.json`,bytes(`${out}/environment.json`));
const release=json('project/release-state.json');
release.candidate_files=[...release.candidate_files.filter(x=>x.revision!==revision),...candidates];
release.candidate_revision=revision;
release.current_body_geometry=`R6 nominal for 3u60/7u60; ${revision} unapproved candidate for 7u40`;
release.current_lid_manufacturing={model:'7u40',revision,candidate_ids:candidates.filter(x=>x.component==='lid').map(x=>x.id)};
release.warning=`${revision} is an unapproved 7u40 candidate. R9-PROTOTYPE-01 is retained as history. No approved manufacturing release.`;
put('project/release-state.json',encode(release));
const ledger=json('project/artifact-manifest.json');
const remainingArtifacts=new Map(artifacts.map(x=>[x.path,x]));
ledger.files=ledger.files.flatMap(x=>{
  const owned=x.path.startsWith(`${out}/`)||x.path.includes('/r9-fitfix-01');
  if(!owned) return [x];
  const replacement=remainingArtifacts.get(x.path);
  remainingArtifacts.delete(x.path);
  return replacement ? [replacement] : [];
});
ledger.files.push(...remainingArtifacts.values());
put('project/artifact-manifest.json',encode(ledger));
const spec=json('project/current-spec.json'), model=spec.models['7u40'];
model.candidate_revision=revision;
model.candidate_interface={};
model.candidate_guard_summary={};
const bom=json(`${out}/BOM.json`);
for(const tag of ['t1p2','t1p0']) {
  const guards=bom.filter(x=>x.variant===tag&&x.group==='guard');
  model.candidate_guard_summary[tag]={count:guards.reduce((n,x)=>n+x.per_set_quantity,0),volume_cm3:guards.reduce((n,x)=>n+x.volume_mm3*x.per_set_quantity/1000,0)};
}
for(const tag of ['t1p2','t1p0']) model.candidate_interface[tag]=json(`${out}/interface-${tag}.json`);
const labels={
  '7u40-t1p2-aluminum-NOT-APPROVED.zip':'アルミ本体＋天板（1.2mm用）',
  '7u40-t1p0-aluminum-NOT-APPROVED.zip':'アルミ本体＋天板（1.0mm用）',
  '7u40-t1p2-pa12-NOT-APPROVED.zip':'PA12ガード＋蓋枠（1.2mm）',
  '7u40-t1p0-pa12-NOT-APPROVED.zip':'PA12ガード＋蓋枠（1.0mm）',
  'fit-coupons-pa12-NOT-APPROVED.zip':'PA12試験片',
  'fit-coupons-metal-NOT-APPROVED.zip':'アルミ試験片',
};
model.candidate_links=candidates.filter(x=>['preview','package'].includes(x.component)).map(x=>({path:x.path.replace(/^public/,''),label:x.component==='preview'?'R9-FITFIX-01プレビュー':labels[path.basename(x.path).replace('r9-fitfix-01-','')]}));
model.candidate_bom_path=`${out}/BOM.json`;
put('project/current-spec.json',encode(spec));
console.log(`Fitfix ${check?'verified':'synchronized'}: ${candidates.length} candidates, ${artifacts.length} artifacts.`);
