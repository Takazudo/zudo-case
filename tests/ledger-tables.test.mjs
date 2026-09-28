import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFile, mkdir, mkdtemp, readFile, rm, stat, symlink, utimes, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { renderReferencePages } from "../scripts/sync-reference-tables.mjs";

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

  const spec = JSON.parse(await readFile(specPath, "utf8"));
  const pages = renderReferencePages(spec);
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
  assert.equal(pages.length, 5);

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

  const result = runCli(root, "--check");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /src\/content\/docs\/models\/7u40\.mdx/);
  assert.match(result.stderr, /src\/content\/docs\/models\/comparison\.mdx/);
  assert.match(result.stderr, /node scripts\/sync-reference-tables\.mjs/);
});

test("a hand-edited generated page fails --check", async t => {
  const { root } = await makeFixture(t);
  const rel = "src/content/docs/models/7u40.mdx";
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
  assert.match(regeneration.stdout, /Generated 5 reference pages/);

  const afterRegeneration = runCli(root, "--check");
  assert.equal(afterRegeneration.status, 0, afterRegeneration.stderr);
});
