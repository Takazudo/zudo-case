import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';

export function verifyP6(root) {
  const read = p => JSON.parse(readFileSync(resolve(root, p)));
  const registry = read('project/printed-5mm/p6-lid-slots/files.json');
  const revision = 'P6-PRINTED-5MM-LID-SLOTS';
  assert.equal(registry.revision, revision);
  assert.equal(registry.production_approved, false);
  assert.equal(registry.unsliced, true);
  assert.deepEqual(registry.print_parts, {structural: 12, optional_types: 3});
  assert.deepEqual(registry.optional_quantities, {'pad-horizontal': 48, 'pad-vertical': 48, 'washer-round': 28});
  assert.deepEqual(registry.replaced_parts, ['lid-top-1', 'lid-top-2']);
  assert.equal(registry.parts.length, 15);
  assert.equal(new Set(registry.parts.map(p => p.id)).size, 15);
  assert.equal(registry.reused_parts.length, 13);
  const lid = registry.lid_printing;
  assert.equal(lid.source_part_id, 'lid-top-1');
  assert.deepEqual(lid.assembly_part_ids, ['lid-top-1', 'lid-top-2']);
  assert.equal(lid.quantity, 2);
  assert.equal(lid.assembly_rotation_z_degrees, 180);
  assert.equal(lid.mirror_required, false);
  assert.equal(lid.stl_download_path, 'public/downloads/candidate/printed-5mm-p6-lid-top.stl');
  assert.equal(lid.stl_member, 'stl/lid-top-1.stl');
  assert.equal(lid.project_member, 'projects/p6-lid-top-1-h2d-pla06.3mf');
  assert.deepEqual(lid.equivalence.difference_volumes_mm3, [0, 0]);
  const roof = registry.parts.find(p => p.id === lid.source_part_id);
  const roofStl = roof.files.find(f => f.format === 'stl');
  assert.deepEqual(readFileSync(resolve(root, lid.stl_download_path)), readFileSync(resolve(root, roofStl.path)), 'Direct lid STL must preserve the source mesh bytes');
  assert.equal(registry.files.find(f => f.path === lid.stl_download_path)?.sha256, roofStl.sha256);
  for (const id of lid.assembly_part_ids) {
    const step = registry.parts.find(p => p.id === id).files.find(f => f.format === 'step');
    assert.equal(step.sha256, lid.equivalence.input_step_sha256[id], 'Same-shape evidence must match the current STEP: ' + id);
  }
  const release = read('project/release-state.json').current_printed_5mm_candidate;
  const selection = read('project/current-selection.json').selections.find(s => s.project === 'printed-5mm');
  assert.equal(release.revision, revision);
  assert.equal(release.production_approved, false);
  assert.equal(release.registry, 'project/printed-5mm/p6-lid-slots/files.json');
  assert.equal(selection.revision, revision);
  assert.equal(selection.preview.path, '/previews/printed-5mm-p6-lid-slots.html');
  for (const file of [...registry.files, ...registry.parts.flatMap(p => p.files)]) {
    const bytes = readFileSync(resolve(root, file.path));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), file.sha256, `Changed P6 ${file.path}`);
    assert.equal(bytes.length, file.bytes, file.path);
    assert.ok(bytes.length < 25 * 1024 * 1024, file.path);
  }
  for (const part of registry.parts) {
    const replaced = registry.replaced_parts.includes(part.id);
    assert.equal(part.unchanged_from_p5, !replaced);
    assert.equal(part.source_revision, replaced ? revision : 'P5-PRINTED-5MM-TAB-JOINTS-J3');
    assert.equal(part.quantity, registry.optional_quantities[part.id] ?? 1);
    assert.deepEqual(part.files.map(f => f.format), ['stl', 'step', '3mf']);
    for (const file of part.files) {
      assert.ok(file.path.includes(replaced ? '/p6-lid-slots/' : '/p5-'), file.path);
      const packageName = file.format === '3mf' ? 'h2d-3mf' : 'stl';
      const archive = resolve(root, `public/downloads/candidate/printed-5mm-p6-lid-slots-${packageName}.zip`);
      const bytes = execFileSync('unzip', ['-p', archive, file.member], {maxBuffer: 25 * 1024 * 1024});
      assert.equal(createHash('sha256').update(bytes).digest('hex'), file.sha256, `P6 package ${file.member}`);
      if (replaced) {
        const replacement = resolve(root, 'public/downloads/candidate/printed-5mm-p6-lid-slots.zip');
        const payload = execFileSync('unzip', ['-p', replacement, file.member], {maxBuffer: 25 * 1024 * 1024});
        assert.equal(createHash('sha256').update(payload).digest('hex'), file.sha256, `P6 replacement ${file.member}`);
      }
    }
  }
  for (const [suffix, counts] of [['-stl', [15,15,0]], ['-h2d-3mf', [0,0,15]], ['', [2,2,2]]]) {
    const names = execFileSync('unzip', ['-Z1', resolve(root, `public/downloads/candidate/printed-5mm-p6-lid-slots${suffix}.zip`)], {encoding:'utf8'}).trim().split('\n');
    assert.equal(names.length, new Set(names).size);
    assert.deepEqual(['.stl','.step','.3mf'].map(ext => names.filter(n => n.endsWith(ext)).length), counts);
  }
  const report = read(registry.geometry_verification);
  assert.equal(report.passed, true);
  assert.equal(report.physical_validation, false);
  assert.equal(report.parts.length, 2);
  for (const part of report.parts) {
    assert.equal(part.holes.length, 4);
    assert.ok(Math.abs(part.removed_volume_mm3 - 550) < 1e-6);
    assert.equal(part.minimum_edge_margin_mm, 5.45);
    assert.equal(part.bambu_project.settings_bytes_unchanged, true);
    for (const hole of part.holes) {
      assert.equal(hole.length_mm, 10.5);
      assert.equal(hole.width_mm, 5.5);
      assert.equal(hole.angle_deg, ['front','back'].includes(hole.face) ? 90 : 0);
      assert.deepEqual(hole.m5_travel_checks.map(c => c.offset_mm), [-2.5,0,2.5]);
      assert.ok(hole.m5_travel_checks.every(c => c.m5_shaft_collision_mm3 < 1e-8));
    }
  }
  console.log('P6 registry and packages: one roof STL x2, 2 assembly IDs, 13 unchanged part IDs');
}
