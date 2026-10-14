import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, cp, writeFile, readFile, readdir, symlink, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:net';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { PRODUCTION_PREVIEW_ORIGIN } from '../../scripts/lib/preview-origin.mjs';

const checkout = fileURLToPath(new URL('../../', import.meta.url));
async function port() {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const value = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return value;
}
async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'zudo-real-cli-'));
  const processes = [];
  t.after(async () => {
    for (const run of processes.reverse()) {
      if (run.child.exitCode === null && run.child.signalCode === null) {
        if (run.direct) process.kill(-run.child.pid, 'SIGTERM');
        else run.child.kill('SIGTERM');
      }
      await run.done;
    }
    await rm(root, { recursive: true, force: true });
  });
  for (const dir of ['pages', 'src/components', 'scripts/lib', 'public/previews', 'src/content/docs']) await mkdir(path.join(root, dir), { recursive: true });
  for (const rel of ['scripts/run-site.mjs', 'scripts/lib/preview-origin.mjs', 'src/components/preview-links.jsx']) await cp(path.join(checkout, rel), path.join(root, rel));
  await cp(path.join(checkout, 'src'), path.join(root, 'src'), { recursive: true });
  await cp(path.join(checkout, 'pages'), path.join(root, 'pages'), { recursive: true });
  await cp(path.join(checkout, 'public/assets'), path.join(root, 'public/assets'), { recursive: true });
  await symlink(path.join(checkout, 'node_modules'), path.join(root, 'node_modules'), 'dir');
  await cp(path.join(checkout, 'package.json'), path.join(root, 'package.json'));
  await cp(path.join(checkout, 'pnpm-lock.yaml'), path.join(root, 'pnpm-lock.yaml'));
  await cp(path.join(checkout, 'pnpm-workspace.yaml'), path.join(root, 'pnpm-workspace.yaml'));
  await cp(path.join(checkout, 'tsconfig.json'), path.join(root, 'tsconfig.json'));
  await writeFile(path.join(root, 'pages/defines.d.ts'), 'declare const __KEPT__: string;');
  const authoredConfig = await readFile(path.join(checkout, 'zfb.config.ts'), 'utf8');
  const config = kept => authoredConfig.replace('siteName: \"ZUDO CASE\",', `siteName: \"Fixture\", bundle: { define: { __KEPT__: ${JSON.stringify(JSON.stringify(kept))} } },`);
  await writeFile(path.join(root, 'zfb.config.ts'), config('authored'));
  const page = text => `import { h } from '@takazudo/zfb/zudo-react';\nimport { PreviewFrame } from '../src/components/preview-links.jsx';\nexport default function Page() { return h('main', null, h('p', null, __KEPT__), h('p', null, ${JSON.stringify(text)}), h(PreviewFrame, { path: '/previews/local.html', title: 'Preview' })); }\n`;
  await writeFile(path.join(root, 'pages/index.tsx'), page('initial'));
  await writeFile(path.join(root, 'public/assets/live.txt'), 'initial public asset');
  await writeFile(path.join(root, 'public/previews/local.html'), '<!doctype html><p>local public asset</p>');
  function launch(command, args = [], override, direct = false) {
    const env = { ...process.env };
    delete env.ZUDO_CASE_PREVIEW_ORIGIN;
    delete env.ZFB_SCRATCH_DIR;
    delete env.ZFB_DEV_BOOT_LAZY;
    delete env.ZUDO_CASE_TEST_ZFB_BINARY;
    if (override !== undefined) env.ZUDO_CASE_PREVIEW_ORIGIN = override;
    const child = direct
      ? spawn(path.join(checkout, 'node_modules/.bin/zfb'), [command, ...args], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'], detached: true })
      : spawn(process.execPath, [path.join(root, 'scripts/run-site.mjs'), command, ...args], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
    const run = { child, direct, output: '' };
    child.stdout.on('data', chunk => { run.output += chunk; });
    child.stderr.on('data', chunk => { run.output += chunk; });
    run.done = once(child, 'close').then(([code, signal]) => ({ code, signal }));
    processes.push(run);
    return run;
  }
  async function served(run, address, matches, status = 200) {
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      assert.equal(run.child.exitCode, null, run.output);
      try {
        const response = await fetch(address, { signal: AbortSignal.timeout(2000) });
        const text = await response.text();
        if (response.status === status && matches.every(value => text.includes(value))) return text;
      } catch (error) { if (error.name === 'AssertionError') throw error; }
      await delay(150);
    }
    throw new Error(`Timed out serving ${address}\n${run.output}`);
  }
  async function completes(run) {
    const result = await run.done;
    assert.equal(result.code, 0, run.output);
    return run.output;
  }
  return { root, launch, served, completes, config, page };
}

