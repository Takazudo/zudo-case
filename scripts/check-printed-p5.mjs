import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
export function verifyP5(root){
 const read=p=>JSON.parse(readFileSync(resolve(root,p)));
 const registry=read('project/printed-5mm/p5-tab-joints/files.json');
 assert.equal(registry.revision,'P5-PRINTED-5MM-TAB-JOINTS-J3');
 assert.deepEqual(registry.print_parts,{structural:12,optional_types:3});
 assert.deepEqual(registry.optional_quantities,{'pad-horizontal':48,'pad-vertical':48,'washer-round':28});
 const release=read('project/release-state.json');
 assert.equal(release.current_printed_5mm_candidate.revision,registry.revision);
 assert.equal(release.current_printed_5mm_candidate.production_approved,false);
 for(const f of registry.files){
  const bytes=readFileSync(resolve(root,f.path));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),f.sha256,`Changed P5 ${f.path}`);
  assert.equal(bytes.length,f.bytes);assert.ok(bytes.length<25*1024*1024);
 }
 const baseline=read('engineering/printed-5mm/p5-tab-joints/reference/P5-BASELINE.json');
 for(const f of baseline.files)assert.equal(createHash('sha256').update(readFileSync(resolve(root,f.path))).digest('hex'),f.sha256,`Protected P5 baseline ${f.path}`);
 for(const [name,count] of [['stl',15],['body',6]]){
  const path=`public/downloads/candidate/printed-5mm-p5-tab-joints-${name}.zip`;
  assert.ok(registry.files.some(f=>f.path===path));
  const names=execFileSync('unzip',['-Z1',resolve(root,path)],{encoding:'utf8'}).trim().split('\n');
  assert.equal(names.length,new Set(names).size);
  assert.equal(names.filter(n=>n.endsWith('.stl')).length,count);
  assert.equal(names.filter(n=>n.endsWith('.step')).length,count);
 }
 const mapping=read('engineering/printed-5mm/p5-tab-joints/out/PRINT-MAPPING.json');
 assert.equal(mapping.length,30);
 assert.equal(mapping.filter(r=>r.unchanged_bytes).length,18);
 for(const row of mapping)assert.equal(row.unchanged_bytes,!row.part.startsWith('wall-')&&!row.part.startsWith('floor-'));
 const projects=read('engineering/printed-5mm/p5-h2d-3mf/out/PROJECTS.json');
 assert.equal(projects.unsliced,true);assert.equal(projects.projects.length,15);
 for(const p of projects.projects){assert.equal(p.brim_mm,0);assert.equal(p.additional_rotation_degrees,0);}
 console.log(`P5 registry: ${registry.files.length} files; 6 changed body pieces, 9 unchanged types`);
}
