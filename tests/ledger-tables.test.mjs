import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFile, mkdir, mkdtemp, readFile, rm, stat, symlink, utimes, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { ARCHIVE_7U40, loadR11Inputs, renderReferencePages } from "../scripts/sync-reference-tables.mjs";

const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const scriptPath = path.join(repoRoot, "scripts/sync-reference-tables.mjs");
const specPath = path.join(repoRoot, "project/current-spec.json");

async function makeFixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "zudo-ledger-tables-"));
  t.after(() => rm(root, { recursive: true, force: true }));

  const scriptDir = path.join(root, "scripts");
  await mkdir(scriptDir, { recursive: true });
  await copyFile(scriptPath, path.join(scriptDir, "sync-reference-tables.mjs"));
  await mkdir(path.join(root, "project"), { recursive: true });
  await copyFile(specPath, path.join(root, "project/current-spec.json"));
  // The current 7U40 tables come from the active R11 selection and its imported outputs.
  const r11 = await loadR11Inputs(repoRoot);
  const out = path.posix.dirname(r11.pointer.manifest_path);
  for (const rel of ["project/release-state.json", r11.pointer.manifest_path, `${out}/validation.json`, `${out}/scene.json`, `${path.posix.dirname(out)}/parameters.json`]) {
    await mkdir(path.dirname(path.join(root, rel)), { recursive: true });
    await copyFile(path.join(repoRoot, rel), path.join(root, rel));
  }

  const spec = JSON.parse(await readFile(specPath, "utf8"));
  const pages = renderReferencePages(spec, r11);
  for (const { rel } of pages) {
    const destination = path.join(root, rel);
    await mkdir(path.dirname(destination), { recursive: true });
    await copyFile(path.join(repoRoot, rel), destination);
  }
  return { root, pages };
}

function runCli(root, ...args) {
  const result = spawnSync(process.execPath, [path.join(root, "scripts/sync-reference-tables.mjs"), ...args], {
    cwd: root,
    encoding: "utf8",
  });
  if (result.error) throw result.error;
  return result;
}

test("synced generated pages pass --check", async t => {
  const { root, pages } = await makeFixture(t);
  assert.equal(pages.length, 6);
  assert.ok(pages.some(p => p.rel === ARCHIVE_7U40));

  const result = runCli(root, "--check");
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /OK: generated reference pages match project\/current-spec\.json/);
});

test("CLI through a symlinked directory runs and detects drift", async t => {
  const { root, pages } = await makeFixture(t);
  const alias = `${root}-alias`;
  await symlink(root, alias, "dir");
  t.after(() => rm(alias));
  const valid = runCli(alias, "--check");
  assert.equal(valid.status, 0, valid.stderr);
  assert.match(valid.stdout, /OK: generated reference pages match/);
  const page = path.join(root, pages[0].rel);
  await writeFile(page, `${await readFile(page, "utf8")}\n<!-- drift -->\n`);
  const invalid = runCli(alias, "--check");
  assert.equal(invalid.status, 1, invalid.stderr);
  assert.ok(invalid.stderr.includes(pages[0].rel));
});

test("a ledger-only change fails --check and names affected pages", async t => {
  const { root } = await makeFixture(t);
  const fixtureSpecPath = path.join(root, "project/current-spec.json");
  const spec = JSON.parse(await readFile(fixtureSpecPath, "utf8"));
  spec.models["7u40"].metal_mm[0] += 10;
  await writeFile(fixtureSpecPath, `${JSON.stringify(spec, null, 2)}\n`);

  // The legacy R6 7U40 values now feed only the archive page; the current 7U40 tables follow R11.
  const result = runCli(root, "--check");
  assert.equal(result.status, 1);
  assert.ok(result.stderr.includes(ARCHIVE_7U40), result.stderr);
  assert.doesNotMatch(result.stderr, /src\/content\/docs\/metal-case\/models\/7u40\.mdx/);
  assert.match(result.stderr, /node scripts\/sync-reference-tables\.mjs/);

  spec.models["3u60"].metal_mm[0] += 10;
  await writeFile(fixtureSpecPath, `${JSON.stringify(spec, null, 2)}\n`);
  const current = runCli(root, "--check");
  assert.match(current.stderr, /src\/content\/docs\/metal-case\/models\/3u60\.mdx/);
  assert.match(current.stderr, /src\/content\/docs\/metal-case\/models\/comparison\.mdx/);
});

test("an R11 manifest change fails --check on the current 7U40 table", async t => {
  const { root } = await makeFixture(t);
  const pointer = JSON.parse(await readFile(path.join(root, "project/release-state.json"), "utf8")).current_metal_7u40_candidate;
  const manifestPath = path.join(root, pointer.manifest_path);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const sheet = manifest.parts.find(p => p.category === "aluminum");
  sheet.dimensions_mm[0] += 1;
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  const result = runCli(root, "--check");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /src\/content\/docs\/metal-case\/models\/7u40\.mdx/);
});

