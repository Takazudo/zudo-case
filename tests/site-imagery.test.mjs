import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = rel => readFile(new URL(`../${rel}`, import.meta.url));

test('Graphite is explicit in the runtime config and the scaffold preset', async () => {
  const config = (await read('zfb.config.ts')).toString();
  const preset = JSON.parse(await read('setup.preset.json'));
  assert.match(config, /themePack: "graphite"/);
  assert.equal(preset.themePack, 'graphite');
});

test('sharing metadata points at the committed card and keeps noindex', async () => {
  const config = (await read('zfb.config.ts')).toString();
  assert.match(config, /siteUrl: "https:\/\/zudo-case\.zudolab\.dev"/);
  assert.match(config, /logo: "\/img\/zudo-case-logo\.svg"/);
  assert.match(config, /ogImage: "\/img\/ogp\.png"/);
  assert.match(config, /twitterCard: "summary_large_image"/);
  assert.match(config, /noindex: true/);
});

test('ogp.png is a 1200x630 PNG (zudo-doc declares these og:image dimensions)', async () => {
  const png = await read('public/img/ogp.png');
  assert.deepEqual([...png.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  assert.equal(png.subarray(12, 16).toString('latin1'), 'IHDR');
  assert.equal(png.readUInt32BE(16), 1200);
  assert.equal(png.readUInt32BE(20), 630);
});

test('logo SVG is a transparent mask source, not an opaque rectangle', async () => {
  const svg = (await read('public/img/zudo-case-logo.svg')).toString();
  assert.match(svg, /viewBox="0 0 1200 630"/);
  assert.doesNotMatch(svg, /<rect\b/);
  assert.doesNotMatch(svg, /<image\b|<text\b/);
});
