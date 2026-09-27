import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const DEFAULT_ORIGIN = "https://zudo-case-preview.zudolab.dev";
export const ASSET_ROUTES = [
  "/previews/r6-body.html",
  "/downloads/archive/r7-m3-lid-source.zip",
];
export const REPORT_SCOPE = "full-body transport identity — not WebGL/browser or manufacturing validation";

const defaultRepoRoot = fileURLToPath(new URL("../", import.meta.url));

export class VerificationFailure extends Error {
  constructor(message, result) {
    super(message);
    this.name = "VerificationFailure";
    this.result = result;
  }
}

export function validateOrigin(input) {
  if (typeof input !== "string" || !/^https?:\/\/[^/?#]+\/?$/i.test(input)) {
    throw new TypeError("Origin must be an http(s) origin with no credentials, path, query, or fragment");
  }

  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    throw new TypeError("Origin must be a valid http(s) origin with no credentials, path, query, or fragment");
  }

  if (
    (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new TypeError("Origin must be an http(s) origin with no credentials, path, query, or fragment");
  }

  return parsed.origin;
}

async function hashLocalFile(localPath) {
  const info = await stat(localPath);
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(localPath)) hash.update(chunk);
  return { expectedBytes: info.size, expectedSha256: hash.digest("hex") };
}

function makeFailure(message, result) {
  return new VerificationFailure(message, { ...result, ok: false });
}

export async function verifyRemoteAsset(localPath, url, timeoutMs = 120_000) {
  const local = await hashLocalFile(localPath);
  const baseResult = {
    url: String(url),
    status: null,
    ...local,
    receivedBytes: 0,
    actualSha256: null,
    ok: false,
    failure: null,
    retryable: false,
  };

  let response;
  try {
    response = await fetch(url, {
      redirect: "follow",
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    throw makeFailure(`Full GET failed for ${url}: ${error.message}`, {
      ...baseResult,
      failure: "transport",
      retryable: true,
      error: error.message,
    });
  }

  const responseResult = { ...baseResult, status: response.status };
  if (response.status !== 200) {
    await response.body?.cancel().catch(() => {});
    throw makeFailure(`Expected HTTP 200 from ${url}; received ${response.status}`, {
      ...responseResult,
      failure: "http_status",
      retryable: true,
      error: `Expected HTTP 200; received ${response.status}`,
    });
  }
  if (!response.body) {
    throw makeFailure(`HTTP 200 response from ${url} has no body`, {
      ...responseResult,
      failure: "missing_body",
      retryable: false,
      error: "HTTP 200 response has no body",
    });
  }

  const actual = createHash("sha256");
  let receivedBytes = 0;
  try {
    for await (const chunk of response.body) {
      receivedBytes += chunk.byteLength;
      actual.update(chunk);
    }
  } catch (error) {
    throw makeFailure(`Full GET body failed while streaming from ${url}: ${error.message}`, {
      ...responseResult,
      receivedBytes,
      failure: "transport",
      retryable: true,
      error: error.message,
    });
  }

  const actualSha256 = actual.digest("hex");
  const completedResult = { ...responseResult, receivedBytes, actualSha256 };
  if (receivedBytes !== local.expectedBytes) {
    throw makeFailure(`Byte count mismatch for ${url}: expected ${local.expectedBytes}, received ${receivedBytes}`, {
      ...completedResult,
      failure: "size_mismatch",
      error: `Expected ${local.expectedBytes} bytes; received ${receivedBytes}`,
    });
  }
  if (actualSha256 !== local.expectedSha256) {
    throw makeFailure(`SHA-256 mismatch for ${url}`, {
      ...completedResult,
      failure: "hash_mismatch",
      error: "The downloaded body SHA-256 differs from the local asset",
    });
  }

  return { ...completedResult, ok: true, failure: null, retryable: false };
}

export async function verifyDeployedAssets({
  origin = DEFAULT_ORIGIN,
  repoRoot = defaultRepoRoot,
  timeoutMs = 120_000,
} = {}) {
  const normalizedOrigin = validateOrigin(origin);
  const root = resolve(repoRoot);
  const results = [];

  for (const route of ASSET_ROUTES) {
    const localPath = resolve(root, "public", `.${route}`);
    const url = new URL(route, `${normalizedOrigin}/`);
    try {
      const result = await verifyRemoteAsset(localPath, url, timeoutMs);
      results.push({ path: route, ...result });
    } catch (error) {
      if (error instanceof VerificationFailure) {
        results.push({ path: route, ...error.result });
      } else {
        results.push({
          path: route,
          url: String(url),
          status: null,
          expectedBytes: null,
          receivedBytes: 0,
          expectedSha256: null,
          actualSha256: null,
          ok: false,
          failure: "local_file",
          retryable: false,
          error: error.message,
        });
      }
    }
  }

  return {
    checkedAt: new Date().toISOString(),
    origin: normalizedOrigin,
    scope: REPORT_SCOPE,
    results,
  };
}

export async function main(args = process.argv.slice(2)) {
  if (args.length > 2) {
    throw new TypeError("Usage: node scripts/verify-deployed-assets.mjs [origin] [repo-root]");
  }
  const [origin = DEFAULT_ORIGIN, repoRoot = defaultRepoRoot] = args;
  const report = await verifyDeployedAssets({ origin, repoRoot });
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  return report.results.every((result) => result.ok) ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    process.exitCode = await main();
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
