import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";
import { createWorker } from "../src/worker-handler.js";

const assetPath = "/fixture.bin";

function createFixture({ chunks, missingChunk, truncateChunk, corruptChunk } = {}) {
  const original = Buffer.from("small worker stream fixture");
  const sourceChunks = chunks ?? [original];
  const chunkPaths = sourceChunks.map((_, index) => `/__test_chunks__/${index}`);
  const manifestHash = createHash("sha256").update(original).digest("hex");
  const manifest = {
    [assetPath]: {
      type: "application/octet-stream",
      size: original.byteLength,
      hash: manifestHash,
      chunks: chunkPaths,
    },
  };
  const calls = [];
  const worker = createWorker(manifest);
  const env = {
    ASSETS: {
      async fetch(request) {
        const path = new URL(request.url).pathname;
        calls.push(path);
        const index = chunkPaths.indexOf(path);
        if (index === missingChunk) return new Response(null, { status: 404 });

        let body = Buffer.from(sourceChunks[index]);
        if (index === truncateChunk) body = body.subarray(0, Math.max(0, body.byteLength - 2));
        if (index === corruptChunk && body.byteLength > 0) body[0] ^= 0xff;
        return new Response(body);
      },
    },
  };

  return { original, chunkPaths, calls, manifestHash, worker, env };
}

async function readAsset(fixture) {
  return fixture.worker.fetch(new Request(`https://worker.test${assetPath}`), fixture.env);
}

test("small fixture asset streams every chunk and preserves its manifest metadata", async () => {
  const original = Buffer.from("small worker stream fixture");
  const fixture = createFixture({
    chunks: [original.subarray(0, 7), original.subarray(7)],
  });

  const response = await readAsset(fixture);
  const served = Buffer.from(await response.arrayBuffer());

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-length"), String(original.byteLength));
  assert.equal(response.headers.get("content-type"), "application/octet-stream");
  assert.deepEqual(served, original);
  assert.deepEqual(fixture.calls, fixture.chunkPaths);
});

test("missing first chunk rejects the asset body", async () => {
  const original = Buffer.from("small worker stream fixture");
  const fixture = createFixture({
    chunks: [original.subarray(0, 7), original.subarray(7)],
    missingChunk: 0,
  });
  const response = await readAsset(fixture);

  await assert.rejects(response.arrayBuffer(), /Unable to read asset chunk/);
  assert.deepEqual(fixture.calls, [fixture.chunkPaths[0]]);
});

test("missing later chunk rejects the asset body", async () => {
  const original = Buffer.from("small worker stream fixture");
  const fixture = createFixture({
    chunks: [original.subarray(0, 7), original.subarray(7)],
    missingChunk: 1,
  });
  const response = await readAsset(fixture);

  await assert.rejects(response.arrayBuffer(), /Unable to read asset chunk/);
  assert.deepEqual(fixture.calls, fixture.chunkPaths);
});

test("short chunk rejects the body when its final byte count differs from the manifest", async () => {
  const fixture = createFixture({ truncateChunk: 0 });
  const response = await readAsset(fixture);

  await assert.rejects(response.arrayBuffer(), /Asset stream size mismatch/);
});

test("same-length altered chunk streams and differs from the manifest SHA-256", async () => {
  const fixture = createFixture({ corruptChunk: 0 });
  const response = await readAsset(fixture);
  const served = Buffer.from(await response.arrayBuffer());
  const actualHash = createHash("sha256").update(served).digest("hex");

  assert.equal(served.byteLength, fixture.original.byteLength);
  assert.notEqual(actualHash, fixture.manifestHash);
  assert.equal(response.headers.get("content-length"), String(fixture.original.byteLength));
});

test("HEAD returns manifest metadata without fetching any chunks", async () => {
  const fixture = createFixture();
  const response = await fixture.worker.fetch(
    new Request(`https://worker.test${assetPath}`, { method: "HEAD" }),
    fixture.env,
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-length"), String(fixture.original.byteLength));
  assert.equal((await response.arrayBuffer()).byteLength, 0);
  assert.deepEqual(fixture.calls, []);
});
