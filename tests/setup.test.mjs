import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, access, rm } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { integrateScaffold } from '../scripts/setup.mjs';
const save=async(p,s)=>{await mkdir(path.dirname(p),{recursive:true});await writeFile(p,s);};
const exists=async p=>{try{await access(p);return true;}catch{return false;}};
async function fixture(t){
 const tmp=await mkdtemp(path.join(tmpdir(),'zudo-doc-test-'));t.after(()=>rm(tmp,{recursive:true,force:true}));
 const root=path.join(tmp,'authored'),scaffold=path.join(tmp,'official-mock');
 await save(path.join(root,'package.json'),JSON.stringify({name:'zudo-case-doc',type:'module',private:true,scripts:{dev:'placeholder',build:'placeholder'}}));
 await save(path.join(root,'zfb.config.ts'),'AUTHORED CONFIG');
 await save(path.join(root,'src/content/docs/overview/start.mdx'),'AUTHORED CONTENT');
 await save(path.join(root,'public/evidence.txt'),'USER ASSET');
 await save(path.join(scaffold,'package.json'),JSON.stringify({name:'temporary',private:true,type:'module',scripts:{dev:'zfb dev',build:'zfb build'},dependencies:{'@takazudo/zudo-doc':'MOCK_VERSION','zfb':'MOCK_VERSION'}}));
 await save(path.join(scaffold,'zfb.config.ts'),'SCAFFOLD CONFIG');
 await save(path.join(scaffold,'src/pages/index.tsx'),'SCAFFOLD ROUTE');
 await save(path.join(scaffold,'src/content/docs/start.mdx'),'STARTER CONTENT');
 await save(path.join(scaffold,'README.md'),'SCAFFOLD README');
 await save(path.join(scaffold,'pnpm-lock.yaml'),'STALE LOCK');
 return {root,scaffold};
}
test('mock scaffold: framework only; preserve MDX/config/assets; use generated versions',async t=>{
 const {root,scaffold}=await fixture(t);await integrateScaffold(root,scaffold,{mode:'test-mock'});
 assert.equal(await readFile(path.join(root,'zfb.config.ts'),'utf8'),'AUTHORED CONFIG');
 assert.equal(await readFile(path.join(root,'src/content/docs/overview/start.mdx'),'utf8'),'AUTHORED CONTENT');
 assert.equal(await readFile(path.join(root,'public/evidence.txt'),'utf8'),'USER ASSET');
 assert.equal(await readFile(path.join(root,'src/pages/index.tsx'),'utf8'),'SCAFFOLD ROUTE');
 assert.equal(await exists(path.join(root,'src/content/docs/start.mdx')),false);
 assert.equal(await exists(path.join(root,'pnpm-lock.yaml')),false);
 const pkg=JSON.parse(await readFile(path.join(root,'package.json')));
 assert.equal(pkg.dependencies['@takazudo/zudo-doc'],'MOCK_VERSION');assert.equal(pkg.scripts.build,'zfb build');
 assert.equal(pkg.scripts['check:assets'],'node scripts/verify-assets.mjs');assert.equal(pkg.name,'zudo-case-doc');
 const record=JSON.parse(await readFile(path.join(root,'.handoff/setup-record.json')));
 assert.equal(record.actualBuildVerified,false);assert.equal(record.dependenciesInstalled,false);
});
test('collision is detected before copying',async t=>{
 const {root,scaffold}=await fixture(t);await save(path.join(root,'src/pages/index.tsx'),'EXISTING ROUTE');
 await assert.rejects(integrateScaffold(root,scaffold),/衝突/);
 assert.equal(await readFile(path.join(root,'src/pages/index.tsx'),'utf8'),'EXISTING ROUTE');
 assert.equal(await exists(path.join(root,'.handoff/setup-record.json')),false);
 assert.equal(JSON.parse(await readFile(path.join(root,'package.json'))).scripts.dev,'placeholder');
});
test('already integrated project is not overwritten',async t=>{
 const {root,scaffold}=await fixture(t);await integrateScaffold(root,scaffold);
 await assert.rejects(integrateScaffold(root,scaffold),/初期化済み/);
});
test('non-zudo-doc input is rejected',async t=>{
 const {root,scaffold}=await fixture(t);await writeFile(path.join(scaffold,'package.json'),JSON.stringify({scripts:{dev:'x',build:'x'}}));
 await assert.rejects(integrateScaffold(root,scaffold),/公式scaffold/);
 assert.equal(await exists(path.join(root,'src/pages/index.tsx')),false);
});
test('copy failure rolls back newly copied paths and package',async t=>{
 const {root,scaffold}=await fixture(t);await rm(path.join(scaffold,'zfb.config.ts'));
 await assert.rejects(integrateScaffold(root,scaffold));
 assert.equal(await exists(path.join(root,'src/pages/index.tsx')),false);
 assert.equal(JSON.parse(await readFile(path.join(root,'package.json'))).scripts.dev,'placeholder');
});
