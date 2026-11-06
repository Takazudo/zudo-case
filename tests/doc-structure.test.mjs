import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkNavigationOrder, checkRouteMap, siblingGroup } from '../scripts/lib/doc-structure-checks.mjs';
import { GENERATED_MARK, frontmatter, isCompatibility, renderRoutePages, routeFor } from '../scripts/sync-doc-routes.mjs';
import { renderReferencePages } from '../scripts/sync-reference-tables.mjs';
import { sidebars } from '../src/sidebars.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const docs = path.join(root, 'src/content/docs');
const SECTIONS = ['overview', 'metal-case', 'printed-5mm', 'two-way', 'shared', 'development'];

async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...await walk(p)); else if (e.name.endsWith('.mdx')) out.push(p);
  }
  return out;
}
async function inventory() {
  const nav = [];
  for (const file of await walk(docs)) {
    const text = await readFile(file, 'utf8');
    const rel = path.relative(docs, file).split(path.sep).join('/');
    nav.push({ path: rel, ...frontmatter(text), body: text.replace(/^---[\s\S]*?\n---\n/, '') });
  }
  return nav;
}
const map = JSON.parse(await readFile(path.join(root, 'project/doc-routes.json'), 'utf8'));
const doc = (p, pos, extra = {}) => ({ path: p, sidebar_position: pos, body: '', ...extra });

test('a category index is ordered among its parent siblings', () => {
  assert.equal(siblingGroup('metal-case/index.mdx'), '.');
  assert.equal(siblingGroup('metal-case/models/index.mdx'), 'metal-case');
  assert.equal(siblingGroup('metal-case/models/7u40.mdx'), 'metal-case/models');
  assert.deepEqual(checkNavigationOrder([doc('metal-case/status.mdx', 10), doc('metal-case/models/index.mdx', 40), doc('metal-case/models/3u60.mdx', 10)]), []);
  const clash = checkNavigationOrder([doc('metal-case/status.mdx', 40), doc('metal-case/models/index.mdx', 40)]);
  assert.equal(clash.length, 1);
  assert.match(clash[0], /metal-case: sidebar_position 40/);
});

test('duplicate sibling positions fail; independent groups may repeat; unlisted pages are ignored', () => {
  assert.equal(checkNavigationOrder([doc('a/x.mdx', 10), doc('a/y.mdx', 10)]).length, 1);
  assert.deepEqual(checkNavigationOrder([doc('a/x.mdx', 10), doc('b/x.mdx', 10), doc('a/index.mdx', 10), doc('b/index.mdx', 20)]), []);
  assert.deepEqual(checkNavigationOrder([doc('a/x.mdx', 10), doc('a/old.mdx', 10, { unlisted: true })]), []);
  assert.equal(checkNavigationOrder([doc('a/index.mdx', 10), doc('b/index.mdx', 10)]).length, 1);
});

test('route map rejects orphaned, hand-written or listed compatibility pages', () => {
  const m = { entries: [
    { source: 'old/a.mdx', canonical: 'new/a.mdx', owner: 'new', treatment: 'moved' },
    { source: null, canonical: 'new/b.mdx', owner: 'new', treatment: 'new' },
  ] };
  const ok = [doc('old/a.mdx', 999, { unlisted: true, body: GENERATED_MARK }), doc('new/a.mdx', 10), doc('new/b.mdx', 20)];
  assert.deepEqual(checkRouteMap(ok, m), []);
  assert.ok(checkRouteMap([...ok, doc('new/c.mdx', 30)], m).some(e => /new\/c\.mdx: doc-routes/.test(e)));
  assert.ok(checkRouteMap([doc('old/a.mdx', 999, { body: GENERATED_MARK }), ...ok.slice(1)], m).some(e => /unlisted: true/.test(e)));
  assert.ok(checkRouteMap([doc('old/a.mdx', 999, { unlisted: true }), ...ok.slice(1)], m).some(e => /生成/.test(e)));
  assert.ok(checkRouteMap([...ok, doc('new/x.mdx', 40, { unlisted: true })], m).some(e => /unlistedページ/.test(e)));
});

test('every baseline document is accounted for and the generated pages are current', async () => {
  const sources = map.entries.filter(e => e.source !== null);
  assert.equal(sources.length, map.baseline.documents);
  assert.equal(new Set(sources.map(e => e.source)).size, sources.length);
  const nav = await inventory();
  assert.deepEqual(checkRouteMap(nav, map), []);
  assert.deepEqual(checkNavigationOrder(nav), []);
  for (const { rel, text } of await renderRoutePages(root)) assert.equal(await readFile(path.join(root, rel), 'utf8'), text, `${rel} drifted; run node scripts/sync-doc-routes.mjs`);
});

