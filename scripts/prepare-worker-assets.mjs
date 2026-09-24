import { createHash } from "node:crypto";
import { createReadStream, createWriteStream } from "node:fs";
import { mkdir, readdir, rename, rm, stat, writeFile } from "node:fs/promises";
import { extname, join, relative, sep } from "node:path";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";

// Cloudflare Workers Static Assets accepts files no larger than 25 MiB.
const limit = 25 * 1024 * 1024;
const chunkSize = 20 * 1024 * 1024;
const dist = new URL("../dist/", import.meta.url);
const preview = new URL("../dist-preview/", import.meta.url);
const generated = new URL("../.worker-build/", import.meta.url);
const routedLargeAssets = new Set([
  "/previews/r6-body.html",
  "/downloads/archive/r7-m3-lid-source.zip",
]);

async function* files(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) yield* files(path);
    else if (entry.isFile()) yield path;
  }
}

const distPath = fileURLToPath(dist);
const previewPath = fileURLToPath(preview);
await stat(distPath);
await rm(previewPath, { recursive: true, force: true });
await mkdir(previewPath, { recursive: true });
for (const directory of ["previews", "downloads"]) {
  await rename(join(distPath, directory), join(previewPath, directory));
}
await writeFile(
  join(previewPath, "index.html"),
  '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>ZUDO CASE previews</title></head><body><h1>ZUDO CASE previews</h1><p><a href="https://zudo-case.zudolab.dev/docs/resources/">文書とデータの説明</a></p><ul><li><a href="/previews/r8-simple-lid.html">R8載せ蓋プレビュー</a></li><li><a href="/previews/r6-body.html">R6本体プレビュー</a></li></ul><p>表示用・参照用の資料です。製作承認データではありません。</p></body></html>\n',
);
await writeFile(join(previewPath, "robots.txt"), "User-agent: *\nDisallow: /\n");
const manifest = {};
for await (const file of files(previewPath)) {
  const size = (await stat(file)).size;
  if (size <= limit) continue;

  const urlPath = `/${relative(previewPath, file).split(sep).join("/")}`;
  if (!routedLargeAssets.has(urlPath)) {
    throw new Error(`Oversized asset needs a Worker route: ${urlPath} (${size} bytes)`);
  }

  const hash = createHash("sha256");
  const chunks = [];
  const extension = extname(file);
  const type = extension === ".html" ? "text/html; charset=utf-8" : "application/zip";
  const base = `/__worker_parts${urlPath}`;
  let offset = 0;
  let index = 0;
  while (offset < size) {
    const length = Math.min(chunkSize, size - offset);
    const chunkPath = `${base}.part${index}`;
    const output = join(previewPath, chunkPath.slice(1));
    await mkdir(join(output, ".."), { recursive: true });
    await pipeline(
      createReadStream(file, { start: offset, end: offset + length - 1 }),
      createWriteStream(output),
    );
    for await (const bytes of createReadStream(output)) hash.update(bytes);
    chunks.push(chunkPath);
    offset += length;
    index++;
  }
  await rm(file);
  manifest[urlPath] = { size, type, hash: hash.digest("hex"), chunks };
}

await mkdir(generated, { recursive: true });
await writeFile(new URL("large-assets.json", generated), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Prepared ${Object.keys(manifest).length} oversized assets for Workers.`);
