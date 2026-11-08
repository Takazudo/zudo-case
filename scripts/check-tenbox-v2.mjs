import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root = path.resolve(import.meta.dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'project/tenbox-v2/manifest.json')));
assert.equal(manifest.family, 'tenbox-v2');
assert.equal(manifest.current_revision, 'r5');
assert.equal(manifest.production_approved, false);
for (const record of [...manifest.inputs, ...manifest.source_files, ...manifest.tooling_files, ...manifest.public_files]) {
  const bytes = fs.readFileSync(path.join(root, record.path));
  assert.equal(bytes.length, record.bytes, record.path);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), record.sha256, record.path);
}
assert.equal(manifest.print_projects.length, 15);
assert.equal(manifest.print_projects.reduce((n, p) => n + p.stored_object_count, 0), 22);
assert.equal(manifest.print_projects.reduce((n, p) => n + p.required_physical_quantity, 0), 23);
assert.equal(manifest.print_projects.reduce((n, p) => n + p.plate_runs_for_assembly, 0), 16);
assert.equal(manifest.printed_parts.length, 23);
assert.equal(manifest.print_poses.floor.yaw_degrees, -45);
assert.deepEqual(manifest.print_poses.floor.left_area_xy_mm, [0, 0, 325, 320]);
assert.deepEqual(manifest.print_poses.floor.plate_override, {filament_map_mode: 'Manual', filament_maps: '1 1'});
assert.equal(manifest.verification.native_studio_load, 'not_performed');
assert.equal(manifest.verification.physical_print_fit_load, 'not_performed');
console.log(`10BOX-v2: ${manifest.source_files.length} source receipts, ${manifest.public_files.length} public receipts; 15 projects / 23 parts / 16 plate runs`);
