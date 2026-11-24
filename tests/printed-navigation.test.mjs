import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildNavTree, isNavVisible } from '@takazudo/zudo-doc/site-schema';
import { buildSidebarNavigation, broaderSidebarScope, sidebarScopeNodes, sidebarBaselineOpen } from '@takazudo/zudo-doc/sidebar-utils';
import { frontmatter, routeFor } from '../scripts/sync-doc-routes.mjs';
import { sidebars } from '../src/sidebars.js';
import { PRINTED_SECTION, printedMembers, toPrintedTree } from '../src/navigation/printed-tree.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const docsRoot = path.join(root, 'src/content/docs');
const sections = Object.keys(sidebars);
const flatten = (nodes) => nodes.flatMap(node => [node, ...flatten(node.children)]);

async function readDocs(dir = docsRoot) {
  const docs = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) docs.push(...await readDocs(file));
    else if (entry.name.endsWith('.mdx')) {
      const rel = path.relative(docsRoot, file).split(path.sep).join('/');
      docs.push({ slug: rel.replace(/\.mdx$/, ''), data: frontmatter(await readFile(file, 'utf8')) });
    }
  }
  return docs;
}
const docs = (await readDocs()).filter(doc => isNavVisible(doc) && !doc.data.draft);
const buildNative = (entries, lang, meta) => buildNavTree(entries, lang, meta, (slug) => `/docs/${slug}/`);
const native = buildNative(docs, 'ja');
const printed = toPrintedTree(native);
const resolve = (section, tree = native) => buildSidebarNavigation(docs, 'ja', section, undefined, sidebars, () => tree, sections);

test('real printed pages appear exactly once under linked design parents, preserving all URLs', async () => {
  const map = JSON.parse(await readFile(path.join(root, 'project/doc-routes.json'), 'utf8'));
  const expected = map.entries.filter(row => row.owner === PRINTED_SECTION).map(row => routeFor(row.canonical).slice('/docs/'.length, -1));
  const produced = flatten(printed);
  assert.deepEqual(produced.map(node => node.slug).sort(), [...expected].sort());
  assert.equal(new Set(produced.map(node => node.slug)).size, produced.length);
  assert.deepEqual(printed.map(node => node.slug), [PRINTED_SECTION]);
  for (const node of produced) {
    assert.equal(node.hasPage, true, node.slug);
    assert.equal(node.href, `/docs/${node.slug}/`, node.slug);
    assert.deepEqual(node.children.map(child => child.slug), printedMembers.get(node.slug) ?? [], node.slug);
  }
  assert.equal(native.find(node => node.slug === PRINTED_SECTION).children.length, expected.length - 1);
  assert.ok(flatten(native).some(node => node.slug === 'metal-case'));
});

test('resolved sidebar preserves editorial children, restores its linked root and cannot broaden into other sections', () => {
  const { nodes, navigation } = resolve(PRINTED_SECTION, printed);
  assert.deepEqual(flatten(nodes).map(node => node.slug), flatten(printed).map(node => node.slug));
  assert.deepEqual(nodes.map(node => node.slug), [PRINTED_SECTION]);
  assert.equal(broaderSidebarScope(navigation, nodes, null), null);
  assert.deepEqual(sidebarScopeNodes(navigation, nodes, null), nodes);
  const p6 = flatten(nodes).find(node => node.slug === 'printed-5mm/p6-design');
  const focused = sidebarScopeNodes(navigation, nodes, p6.occurrenceId);
  assert.deepEqual(focused.map(node => node.slug), [p6.slug]);
  const broad = broaderSidebarScope(navigation, nodes, p6.occurrenceId);
  assert.equal(broad, nodes[0].occurrenceId);
  assert.equal(broaderSidebarScope(navigation, nodes, broad), null);
  assert.ok(flatten(navigation.roots).every(node => node.slug.startsWith(PRINTED_SECTION)));
});

test('printed navigation is current-only: P6 tasks, no P5/P4/P3 or history rows', () => {
  const { nodes } = resolve(PRINTED_SECTION, printed);
  const slugs = flatten(nodes).map(node => node.slug);
  assert.deepEqual(slugs, ['printed-5mm', 'printed-5mm/p6-design', 'printed-5mm/p6-preview', 'printed-5mm/p6-print-files', 'printed-5mm/ventilation']);
  for (const node of flatten(nodes)) assert.notEqual(node.collapsed, true, node.slug);
  assert.equal(sidebarBaselineOpen(flatten(nodes).find(node => node.slug === 'printed-5mm/p6-design'), undefined, PRINTED_SECTION), true);
  // The archive is its own section; its printed pages never enter the current tree.
  const archive = native.find(node => node.slug === 'archive');
  assert.ok(flatten([archive]).some(node => node.slug === 'archive/printed-5mm/p4'));
  assert.ok(!slugs.some(slug => slug.startsWith('archive/')));
});

test('native prev/next order of the current printed section never walks into archived pages', () => {
  const section = native.find(node => node.slug === PRINTED_SECTION);
  const order = flatten([section]).filter(node => node.hasPage).map(node => node.slug);
  assert.ok(order.every(slug => slug.startsWith('printed-5mm')), order.join(','));
  assert.ok(!order.some(slug => /p5|p4|p3|history|\/design$|\/preview$|\/print-files$/.test(slug.replace(/p6-[a-z-]+$/, ''))), order.join(','));
});

test('native section sidebars retain linked roots and all descendants, bounded at their own section', () => {
  for (const section of sections.filter(section => section !== PRINTED_SECTION)) {
    const { nodes, navigation } = resolve(section);
    const original = native.find(node => node.slug === section);
    assert.ok(original, section);
    assert.deepEqual(nodes.map(node => node.slug), [section]);
    assert.deepEqual(flatten(nodes).map(node => node.slug), flatten([original]).map(node => node.slug));
    assert.equal(broaderSidebarScope(navigation, nodes, null), null, section);
    assert.deepEqual(sidebarScopeNodes(navigation, nodes, null), nodes, section);
    assert.equal(sidebars[section].initialPath, undefined);
  }
});

test('compatibility and draft pages are excluded before native/editorial navigation construction', () => {
  const hidden = { slug: 'printed-5mm/retired', data: { title: 'retired', unlisted: true } };
  assert.equal(isNavVisible(hidden), false);
  const extra = buildNative([...docs, hidden].filter(isNavVisible), 'ja');
  assert.ok(!flatten(extra).some(node => node.slug === hidden.slug));
  assert.ok(!flatten(toPrintedTree(extra)).some(node => node.slug === hidden.slug));
});

test('editorial transform clones nodes, keeps native labels and base/locale hrefs, and falls back without a root', () => {
  const snapshot = JSON.stringify(native);
  const output = toPrintedTree(native);
  assert.equal(JSON.stringify(native), snapshot);
  assert.notEqual(output[0], native.find(node => node.slug === PRINTED_SECTION));
  const localized = buildNavTree(docs, 'ja', undefined, slug => `/custom/ja/docs/${slug}/`);
  for (const node of flatten(toPrintedTree(localized))) {
    assert.equal(node.href, `/custom/ja/docs/${node.slug}/`);
    assert.equal(node.label, flatten(localized).find(source => source.slug === node.slug).label);
  }
  const absent = native.filter(node => node.slug !== PRINTED_SECTION);
  assert.equal(toPrintedTree(absent), absent);
  assert.throws(() => toPrintedTree([{ slug: PRINTED_SECTION, hasPage: false, children: [] }]), /authored page/);
});
