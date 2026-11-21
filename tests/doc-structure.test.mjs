import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { checkNavigationOrder, checkRouteMap, siblingGroup } from '../scripts/lib/doc-structure-checks.mjs';
import { ARCHIVE_OWNER, GENERATED_MARK, compatibilityRoutes, expectsSearch, frontmatter, isCompatibility, lifecycleOf, renderRoutePages, routeFor } from '../scripts/sync-doc-routes.mjs';
import { renderReferencePages, loadR11Inputs, ARCHIVE_7U40 } from '../scripts/sync-reference-tables.mjs';
import { sidebars } from '../src/sidebars.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const docs = path.join(root, 'src/content/docs');
const SECTIONS = ['overview', 'metal-case', 'printed-5mm', 'tenbox-v2', 'two-way', 'shared', 'development', 'archive'];

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

test('independent sections own every canonical page and nested header destination', async () => {
  const config = await readFile(path.join(root, 'zfb.config.ts'), 'utf8');
  const header = vm.runInNewContext(`(${config.match(/headerNav:\s*(\[[\s\S]*?\]),\n    headerRightItems/)[1]})`);
  const allItems = items => items.flatMap(item => [item, ...allItems(item.children ?? [])]);
  const owners = allItems(header).filter(item => item.categoryMatch).map(item => item.categoryMatch);
  assert.deepEqual(Array.from(owners), SECTIONS);
  assert.equal(header[0].label, 'ケース');
  assert.equal(header[0].path, '/docs/overview/start');
  assert.deepEqual(Array.from(header[0].children, item => item.categoryMatch), ['metal-case', 'printed-5mm', 'tenbox-v2', 'two-way']);
  assert.equal(header.filter(item => item.categoryMatch === 'overview').length, 1);
  assert.equal(header.find(item => item.path === '/files').versioned, false);
  for (const section of SECTIONS) {
    const definition = sidebars[section];
    assert.ok(definition && !Array.isArray(definition), section);
    assert.equal(definition.scopeRoot, 'configured', section);
    if (section !== 'printed-5mm') {
      assert.deepEqual(definition.items, [], section);
      assert.equal(definition.initialPath, undefined, section);
    }
  }
  assert.match(config, /path: "\/files"/);
  assert.match(config, /themePack: "graphite"/);
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

test('current printed P5 URLs stay canonical; P3/P4/history URLs resolve directly to the archive', async () => {
  for (const leaf of ['p5-design', 'p5-preview', 'p5-print-files', 'ventilation'])
    assert.ok(map.entries.some(e => e.source === `printed-5mm/${leaf}.mdx` && e.canonical === e.source && ['retained', 'split'].includes(e.treatment)), leaf);
  const archived = {
    'printed-5mm/p4-design.mdx': 'archive/printed-5mm/p4/index.mdx',
    'printed-5mm/p4-preview.mdx': 'archive/printed-5mm/p4/preview.mdx',
    'printed-5mm/p4-print-files.mdx': 'archive/printed-5mm/p4/print-files.mdx',
    'printed-5mm/design.mdx': 'archive/printed-5mm/p3/index.mdx',
    'printed-5mm/preview.mdx': 'archive/printed-5mm/p3/preview.mdx',
    'printed-5mm/print-files.mdx': 'archive/printed-5mm/p3/print-files.mdx',
    'printed-5mm/history.mdx': 'archive/printed-5mm/index.mdx',
  };
  const routes = new Map(compatibilityRoutes(map).map(r => [r.source, r]));
  for (const [old, canonical] of Object.entries(archived)) {
    assert.equal(routes.get(old)?.canonical, canonical, old);
    assert.equal(lifecycleOf(canonical), 'archive');
  }
  const nav = await inventory();
  for (const old of Object.keys(archived)) assert.equal(nav.find(d => d.path === old)?.unlisted, true, old);
});

test('multi-generation URLs and anchors point directly to one final canonical page (no chains)', async () => {
  const routes = compatibilityRoutes(map);
  const canonicals = map.entries.map(e => e.canonical);
  assert.equal(new Set(canonicals).size, canonicals.length, 'exactly one record per canonical page');
  assert.equal(new Set(routes.map(r => r.source)).size, routes.length, 'each old URL has one owner');
  for (const r of routes) assert.ok(!canonicals.includes(r.source), `${r.source} is both old URL and canonical`);
  // Baseline coverage stays a distinct invariant from later aliases.
  assert.equal(routes.filter(r => r.kind === 'baseline').length + map.entries.filter(e => e.source !== null && !isCompatibility(e)).length, map.baseline.documents);
  // Two generations of R9/R10 metal URLs reach the archive directly.
  const twoGen = {
    'design/r9-prototype-01.mdx': 'archive/metal-case/design/r9-prototype-01.mdx',
    'metal-case/design/history/r9-prototype-01.mdx': 'archive/metal-case/design/r9-prototype-01.mdx',
    'design/r10-fullset-01.mdx': 'archive/metal-case/design/r10-fullset-01.mdx',
    'metal-case/design/r10-fullset-01.mdx': 'archive/metal-case/design/r10-fullset-01.mdx',
    'decisions/decisions.mdx': 'archive/metal-case/history/decisions.mdx',
    'metal-case/history/decisions.mdx': 'archive/metal-case/history/decisions.mdx',
    'verification/fit-test.mdx': 'archive/metal-case/verification/fit-test.mdx',
    'metal-case/verification/history/fit-test.mdx': 'archive/metal-case/verification/fit-test.mdx',
  };
  const bySource = new Map(routes.map(r => [r.source, r]));
  for (const [old, canonical] of Object.entries(twoGen)) assert.equal(bySource.get(old)?.canonical, canonical, old);
  assert.equal(bySource.get('design/r10-fullset-01.mdx').kind, 'baseline');
  assert.equal(bySource.get('metal-case/design/r10-fullset-01.mdx').kind, 'alias');
  assert.ok(bySource.get('metal-case/design/r10-fullset-01.mdx').anchors.includes('一式を選ぶ'));
  // The generated alias page is itself a direct pointer with every preserved anchor.
  const pages = new Map((await renderRoutePages(root)).map(p => [p.rel, p.text]));
  for (const r of routes) {
    const text = pages.get(`src/content/docs/${r.source}`);
    assert.ok(text, r.source);
    const rel = path.posix.relative(path.posix.dirname(r.source), r.canonical);
    assert.ok(text.includes(`(${rel.startsWith('.') ? rel : `./${rel}`})`), `${r.source} → ${r.canonical}`);
    for (const a of r.anchors) assert.ok(text.includes(`<span id="${a}"></span>`), `${r.source}#${a}`);
  }
  // A route map that chains an alias through another canonical page is rejected.
  const chained = { ...map, entries: [...map.entries, { source: null, canonical: 'archive/x.mdx', owner: 'archive', treatment: 'archived', aliases: [{ path: 'archive/metal-case/index.mdx' }] }] };
  assert.ok(checkRouteMap(await inventory(), chained).some(e => /連鎖/.test(e)));
});

test('lifecycle: current owners hold current pages; archive detail pages are excluded from default search', async () => {
  const nav = await inventory();
  const byPath = new Map(nav.map(d => [d.path, d]));
  for (const entry of map.entries) {
    const page = byPath.get(entry.canonical);
    assert.equal(entry.owner === ARCHIVE_OWNER, lifecycleOf(entry.canonical) === 'archive', entry.canonical);
    assert.equal(page.search_exclude === true, !expectsSearch(entry.canonical), entry.canonical);
  }
  for (const landing of ['archive/index.mdx', 'archive/metal-case/index.mdx', 'archive/printed-5mm/index.mdx']) assert.ok(expectsSearch(landing), landing);
  assert.ok(!expectsSearch('archive/metal-case/design/r10-fullset-01.mdx'));
  // No current page lives under the archive, and no archive page under a current owner.
  for (const d of nav.filter(d => d.unlisted !== true)) assert.equal(d.path.startsWith('archive/'), lifecycleOf(d.path) === 'archive', d.path);
  // Mis-marking either way is reported.
  const flip = nav.map(d => d.path === 'archive/metal-case/design/r10-fullset-01.mdx' ? { ...d, search_exclude: false } : d.path === 'metal-case/status.mdx' ? { ...d, search_exclude: true } : d);
  const errors = checkRouteMap(flip, map);
  assert.ok(errors.some(e => e.startsWith('archive/metal-case/design/r10-fullset-01.mdx')));
  assert.ok(errors.some(e => e.startsWith('metal-case/status.mdx')));
});

test('every project has one current entry and the archive has project indexes only where history exists', async () => {
  const nav = await inventory();
  const has = p => nav.some(d => d.path === p && d.unlisted !== true);
  for (const section of SECTIONS) assert.ok(has(`${section}/index.mdx`), section);
  for (const project of ['metal-case', 'printed-5mm']) assert.ok(has(`archive/${project}/index.mdx`), project);
  const archiveIndex = nav.find(d => d.path === 'archive/index.mdx').body;
  for (const project of ['metal-case', 'printed-5mm']) assert.match(archiveIndex, new RegExp(`\\(\\./${project}/index\\.mdx\\)`));
  // Current pages never send readers to archived pages as current material, but link to the archive explicitly.
  for (const d of nav.filter(d => d.unlisted !== true && lifecycleOf(d.path) === 'current')) {
    for (const m of d.body.matchAll(/\]\((\.[^)#\s]+\.mdx)/g)) {
      const target = path.posix.normalize(path.posix.join(path.posix.dirname(d.path), m[1]));
      const route = compatibilityRoutes(map).find(r => r.source === target);
      assert.ok(!route, `${d.path} links to compatibility route ${target}`);
    }
  }
});

test('generated documents are written to canonical metal-case pages', async () => {
  const spec = JSON.parse(await readFile(path.join(root, 'project/current-spec.json'), 'utf8'));
  const canonical = new Set(map.entries.map(e => `src/content/docs/${e.canonical}`));
  const pages = renderReferencePages(spec, await loadR11Inputs(root));
  assert.deepEqual(pages.map(p => p.rel).sort(), [...['bom', 'models/3u60', 'models/7u40', 'models/7u60', 'models/comparison'].map(x => `src/content/docs/metal-case/${x === 'bom' ? 'manufacturing/bom' : x}.mdx`), ARCHIVE_7U40].sort());
  // The current 7U40 table comes from the active R11 selection; R6/R9 values live only in the archive page.
  const current7u40 = pages.find(p => p.rel.endsWith('metal-case/models/7u40.mdx')).text;
  assert.match(current7u40, /R11-BUILD-FEEDBACK-04/);
  assert.doesNotMatch(current7u40, /R9-FITFIX-01の製作候補|R6基準のアルミ本体/);
  assert.match(pages.find(p => p.rel === ARCHIVE_7U40).text, /search_exclude: true/);
  for (const p of pages) {
    assert.ok(canonical.has(p.rel), p.rel);
    for (const m of p.text.matchAll(/\]\((\.[^)#]+\.mdx)/g)) {
      const target = path.posix.normalize(path.posix.join(path.posix.dirname(p.rel), m[1]));
      assert.ok(canonical.has(target), `${p.rel} links to non-canonical ${target}`);
    }
  }
  // Historical generators write their archive canonical pages, never a compatibility stub.
  const compat = new Set(compatibilityRoutes(map).map(r => `src/content/docs/${r.source}`));
  for (const script of ['scripts/sync-r9-doc-table.mjs', 'scripts/sync-fullset.mjs']) {
    const target = (await readFile(path.join(root, script), 'utf8')).match(/'(src\/content\/docs\/[^']+\.mdx)'/)[1];
    assert.ok(canonical.has(target), `${script} writes ${target}`);
    assert.ok(target.startsWith('src/content/docs/archive/'), `${script} must target the archive`);
    assert.ok(!compat.has(target), `${script} would overwrite a compatibility page`);
  }
});

test('compatibility pages link to their canonical destination and keep old anchors', async () => {
  for (const entry of compatibilityRoutes(map)) {
    const text = await readFile(path.join(docs, entry.source), 'utf8');
    const rel = path.posix.relative(path.posix.dirname(entry.source), entry.canonical);
    assert.ok(text.includes(`(${rel.startsWith('.') ? rel : `./${rel}`})`), entry.source);
    for (const anchor of entry.anchors ?? []) assert.ok(text.includes(`<span id="${anchor}"></span>`), `${entry.source}#${anchor}`);
  }
});
