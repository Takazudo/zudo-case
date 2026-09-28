import { mkdir, mkdtemp, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { resolvePreviewOrigin, previewRunConfig } from './lib/preview-origin.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const [command, ...args] = process.argv.slice(2);
if (!['dev', 'build', 'check', 'preview'].includes(command)) throw new Error(`Unknown zfb command: ${command}`);
const previewOrigin = resolvePreviewOrigin({ dev: command === 'dev', override: process.env.ZUDO_CASE_PREVIEW_ORIGIN });
const runs = path.join(root, '.cache/site-runs');
await mkdir(runs, { recursive: true });
const runRoot = await mkdtemp(path.join(runs, 'run-'));
const inputs = new Set(['src', 'pages', 'content', 'components', 'layouts', 'styles', 'data', 'public', 'scripts', 'node_modules', 'tsconfig.json', 'package.json', 'pnpm-lock.yaml']);
let child;
const signals = ['SIGINT', 'SIGTERM', 'SIGHUP'];
const killChildGroup = signal => {
  if (!child?.pid) return;
  try {
    if (process.platform === 'win32') child.kill(signal);
    else process.kill(-child.pid, signal);
  } catch (error) { if (error.code !== 'ESRCH') throw error; }
};
const handlers = new Map(signals.map(signal => [signal, () => killChildGroup(signal)]));
try {
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (inputs.has(entry.name)) await symlink(path.join(root, entry.name), path.join(runRoot, entry.name), entry.isDirectory() ? 'dir' : 'file');
  }
  await writeFile(path.join(runRoot, 'zfb.config.ts'), previewRunConfig({ root, command, origin: previewOrigin }));
  // The injectable binary is reserved for fixture tests; normal launches use the locked project CLI.
  const binary = process.env.NODE_ENV === 'test' && process.env.ZUDO_CASE_TEST_ZFB_BINARY
    ? process.env.ZUDO_CASE_TEST_ZFB_BINARY : path.join(root, 'node_modules/.bin/zfb');
  child = spawn(binary, [command, ...args], { cwd: runRoot, stdio: 'inherit', env: process.env, detached: process.platform !== 'win32' });
  for (const signal of signals) process.on(signal, handlers.get(signal));
  process.exitCode = await new Promise(resolve => {
    child.once('error', error => { console.error(error); resolve(1); });
    child.once('close', (code, signal) => resolve(signal ? 1 : (code ?? 1)));
  });
} finally {
  for (const signal of signals) process.removeListener(signal, handlers.get(signal));
  await rm(runRoot, { recursive: true, force: true });
}
