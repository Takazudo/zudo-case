import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = path.join(root, 'engineering/r9-prototype-01/out/preview/file-table.json');
const target = path.join(root, 'src/content/docs/design/r9-prototype-01.mdx');
const opening = '<table data-r9-file-table="generated">';
const closing = '</table>';

function escapeHtml(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

function renderTable(data) {
  if (data.revision !== 'R9-PROTOTYPE-01' || data.model !== '7u40' || !Array.isArray(data.parts)) {
    throw new Error('Unexpected R9 file-table schema or revision');
  }
  const parts = data.parts.filter(part => part.category !== 'hardware-envelopes');
  const ids = new Set();
  const rows = parts.map(part => {
    if (!part.partId || ids.has(part.partId) || !Array.isArray(part.formats) || part.formats.length === 0) {
      throw new Error(`Invalid or duplicate R9 file-table part: ${part.partId}`);
    }
    ids.add(part.partId);
    const formats = part.formats.map(item => `<div>${escapeHtml(item.format.toUpperCase())}: <code>${escapeHtml(item.path)}</code></div>`).join('');
    return `<tr><td>${escapeHtml(data.revision)}<br />${escapeHtml(part.partId)}</td><td>${escapeHtml(part.name)} × ${escapeHtml(part.quantity)}</td><td>${formats}</td><td>${escapeHtml(part.packageZip ?? '')}</td></tr>`;
  });
  return [opening,
    '<thead><tr><th>版・部品ID</th><th>名称・数量</th><th>形式と元ファイル</th><th>候補ZIP</th></tr></thead>',
    '<tbody>', ...rows, '</tbody>', closing].join('\n');
}

const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== '--check')) {
  throw new Error('Usage: node scripts/sync-r9-doc-table.mjs [--check]');
}

const data = JSON.parse(await readFile(source, 'utf8'));
const current = await readFile(target, 'utf8');
const start = current.indexOf(opening);
const end = current.indexOf(closing, start + opening.length);
if (start < 0 || end < 0 || current.indexOf(opening, start + opening.length) >= 0) {
  throw new Error('Expected exactly one R9 generated table in the candidate page');
}
const expected = current.slice(0, start) + renderTable(data) + current.slice(end + closing.length);
if (args.includes('--check')) {
  if (expected !== current) {
    console.error('R9 documentation file table differs from out/preview/file-table.json');
    process.exitCode = 1;
  } else {
    console.log(`R9 documentation file table verified: ${data.parts.length} source parts`);
  }
} else {
  await writeFile(target, expected);
  console.log(`Updated R9 documentation file table from ${data.parts.length} source parts`);
}
