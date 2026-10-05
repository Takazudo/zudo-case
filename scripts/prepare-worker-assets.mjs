import { createHash, randomUUID } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { cp, lstat, mkdir, readdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { extname, join, relative, resolve, sep } from "node:path";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";

const root = resolve(process.env.ZUDO_CASE_ROOT ?? fileURLToPath(new URL("..", import.meta.url)));
const dist = join(root, "dist");
const preview = join(root, "dist-preview");
const generated = join(root, ".worker-build");
const manifestPath = join(generated, "large-assets.json");
const generationPath = join(generated, "generation.json");
const routedLargeAssets = new Set([
  "/previews/r6-body.html",
  "/downloads/archive/r7-m3-lid-source.zip",
]);

function positiveByteCount(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined) return fallback;
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`${name} must be a positive integer`);
  return value;
}
const limit = positiveByteCount("PREPARE_LIMIT_BYTES", 25 * 1024 * 1024);
const chunkSize = positiveByteCount("PREPARE_CHUNK_BYTES", 20 * 1024 * 1024);

async function exists(path) {
  try { await lstat(path); return true; }
  catch (error) { if (error.code === "ENOENT") return false; throw error; }
}

async function* files(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) yield* files(path);
    else if (entry.isFile()) yield path;
    else throw new Error(`Unsupported input entry: ${path}`);
  }
}

function routeFor(base, file) {
  return `/${relative(base, file).split(sep).join("/")}`;
}

async function validateInputs() {
  for (const name of ["previews", "downloads"]) {
    const directory = join(dist, name);
    if (!(await lstat(directory)).isDirectory()) throw new Error(`Input is not a directory: ${directory}`);
    for await (const file of files(directory)) {
      const size = (await stat(file)).size;
      if (size > limit && !routedLargeAssets.has(routeFor(dist, file))) {
        throw new Error(`Oversized asset needs a Worker route: ${routeFor(dist, file)} (${size} bytes)`);
      }
    }
  }
}

async function verifyPrepared() {
  const previewGeneration = JSON.parse(await readFile(join(preview, ".generation.json"), "utf8"));
  const workerGeneration = JSON.parse(await readFile(generationPath, "utf8"));
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const id = previewGeneration.id;
  if (typeof id !== "string" || !id || workerGeneration.id !== id ||
      !manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    throw new Error("generation metadata is inconsistent");
  }
  for (const [route, asset] of Object.entries(manifest)) {
    if (!routedLargeAssets.has(route) || !asset || !Number.isSafeInteger(asset.size) || asset.size <= 0 ||
        !Array.isArray(asset.chunks) || asset.chunks.length === 0) throw new Error(`invalid manifest entry: ${route}`);
    let size = 0;
    for (const chunk of asset.chunks) {
      if (typeof chunk !== "string" || !chunk.startsWith(`/__worker_parts${route}.part`) ||
          !/^\d+$/.test(chunk.slice(`/__worker_parts${route}.part`.length))) {
        throw new Error(`invalid chunk path: ${chunk}`);
      }
      size += (await stat(join(preview, chunk.slice(1)))).size;
    }
    if (size !== asset.size) throw new Error(`chunk size mismatch: ${route}`);
  }
  return id;
}

async function cleanStale() {
  // Live output has already been verified. Backups and staging from older crashed runs are now stale.
  for (const [directory, prefix] of [[root, "dist-preview."], [generated, "large-assets."], [generated, "generation."]]) {
    if (!(await exists(directory))) continue;
    for (const name of await readdir(directory)) {
      if (name.startsWith(prefix) && /\.(?:staging|backup)-/.test(name)) {
        await rm(join(directory, name), { recursive: true, force: true });
        console.log(`Removed stale ${join(directory, name)}`);
      }
    }
  }
}

function failAt(step) {
  if (process.env.PREPARE_FAIL_AT === step) throw new Error(`Injected failure at ${step}`);
}

