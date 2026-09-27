import { mkdir, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { resolvePreviewOrigin } from './lib/preview-origin.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const [command, ...args] = process.argv.slice(2);
if (!['dev', 'build', 'check', 'preview'].includes(command)) throw new Error(`Unknown zfb command: ${command}`);
const previewOrigin = resolvePreviewOrigin({ dev: command === 'dev', override: process.env.ZUDO_CASE_PREVIEW_ORIGIN });
const cache = path.join(root, '.cache');
await mkdir(cache, { recursive: true });
await writeFile(path.join(cache, 'preview-origin-override.mjs'), `export const previewOrigin = ${JSON.stringify(previewOrigin)};\n`);
const child = spawn(path.join(root, 'node_modules/.bin/zfb'), [command, ...args], { cwd: root, stdio: 'inherit', env: process.env });
child.on('error', error => { console.error(error); process.exitCode = 1; });
child.on('exit', (code, signal) => { process.exitCode = signal ? 1 : (code ?? 1); });
