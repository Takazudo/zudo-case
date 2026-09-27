const PLATE_ROLES = [
  {
    role: 'bottom',
    part: '底板',
    quantity: 1,
    dimensions: ([width, depth], thickness) => [width, depth, thickness],
  },
  {
    role: 'front_back',
    part: '前後板',
    quantity: 2,
    dimensions: ([width, , height], thickness) => [width - 2 * thickness, height - thickness, thickness],
  },
  {
    role: 'left_right',
    part: '左右板',
    quantity: 2,
    dimensions: ([, depth, height], thickness) => [depth, height - thickness, thickness],
  },
];

const near = (actual, expected) => Math.abs(actual - expected) < 0.00002;
const isFinitePositive = value => typeof value === 'number' && Number.isFinite(value) && value > 0;
const display = value => value === undefined ? 'undefined' : String(value);

/**
 * Check that each model's plate ledger matches its metal outline.
 * Returns one diagnostic per detected inconsistency and does not mutate spec.
 * @param {object} spec
 * @returns {string[]}
 */
export function checkPlateGeometry(spec) {
  const errors = [];
  if (!spec || typeof spec !== 'object' || !spec.models || typeof spec.models !== 'object') {
    return ['spec.models: expected a model object'];
  }

  for (const [modelId, model] of Object.entries(spec.models)) {
    if (!model || typeof model !== 'object') {
      errors.push(`${modelId}: expected a model object`);
      continue;
    }

    const metal = model.metal_mm;
    if (!Array.isArray(metal) || metal.length !== 3) {
      errors.push(`${modelId}: metal_mm expected [W, D, H], actual ${display(metal)}`);
    }
    if (Array.isArray(metal)) {
      metal.forEach((value, axis) => {
        if (!isFinitePositive(value)) {
          errors.push(`${modelId}: metal_mm[${axis}] expected a finite value > 0, actual ${display(value)}`);
        }
      });
    }

    const thickness = model.metal_thickness_mm;
    if (!isFinitePositive(thickness)) {
      errors.push(`${modelId}: metal_thickness_mm expected a finite value > 0, actual ${display(thickness)}`);
    }

    const plates = model.plates;
    if (!Array.isArray(plates)) {
      errors.push(`${modelId}: plates expected an array, actual ${display(plates)}`);
      continue;
    }

    const byRole = new Map(PLATE_ROLES.map(({ role }) => [role, []]));
    for (const plate of plates) {
      if (!plate || typeof plate !== 'object') {
        errors.push(`${modelId}/unknown(unknown): plate entry must be an object`);
        continue;
      }
      const part = display(plate.part ?? 'unknown');
      if (!byRole.has(plate.role)) {
        const role = plate.role === undefined || plate.role === null || plate.role === ''
          ? 'unassigned'
          : display(plate.role);
        errors.push(`${modelId}/${role}(${part}): role must be one of ${PLATE_ROLES.map(item => item.role).join(', ')}`);
        continue;
      }
      byRole.get(plate.role).push(plate);
    }

    for (const roleSpec of PLATE_ROLES) {
      const matchingPlates = byRole.get(roleSpec.role);
      if (matchingPlates.length === 0) {
        errors.push(`${modelId}/${roleSpec.role}(${roleSpec.part}): missing plate role`);
        continue;
      }
      if (matchingPlates.length > 1) {
        const part = display(matchingPlates[0].part ?? roleSpec.part);
        errors.push(`${modelId}/${roleSpec.role}(${part}): expected one plate for role, actual ${matchingPlates.length}`);
      }

      for (const plate of matchingPlates) {
        const part = display(plate.part ?? roleSpec.part);
        if (plate.quantity !== roleSpec.quantity) {
          errors.push(`${modelId}/${roleSpec.role}(${part}): quantity expected ${roleSpec.quantity} actual ${display(plate.quantity)}`);
        }

        const size = plate.size_mm;
        const expectedSize = Array.isArray(metal) && metal.length >= 3 && isFinitePositive(thickness)
          ? roleSpec.dimensions(metal, thickness)
          : null;
        if (!Array.isArray(size)) {
          errors.push(`${modelId}/${roleSpec.role}(${part}): size_mm expected 3 values actual ${display(size)}`);
          continue;
        }
        if (size.length !== 3) {
          errors.push(`${modelId}/${roleSpec.role}(${part}): size_mm length expected 3 actual ${size.length}`);
        }
        if (!expectedSize) continue;

        for (let axis = 0; axis < 3; axis++) {
          const expected = expectedSize[axis];
          const actual = size[axis];
          if (!isFinitePositive(expected)) {
            errors.push(`${modelId}/${roleSpec.role}(${part}): expected geometry size_mm[${axis}] must be finite and > 0, actual ${display(expected)}`);
            continue;
          }
          if (!isFinitePositive(actual) || !near(actual, expected)) {
            errors.push(`${modelId}/${roleSpec.role}(${part}): size_mm[${axis}] expected ${display(expected)} actual ${display(actual)}`);
          }
        }
      }
    }
  }

  return errors;
}
