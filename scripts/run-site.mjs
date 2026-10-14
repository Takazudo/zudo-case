import { mkdir, mkdtemp, readdir, readFile, rename, rm, symlink, access, writeFile } from 'node:fs/promises';
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
let runRoot;
const buildLock = path.join(root, '.cache/site-build.lock');
let ownsBuildLock = false;
let nativeReady = false;
let scratchArgument = process.env.ZFB_SCRATCH_DIR;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--scratch-dir') scratchArgument = args[i + 1];
  else if (args[i].startsWith('--scratch-dir=')) scratchArgument = args[i].slice(14);
}
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
  // https://github.com/Takazudo/zudo-front-builder/issues/4233: native /assets serving omits public/assets; keep these bytes in each dev's owned asset root.
  if (command === 'dev') await collect('public/assets');
  const destinationFor = rel => rel.startsWith('public/assets/')
    ? path.join(path.resolve(runRoot, scratchArgument || '.zfb-build'), 'dev-assets/assets', rel.slice('public/assets/'.length))
    : path.join(runRoot, rel === 'zfb.config.ts' ? 'authored-zfb.config.ts' : rel);
  for (const [rel, bytes] of sources) {
    if (rel.startsWith('public/assets/') && scratchArgument && !nativeReady) continue;
    const destination = destinationFor(rel);
    if (previousSources.get(rel)?.equals(bytes)) {
      try { await access(destination); continue; }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
    await mkdir(path.dirname(destination), { recursive: true });
    const temporary = path.join(path.dirname(destination), `.${path.basename(destination)}.mirror-tmp`);
    await writeFile(temporary, bytes);
    await rename(temporary, destination);
  }
  for (const rel of previousSources.keys()) {
    if (rel.startsWith('public/assets/') && scratchArgument && !nativeReady) continue;
    if (!sources.has(rel)) await rm(destinationFor(rel), { force: true });
  }
  if (previousSources.has('zfb.config.ts') && sources.has('zfb.config.ts')
    && !previousSources.get('zfb.config.ts').equals(sources.get('zfb.config.ts'))) {
    await writeFile(path.join(runRoot, 'zfb.config.ts'), previewRunConfig({ root, configRoot: runRoot, command, origin: previewOrigin }));
    // Imported authored config changes need a fresh native process on zfb 4.5.0.
    restartRequested = true;
    killChildGroup('SIGTERM');
  }
  if (scratchArgument && !nativeReady) {
    for (const [rel, bytes] of previousSources) {
      if (rel.startsWith('public/assets/') && !sources.has(rel)) sources.set(rel, bytes);
    }
  }
  previousSources = sources;
}
let child;
let restartRequested = false;
let stopping = false;
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
const handlers = new Map(signals.map(signal => [signal, () => { stopping = true; killChildGroup(signal); }]));
try {
  if (command === 'build') {
    try { await mkdir(buildLock); }
    catch (error) {
      if (error.code === 'EEXIST') throw new Error('Another build owns .cache/site-build.lock; wait for it to finish. If a process was forcibly killed, verify it has stopped before removing the stale lock.');
      throw error;
    }
    ownsBuildLock = true;
    await writeFile(path.join(buildLock, 'owner.json'), JSON.stringify({ pid: process.pid }));
  }
  runRoot = await mkdtemp(path.join(runs, 'run-'));
  for (const input of linkedInputs) {
    try { await symlink(path.join(root, input), path.join(runRoot, input), 'dir'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  await mirrorSources();
  await writeFile(path.join(runRoot, 'zfb.config.ts'), previewRunConfig({ root, configRoot: runRoot, command, origin: previewOrigin }));
  // The injectable binary is reserved for fixture tests; normal launches use the locked project CLI.
  const binary = process.env.NODE_ENV === 'test' && process.env.ZUDO_CASE_TEST_ZFB_BINARY
    ? process.env.ZUDO_CASE_TEST_ZFB_BINARY : path.join(root, 'node_modules/.bin/zfb');
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
  do {
    restartRequested = false;
    nativeReady = false;
    child = spawn(binary, [command, ...args], { cwd: runRoot, stdio: command === 'dev' ? ['inherit', 'pipe', 'inherit'] : 'inherit', env: process.env, detached: process.platform !== 'win32' });
    let outputTail = '';
    child.stdout?.on('data', bytes => {
      process.stdout.write(bytes);
      outputTail = (outputTail + bytes.toString()).slice(-1024);
      // Wait for the native process to validate and lock any explicitly selected scratch root.
      if (outputTail.includes('ready on')) nativeReady = true;
    });
    process.exitCode = await new Promise(resolve => {
      child.once('error', error => { console.error(error); resolve(1); });
      child.once('close', (code, signal) => resolve(signal ? 1 : (code ?? 1)));
    });
  } while (restartRequested && !stopping && !mirrorFailed);
  if (mirrorFailed) process.exitCode = 1;
} finally {
  clearInterval(mirrorTimer);
  await mirroring;
  for (const signal of signals) process.removeListener(signal, handlers.get(signal));
  if (runRoot) await rm(runRoot, { recursive: true, force: true });
  if (ownsBuildLock) await rm(buildLock, { recursive: true, force: true });
}
