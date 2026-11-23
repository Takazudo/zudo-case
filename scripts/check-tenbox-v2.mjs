import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root = path.resolve(import.meta.dirname, '..');
// The R5 manifest is an immutable input/hash contract, not the active selection.
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

const currentPath = 'project/tenbox-v2/current.json';
const current = JSON.parse(fs.readFileSync(path.join(root, currentPath)));
assert.equal(current.schema_version, 1);
assert.equal(current.family, 'tenbox-v2');
assert.equal(current.current_revision, 'R8-LID-LEDGE-01');
assert.equal(current.status, 'current');
assert.equal(current.development_stage, 'ongoing_prototype');
assert.equal(current.selection_basis, 'explicit_user_instruction');
assert.equal(current.production_approved, false);
assert.equal(current.preserved_baseline_registry, 'project/tenbox-v2/manifest.json');
assert.equal(current.source, 'engineering/tenbox-v2/r8-lid-ledge-01/');
assert.equal(current.docs, 'src/content/docs/tenbox-v2/');
for (const directory of [current.source, current.docs]) {
  assert.ok(fs.statSync(path.join(root, directory)).isDirectory(), directory);
}

const selections = JSON.parse(fs.readFileSync(path.join(root, 'project/current-selection.json')));
const familySelections = selections.selections.filter((entry) => entry.project === current.family);
assert.equal(familySelections.length, 1);
const selection = familySelections[0];
assert.deepEqual(selection.registry, {file: currentPath, key: 'current_revision'});
assert.equal(selection.revision, current.current_revision);
assert.equal(selection.production_approved, false);
assert.equal(selection.preview.path, current.preview);
assert.equal(`src/content/docs/${selection.current_doc}`, `${current.docs}index.mdx`);
assert.ok(fs.statSync(path.join(root, 'src/content/docs', selection.current_doc)).isFile());

const release = JSON.parse(fs.readFileSync(path.join(root, 'project/release-state.json'))).current_tenbox_v2_candidate;
assert.equal(release.family, current.family);
assert.equal(release.revision, current.current_revision);
assert.equal(release.registry, currentPath);
assert.equal(release.source, current.source);
assert.equal(release.production_approved, false);

// Historical R5-R8 receipts are immutable; the selected correction owns current artifacts.
assert.equal(current.artifact_registry, 'project/tenbox-v2/r8-lid-ledge-01.json');
const artifacts = JSON.parse(fs.readFileSync(path.join(root, current.artifact_registry)));
assert.equal(artifacts.family, current.family);
assert.equal(artifacts.revision, current.current_revision);
assert.equal(artifacts.production_approved, false);
assert.equal(artifacts.preview, current.preview);
assert.equal(current.preview, '/previews/tenbox-v2-r8-lid-ledge-01.html');
assert.deepEqual(Object.keys(current.downloads).sort(), ['print', 'review', 'source']);
for (const [kind, download] of Object.entries(current.downloads)) {
  assert.equal(download, `/downloads/candidate/tenbox-v2-r8-lid-ledge-01-${kind}.zip`);
}
assert.deepEqual(current.lid_downloads, {
  stl: '/downloads/candidate/10box-v2-lid-frontback-connected-r01.stl',
  project: '/downloads/candidate/10box-v2-lid-frontback-connected-r01.3mf',
});
for (const url of [current.preview, ...Object.values(current.downloads), ...Object.values(current.lid_downloads)]) {
  const file = `public${url}`;
  const record = artifacts.files.find((entry) => entry.path === file);
  assert.ok(record, `Current artifact receipt: ${file}`);
  const bytes = fs.readFileSync(path.join(root, file));
  assert.equal(bytes.length, record.bytes, file);
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), record.sha256, file);
}
for (const verification of ['native_studio_load', 'native_studio_slice', 'physical_print_fit_load']) {
  assert.equal(artifacts.verification[verification], 'not_performed');
}
const h2d = artifacts.verification.h2d;
assert.equal(h2d.project_count, 15);
assert.equal(h2d.stored_object_count, 22);
assert.equal(h2d.required_physical_part_count, 23);
assert.equal(h2d.plate_runs_for_assembly, 16);
assert.equal(h2d.changed_project_count, 2);
assert.equal(h2d.byte_identical_project_count, 13);
assert.equal(h2d.global_settings_bytes_unchanged, true);
const approvedLid = fs.readFileSync(path.join(root, 'public', current.lid_downloads.stl));
assert.equal(crypto.createHash('sha256').update(approvedLid).digest('hex'),
  '3426afa3086cdee245bb4dfa63387a8576b7d8551d895a982aa2a4b81f03859a', 'User-approved common lid STL');
console.log(`10BOX-v2 current ${current.current_revision}: selection, preview, 3 full-set downloads and 2 direct lid receipts verified; 2 lid projects changed / 13 unchanged; preserved R5: ${manifest.source_files.length} source receipts, ${manifest.public_files.length} public receipts; 15 projects / 23 parts / 16 plate runs`);