test("R11 envelope and washer data reach the 7U40 table, comparison and BOM", async t => {
  const { root } = await makeFixture(t);
  const pointer = JSON.parse(await readFile(path.join(root, "project/release-state.json"), "utf8")).current_metal_7u40_candidate;
  const out = path.posix.dirname(pointer.manifest_path);
  const paramsPath = path.join(root, path.posix.dirname(out), "parameters.json");
  const params = JSON.parse(await readFile(paramsPath, "utf8"));
  params.body.height += 1;
  await writeFile(paramsPath, `${JSON.stringify(params, null, 2)}\n`);
  const envelope = runCli(root, "--check");
  assert.equal(envelope.status, 1);
  for (const rel of ["models/7u40.mdx", "models/comparison.mdx"]) assert.ok(envelope.stderr.includes(`src/content/docs/metal-case/${rel}`), envelope.stderr);

  const { root: other } = await makeFixture(t);
  const scenePath = path.join(other, out, "scene.json");
  const scene = JSON.parse(await readFile(scenePath, "utf8"));
  scene.lid_metadata.counts.round_washers += 1;
  await writeFile(scenePath, JSON.stringify(scene));
  const washer = runCli(other, "--check");
  assert.equal(washer.status, 1);
  for (const rel of ["models/7u40.mdx", "manufacturing/bom.mdx"]) assert.ok(washer.stderr.includes(`src/content/docs/metal-case/${rel}`), washer.stderr);
});

test("an R11 revision or approval drift is refused instead of rendered", async t => {
  const { root } = await makeFixture(t);
  const pointer = JSON.parse(await readFile(path.join(root, "project/release-state.json"), "utf8")).current_metal_7u40_candidate;
  const manifestPath = path.join(root, pointer.manifest_path);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  manifest.production_approved = true;
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  const result = runCli(root, "--check");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /approval drift/);
});

test("a hand-edited generated page fails --check", async t => {
  const { root } = await makeFixture(t);
  const rel = "src/content/docs/metal-case/models/7u40.mdx";
  const pagePath = path.join(root, rel);
  await writeFile(pagePath, `${await readFile(pagePath, "utf8")}\n<!-- hand edit -->\n`);

  const result = runCli(root, "--check");
  assert.equal(result.status, 1);
  assert.ok(result.stderr.includes(rel));
});

test("--check leaves fixture content and mtimes unchanged", async t => {
  const { root, pages } = await makeFixture(t);
  const specPath = path.join(root, "project/current-spec.json");
  const editedRel = pages[0].rel;
  const editedPath = path.join(root, editedRel);
  await writeFile(editedPath, `${await readFile(editedPath, "utf8")}\n<!-- drift -->\n`);

  const trackedPaths = [specPath, ...pages.map(({ rel }) => path.join(root, rel))];
  const oldTime = new Date("2001-02-03T04:05:06.000Z");
  for (const trackedPath of trackedPaths) await utimes(trackedPath, oldTime, oldTime);
  const before = await Promise.all(trackedPaths.map(async trackedPath => ({
    content: await readFile(trackedPath),
    mtimeNs: (await stat(trackedPath, { bigint: true })).mtimeNs,
  })));

  const result = runCli(root, "--check");
  assert.equal(result.status, 1);

  const after = await Promise.all(trackedPaths.map(async trackedPath => ({
    content: await readFile(trackedPath),
    mtimeNs: (await stat(trackedPath, { bigint: true })).mtimeNs,
  })));
  assert.deepEqual(after, before);
});

test("missing generated pages fail --check", async t => {
  const { root, pages } = await makeFixture(t);
  const missing = pages[0].rel;
  await rm(path.join(root, missing));

  const result = runCli(root, "--check");
  assert.equal(result.status, 1);
  assert.ok(result.stderr.includes(`${missing} (missing)`));
});

test("regeneration restores a passing --check", async t => {
  const { root } = await makeFixture(t);
  const fixtureSpecPath = path.join(root, "project/current-spec.json");
  const spec = JSON.parse(await readFile(fixtureSpecPath, "utf8"));
  spec.models["7u40"].metal_mm[0] += 10;
  await writeFile(fixtureSpecPath, `${JSON.stringify(spec, null, 2)}\n`);

  const beforeRegeneration = runCli(root, "--check");
  assert.equal(beforeRegeneration.status, 1);

  const regeneration = runCli(root);
  assert.equal(regeneration.status, 0, regeneration.stderr);
  assert.match(regeneration.stdout, /Generated 6 reference pages/);

  const afterRegeneration = runCli(root, "--check");
  assert.equal(afterRegeneration.status, 0, afterRegeneration.stderr);
});
