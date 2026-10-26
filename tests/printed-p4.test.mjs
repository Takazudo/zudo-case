import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,mkdirSync,copyFileSync,unlinkSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve,dirname} from 'node:path';
import {verifyPrinted} from '../scripts/check-printed-5mm.mjs';
const root=resolve(import.meta.dirname,'..');
const registryPath='project/printed-5mm/p4-uniform-vents/files.json';
const preservedPath='engineering/printed-5mm/p4-uniform-vents/reference/PRESERVATION.json';
const read=p=>JSON.parse(readFileSync(resolve(root,p)));
const current=read(registryPath),old=read('project/printed-5mm/files.json'),preserved=read(preservedPath);
function fixture(fn){const dir=mkdtempSync(resolve(tmpdir(),'p4-contract-'));try{
 const paths=new Set([...old.files,...current.files,...preserved.files].map(f=>f.path));
 for(const p of [registryPath,preservedPath,'project/printed-5mm/files.json','project/release-state.json','project/order-records/r10-fullset-01-jlc-cart-2026-10-26.json'])paths.add(p);
 for(const p of paths){mkdirSync(dirname(resolve(dir,p)),{recursive:true});copyFileSync(resolve(root,p),resolve(dir,p));}
 const write=(p,data)=>{unlinkSync(resolve(dir,p));writeFileSync(resolve(dir,p),typeof data==='string'?data:JSON.stringify(data));};fn(dir,write);
}finally{rmSync(dir,{recursive:true,force:true});}}
test('P4 full package and P3/R10 immutable records',()=>verifyPrinted(root));
test('reject P4 registry substituting P3 packages',()=>fixture((dir,write)=>{const r=structuredClone(current);r.files=r.files.map(f=>f.path.endsWith('-stl.zip')?old.files.find(f=>f.path.endsWith('-stl.zip')):f);write(registryPath,r);assert.throws(()=>verifyPrinted(dir));}));
test('reject stale current pointer',()=>fixture((dir,write)=>{const r=read('project/release-state.json');r.current_printed_5mm_candidate.revision=old.revision;write('project/release-state.json',r);assert.throws(()=>verifyPrinted(dir));}));
for(const path of ['engineering/printed-5mm/p3/source/parameters.json','engineering/printed-5mm/p3/out/stl/wall-left.stl','public/downloads/candidate/R10-FULLSET-01-aluminum.zip','project/order-records/r10-fullset-01-jlc-cart-2026-10-26.json']){
 test('reject protected byte change '+path,()=>fixture((dir,write)=>{write(path,'changed');assert.throws(()=>verifyPrinted(dir));}));
}
