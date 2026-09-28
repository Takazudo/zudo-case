import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, copyFile, writeFile, readFile, readdir, rm, access, realpath } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import os from 'node:os';
import { PRODUCTION_PREVIEW_ORIGIN } from '../scripts/lib/preview-origin.mjs';

async function waitFor(read, description) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    const value = await read();
    if (value !== undefined) return value;
    await delay(20);
  }
  throw new Error(`Timed out: ${description}`);
}

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'zudo-origin-isolation-'));
  const children = [];
  t.after(async () => {
    await Promise.all(children.map(async ({ child, done }) => {
      if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
      await done;
    }));
    await rm(root, { recursive: true, force: true });
  });
  await mkdir(path.join(root, 'scripts/lib'), { recursive: true });
  await mkdir(path.join(root, 'public/previews'), { recursive: true });
  await mkdir(path.join(root, 'src/content/docs'), { recursive: true });
  await writeFile(path.join(root, 'src/content/docs/article.mdx'), 'initial article');
  for (const rel of ['scripts/run-site.mjs', 'scripts/lib/preview-origin.mjs'])
    await copyFile(new URL(`../${rel}`, import.meta.url), path.join(root, rel));
  await writeFile(path.join(root, 'zfb.config.ts'), 'export default {};\n');
  await writeFile(path.join(root, 'public/previews/local.html'), 'local asset');
  const binary = path.join(root, 'mock-zfb.mjs');
  await writeFile(binary, `#!/usr/bin/env node
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
const [command, id, stay] = process.argv.slice(2);
const control = process.env.MOCK_CONTROL;
async function snapshot(sequence) {
  const config = await readFile('zfb.config.ts', 'utf8');
  const value = config.match(/__ZUDO_CASE_PREVIEW_ORIGIN__: ("(?:[^"\\\\]|\\\\.)*")/)[1];
  const origin = JSON.parse(JSON.parse(value));
  await mkdir('.zfb-build', { recursive: true });
  await writeFile('.zfb-build/effective-origin.json', JSON.stringify(origin));
  await writeFile(path.join(control, id + '-' + sequence + '.json'), JSON.stringify({ origin, cwd: process.cwd(), config }));
}
await snapshot('ready');
if (command === 'dev' || stay === 'stay') {
  let busy = false;
  setInterval(async () => {
    if (busy) return;
    busy = true;
    try {
      const sequence = await readFile(path.join(control, id + '.request'), 'utf8');
      await snapshot(sequence);
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    finally { busy = false; }
  }, 20);
}
`, { mode: 0o755 });
  async function report(id, sequence) {
    return waitFor(async () => {
      try { return JSON.parse(await readFile(path.join(root, `${id}-${sequence}.json`), 'utf8')); }
      catch (error) { if (error.code === 'ENOENT' || error instanceof SyntaxError) return undefined; throw error; }
    }, `${id} ${sequence}`);
  }
  async function launch(command, id, { override, stay = false } = {}) {
    const env = { ...process.env, NODE_ENV: 'test', ZUDO_CASE_TEST_ZFB_BINARY: binary, MOCK_CONTROL: root };
    delete env.ZUDO_CASE_PREVIEW_ORIGIN;
    if (override !== undefined) env.ZUDO_CASE_PREVIEW_ORIGIN = override;
    const child = spawn(process.execPath, [path.join(root, 'scripts/run-site.mjs'), command, id, ...(stay ? ['stay'] : [])], { env, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    child.stdout.on('data', chunk => { output += chunk; });
    child.stderr.on('data', chunk => { output += chunk; });
    const done = once(child, 'close').then(([code, signal]) => ({ code, signal, output }));
    children.push({ child, done });
    const ready = await report(id, 'ready');
    let rereadCount = 0;
    return { child, done, ready, async reread() {
      const sequence = `reread-${++rereadCount}`;
      await writeFile(path.join(root, `${id}.request`), sequence);
      return report(id, sequence);
    } };
  }
  return { root, launch };
}

for (const command of ['check', 'build']) {
  test(`live dev rereads its local origin after ${command}`, async t => {
    const { root, launch } = await fixture(t);
    const dev = await launch('dev', 'dev');
    const other = await launch(command, 'other');
    assert.equal((await other.done).code, 0);
    assert.equal(other.ready.origin, PRODUCTION_PREVIEW_ORIGIN);
    assert.notEqual(dev.ready.cwd, other.ready.cwd);
    const reread = await dev.reread();
    assert.equal(reread.origin, '');
    assert.equal(await readFile(path.join(reread.cwd, 'public/previews/local.html'), 'utf8'), 'local asset');
    await assert.rejects(access(other.ready.cwd), { code: 'ENOENT' });
    await assert.rejects(access(path.join(root, '.cache/preview-origin-override.mjs')), { code: 'ENOENT' });
    dev.child.kill('SIGTERM');
    await dev.done;
    assert.deepEqual(await readdir(path.join(root, '.cache/site-runs')), []);
  });
}

test('two live same-mode runs retain distinct overrides on reread', async t => {
  const { launch } = await fixture(t);
  const first = await launch('dev', 'first', { override: 'http://localhost:8787/' });
  const second = await launch('dev', 'second', { override: 'https://preview.example.test' });
  assert.notEqual(first.ready.cwd, second.ready.cwd);
  assert.equal((await first.reread()).origin, 'http://localhost:8787');
  assert.equal((await second.reread()).origin, 'https://preview.example.test');
});

test('override validation fails before a CLI or run directory is created', async t => {
  const { root } = await fixture(t);
  const child = spawn(process.execPath, [path.join(root, 'scripts/run-site.mjs'), 'dev'], {
    env: { ...process.env, ZUDO_CASE_PREVIEW_ORIGIN: 'https://example.test/path' }, stdio: 'ignore',
  });
  assert.notEqual((await once(child, 'close'))[0], 0);
  await assert.rejects(access(path.join(root, '.cache')), { code: 'ENOENT' });
});


test('dev mirrors source edits, additions, removals and config into its own run only', async t => {
  const { root, launch } = await fixture(t);
  const dev = await launch('dev', 'dev', { override: 'http://localhost:8787' });
  const check = await launch('check', 'check', { stay: true });
  const relative = 'src/content/docs/article.mdx';
  assert.equal(await realpath(path.join(dev.ready.cwd, relative)), path.join(dev.ready.cwd, relative));
  assert.notEqual(await realpath(path.join(root, relative)), await realpath(path.join(dev.ready.cwd, relative)));
  await writeFile(path.join(root, relative), 'updated article');
  await writeFile(path.join(root, 'src/content/docs/added.mdx'), 'new article');
  await writeFile(path.join(root, 'zfb.config.ts'), 'export default { site: "https://example.test" };\n');
  await waitFor(async () => {
    const article = await readFile(path.join(dev.ready.cwd, relative), 'utf8');
    const config = await readFile(path.join(dev.ready.cwd, 'authored-zfb.config.ts'), 'utf8');
    return article === 'updated article' && config.includes('example.test') ? true : undefined;
  }, 'source/config mirror');
  assert.equal(await readFile(path.join(dev.ready.cwd, 'src/content/docs/added.mdx'), 'utf8'), 'new article');
  assert.equal(await readFile(path.join(check.ready.cwd, relative), 'utf8'), 'initial article');
  await rm(path.join(root, relative));
  await waitFor(async () => {
    try { await access(path.join(dev.ready.cwd, relative)); return undefined; }
    catch (error) { if (error.code === 'ENOENT') return true; throw error; }
  }, 'deleted source mirror');
  assert.equal((await dev.reread()).origin, 'http://localhost:8787');
  assert.equal((await check.reread()).origin, PRODUCTION_PREVIEW_ORIGIN);
});
