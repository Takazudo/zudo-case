import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const script = fileURLToPath(new URL("../scripts/prepare-worker-assets.mjs", import.meta.url));
const sourceHtml = Buffer.from("<html>" + "x".repeat(3100) + "</html>");
const sourceZip = Buffer.from("PK" + "z".repeat(2700));

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "prepare-worker-assets-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await inputs(root);
  return root;
}

async function inputs(root) {
  await mkdir(join(root, "dist/previews"), { recursive: true });
  await mkdir(join(root, "dist/downloads/archive"), { recursive: true });
  await writeFile(join(root, "dist/previews/r6-body.html"), sourceHtml);
  await writeFile(join(root, "dist/downloads/archive/r7-m3-lid-source.zip"), sourceZip);
  await writeFile(join(root, "dist/previews/r8-simple-lid.html"), "small preview");
}

function run(root, failAt) {
  return spawnSync(process.execPath, [script], {
    encoding: "utf8",
    env: {
      ...process.env,
      ZUDO_CASE_ROOT: root,
      PREPARE_LIMIT_BYTES: "1024",
      PREPARE_CHUNK_BYTES: "700",
      ...(failAt ? { PREPARE_FAIL_AT: failAt } : {}),
    },
  });
}

async function snapshot(root) {
  const result = {};
  for (const name of ["dist-preview", ".worker-build"]) {
    async function walk(path, key) {
      for (const entry of await readdir(path, { withFileTypes: true })) {
        const next = join(path, entry.name);
        const label = `${key}/${entry.name}`;
        if (entry.isDirectory()) await walk(next, label);
        else result[label] = (await readFile(next)).toString("base64");
      }
    }
    await walk(join(root, name), name);
  }
  return result;
}

async function assertNoTemporary(root) {
  assert.equal((await readdir(root)).some((name) => /dist-preview\.(?:staging|backup)-/.test(name)), false);
  assert.equal((await readdir(join(root, ".worker-build"))).some((name) => /\.(?:staging|backup)-/.test(name)), false);
}

async function assertPrepared(root) {
  const preview = join(root, "dist-preview");
  const manifest = JSON.parse(await readFile(join(root, ".worker-build/large-assets.json"), "utf8"));
  const { id } = JSON.parse(await readFile(join(preview, ".generation.json"), "utf8"));
  assert.equal(id, JSON.parse(await readFile(join(root, ".worker-build/generation.json"), "utf8")).id);
  for (const [route, original] of [
    ["/previews/r6-body.html", sourceHtml],
    ["/downloads/archive/r7-m3-lid-source.zip", sourceZip],
  ]) {
    const asset = manifest[route];
    assert.equal(asset.size, original.length);
    const chunks = await Promise.all(asset.chunks.map((path) => readFile(join(preview, path.slice(1)))));
    assert.deepEqual(Buffer.concat(chunks), original);
    for (const path of asset.chunks) assert.ok((await stat(join(preview, path.slice(1)))).size <= 1024);
  }
  assert.equal(Object.keys(manifest).length, 2);
  await assert.rejects(stat(join(root, "dist/previews")), { code: "ENOENT" });
  await assert.rejects(stat(join(root, "dist/downloads")), { code: "ENOENT" });
}

test("fresh run stages complete output; rerun verifies and changes no bytes", async (t) => {
  const root = await fixture(t);
  assert.equal(run(root).status, 0);
  await assertPrepared(root);
  const before = await snapshot(root);
  const second = run(root);
  assert.equal(second.status, 0, second.stderr);
  assert.match(second.stdout, /already prepared \(generation /);
  assert.deepEqual(await snapshot(root), before);
});

test("missing chunk rejects rerun without changing live output", async (t) => {
  const root = await fixture(t);
  assert.equal(run(root).status, 0);
  const manifest = JSON.parse(await readFile(join(root, ".worker-build/large-assets.json"), "utf8"));
  await rm(join(root, "dist-preview", manifest["/previews/r6-body.html"].chunks[0].slice(1)));
  const before = await snapshot(root);
  const result = run(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /run pnpm build again/);
  assert.deepEqual(await snapshot(root), before);
});

test("generation mismatch rejects rerun without changing live output", async (t) => {
  const root = await fixture(t);
  assert.equal(run(root).status, 0);
  await writeFile(join(root, ".worker-build/generation.json"), '{"id":"wrong"}\n');
  const before = await snapshot(root);
  const result = run(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /run pnpm build again/);
  assert.deepEqual(await snapshot(root), before);
});

test("verified live output allows stale staging and backup cleanup", async (t) => {
  const root = await fixture(t);
  assert.equal(run(root).status, 0);
  const before = await snapshot(root);
  await mkdir(join(root, "dist-preview.staging-old"));
  await mkdir(join(root, "dist-preview.backup-old"));
  await writeFile(join(root, ".worker-build/large-assets.staging-old.json"), "old");
  await writeFile(join(root, ".worker-build/generation.backup-old.json"), "old");
  const result = run(root);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Removed stale/);
  assert.deepEqual(await snapshot(root), before);
  await assertNoTemporary(root);
});

test("partial input preserves previous output", async (t) => {
  const root = await fixture(t);
  assert.equal(run(root).status, 0);
  const before = await snapshot(root);
  await mkdir(join(root, "dist/previews"), { recursive: true });
  const result = run(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Partial prepare state/);
  assert.deepEqual(await snapshot(root), before);
});

test("unrouted oversize rejects before writing", async (t) => {
  const root = await fixture(t);
  await writeFile(join(root, "dist/previews/unrouted.html"), Buffer.alloc(1025));
  const result = run(root);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /Oversized asset needs a Worker route/);
  await assert.rejects(stat(join(root, "dist-preview")), { code: "ENOENT" });
  await assert.rejects(stat(join(root, ".worker-build")), { code: "ENOENT" });
});

for (const step of [
  "after-stage",
  "after-preview-backup", "after-manifest-backup", "after-generation-backup",
  "after-preview-publish", "after-manifest-publish", "after-generation-publish",
]) {
  test(`${step} rolls back to the previous good generation`, async (t) => {
    const root = await fixture(t);
    assert.equal(run(root).status, 0);
    const before = await snapshot(root);
    await inputs(root);
    const result = run(root, step);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Injected failure/);
    assert.deepEqual(await snapshot(root), before);
    await assertNoTemporary(root);
    assert.deepEqual(await readFile(join(root, "dist/previews/r6-body.html")), sourceHtml);
    assert.deepEqual(await readFile(join(root, "dist/downloads/archive/r7-m3-lid-source.zip")), sourceZip);
  });
}
