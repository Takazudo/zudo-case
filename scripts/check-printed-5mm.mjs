import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
const root=resolve(import.meta.dirname,'..');
const registry=JSON.parse(readFileSync(resolve(root,'project/printed-5mm/files.json')));
assert.equal(registry.revision,'P3-PRINTED-5MM-7U-RAILS');
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
assert.equal(release.current_printed_5mm_candidate.revision,registry.revision);
assert.equal(release.current_fullset_candidate?.revision,'R10-FULLSET-01');
const cart=JSON.parse(readFileSync(resolve(root,'project/order-records/r10-fullset-01-jlc-cart-2026-10-26.json')));
assert.equal(cart.status,'CART_PREPARED_NOT_ORDERED_NOT_PAID');
assert.equal(cart.selected_manifest_sha256,'1119d18d37ab5b48d49709ba725214bbd70ff548d4b5f028ea4b4551c7cbe496');
for(const pkg of registry.files.filter(f=>f.path.endsWith('.zip'))){
 const listing=execFileSync('unzip',['-Z1',resolve(root,pkg.path)],{encoding:'utf8'}).trim().split('\n');
 assert.equal(new Set(listing).size,listing.length,`Duplicate archive paths: ${pkg.path}`);
 assert.ok(listing.includes('PRINT-START-HERE.md'));
 if(pkg.path.endsWith('-stl.zip')) {
  assert.equal(listing.filter(x=>x.endsWith('.stl')).length,15);
  assert.equal(listing.filter(x=>x.endsWith('.step')).length,15);
 }
}
console.log(`P3 registry: ${registry.files.length} files verified`);
