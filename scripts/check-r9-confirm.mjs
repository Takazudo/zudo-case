import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { buildR9CandidateEntries } from "./sync-r9-ledger.mjs";
import { verifyR9OutputManifest } from "./lib/r9-manifest-check.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REVISION = "R9-PROTOTYPE-01";
const MODEL = "7u40";
const MAX_FILE_BYTES = 25 * 1024 * 1024;
const PROTECTED_PATHS = [
  "engineering/r6-body",
  "engineering/r8-preview",
  "public/downloads/archive",
  "engineering/release",
];

const failures = [];
const check = (condition, message) => {
  if (!condition) failures.push(message);
};
const readJson = relative => JSON.parse(readFileSync(path.join(ROOT, relative), "utf8"));
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");
const git = args => execFileSync("git", args, { cwd: ROOT, encoding: "utf8" });
const gitPaths = args => git(args).split("\0").filter(Boolean);
const sameJson = (left, right) => JSON.stringify(left) === JSON.stringify(right);

function parseArgs(args) {
  let base = "main";
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--base" && args[index + 1]) {
      base = args[index + 1];
      index += 1;
    } else {
      throw new Error("Usage: node scripts/check-r9-confirm.mjs [--base REF]");
    }
  }
  return base;
}

function changedPaths(base) {
  return new Set([
    ...gitPaths(["diff", "--name-only", "-z", `${base}...HEAD`]),
    ...gitPaths(["diff", "--name-only", "-z"]),
    ...gitPaths(["diff", "--cached", "--name-only", "-z"]),
    ...gitPaths(["ls-files", "--others", "--exclude-standard", "-z"]),
  ]);
}

