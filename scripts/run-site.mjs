import { mkdir, mkdtemp, readdir, readFile, rename, rm, symlink, writeFile } from 'node:fs/promises';
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
const linkedInputs = new Set(['public', 'node_modules']);
let previousSources = new Map();
async function mirrorSources() {
  const sources = new Map();
  async function collect(rel) {
    const source = path.join(root, rel);
    try {
      const entries = await readdir(source, { withFileTypes: true });
      for (const entry of entries) await collect(path.join(rel, entry.name));
    } catch (error) {
      if (error.code === 'ENOENT') return;
      if (error.code !== 'ENOTDIR') throw error;
      try { sources.set(rel, await readFile(source)); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  }
  for (const input of inputs) if (!linkedInputs.has(input)) await collect(input);
  await collect('zfb.config.ts');
  for (const [rel, bytes] of sources) {
    if (previousSources.get(rel)?.equals(bytes)) continue;
    const destination = path.join(runRoot, rel === 'zfb.config.ts' ? 'authored-zfb.config.ts' : rel);
    await mkdir(path.dirname(destination), { recursive: true });
    const temporary = path.join(path.dirname(destination), `.${path.basename(destination)}.mirror-tmp`);
    await writeFile(temporary, bytes);
    await rename(temporary, destination);
  }
  for (const rel of previousSources.keys()) {
    if (!sources.has(rel)) await rm(path.join(runRoot, rel === 'zfb.config.ts' ? 'authored-zfb.config.ts' : rel), { force: true });
  }
  if (previousSources.has('zfb.config.ts') && sources.has('zfb.config.ts')
    && !previousSources.get('zfb.config.ts').equals(sources.get('zfb.config.ts'))) {
    await writeFile(path.join(runRoot, 'zfb.config.ts'), previewRunConfig({ root, configRoot: runRoot, command, origin: previewOrigin }));
  }
  previousSources = sources;
}
let child;
let mirrorTimer;
let mirroring;
let mirrorFailed = false;
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
  for (const input of linkedInputs) {
    try { await symlink(path.join(root, input), path.join(runRoot, input), 'dir'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  await mirrorSources();
  await writeFile(path.join(runRoot, 'zfb.config.ts'), previewRunConfig({ root, configRoot: runRoot, command, origin: previewOrigin }));
  // The injectable binary is reserved for fixture tests; normal launches use the locked project CLI.
  const binary = process.env.NODE_ENV === 'test' && process.env.ZUDO_CASE_TEST_ZFB_BINARY
    ? process.env.ZUDO_CASE_TEST_ZFB_BINARY : path.join(root, 'node_modules/.bin/zfb');
  child = spawn(binary, [command, ...args], { cwd: runRoot, stdio: 'inherit', env: process.env, detached: process.platform !== 'win32' });
  for (const signal of signals) process.on(signal, handlers.get(signal));
  // Workaround for https://github.com/Takazudo/zudo-front-builder/issues/3318: mirror code into each run's graph root.
  if (command === 'dev') mirrorTimer = setInterval(() => {
    if (mirroring) return;
    mirroring = mirrorSources().catch(error => {
      console.error(error);
      mirrorFailed = true;
      killChildGroup('SIGTERM');
    }).finally(() => { mirroring = undefined; });
  }, 250);
  process.exitCode = await new Promise(resolve => {
    child.once('error', error => { console.error(error); resolve(1); });
    child.once('close', (code, signal) => resolve(signal ? 1 : (code ?? 1)));
  });
  if (mirrorFailed) process.exitCode = 1;
} finally {
  clearInterval(mirrorTimer);
  await mirroring;
  for (const signal of signals) process.removeListener(signal, handlers.get(signal));
  await rm(runRoot, { recursive: true, force: true });
}
