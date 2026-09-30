import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { buildR9CandidateEntries } from "../scripts/sync-r9-ledger.mjs";
import { checkProjectState } from "../scripts/lib/state-checks.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const readJson = async relative => JSON.parse(await readFile(path.join(root, relative), "utf8"));
const isCandidateOutput = output => [".dxf", ".step", ".stl"].includes(path.extname(output.path).toLowerCase()) ||
  ["candidate_package_zip", "single_file_preview_html"].includes(output.kind);

test("R9 ledger registers every CAD output, candidate package, and preview from the output manifest", async () => {
  const outputManifest = await readJson("engineering/r9-prototype-01/out/outputs-manifest.json");
  const candidates = buildR9CandidateEntries(outputManifest);
  const expectedPaths = outputManifest.outputs.filter(isCandidateOutput).map(output => output.path).sort();

  assert.deepEqual(candidates.map(entry => entry.path), expectedPaths);
  assert.equal(candidates.length, 141);
  assert.equal(candidates.filter(entry => entry.component === "package").length, 3);
  assert.equal(candidates.filter(entry => entry.component === "preview").length, 1);
  assert.equal(candidates.filter(entry => entry.component === "lid").length, 11);
  assert.equal(candidates.filter(entry => entry.component === "coupon").length, 68);
  assert.equal(candidates.filter(entry => entry.component === "reference-geometry").length, 25);
  assert.ok(candidates.every(entry => entry.model === "7u40" && entry.revision === "R9-PROTOTYPE-01"));
  assert.equal(new Set(candidates.map(entry => entry.id)).size, candidates.length);

  const release = await readJson("project/release-state.json");
  assert.deepEqual(release.candidate_files.filter(x=>x.revision === "R9-PROTOTYPE-01"), candidates);
  assert.deepEqual(release.current_lid_manufacturing, {
    model: "7u40",
    revision: "R9-FITFIX-01",
    candidate_ids: release.candidate_files.filter(entry => entry.revision === "R9-FITFIX-01" && entry.component === "lid").map(entry => entry.id),
  });
  assert.equal(release.slot_manufacturing, null);
  assert.equal(release.production_approved, false);
  assert.deepEqual(release.published_release_files, []);
});

test("the saved R9 candidate state passes ledger checks without approving production", async () => {
  const [spec, release, quotes, gates] = await Promise.all([
    readJson("project/current-spec.json"),
    readJson("project/release-state.json"),
    readJson("project/quote-records.json"),
    readJson("project/open-issues.json"),
  ]);

  assert.equal(spec.models["7u40"].candidate_revision, "R9-FITFIX-01");
  assert.ok(spec.models["7u40"].candidate_body_summary);
  assert.ok(spec.models["7u40"].candidate_lid_summary);
  for (const model of ["3u60", "7u60"]) assert.equal(spec.models[model].candidate_revision, undefined);
  assert.equal(spec.models["7u40"].manufacturing_release, null);
  assert.equal(spec.release_gate.approved_for_production, false);
  for (const id of Array.from({ length: 11 }, (_, i) => `G${String(i + 1).padStart(2, "0")}`)) {
    const gate = gates.find(item => item.id === id);
    assert.equal(gate?.status, "open", `${id} remains open`);
    assert.equal(gate?.result, null, `${id} has no result`);
  }
  assert.equal(quotes.current_total_jpy, null);
  assert.equal(quotes.current_lid_price_jpy, null);
  assert.equal(quotes.current_band_price_jpy, null);
  assert.deepEqual(await checkProjectState({ root, spec, release, quotes, gates }), []);
});

test("the R9 artifact manifest includes all output files and the self-excluded output manifest", async () => {
  const outputManifest = await readJson("engineering/r9-prototype-01/out/outputs-manifest.json");
  const artifactManifest = await readJson("project/artifact-manifest.json");
  const expectedPaths = [
    ...outputManifest.outputs.map(output => output.path),
    "engineering/r9-prototype-01/out/outputs-manifest.json",
  ];
  const entries = artifactManifest.files.filter(entry =>
    entry.path.startsWith("engineering/r9-prototype-01/out/") ||
    entry.path.startsWith("public/downloads/candidate/7u40-r9-prototype-01-") ||
    entry.path === "public/previews/r9-prototype-01.html",
  );

  assert.deepEqual(entries.map(entry => entry.path).sort(), expectedPaths.sort());
  assert.ok(entries.every(entry => entry.status === "candidate-not-approved"));
});
