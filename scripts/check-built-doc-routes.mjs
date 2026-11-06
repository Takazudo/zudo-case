// Checks the built site against project/doc-routes.json: every old URL and
// canonical page is emitted, compatibility pages stay out of search and out of
// other pages' navigation, preserved anchors resolve, and every internal docs
// link and fragment in the built HTML resolves (a local route/link crawl).
import { readFile, readdir, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { anchorTarget, isCompatibility, routeFor } from './sync-doc-routes.mjs';

const exists = async p => { try { await access(p); return true; } catch { return false; } };
async function walk(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...await walk(p)); else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}
const attr = name => new RegExp(`\\s${name}=(?:"([^"]*)"|'([^']*)'|([^\\s>"']+))`, 'g');
const values = (html, name) => [...html.matchAll(attr(name))].map(m => m[1] ?? m[2] ?? m[3]);
const decode = s => s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'");

export async function checkBuiltDocRoutes(root, dist = path.join(root, 'dist')) {
  const errors = [];
  const map = JSON.parse(await readFile(path.join(root, 'project/doc-routes.json'), 'utf8'));
  const htmlFor = route => path.join(dist, decodeURIComponent(route).replace(/^\//, ''), 'index.html');
  const pages = new Map();
  for (const file of await walk(path.join(dist, 'docs'))) {
    const route = `/${path.relative(dist, path.dirname(file)).split(path.sep).join('/')}/`;
    const html = await readFile(file, 'utf8');
    pages.set(route, { html, ids: new Set(values(html, 'id').map(decode)) });
  }
  const compat = new Map(map.entries.filter(isCompatibility).map(e => [routeFor(e.source), e]));

  for (const entry of map.entries) {
    const canonicalRoute = routeFor(entry.canonical);
    if (!pages.has(canonicalRoute)) errors.push(`canonical route not built: ${canonicalRoute}`);
    if (entry.source === null) continue;
    const oldRoute = routeFor(entry.source);
    const old = pages.get(oldRoute);
    if (!old) { errors.push(`old route not built: ${oldRoute}`); continue; }
    // The link must be in the page body: the sidebar on a compatibility page may already link the canonical page.
    const main = old.html.match(/<main[\s>][\s\S]*?<\/main>/)?.[0] ?? '';
    if (isCompatibility(entry) && !values(main, 'href').some(h => decode(h).split('#')[0].replace(/\/?$/, '/') === canonicalRoute))
      errors.push(`${oldRoute}: no link to canonical ${canonicalRoute}`);
    for (const anchor of entry.anchors ?? []) {
      if (!old.ids.has(anchor)) errors.push(`${oldRoute}: preserved anchor #${anchor} missing`);
      const [file, hash] = anchorTarget(entry, anchor).split('#');
      const target = pages.get(routeFor(file));
      if (!target) errors.push(`${oldRoute}#${anchor}: target page ${file} not built`);
      else if (hash !== undefined && !target.ids.has(hash)) errors.push(`${oldRoute}#${anchor}: target ${routeFor(file)}#${hash} missing`);
    }
  }

  // Search excludes compatibility pages and includes every canonical page.
  const search = JSON.parse(await readFile(path.join(dist, 'search-index.json'), 'utf8'));
  const searched = new Set(search.filter(x => !String(x.id).startsWith('asset:')).map(x => x.url.endsWith('/') ? x.url : `${x.url}/`));
  for (const route of compat.keys()) if (searched.has(route)) errors.push(`search index lists compatibility page ${route}`);
  for (const entry of map.entries) if (!searched.has(routeFor(entry.canonical))) errors.push(`search index misses ${routeFor(entry.canonical)}`);

  // Crawl: internal docs links and fragments resolve; only compatibility pages link to compatibility routes.
  let links = 0;
  for (const [route, page] of pages) {
    const raw = page.html;
    for (const value of values(raw, 'href')) {
      const href = decode(value);
      if (!href.startsWith('/docs/') && !href.startsWith('#')) continue;
      links++;
      const [p, hash] = href.startsWith('#') ? [route, href.slice(1)] : href.split('#');
      const targetRoute = p.endsWith('/') ? p : `${p}/`;
      const target = pages.get(decodeURIComponent(targetRoute));
      if (!target) { if (!await exists(htmlFor(targetRoute))) errors.push(`${route}: broken link ${href}`); continue; }
      if (hash && !target.ids.has(decodeURIComponent(hash))) errors.push(`${route}: missing fragment ${href}`);
    }
    if (compat.has(route)) continue;
    for (const compatRoute of compat.keys()) {
      const escaped = compatRoute.slice(0, -1).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (new RegExp(`${escaped}(?=/?["'\\s>#\\\\])`).test(raw)) errors.push(`${route}: references compatibility route ${compatRoute}`);
    }
  }
  return { errors, pages: pages.size, links, compatibility: compat.size };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const result = await checkBuiltDocRoutes(root, process.argv[2] ? path.resolve(process.argv[2]) : undefined);
  if (result.errors.length) { console.error(result.errors.join('\n')); process.exitCode = 1; }
  else console.log(`OK: ${result.pages} built docs pages, ${result.compatibility} compatibility routes, ${result.links} internal links and fragments resolve.`);
}
