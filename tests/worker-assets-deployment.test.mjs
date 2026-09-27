import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import largeAssets from "../.worker-build/large-assets.json" with { type: "json" };
import worker from "../src/worker.js";

const maxAssetBytes = 25 * 1024 * 1024;
const calls = [];
const env = {
  ASSETS: {
    async fetch(request) {
      const path = new URL(request.url).pathname;
      calls.push(path);
      try {
        const body = await readFile(new URL(`../dist-preview${path}`, import.meta.url));
        return new Response(body);
      } catch {
        return new Response(null, { status: 404 });
      }
    },
  },
};

async function* files(directory) {
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, item.name);
    if (item.isDirectory()) yield* files(path);
    else yield path;
  }
}

test("deployment outputs have separate audiences and stay under the asset size limit", async () => {
  assert.equal(Object.keys(largeAssets).length, 2);
  await assert.rejects(stat(new URL("../dist/previews", import.meta.url)));
  await assert.rejects(stat(new URL("../dist/downloads", import.meta.url)));
  await assert.rejects(stat(new URL("../dist-preview/docs", import.meta.url)));
  for (const directory of ["dist", "dist-preview"]) {
    for await (const file of files(fileURLToPath(new URL(`../${directory}/`, import.meta.url)))) {
      assert.ok((await stat(file)).size <= maxAssetBytes, file);
    }
  }
});

for (const path of [
  "/previews/r6-body.html",
  "/downloads/archive/r7-m3-lid-source.zip",
]) {
  test(`large ${path} streams the original bytes`, async () => {
    const url = `https://zudo-case-preview.zudolab.dev${path}`;
    const head = await worker.fetch(new Request(url, { method: "HEAD" }), env);
    assert.equal(head.status, 200);
    assert.equal(head.headers.get("content-length"), String(largeAssets[path].size));
    assert.equal((await head.arrayBuffer()).byteLength, 0);

    calls.length = 0;
    const response = await worker.fetch(new Request(url), env);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("content-type"), largeAssets[path].type);
    const served = Buffer.from(await response.arrayBuffer());
    const source = await readFile(new URL(`../public${path}`, import.meta.url));
    assert.deepEqual(served, source);
    assert.equal(createHash("sha256").update(served).digest("hex"), largeAssets[path].hash);
    assert.deepEqual(calls, largeAssets[path].chunks);
  });
}