test('real CLI keeps live dev origins through build/check, reloads and distinct ports', { timeout: 180000 }, async t => {
  const f = await fixture(t);
  const ports = await Promise.all([port(), port(), port()]);
  const urls = ports.map(p => `http://127.0.0.1:${p}`);
  const local = f.launch('dev', ['--host', '127.0.0.1', '--port', String(ports[0])]);
  const first = f.launch('dev', ['--host', '127.0.0.1', '--port', String(ports[1]), '--scratch-dir', '.zfb-build/selected'], 'http://localhost:8787');
  const second = f.launch('dev', ['--host', '127.0.0.1', '--port', String(ports[2])], 'https://preview.example.test');
  const origins = ['', 'http://localhost:8787', 'https://preview.example.test'];
  const runs = [local, first, second];
  async function verify(text = 'initial', kept = 'authored') {
    for (const [i, run] of runs.entries()) {
      const html = await f.served(run, urls[i], [`src="${origins[i]}/previews/local.html"`, text, kept]);
      assert.ok(html.includes('border-radius:8px') || html.includes('border-radius: 8px'), html);
      assert.match(html, /loading="lazy"/);
      assert.ok(html.includes(i === 0 ? 'ローカル (public/)' : new URL(origins[i]).host));
    }
  }
  await verify();
  assert.match(await (await fetch(urls[0] + '/previews/local.html')).text(), /local public asset/);
  await f.served(local, urls[0] + '/assets/live.txt', ['initial public asset']);
  await f.served(first, urls[1] + '/assets/live.txt', ['initial public asset']);
  await writeFile(path.join(f.root, 'public/assets/live.txt'), 'edited public asset');
  await f.served(local, urls[0] + '/assets/live.txt', ['edited public asset']);
  await f.served(first, urls[1] + '/assets/live.txt', ['edited public asset']);
  await f.completes(f.launch('check'));
  const build = f.launch('build', ['--no-minify-html']);
  const started = Date.now();
  while (!build.output.includes('info package route')) {
    assert.equal(build.child.exitCode, null, build.output);
    assert.ok(Date.now() - started < 30000, build.output);
    await delay(25);
  }
  const competingBuild = f.launch('build');
  assert.notEqual((await competingBuild.done).code, 0);
  assert.match(competingBuild.output, /Another build owns/);
  await writeFile(path.join(f.root, 'pages/index.tsx'), f.page('edited during build'));
  await f.completes(build);
  const built = await readFile(path.join(f.root, 'dist/index.html'), 'utf8');
  assert.ok(built.includes(`src="${PRODUCTION_PREVIEW_ORIGIN}/previews/local.html"`));
  assert.ok(built.includes('initial'));
  assert.ok(!built.includes('edited during build'));
  await verify('edited during build');
  await writeFile(path.join(f.root, 'pages/index.tsx'), f.page('edited source'));
  await verify('edited source');
  await writeFile(path.join(f.root, 'pages/added.tsx'), `import { h } from '@takazudo/zfb/zudo-react'; export default () => h('p', null, 'new route');`);
  await f.served(local, urls[0] + '/added/', ['new route']);
  await rm(path.join(f.root, 'pages/added.tsx'));
  await f.served(local, urls[0] + '/added/', [], 404);
  await writeFile(path.join(f.root, 'zfb.config.ts'), f.config('changed config'));
  await rm(path.join(f.root, 'public/assets/live.txt'));
  await verify('edited source', 'changed config');
  await f.served(local, urls[0] + '/assets/live.txt', [], 404);
  await f.served(first, urls[1] + '/assets/live.txt', [], 404);
  const previewPort = await port();
  const preview = f.launch('preview', ['--host', '127.0.0.1', '--port', String(previewPort)]);
  await f.served(preview, `http://127.0.0.1:${previewPort}`, [`src="${PRODUCTION_PREVIEW_ORIGIN}/previews/local.html"`, 'initial']);
  for (const run of [...runs, preview]) { run.child.kill('SIGTERM'); await run.done; }
  assert.deepEqual(await readdir(path.join(f.root, '.cache/site-runs')), []);
});

test('real direct CLI scratch/define isolation works but reads mutable checkout inputs', { timeout: 90000 }, async t => {
  const f = await fixture(t);
  const firstPort = await port();
  const secondPort = await port();
  const first = f.launch('dev', ['--host', '127.0.0.1', '--port', String(firstPort), '--scratch-dir', '.zfb-build/direct-first', '--define', '__ZUDO_CASE_PREVIEW_ORIGIN__="http://localhost:8787"'], undefined, true);
  const second = f.launch('dev', ['--host', '127.0.0.1', '--port', String(secondPort), '--scratch-dir', '.zfb-build/direct-second', '--define', '__ZUDO_CASE_PREVIEW_ORIGIN__="https://preview.example.test"'], undefined, true);
  await f.served(first, `http://127.0.0.1:${firstPort}`, ['http://localhost:8787/previews/local.html']);
  await f.served(second, `http://127.0.0.1:${secondPort}`, ['https://preview.example.test/previews/local.html']);
  await f.completes(f.launch('build', ['--scratch-dir', '.zfb-build/direct-build', '--define', `__ZUDO_CASE_PREVIEW_ORIGIN__=${JSON.stringify(PRODUCTION_PREVIEW_ORIGIN)}`], undefined, true));
  await f.served(first, `http://127.0.0.1:${firstPort}`, ['http://localhost:8787/previews/local.html']);
  await f.served(second, `http://127.0.0.1:${secondPort}`, ['https://preview.example.test/previews/local.html']);
  await writeFile(path.join(f.root, 'pages/index.tsx'), f.page('shared authored change'));
  await f.served(first, `http://127.0.0.1:${firstPort}`, ['shared authored change']);
  await f.served(second, `http://127.0.0.1:${secondPort}`, ['shared authored change']);
});
