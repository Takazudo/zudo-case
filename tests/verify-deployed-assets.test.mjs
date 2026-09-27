import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import {
  ASSET_ROUTES,
  REPORT_SCOPE,
  VerificationFailure,
  validateOrigin,
  verifyDeployedAssets,
  verifyRemoteAsset,
} from "../scripts/verify-deployed-assets.mjs";

const expected = Buffer.from("fixture bytes for streamed verification\n");

async function withFixture(mode, run) {
  const root = await mkdtemp(join(tmpdir(), "verify-deployed-assets-"));
  const publicRoot = join(root, "public");
  await mkdir(publicRoot, { recursive: true });
  const localPath = join(publicRoot, "asset.bin");
  await writeFile(localPath, expected);

  const server = createServer((request, response) => {
    if (mode === "not-found") {
      response.writeHead(404);
      response.end("missing");
      return;
    }
    if (mode === "altered") {
      const altered = Buffer.from(expected);
      altered[0] ^= 0xff;
      response.writeHead(200);
      response.end(altered);
      return;
    }
    if (mode === "short") {
      response.writeHead(200);
      response.end(expected.subarray(0, expected.byteLength - 1));
      return;
    }
    if (mode === "long") {
      response.writeHead(200);
      response.end(Buffer.concat([expected, Buffer.from("extra")]));
      return;
    }
    if (mode === "cut-mid-stream") {
      response.writeHead(200, { "content-length": String(expected.byteLength) });
      response.write(expected.subarray(0, 8));
      setTimeout(() => response.destroy(), 10);
      return;
    }
    response.writeHead(200);
    response.end(expected);
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}/asset.bin`;

  try {
    await run({ localPath, url });
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    await rm(root, { recursive: true, force: true });
  }
}

test("streams a full body and matches the local byte count and SHA-256", async () => {
  await withFixture("match", async ({ localPath, url }) => {
    const result = await verifyRemoteAsset(localPath, url);

    assert.equal(result.status, 200);
    assert.equal(result.expectedBytes, expected.byteLength);
    assert.equal(result.receivedBytes, expected.byteLength);
    assert.equal(result.actualSha256, result.expectedSha256);
    assert.equal(result.ok, true);
  });
});

test("same-length altered body fails by SHA-256", async () => {
  await withFixture("altered", async ({ localPath, url }) => {
    await assert.rejects(verifyRemoteAsset(localPath, url), (error) => {
      assert.ok(error instanceof VerificationFailure);
      assert.equal(error.result.failure, "hash_mismatch");
      assert.equal(error.result.receivedBytes, expected.byteLength);
      assert.equal(error.result.retryable, false);
      return true;
    });
  });
});

test("short 200 body fails by byte count", async () => {
  await withFixture("short", async ({ localPath, url }) => {
    await assert.rejects(verifyRemoteAsset(localPath, url), (error) => {
      assert.ok(error instanceof VerificationFailure);
      assert.equal(error.result.failure, "size_mismatch");
      assert.equal(error.result.retryable, false);
      return true;
    });
  });
});

test("long 200 body fails by byte count", async () => {
  await withFixture("long", async ({ localPath, url }) => {
    await assert.rejects(verifyRemoteAsset(localPath, url), (error) => {
      assert.ok(error instanceof VerificationFailure);
      assert.equal(error.result.failure, "size_mismatch");
      assert.equal(error.result.receivedBytes, expected.byteLength + 5);
      return true;
    });
  });
});

test("HTTP 404 fails as a retryable status failure", async () => {
  await withFixture("not-found", async ({ localPath, url }) => {
    await assert.rejects(verifyRemoteAsset(localPath, url), (error) => {
      assert.ok(error instanceof VerificationFailure);
      assert.equal(error.result.status, 404);
      assert.equal(error.result.failure, "http_status");
      assert.equal(error.result.retryable, true);
      return true;
    });
  });
});

test("body cut mid-stream fails as a retryable transport failure", async () => {
  await withFixture("cut-mid-stream", async ({ localPath, url }) => {
    await assert.rejects(verifyRemoteAsset(localPath, url), (error) => {
      assert.ok(error instanceof VerificationFailure);
      assert.equal(error.result.status, 200);
      assert.equal(error.result.failure, "transport");
      assert.equal(error.result.retryable, true);
      assert.ok(error.result.receivedBytes > 0);
      return true;
    });
  });
});

test("origin validation rejects credentials, paths, queries, and fragments", () => {
  for (const origin of [
    "https://user:pass@example.test",
    "https://example.test/docs",
    "https://example.test?",
    "https://example.test#",
    "ftp://example.test",
  ]) {
    assert.throws(() => validateOrigin(origin), TypeError, origin);
  }
  assert.equal(validateOrigin("https://example.test/"), "https://example.test");
});

test("deployed report records both full-body checks and their evidence scope", async () => {
  const root = await mkdtemp(join(tmpdir(), "verify-deployed-report-"));
  const files = new Map();
  for (const [index, route] of ASSET_ROUTES.entries()) {
    const body = Buffer.from(`fixture public asset ${index}\n`);
    const localPath = join(root, "public", route.slice(1));
    await mkdir(dirname(localPath), { recursive: true });
    await writeFile(localPath, body);
    files.set(route, body);
  }

  const server = createServer((request, response) => {
    const body = files.get(new URL(request.url, "http://localhost").pathname);
    if (!body) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200);
    response.end(body);
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();

  try {
    const report = await verifyDeployedAssets({
      origin: `http://127.0.0.1:${address.port}`,
      repoRoot: root,
    });

    assert.match(report.checkedAt, /^\d{4}-\d{2}-\d{2}T/);
    assert.equal(report.origin, `http://127.0.0.1:${address.port}`);
    assert.equal(report.scope, REPORT_SCOPE);
    assert.deepEqual(report.results.map((result) => result.path), ASSET_ROUTES);
    assert.ok(report.results.every((result) => result.ok));
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    await rm(root, { recursive: true, force: true });
  }
});