function audit(base) {
  const spec = readJson("project/current-spec.json");
  const release = readJson("project/release-state.json");
  const artifactManifest = readJson("project/artifact-manifest.json");
  const gates = readJson("project/open-issues.json");
  const outputManifest = readJson("engineering/r9-prototype-01/out/outputs-manifest.json");
  const validation = readJson("engineering/r9-prototype-01/out/validation.json");
  const bom = readJson("engineering/r9-prototype-01/out/bom.json");
  const couponManifest = readJson("engineering/r9-prototype-01/out/coupons/coupon-manifest.json");
  const sourceSpec = JSON.parse(git(["show", `${base}:project/current-spec.json`]));
  const sourceArtifacts = JSON.parse(git(["show", `${base}:project/artifact-manifest.json`]));
  const currentModel = spec.models[MODEL];

  for (const model of ["3u60", "7u60"]) {
    check(sameJson(spec.models[model], sourceSpec.models[model]), `${model} current-spec entry changed from ${base}`);
    const page = `src/content/docs/models/${model}.mdx`;
    check(readFileSync(path.join(ROOT, page), "utf8") === git(["show", `${base}:${page}`]), `${page} changed from ${base}`);
  }

  const baseArtifactByPath = new Map(sourceArtifacts.files.map(entry => [entry.path, entry]));
  const currentArtifactByPath = new Map(artifactManifest.files.map(entry => [entry.path, entry]));
  for (const [artifactPath, entry] of baseArtifactByPath) {
    check(sameJson(currentArtifactByPath.get(artifactPath), entry), `pre-existing artifact-manifest entry changed or disappeared: ${artifactPath}`);
  }

  const paths = changedPaths(base);
  for (const relative of paths) {
    if (PROTECTED_PATHS.some(prefix => relative === prefix || relative.startsWith(`${prefix}/`))) {
      failures.push(`protected source path changed: ${relative}`);
    }
    const absolute = path.join(ROOT, relative);
    try {
      const stat = statSync(absolute);
      if (stat.isFile()) check(stat.size < MAX_FILE_BYTES, `changed file is not below 25 MiB: ${relative} (${stat.size} bytes)`);
    } catch {
      // Removed paths are not new or modified files whose size can be checked.
    }
  }

  verifyR9OutputManifest(ROOT);
  const candidateFiles = buildR9CandidateEntries(outputManifest);
  check(currentModel?.candidate_revision === REVISION, `current-spec 7u40 candidate revision is not ${REVISION}`);
  check(currentModel?.candidate_status === "candidate-not-approved", "current-spec 7u40 candidate status is not unapproved");
  check(release.candidate_revision === REVISION, `release-state candidate revision is not ${REVISION}`);
  check(release.current_lid_manufacturing?.revision === REVISION, `release-state lid revision is not ${REVISION}`);
  check(outputManifest.revision === REVISION && outputManifest.model === MODEL && outputManifest.units === "mm", "output manifest revision, model, or units mismatch");
  check(validation.revision === REVISION && bom.revision === REVISION && couponManifest.revision === REVISION, "validation, BOM, or coupon manifest revision mismatch");
  check(outputManifest.productionApproved === false && release.production_approved === false, "R9 output or release state marks production approved");
  check(release.published_release_files?.length === 0, "published_release_files is not empty");
  check(release.candidate_files?.length === candidateFiles.length && sameJson(release.candidate_files, candidateFiles), "release candidate ledger differs from generated output manifest");
  check(spec.release_gate?.approved_for_production === false, "current-spec release gate marks production approved");

  const expectedGateIds = Array.from({ length: 11 }, (_, index) => `G${String(index + 1).padStart(2, "0")}`);
  for (const id of expectedGateIds) {
    const gate = gates.find(entry => entry.id === id);
    check(gate?.status === "open" && gate?.result === null, `${id} must remain open with a null result`);
  }

  const railPath = "engineering/r6-body/source-data/rail40/nuts-v2-40hp-single.stl";
  const railDimensionsPath = "engineering/r6-body/source-data/rail40/rail_dimensions.json";
  const railBytes = readFileSync(path.join(ROOT, railPath));
  const railHash = sha256(railBytes);
  const railDimensionsBytes = readFileSync(path.join(ROOT, railDimensionsPath));
  const railDimensions = JSON.parse(railDimensionsBytes.toString("utf8"));
  const railInput = outputManifest.inputs.find(entry => entry.path === railPath);
  const railDimensionsInput = outputManifest.inputs.find(entry => entry.path === railDimensionsPath);
  check(railHash === "88a153fe717f582f80656fe10c74df5ec1717f53e6b202fff078532b00b06c5a", "R6 40HP rail source hash changed");
  check(railHash === railDimensions.source?.sha256 && railHash === railInput?.sha256, "R6 40HP rail source hash differs from its source and output manifests");
  check(sha256(railDimensionsBytes) === railDimensionsInput?.sha256, "rail dimension input hash differs from output manifest");
  check(railBytes.length === 29684 && railDimensions.exact_mesh_measurements?.long_axis_length_mm === 204, "R6 source rail is not the unchanged 204 mm 40HP file");

  check(validation.summary?.failed === 0, "stored CAD validation contains failures");
  check(validation.summary?.passed === 156 && validation.summary?.flagged === 14, "stored CAD validation summary differs from VALIDATION.md");
  check(validation.productionApproved === false, "CAD validation record marks production approved");

  const releaseFiles = readdirSync(path.join(ROOT, "engineering/release"), { withFileTypes: true })
    .map(entry => entry.name)
    .sort();
  check(sameJson(releaseFiles, ["README.md"]), `engineering/release must contain only README.md (found: ${releaseFiles.join(", ")})`);

  const previewPath = "public/previews/r9-prototype-01.html";
  const preview = readFileSync(path.join(ROOT, previewPath), "utf8");
  check(Buffer.byteLength(preview) < MAX_FILE_BYTES, "R9 preview is not below 25 MiB");
  check(!/<(?:script|link)\b[^>]+(?:src|href)\s*=\s*["'](?:https?:)?\/\//i.test(preview), "R9 preview contains an external script or stylesheet reference");
  check(preview.includes(REVISION), "R9 preview does not identify the candidate revision");
  const browserCheckPath = outputManifest.browserEvidence?.checkFile;
  let browserCheck;
  try {
    browserCheck = readJson(path.relative(ROOT, path.join(ROOT, browserCheckPath)));
  } catch {
    failures.push("manager browser-check evidence file is missing or unreadable");
  }
  check(outputManifest.browserEvidence?.status === "passed", "output manifest does not record a passed browser check");
  check(browserCheck?.status === "passed" && browserCheck?.model === MODEL && browserCheck?.revision === REVISION, "browser check revision or model mismatch");
  check(browserCheck?.checks?.noNetworkRequests === true && browserCheck?.networkRequests?.length === 0, "browser check did not confirm offline preview behavior");
  check(browserCheck?.checks?.noConsoleErrors === true && browserCheck?.checks?.mobileNoHorizontalScroll === true, "browser check reported a console error or mobile overflow");

  const changedFiles = [...paths].filter(relative => {
    try {
      return statSync(path.join(ROOT, relative)).isFile();
    } catch {
      return false;
    }
  });
  return {
    candidateFileCount: candidateFiles.length,
    generatedOutputCount: outputManifest.outputs.length,
    changedFileCount: changedFiles.length,
    validation: validation.summary,
    railSha256: railHash,
    railLengthMm: railDimensions.exact_mesh_measurements.long_axis_length_mm,
  };
}

try {
  const base = parseArgs(process.argv.slice(2));
  const summary = audit(base);
  if (failures.length > 0) {
    console.error(`R9 confirmation check failed against ${base}:\n${failures.map(failure => `- ${failure}`).join("\n")}`);
    process.exitCode = 1;
  } else {
    console.log(`R9 confirmation check passed against ${base}: ${summary.candidateFileCount} candidate files, ${summary.generatedOutputCount} generated outputs, ${summary.changedFileCount} changed files below 25 MiB.`);
    console.log(`Stored CAD validation: ${summary.validation.passed} pass, ${summary.validation.flagged} flags, ${summary.validation.failed} fail; 40HP rail ${summary.railLengthMm} mm SHA-256 ${summary.railSha256}.`);
    console.log("Physical fit, strength, transport, supplier quote, and clean-worktree regeneration remain separate gates.");
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
}
