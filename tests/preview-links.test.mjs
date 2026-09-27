import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { resolvePreviewOrigin, previewUrl, previewSourceLabel, PRODUCTION_PREVIEW_ORIGIN } from '../scripts/lib/preview-origin.mjs';
import { missingPreviewTargets } from '../scripts/lib/preview-links-check.mjs';
import { renderReferencePages } from '../scripts/sync-reference-tables.mjs';
import { readFile } from 'node:fs/promises';

test('production, dev, and override origins', () => {
  assert.equal(resolvePreviewOrigin(), PRODUCTION_PREVIEW_ORIGIN);
  assert.equal(resolvePreviewOrigin({ dev: true }), '');
  assert.equal(resolvePreviewOrigin({ dev: true, override: 'http://localhost:8787/' }), 'http://localhost:8787');
  assert.equal(previewUrl('/previews/r8-simple-lid.html', ''), '/previews/r8-simple-lid.html');
  assert.equal(previewUrl('/previews/r8-simple-lid.html', PRODUCTION_PREVIEW_ORIGIN), `${PRODUCTION_PREVIEW_ORIGIN}/previews/r8-simple-lid.html`);
  assert.equal(previewSourceLabel(''), 'ローカル (public/)');
  assert.equal(previewSourceLabel(PRODUCTION_PREVIEW_ORIGIN), 'zudo-case-preview.zudolab.dev');
  assert.throws(() => resolvePreviewOrigin({ override: 'http://localhost:8787/path' }));
});

test('missing markdown, frame/component, and generated preview targets fail', async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'zudo-preview-links-'));
  try {
    await mkdir(path.join(dir, 'downloads/reference'), { recursive: true });
    await mkdir(path.join(dir, 'previews'), { recursive: true });
    const forms = [
      '[file](/downloads/reference/missing.zip)',
      '<iframe src="/previews/missing.html" />',
      '<PreviewFrame path="/previews/missing.html" />',
      '<PreviewLink path="/downloads/reference/missing.zip">file</PreviewLink>',
    ];
    for (const form of forms) assert.equal((await missingPreviewTargets(form, dir)).length, 1, form);
    const spec = JSON.parse(await readFile(new URL('../project/current-spec.json', import.meta.url), 'utf8'));
    const generated = renderReferencePages(spec).find(page => page.rel.endsWith('models/7u40.mdx')).text;
    assert.ok((await missingPreviewTargets(generated, dir)).length >= 3);
    await writeFile(path.join(dir, 'previews/r8-simple-lid.html'), 'ok');
    assert.deepEqual(await missingPreviewTargets('<PreviewFrame path="/previews/r8-simple-lid.html" />', dir), []);
  } finally { await rm(dir, { recursive: true, force: true }); }
});
