import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { PRODUCTION_PREVIEW_ORIGIN } from './lib/preview-origin.mjs';
import { extractDocumentUrls } from './lib/preview-links-check.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const dist = path.resolve(process.argv[2] || path.join(root, 'dist'));
const docs = path.join(root, 'src/content/docs');
async function walk(dir, ext) {
  const files = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const target = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await walk(target, ext));
    else if (entry.name.endsWith(ext)) files.push(target);
  }
  return files;
}
const expected = new Set();
for (const file of await walk(docs, '.mdx')) {
  for (const url of extractDocumentUrls(await readFile(file, 'utf8'))) {
    if (/^\/(?:previews|downloads)\//.test(url)) expected.add(`${PRODUCTION_PREVIEW_ORIGIN}${url}`);
  }
}
const pages = await walk(path.join(dist, 'docs'), '.html');
if (!pages.length) throw new Error(`No built docs HTML in ${dist}`);
const html = (await Promise.all(pages.map(file => readFile(file, 'utf8')))).join('\n');
const missing = [...expected].filter(url => !html.includes(url));
const leaked = [...html.matchAll(/(?:href|src)=["']([^"']*(?:\/previews\/|\/downloads\/)[^"']*)["']/g)]
  .map(match => match[1]).filter(url => !url.startsWith(`${PRODUCTION_PREVIEW_ORIGIN}/`));
if (missing.length || leaked.length || /(?:localhost|127\.0\.0\.1):\d+/.test(html)) {
  throw new Error(`Built preview links invalid: ${missing.length} missing, ${leaked.length} wrong-origin links, localhost=${/(?:localhost|127\.0\.0\.1):\d+/.test(html)}\n${[...missing, ...leaked].slice(0, 10).join('\n')}`);
}
console.log(`OK: ${expected.size} production preview URLs in ${pages.length} built docs pages.`);
