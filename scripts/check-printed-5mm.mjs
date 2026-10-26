import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
export function verifyPrinted(root=resolve(import.meta.dirname,'..')) {
const currentPath='project/printed-5mm/p4-uniform-vents/files.json';
const current=JSON.parse(readFileSync(resolve(root,currentPath)));
assert.equal(current.revision,'P4-PRINTED-5MM-UNIFORM-VENTS');
assert.ok(current.files.some(f=>f.path==='public/downloads/candidate/printed-5mm-p4-uniform-vents-stl.zip'));
assert.ok(current.files.some(f=>f.path==='public/downloads/candidate/printed-5mm-p4-uniform-vents-source.zip'));
assert.ok(current.files.every(f=>!f.path.includes('/p3/')&&!f.path.includes('printed-5mm-p3')));
for(const registryPath of ['project/printed-5mm/files.json',currentPath]) {
const registry=JSON.parse(readFileSync(resolve(root,registryPath)));
assert.equal(registry.revision,registryPath===currentPath?current.revision:'P3-PRINTED-5MM-7U-RAILS');
assert.equal(registry.print_parts.structural,12);
assert.equal(registry.print_parts.optional_types,3);
assert.deepEqual(registry.optional_quantities,{'pad-horizontal':48,'pad-vertical':48,'washer-round':28});
for(const file of registry.files){
 const path=resolve(root,file.path);
 assert.ok(existsSync(path),`Missing ${file.path}`);
 const data=readFileSync(path);
 assert.equal(createHash('sha256').update(data).digest('hex'),file.sha256,`Changed ${file.path}`);
 assert.ok(data.length<25*1024*1024,`Asset too large: ${file.path}`);
}
const release=JSON.parse(readFileSync(resolve(root,'project/release-state.json')));
assert.equal(release.current_printed_5mm_candidate.revision,current.revision);
assert.equal(release.current_fullset_candidate?.revision,'R10-FULLSET-01');
const cart=JSON.parse(readFileSync(resolve(root,'project/order-records/r10-fullset-01-jlc-cart-2026-10-26.json')));
assert.equal(cart.status,'CART_PREPARED_NOT_ORDERED_NOT_PAID');
assert.equal(cart.selected_manifest_sha256,'1119d18d37ab5b48d49709ba725214bbd70ff548d4b5f028ea4b4551c7cbe496');
for(const pkg of registry.files.filter(f=>f.path.endsWith('.zip'))){
 const listing=execFileSync('unzip',['-Z1',resolve(root,pkg.path)],{encoding:'utf8'}).trim().split('\n');
 assert.equal(new Set(listing).size,listing.length,`Duplicate archive paths: ${pkg.path}`);
 assert.ok(listing.includes('PRINT-START-HERE.md'));
 if(registryPath===currentPath)assert.ok(listing.every(x=>!/(?:pattern-?0[234]|alternative|02-wall|03-wall|04-wall)/.test(x)));
 if(pkg.path.endsWith('-stl.zip')) {
  assert.equal(listing.filter(x=>x.endsWith('.stl')).length,15);
  assert.equal(listing.filter(x=>x.endsWith('.step')).length,15);
  const ids=['floor-1','floor-2','wall-front','wall-back','wall-right','wall-left','lid-edge-front','lid-edge-back','lid-edge-right','lid-edge-left','lid-top-1','lid-top-2','pad-horizontal','pad-vertical','washer-round'];
  for(const ext of ['stl','step'])assert.deepEqual(listing.filter(x=>x.endsWith('.'+ext)).sort(),ids.map(x=>`${ext}/${x}.${ext}`).sort());
 }
}
console.log(`${registry.revision} registry: ${registry.files.length} files verified`);

}
const protectedFiles=JSON.parse(readFileSync(resolve(root,'engineering/printed-5mm/p4-uniform-vents/reference/PRESERVATION.json')));
for(const f of protectedFiles.files)assert.equal(createHash('sha256').update(readFileSync(resolve(root,f.path))).digest('hex'),f.sha256,`Protected bytes changed: ${f.path}`);
const release=JSON.parse(readFileSync(resolve(root,'project/release-state.json')));
assert.deepEqual(release.current_fullset_candidate,protectedFiles.current_fullset_candidate);
const vents=JSON.parse(readFileSync(resolve(root,'engineering/printed-5mm/p4-uniform-vents/out/VENTILATION.json')));
assert.equal(vents.total_vents,82);assert.equal(vents.assembly_slots,28);assert.equal(vents.rail_holes,10);
assert.equal(vents.pattern,'uniform-four-walls');
}
if(process.argv[1]===new URL(import.meta.url).pathname)verifyPrinted();
