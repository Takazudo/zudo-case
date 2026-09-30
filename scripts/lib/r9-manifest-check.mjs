import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const R9_OUTPUT_MANIFEST = "engineering/r9-prototype-01/out/outputs-manifest.json";

function isInside(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative !== "" && relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

export function verifyR9OutputManifest(root = REPO_ROOT) {
  const repoRoot = path.resolve(root);
  const manifestPath = path.join(repoRoot, R9_OUTPUT_MANIFEST);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (!Array.isArray(manifest.outputs)) {
    throw new Error(`${R9_OUTPUT_MANIFEST} must contain an outputs array`);
  }

  const failures = [];
  for (const [index, output] of manifest.outputs.entries()) {
    const label = `outputs[${index}]`;
    if (typeof output?.path !== "string" || output.path.length === 0) {
      failures.push(`${label} has no output path`);
      continue;
    }
    if (!/^[a-f0-9]{64}$/i.test(output.sha256 ?? "")) {
      failures.push(`${label} (${output.path}) has an invalid SHA-256`);
      continue;
    }

    const outputPath = path.resolve(repoRoot, output.path);
    if (!isInside(repoRoot, outputPath)) {
      failures.push(`${label} (${output.path}) points outside the repository`);
      continue;
    }

    let stat;
    try {
      stat = statSync(outputPath);
    } catch {
      failures.push(`${label} is missing: ${output.path}`);
      continue;
    }
    if (!stat.isFile()) {
      failures.push(`${label} is not a file: ${output.path}`);
      continue;
    }

    const actualHash = createHash("sha256").update(readFileSync(outputPath)).digest("hex");
    if (actualHash !== output.sha256.toLowerCase()) {
      failures.push(`${label} SHA-256 mismatch: ${output.path}`);
    }
  }

  if (failures.length > 0) {
    throw new Error(`R9 output manifest validation failed:\n${failures.map((item) => `- ${item}`).join("\n")}`);
  }

  return manifest.outputs.length;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const outputCount = verifyR9OutputManifest();
    console.log(`R9 output manifest verified: ${outputCount} outputs`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}
