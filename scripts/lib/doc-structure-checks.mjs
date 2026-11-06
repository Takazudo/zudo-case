// Navigation-order and route-map checks shared by check-docs and tests.
import path from 'node:path';
import { GENERATED_MARK, isCompatibility } from '../sync-doc-routes.mjs';

const isIndex = rel => rel === 'index.mdx' || rel.endsWith('/index.mdx');

// The sibling group a document is ordered in. A category index is ordered
// among its parent's children; a leaf among its own directory's children.
export function siblingGroup(rel) {
  const dir = path.posix.dirname(rel);
  return isIndex(rel) ? path.posix.dirname(dir) : dir;
}

export function checkNavigationOrder(nav) {
  const errors = [];
  const groups = new Map();
  for (const doc of nav) {
    if (doc.unlisted === true) continue;
    const key = siblingGroup(doc.path);
    if (!groups.has(key)) groups.set(key, new Map());
    const seen = groups.get(key);
    if (seen.has(doc.sidebar_position)) errors.push(`${key === '.' ? '(root)' : key}: sidebar_position ${doc.sidebar_position} が重複 (${seen.get(doc.sidebar_position)}, ${doc.path})`);
    else seen.set(doc.sidebar_position, doc.path);
  }
  return errors;
}

export function checkRouteMap(nav, map) {
  const errors = [];
  const byPath = new Map(nav.map(doc => [doc.path, doc]));
  const canonical = new Set();
  const sources = new Set();
  for (const entry of map.entries) {
    if (canonical.has(entry.canonical)) errors.push(`doc-routes: 正式ページが重複 ${entry.canonical}`);
    canonical.add(entry.canonical);
    const target = byPath.get(entry.canonical);
    if (!target) errors.push(`doc-routes: 正式ページなし ${entry.canonical}`);
    else if (target.unlisted === true) errors.push(`doc-routes: 正式ページがunlisted ${entry.canonical}`);
    if (entry.source === null) { if (entry.treatment !== 'new') errors.push(`doc-routes: 旧ページのない項目は新規のみ ${entry.canonical}`); continue; }
    if (sources.has(entry.source)) errors.push(`doc-routes: 旧ページが重複 ${entry.source}`);
    sources.add(entry.source);
    const old = byPath.get(entry.source);
    if (!old) { errors.push(`doc-routes: 旧URLのページなし ${entry.source}`); continue; }
    if (isCompatibility(entry)) {
      if (old.unlisted !== true) errors.push(`${entry.source}: 互換ページはunlisted: trueが必要`);
      if (!old.body.includes(GENERATED_MARK)) errors.push(`${entry.source}: 互換ページはsync-doc-routes.mjsで生成する`);
    } else if (!['retained', 'split'].includes(entry.treatment)) {
      errors.push(`doc-routes: ${entry.source}は同じパスのまま${entry.treatment}になっている`);
    }
  }
  for (const doc of nav) {
    if (doc.unlisted === true) {
      if (!sources.has(doc.path) || canonical.has(doc.path)) errors.push(`${doc.path}: unlistedページはdoc-routes.jsonの互換ページだけに使う`);
    } else if (!canonical.has(doc.path)) {
      errors.push(`${doc.path}: doc-routes.jsonに正式ページとして登録されていない`);
    }
  }
  return errors;
}