async function stage(previewStage, manifestStage, generationStage, id) {
  await mkdir(previewStage);
  for (const directory of ["previews", "downloads"]) {
    await cp(join(dist, directory), join(previewStage, directory), { recursive: true });
  }
  await writeFile(
    join(previewStage, "index.html"),
    '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>ZUDO CASE previews</title></head><body><h1>ZUDO CASE previews</h1><p><a href="https://zudo-case.zudolab.dev/docs/resources/">文書とデータの説明</a></p><ul><li><a href="/previews/r8-simple-lid.html">R8載せ蓋プレビュー</a></li><li><a href="/previews/r6-body.html">R6本体プレビュー</a></li><li><a href="/previews/two-way/tw-01.html">TW-01 2WAY実験設計</a></li></ul><p>表示用・参照用の資料です。製作承認データではありません。</p></body></html>\n',
  );
  await writeFile(join(previewStage, "robots.txt"), "User-agent: *\nDisallow: /\n");
  const manifest = {};
  for await (const file of files(previewStage)) {
    const size = (await stat(file)).size;
    if (size <= limit) continue;
    const urlPath = routeFor(previewStage, file);
    // validateInputs already checked this, but retain the invariant at the write site.
    if (!routedLargeAssets.has(urlPath)) throw new Error(`Oversized asset needs a Worker route: ${urlPath}`);
    const hash = createHash("sha256");
    const chunks = [];
    const type = extname(file) === ".html" ? "text/html; charset=utf-8" : "application/zip";
    let offset = 0;
    for (let index = 0; offset < size; index++) {
      const length = Math.min(chunkSize, size - offset);
      const chunkPath = `/__worker_parts${urlPath}.part${index}`;
      const output = join(previewStage, chunkPath.slice(1));
      await mkdir(join(output, ".."), { recursive: true });
      await pipeline(createReadStream(file, { start: offset, end: offset + length - 1 }), createWriteStream(output));
      for await (const bytes of createReadStream(output)) hash.update(bytes);
      chunks.push(chunkPath);
      offset += length;
    }
    await rm(file);
    manifest[urlPath] = { size, type, hash: hash.digest("hex"), chunks };
  }
  await writeFile(join(previewStage, ".generation.json"), `${JSON.stringify({ id })}\n`);
  await writeFile(manifestStage, `${JSON.stringify(manifest, null, 2)}\n`);
  await writeFile(generationStage, `${JSON.stringify({ id })}\n`);
  return manifest;
}

async function swap(paths) {
  const backedUp = [];
  const published = [];
  try {
    for (const item of paths) {
      if (await exists(item.live)) {
        await rename(item.live, item.backup);
        backedUp.push(item);
      }
      failAt(`after-${item.name}-backup`);
    }
    for (const item of paths) {
      await rename(item.staging, item.live);
      published.push(item);
      failAt(`after-${item.name}-publish`);
    }
  } catch (error) {
    const recoveryErrors = [];
    for (const item of published.reverse()) {
      try { await rm(item.live, { recursive: true, force: true }); }
      catch (restoreError) { recoveryErrors.push(restoreError); }
    }
    for (const item of backedUp.reverse()) {
      try { await rename(item.backup, item.live); }
      catch (restoreError) { recoveryErrors.push(restoreError); }
    }
    if (recoveryErrors.length) throw new AggregateError([error, ...recoveryErrors], "Swap failed and rollback was incomplete");
    throw error;
  }
}

async function main() {
  const inputs = await Promise.all(["previews", "downloads"].map((name) => exists(join(dist, name))));
  const live = await Promise.all([preview, manifestPath, generationPath].map(exists));
  if (inputs.every(Boolean)) {
    await validateInputs();
  } else if (inputs.every((value) => !value) && live.every(Boolean)) {
    try {
      const id = await verifyPrepared();
      await cleanStale();
      console.log(`already prepared (generation ${id})`);
      return;
    } catch (error) {
      throw new Error(`Prepared output is incomplete; run pnpm build again. ${error.message}`, { cause: error });
    }
  } else {
    throw new Error("Partial prepare state; run pnpm build again. No output changed.");
  }

  if (live.every(Boolean)) {
    try { await verifyPrepared(); await cleanStale(); }
    catch { /* Preserve uncertain leftovers; the new generation still stages safely. */ }
  }
  const id = `${Date.now()}-${randomUUID()}`;
  const previewStage = `${preview}.staging-${id}`;
  const manifestStage = join(generated, `large-assets.staging-${id}.json`);
  const generationStage = join(generated, `generation.staging-${id}.json`);
  const paths = [
    { name: "preview", live: preview, staging: previewStage, backup: `${preview}.backup-${id}` },
    { name: "manifest", live: manifestPath, staging: manifestStage, backup: join(generated, `large-assets.backup-${id}.json`) },
    { name: "generation", live: generationPath, staging: generationStage, backup: join(generated, `generation.backup-${id}.json`) },
  ];
  await mkdir(generated, { recursive: true });
  let manifest;
  try {
    manifest = await stage(previewStage, manifestStage, generationStage, id);
    failAt("after-stage");
    await swap(paths);
  } finally {
    for (const item of paths) await rm(item.staging, { recursive: true, force: true });
  }
  for (const item of paths) await rm(item.backup, { recursive: true, force: true });
  try {
    for (const directory of ["previews", "downloads"]) await rm(join(dist, directory), { recursive: true });
  } catch (error) {
    throw new Error(`Output is prepared, but source cleanup failed. Remove dist/previews and dist/downloads manually. ${error.message}`, { cause: error });
  }
  console.log(`Prepared ${Object.keys(manifest).length} oversized assets for Workers (generation ${id}).`);
}

await main();
