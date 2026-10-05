const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),repo=path.resolve(root,'../../..'),{M,G}=require('../load.cjs');
function inventory(dir){const out={};function walk(d){for(const f of fs.readdirSync(d,{withFileTypes:true})){if(['.venv','node_modules','__pycache__'].includes(f.name))continue;const p=path.join(d,f.name);if(f.isDirectory())walk(p);else out[path.relative(dir,p)]=crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}}walk(dir);return out;}
test('two clean generations agree, manifest covers payloads, GLBs reload correct metre/Y bounds, source is unchanged',()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'tw-build-')),before=inventory(root);
 try{
  const a=path.join(tmp,'a'),b=path.join(tmp,'b');for(const out of [a,b])cp.execFileSync(process.execPath,[path.join(root,'build.cjs'),'--out',out]);
  const portable=path.join(tmp,'portable');cp.execFileSync('python3',['-m','zipfile','-e',path.join(a,'public/downloads/studies/two-way/source-TW-01.zip'),portable]);
  cp.execFileSync(process.execPath,['--test',path.join(portable,'engineering/two-way/tw-01/tests/contracts.test.cjs')]);
  cp.execFileSync(process.execPath,[path.join(portable,'engineering/two-way/tw-01/build.cjs'),'--out',path.join(tmp,'portable-build')]);
  assert.deepEqual(inventory(a),inventory(path.join(tmp,'portable-build')));
  assert.deepEqual(inventory(a),inventory(b));assert.deepEqual(inventory(root),before);
  const manifest=JSON.parse(fs.readFileSync(path.join(a,'project/two-way/artifact-manifest.json')));assert.equal(manifest.manufacturingApproved,false);
  for(const artifact of manifest.artifacts){const raw=fs.readFileSync(path.join(a,artifact.path));assert.equal(raw.length,artifact.bytes);assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),artifact.sha256);assert.ok(raw.length<25*1024*1024);
   if(!artifact.path.endsWith('.glb'))continue;
   assert.equal(raw.readUInt32LE(0),0x46546c67);assert.equal(raw.readUInt32LE(8),raw.length);const jl=raw.readUInt32LE(12),doc=JSON.parse(raw.subarray(20,20+jl).toString()),dataStart=28+jl;
   assert.equal(doc.extras.manufacturingApproved,false);assert.equal(doc.extras.upAxis,'Y');
   const filename=path.basename(artifact.path),letter=filename[0],pose=filename.includes('-frame-')?'frame':'play',preset=Object.values(M.presets).find(p=>p.letter===letter),s={...M.defaults,preset:preset.id,baseDepth:preset.baseDepth,lidDepth:preset.lidDepth,pose},g=G.buildGeometry(s,M.dimensions(s));
   assert.equal(doc.meshes.length,pose==='frame'?1:3);
   for(const mesh of doc.meshes){const accessor=doc.accessors[mesh.primitives[0].attributes.POSITION],view=doc.bufferViews[accessor.bufferView],lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity],expectedLo=[Infinity,Infinity,Infinity],expectedHi=[-Infinity,-Infinity,-Infinity];
    assert.equal(accessor.count,g[mesh.name].v.length/9);
    for(let i=0;i<accessor.count;i++)for(let axis=0;axis<3;axis++){const v=raw.readFloatLE(dataStart+view.byteOffset+(i*3+axis)*4);assert.ok(Number.isFinite(v));lo[axis]=Math.min(lo[axis],v);hi[axis]=Math.max(hi[axis],v);}
    const vals=g[mesh.name].v;for(let i=0;i<vals.length;i+=9){let p=vals.slice(i,i+3);if(mesh.name==='lid')p=M.lidPoint(p,s,M.dimensions(s));const pos=[p[0]/1000,p[2]/1000,-p[1]/1000];pos.forEach((v,j)=>{expectedLo[j]=Math.min(expectedLo[j],v);expectedHi[j]=Math.max(expectedHi[j],v);});}
    lo.forEach((v,j)=>assert.ok(Math.abs(v-expectedLo[j])<1e-6));hi.forEach((v,j)=>assert.ok(Math.abs(v-expectedHi[j])<1e-6));
   }
  }
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