test('six sections own every canonical page and match the header navigation', async () => {
  const config = await readFile(path.join(root, 'zfb.config.ts'), 'utf8');
  const matches = [...config.matchAll(/categoryMatch: "([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(matches, SECTIONS);
  assert.match(config, /path: "\/files"/);
  assert.match(config, /themePack: "default"/);
  assert.match(config, /entryDocSlug: "overview\/start"/);
  for (const entry of map.entries) {
    assert.ok(SECTIONS.includes(entry.owner), entry.canonical);
    assert.equal(entry.canonical.split('/')[0], entry.owner);
  }
  const nav = await inventory();
  for (const section of SECTIONS) assert.ok(nav.some(d => d.path === `${section}/index.mdx` && d.unlisted !== true), section);
  // Old top-level directories hold only compatibility pages.
  for (const d of nav.filter(d => !SECTIONS.includes(d.path.split('/')[0]))) assert.equal(d.unlisted, true, d.path);
});

test('compatibility pages stay out of category cards', async () => {
  const nav = await inventory();
  const compatDirs = new Set(nav.filter(d => d.unlisted === true).map(d => path.posix.dirname(d.path)));
  for (const d of nav.filter(d => d.unlisted !== true)) {
    for (const m of d.body.matchAll(/<CategoryNav\s+category="([^"]+)"/g)) {
      assert.ok(!compatDirs.has(m[1]), `${d.path}: CategoryNav category="${m[1]}" would list compatibility pages; use categories={[...]}`);
      assert.ok(nav.some(x => x.path === `${m[1]}/index.mdx`), `${d.path}: unknown category ${m[1]}`);
    }
  }
  for (const d of nav.filter(d => d.unlisted === true)) assert.doesNotMatch(d.body, /<CategoryNav/, d.path);
});

test('printed sidebar lists every printed page once and only canonical pages', async () => {
  const ids = [];
  const visit = items => { for (const item of items) { if (typeof item === 'string') ids.push(item); else if (item.type === 'doc') ids.push(item.id); else if (item.type === 'category') visit(item.items); } };
  visit(sidebars['printed-5mm']);
  const printed = map.entries.filter(e => e.owner === 'printed-5mm').map(e => routeFor(e.canonical).slice('/docs/'.length, -1));
  assert.deepEqual([...ids].sort(), [...printed].sort());
  assert.equal(new Set(ids).size, ids.length);
  // P3/P4/P5 leaf URLs are kept.
  for (const leaf of ['design', 'preview', 'print-files', 'p4-design', 'p4-preview', 'p4-print-files', 'p5-design', 'p5-preview', 'p5-print-files', 'ventilation'])
    assert.ok(map.entries.some(e => e.source === `printed-5mm/${leaf}.mdx` && e.canonical === e.source && e.treatment === 'retained'), leaf);
});

test('generated documents are written to canonical metal-case pages', async () => {
  const spec = JSON.parse(await readFile(path.join(root, 'project/current-spec.json'), 'utf8'));
  const canonical = new Set(map.entries.map(e => `src/content/docs/${e.canonical}`));
  const pages = renderReferencePages(spec);
  assert.deepEqual(pages.map(p => p.rel).sort(), ['bom', 'models/3u60', 'models/7u40', 'models/7u60', 'models/comparison'].map(x => `src/content/docs/metal-case/${x === 'bom' ? 'manufacturing/bom' : x}.mdx`).sort());
  for (const p of pages) {
    assert.ok(canonical.has(p.rel), p.rel);
    for (const m of p.text.matchAll(/\]\((\.[^)#]+\.mdx)/g)) {
      const target = path.posix.normalize(path.posix.join(path.posix.dirname(p.rel), m[1]));
      assert.ok(canonical.has(target), `${p.rel} links to non-canonical ${target}`);
    }
  }
  for (const script of ['scripts/sync-r9-doc-table.mjs', 'scripts/sync-fullset.mjs']) {
    const target = (await readFile(path.join(root, script), 'utf8')).match(/'(src\/content\/docs\/[^']+\.mdx)'/)[1];
    assert.ok(canonical.has(target), `${script} writes ${target}`);
  }
});

test('compatibility pages link to their canonical destination and keep old anchors', async () => {
  for (const entry of map.entries.filter(isCompatibility)) {
    const text = await readFile(path.join(docs, entry.source), 'utf8');
    const rel = path.posix.relative(path.posix.dirname(entry.source), entry.canonical);
    assert.ok(text.includes(`(${rel.startsWith('.') ? rel : `./${rel}`})`), entry.source);
    for (const anchor of entry.anchors ?? []) assert.ok(text.includes(`<span id="${anchor}"></span>`), `${entry.source}#${anchor}`);
  }
});
