import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const base=new URL('../engineering/r9-fitfix-01/',import.meta.url);
const context=vm.createContext({window:{},console});
vm.runInContext(readFileSync(new URL('vendor/three-bundle.js',base),'utf8'),context);
const T=context.window.THREE;
context.T=T;
const template=readFileSync(new URL('fitfix/preview.py',base),'utf8');
const fn=template.slice(template.indexOf('function pcbFaceColors('),template.indexOf('function make('));
vm.runInContext(fn,context);
const scene=JSON.parse(readFileSync(new URL('out/scene.json',base)));
for(const part of scene.reference.filter(p=>p.group==='pcb')) test(`${part.id}: actual assembly side planes and cut faces`,()=>{
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(part.positions,3));g.setIndex(part.indices);
 const flat=g.toNonIndexed();flat.computeBoundingBox();context.pcbFaceColors(part,flat);
 const p=flat.attributes.position,c=flat.attributes.color;
 const side=Math.sign(flat.boundingBox.min.x);const min=flat.boundingBox.min.x,max=flat.boundingBox.max.x;
 const bins={inside:0,outside:0,edge:0};
 for(let i=0;i<p.count;i+=3){
  const x=[p.getX(i),p.getX(i+1),p.getX(i+2)];
  const plane=x.every(v=>v===x[0]);
  const outward=plane&&x[0]===(side>0?max:min);
  const inward=plane&&x[0]===(side>0?min:max);
  const kind=outward?'outside':inward?'inside':'edge';bins[kind]++;
  const black=part.id.startsWith('fixer-')?outward:inward;
  const expected=new T.Color(black?0x171b1e:0xbfc5ca);
  for(let j=0;j<3;j++)for(const [k,v] of [expected.r,expected.g,expected.b].entries())assert.ok(Math.abs(c.array[(i+j)*3+k]-v)<1e-7,`${kind} RGB ${k}`);
 }
 assert.ok(bins.inside>0&&bins.outside>0&&bins.edge>0);
 // Material conversion retains every source triangle exactly, including hole walls.
 for(let i=0;i<part.indices.length;i++)for(let a=0;a<3;a++)assert.equal(p.array[i*3+a],Math.fround(part.positions[part.indices[i]*3+a]));
});

test('published HTML reproduces from retained scene and current presentation source',async()=>{
 const {execFileSync}=await import('node:child_process');
 const {mkdtempSync,rmSync}=await import('node:fs');
 const {tmpdir}=await import('node:os');const {join}=await import('node:path');const {fileURLToPath}=await import('node:url');
 const dir=mkdtempSync(join(tmpdir(),'fitfix-material-'));
 try{
  const output=join(dir,'preview.html');
  execFileSync('python3',['-c',"import json,sys;from pathlib import Path;r=Path(sys.argv[1]);sys.path.insert(0,str(r));from fitfix.preview import make_preview;make_preview(json.loads((r/'out/scene.json').read_text()),r/'vendor/three-bundle.js',sys.argv[2])",fileURLToPath(base),output]);
  const expected=readFileSync(output);
  assert.ok(expected.equals(readFileSync(new URL('out/preview.html',base))));
  assert.ok(expected.equals(readFileSync(new URL('../public/previews/r9-fitfix-01.html',import.meta.url))));
 }finally{rmSync(dir,{recursive:true,force:true})}
});

test('anodizing consumer provenance and embedded manifests match current sources',async()=>{
 const {execFileSync}=await import('node:child_process');const {fileURLToPath}=await import('node:url');
 execFileSync('python3',['-c',`import json,hashlib,zipfile,sys
from pathlib import Path
repo=Path(sys.argv[1]);out=repo/'engineering/r9-anodizing-01/out'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((out/'manifest.json').read_text())
for row in manifest['inputs']+manifest['original_inputs_verified_against_pinned_commit']:assert digest(repo/row['path'])==row['sha256'],row['path']
for row in json.loads((out/'checksums.json').read_text())['files']:assert digest(out/row['path'])==row['sha256'],row['path']
for archive in out.glob('*.zip'):
 with zipfile.ZipFile(archive) as z:assert z.read('manifest.json')==(out/'manifest.json').read_bytes()
`,fileURLToPath(new URL('../',import.meta.url))]);
});
