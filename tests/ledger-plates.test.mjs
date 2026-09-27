import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { checkPlateGeometry } from '../scripts/lib/ledger-checks.mjs';

const spec = JSON.parse(await readFile(new URL('../project/current-spec.json', import.meta.url), 'utf8'));
const copySpec = () => structuredClone(spec);
const getPlate = (data, model, role) => data.models[model].plates.find(plate => plate.role === role);

test('the current three models match their plate geometry', () => {
  assert.deepEqual(checkPlateGeometry(spec), []);
});

test('bottom width mismatch reports model, plate, and axis', () => {
  const changed = copySpec();
  getPlate(changed, '7u40', 'bottom').size_mm[0] += 10;
  assert.ok(checkPlateGeometry(changed).includes(
    '7u40/bottom(底板): size_mm[0] expected 229.4 actual 239.4',
  ));
});

test('front and back plate height mismatch fails', () => {
  const changed = copySpec();
  getPlate(changed, '7u40', 'front_back').size_mm[1] += 1;
  assert.ok(checkPlateGeometry(changed).includes(
    '7u40/front_back(前後板): size_mm[1] expected 89.5 actual 90.5',
  ));
});

test('one plate thickness mismatch fails', () => {
  const changed = copySpec();
  getPlate(changed, '3u60', 'left_right').size_mm[2] = 1.6;
  assert.ok(checkPlateGeometry(changed).includes(
    '3u60/left_right(左右板): size_mm[2] expected 1.5 actual 1.6',
  ));
});

test('a missing role fails with the expected plate identity', () => {
  const changed = copySpec();
  delete getPlate(changed, '3u60', 'bottom').role;
  assert.ok(checkPlateGeometry(changed).some(error => error.includes('3u60/bottom(底板): missing plate role')));
});

test('a duplicate role fails', () => {
  const changed = copySpec();
  getPlate(changed, '3u60', 'front_back').role = 'bottom';
  const errors = checkPlateGeometry(changed);
  assert.ok(errors.some(error => error.includes('3u60/bottom(底板): expected one plate for role, actual 2')));
  assert.ok(errors.some(error => error.includes('3u60/front_back(前後板): missing plate role')));
});

test('a non-finite plate dimension fails', () => {
  const changed = copySpec();
  getPlate(changed, '7u40', 'bottom').size_mm[0] = Number.NaN;
  assert.ok(checkPlateGeometry(changed).includes(
    '7u40/bottom(底板): size_mm[0] expected 229.4 actual NaN',
  ));
});

test('a negative plate dimension fails', () => {
  const changed = copySpec();
  getPlate(changed, '7u40', 'bottom').size_mm[0] = -1;
  assert.ok(checkPlateGeometry(changed).includes(
    '7u40/bottom(底板): size_mm[0] expected 229.4 actual -1',
  ));
});

test('plate array order does not affect role matching', () => {
  const changed = copySpec();
  changed.models['7u40'].plates.reverse();
  assert.deepEqual(checkPlateGeometry(changed), []);
});

test('unexpected role quantity fails', () => {
  const changed = copySpec();
  getPlate(changed, '3u60', 'bottom').quantity = 2;
  assert.ok(checkPlateGeometry(changed).includes(
    '3u60/bottom(底板): quantity expected 1 actual 2',
  ));
});
