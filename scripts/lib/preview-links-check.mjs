import { access } from 'node:fs/promises';
import path from 'node:path';

export function extractDocumentUrls(body) {
  const markdown = [...body.matchAll(/!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g)].map(m => m[1]);
  const attributes = [...body.matchAll(/(?:src|href)=["']([^"']+)["']/g)].map(m => m[1]);
  const previewComponents = [...body.matchAll(/<Preview(?:Link|Frame)\b[^>]*\bpath=["']([^"']+)["']/g)].map(m => m[1]);
  return [...markdown, ...attributes, ...previewComponents];
}

export async function missingPreviewTargets(body, publicDir) {
  const missing = [];
  for (const url of extractDocumentUrls(body)) {
    if (!/^\/(?:previews|downloads)\//.test(url)) continue;
    const target = path.resolve(publicDir, `.${decodeURIComponent(url.split(/[?#]/)[0])}`);
    if (!target.startsWith(`${path.resolve(publicDir)}${path.sep}`)) { missing.push(url); continue; }
    try { await access(target); } catch { missing.push(url); }
  }
  return missing;
}
