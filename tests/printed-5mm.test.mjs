import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const registry=JSON.parse(readFileSync(new URL('../project/printed-5mm/files.json',import.meta.url)));
test('printed candidate remains separate from R10 and contains exactly 12 structural pieces',()=>{
 assert.equal(registry.revision,'P3-PRINTED-5MM-7U-RAILS');
 assert.equal(registry.print_parts.structural,12);
 assert.equal(registry.print_parts.optional_types,3);
 const release=JSON.parse(readFileSync(new URL('../project/release-state.json',import.meta.url)));
 assert.equal(release.current_fullset_candidate.revision,'R10-FULLSET-01');
 assert.equal(release.current_printed_5mm_candidate.production_approved,false);
});
