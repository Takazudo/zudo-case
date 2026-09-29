import { createHash } from "node:crypto";
import { readFile, readdir, realpath, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { R9_OUTPUT_MANIFEST, verifyR9OutputManifest } from "./lib/r9-manifest-check.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REVISION = "R9-PROTOTYPE-01";
const MODEL = "7u40";
const OUT_DIR = "engineering/r9-prototype-01/out";
const RELEASE_PATH = "project/release-state.json";
const ARTIFACT_PATH = "project/artifact-manifest.json";
const OUTPUT_EXTENSIONS = new Set([".dxf", ".step", ".stl"]);
const MAX_BYTES = 25 * 1024 * 1024;

const readJson = async relative => JSON.parse(await readFile(path.join(ROOT, relative), "utf8"));
const jsonText = value => `${JSON.stringify(value, null, 2)}\n`;
const sha256 = bytes => createHash("sha256").update(bytes).digest("hex");

function candidateComponent(output) {
  const { path: outputPath, kind } = output;
  if (kind === "candidate_package_zip") return "package";
  if (kind === "single_file_preview_html") return "preview";

  if (outputPath.includes("/aluminum/")) {
    return outputPath.includes("-lid-plate-") ? "lid" : "body-plate";
  }
  if (outputPath.includes("/pa12/lid/")) return "lid";
  if (outputPath.includes("/pa12/guards/")) return "guard";
  if (outputPath.includes("/coupons/")) return "coupon";
  if (outputPath.includes("/hardware-envelopes/") || outputPath.includes("/assembly/")) return "reference-geometry";
  if (outputPath.includes("/preview/")) return "preview";

  throw new Error(`R9 candidate output has no component mapping: ${outputPath}`);
}

function candidateId(outputPath) {
  const normalized = outputPath
    .replace(/^engineering\/r9-prototype-01\/out\//, "out/")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toUpperCase();
  return `R9-7U40-${normalized}`;
}

export function buildR9CandidateEntries(outputManifest) {
  if (outputManifest?.model !== MODEL || outputManifest?.revision !== REVISION) {
    throw new Error(`Expected ${REVISION} output manifest for ${MODEL}`);
  }
  if (outputManifest.productionApproved !== false || outputManifest.status !== "unapproved_prototype") {
    throw new Error("R9 output manifest must remain explicitly unapproved");
  }
  if (!Array.isArray(outputManifest.outputs)) throw new Error("R9 output manifest must contain outputs");

  const eligible = outputManifest.outputs.filter(output => {
    const extension = path.extname(output.path ?? "").toLowerCase();
    return OUTPUT_EXTENSIONS.has(extension) ||
      output.kind === "candidate_package_zip" ||
      output.kind === "single_file_preview_html";
  });
  const seenPaths = new Set();
  const seenIds = new Set();
  const entries = eligible.map(output => {
    if (typeof output.path !== "string" || !output.path.startsWith(`${OUT_DIR}/`) && !output.path.startsWith("public/")) {
      throw new Error(`R9 candidate path is outside output or public files: ${output.path}`);
    }
    if (seenPaths.has(output.path)) throw new Error(`Duplicate R9 candidate path: ${output.path}`);
    seenPaths.add(output.path);
    if (!/^[a-f0-9]{64}$/i.test(output.sha256 ?? "") || !Number.isSafeInteger(output.bytes) || output.bytes < 0) {
      throw new Error(`R9 candidate needs byte count and SHA-256: ${output.path}`);
    }

    const component = candidateComponent(output);
    const id = candidateId(output.path);
    if (seenIds.has(id)) throw new Error(`Duplicate R9 candidate ID: ${id}`);
    seenIds.add(id);
    return {
      id,
      component,
      model: MODEL,
      revision: REVISION,
      path: output.path,
      sha256: output.sha256.toLowerCase(),
    };
  });

  return entries.sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
}

async function walkFiles(relativeDir) {
  const result = [];
  const fullDir = path.join(ROOT, relativeDir);
  for (const entry of await readdir(fullDir, { withFileTypes: true })) {
    const relative = `${relativeDir}/${entry.name}`;
    if (entry.isDirectory()) result.push(...await walkFiles(relative));
    else if (entry.isFile()) result.push(relative);
    else throw new Error(`Unexpected non-file output in R9 out/: ${relative}`);
  }
  return result;
}

async function buildArtifactEntries(outputManifest) {
  const outFiles = new Set(await walkFiles(OUT_DIR));
  const listedOutFiles = new Set(outputManifest.outputs
    .map(output => output.path)
    .filter(outputPath => outputPath.startsWith(`${OUT_DIR}/`)));
  listedOutFiles.add(R9_OUTPUT_MANIFEST);
  const unlisted = [...outFiles].filter(outputPath => !listedOutFiles.has(outputPath));
  const missing = [...listedOutFiles].filter(outputPath => !outFiles.has(outputPath));
  if (unlisted.length || missing.length) {
    throw new Error([
      ...(unlisted.length ? [`Unlisted R9 output files: ${unlisted.join(", ")}`] : []),
      ...(missing.length ? [`Missing R9 output files: ${missing.join(", ")}`] : []),
    ].join("\n"));
  }

  const listedOutputs = new Map(outputManifest.outputs.map(output => [output.path, output]));
  const paths = [...listedOutputs.keys(), R9_OUTPUT_MANIFEST].sort();
  const entries = [];
  for (const outputPath of paths) {
    const bytes = await readFile(path.join(ROOT, outputPath));
    if (bytes.length > MAX_BYTES) throw new Error(`R9 artifact exceeds 25 MiB: ${outputPath}`);
    const manifestRecord = listedOutputs.get(outputPath);
    const digest = sha256(bytes);
    if (manifestRecord && (manifestRecord.bytes !== bytes.length || manifestRecord.sha256.toLowerCase() !== digest)) {
      throw new Error(`R9 output manifest does not match file bytes: ${outputPath}`);
    }
    entries.push({
      path: outputPath,
      bytes: bytes.length,
      sha256: digest,
      status: "candidate-not-approved",
    });
  }
  return entries;
}

function mergeArtifactEntries(manifest, generatedEntries) {
  const owned = entry => entry.path.startsWith(`${OUT_DIR}/`) ||
    entry.path.startsWith("public/downloads/candidate/7u40-r9-prototype-01-") ||
    entry.path === "public/previews/r9-prototype-01.html";
  const otherEntries = manifest.files.filter(entry => !owned(entry));
  return { ...manifest, files: [...otherEntries, ...generatedEntries] };
}

function updateReleaseState(release, candidates) {
  const owned = entry => entry.model === MODEL && entry.revision === REVISION;
  const lidIds = candidates.filter(entry => entry.component === "lid").map(entry => entry.id);
  if (lidIds.length === 0) throw new Error("R9 manifest contains no lid candidates");

  return {
    ...release,
    current_body_geometry: "R6 nominal for 3u60/7u60; R9-PROTOTYPE-01 unapproved candidate for 7u40",
    candidate_revision: REVISION,
    candidate_files: [
      ...(release.candidate_files ?? []).filter(entry => !owned(entry)),
      ...candidates,
    ],
    current_lid_manufacturing: {
      model: MODEL,
      revision: REVISION,
      candidate_ids: lidIds,
    },
    slot_manufacturing: null,
    production_approved: false,
    published_release_files: [],
    warning: "R9-PROTOTYPE-01 contains unapproved candidate outputs for 7u40. No file in engineering/release is an approved production release.",
  };
}

async function makeExpectedState() {
  verifyR9OutputManifest(ROOT);
  const outputManifest = await readJson(R9_OUTPUT_MANIFEST);
  const candidates = buildR9CandidateEntries(outputManifest);
  const artifacts = await buildArtifactEntries(outputManifest);
  const release = updateReleaseState(await readJson(RELEASE_PATH), candidates);
  const artifactManifest = mergeArtifactEntries(await readJson(ARTIFACT_PATH), artifacts);
  return { candidates, release, artifactManifest };
}

async function runCheck(expected) {
  const [release, artifactManifest] = await Promise.all([
    readJson(RELEASE_PATH),
    readJson(ARTIFACT_PATH),
  ]);
  const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const mismatches = [];
  if (!same(release, expected.release)) mismatches.push(RELEASE_PATH);
  if (!same(artifactManifest, expected.artifactManifest)) mismatches.push(ARTIFACT_PATH);
  if (mismatches.length) {
    console.error(`R9 ledgers differ from outputs-manifest.json: ${mismatches.join(", ")}`);
    process.exitCode = 1;
    return;
  }
  console.log(`R9 ledger verified: ${expected.candidates.length} candidate files; ${expected.candidates.filter(entry => entry.component === "lid").length} lid files.`);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.some(arg => arg !== "--check")) {
    console.error("Usage: node scripts/sync-r9-ledger.mjs [--check]");
    process.exitCode = 2;
    return;
  }

  const expected = await makeExpectedState();
  if (args.includes("--check")) return runCheck(expected);

  await Promise.all([
    writeFile(path.join(ROOT, RELEASE_PATH), jsonText(expected.release)),
    writeFile(path.join(ROOT, ARTIFACT_PATH), jsonText(expected.artifactManifest)),
  ]);
  console.log(`Updated R9 candidate ledger: ${expected.candidates.length} candidate files; ${expected.candidates.filter(entry => entry.component === "lid").length} lid files.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(await realpath(process.argv[1])).href) {
  await main();
}
