#!/usr/bin/env node
/* Render the viewer's real CPU fallback without launching a browser.
 * This checks scene/runtime behavior, not browser layout or WebGL support.
 * Dependencies: jsdom and @napi-rs/canvas. Supply --jsdom /path/to/jsdom when
 * it is not installed in Node's module lookup path. Runtime dependencies may
 * also be resolved from CODEX_PRIMARY_RUNTIME_NODE_MODULES.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const options = {};
for (let i = 2; i < process.argv.length; i += 2) options[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const output = path.resolve(options.out || path.join(__dirname, '../out/preview-renders'));
const modelPath = path.resolve(options.model || path.join(__dirname, '../out/scene.json'));
const templatePath = path.resolve(options.template || path.join(__dirname, 'viewer.html'));
const width = Number(options.width || 1100), height = Number(options.height || 720);

function dependency(name, explicit) {
  if (explicit) return require(explicit);
  try { return require(name); } catch (error) {
    const runtime = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
    if (runtime) { try { return require(path.join(runtime, name)); } catch (ignored) {} }
    throw new Error('Missing ' + name + '. Install it or provide --' + (name === 'jsdom' ? 'jsdom' : 'canvas') + ' /absolute/module/path');
  }
}
const { JSDOM, VirtualConsole } = dependency('jsdom', options.jsdom || process.env.R11_JSDOM_PATH);
const native = dependency('@napi-rs/canvas', options.canvas);
const modelText = fs.readFileSync(modelPath, 'utf8');
const template = fs.readFileSync(templatePath, 'utf8');
const html = template.replace('__MODEL__', modelText.replace(/</g, '\\u003c'));
assert.equal((template.match(/__MODEL__/g) || []).length, 1, 'Expected one model placeholder');
fs.mkdirSync(output, { recursive: true });

const virtualConsole = new VirtualConsole(), errors = [], backing = new WeakMap();
virtualConsole.on('jsdomError', error => errors.push(error.message));
const downloads = [];
const dom = new JSDOM(html, {
  runScripts: 'dangerously', url: 'http://r11-preview.local/', pretendToBeVisual: true, virtualConsole,
  beforeParse(window) {
    window.ResizeObserver = class { observe() {} };
    window.requestAnimationFrame = () => 1;
    window.devicePixelRatio = 1;
    window.URL.createObjectURL = () => 'blob:r11-local-preview';
    window.URL.revokeObjectURL = () => {};
    window.HTMLAnchorElement.prototype.click = function () { downloads.push({ name: this.download, href: this.href }); };
    const proto = window.HTMLCanvasElement.prototype;
    for (const key of ['width', 'height']) {
      const original = Object.getOwnPropertyDescriptor(proto, key);
      Object.defineProperty(proto, key, {
        get: original.get,
        set(value) { original.set.call(this, value); if (backing.has(this)) backing.get(this)[key] = value; }
      });
    }
    Object.defineProperty(proto, 'clientWidth', { get() { return width; } });
    Object.defineProperty(proto, 'clientHeight', { get() { return height; } });
    proto.getBoundingClientRect = function () { return { x: 0, y: 0, left: 0, top: 0, width, height }; };
    proto.getContext = function (kind) {
      if (kind !== '2d') return null;
      if (!backing.has(this)) {
        const canvas = native.createCanvas(this.width, this.height);
        backing.set(this, canvas);
        const context = canvas.getContext('2d'), original = context.drawImage.bind(context);
        context.drawImage = function (image, ...rest) { return original(backing.get(image) || image, ...rest); };
      }
      return backing.get(this).getContext('2d');
    };
    proto.toBlob = function (callback) { callback(new window.Blob([backing.get(this).toBuffer('image/png')], { type: 'image/png' })); };
    proto.setPointerCapture = function () {};
  }
});
const window = dom.window, document = window.document, study = window.study;
assert.ok(study, document.getElementById('fail').textContent || 'Viewer did not initialize');
assert.equal(study.glInfo().version, 'Canvas 2D');
const model = JSON.parse(modelText), views = [], checks = {};

function lines(context, text, x, y, maxWidth, lineHeight, maxLines = 2) {
  let current = '', count = 0;
  for (const character of text) {
    if (context.measureText(current + character).width > maxWidth && current) {
      context.fillText(current, x, y + count * lineHeight); current = character; count++;
      if (count >= maxLines) return count;
    } else current += character;
  }
  if (current && count < maxLines) { context.fillText(current, x, y + count * lineHeight); count++; }
  return count;
}

function imageStats(canvas) {
  const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
  let count = 0, left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
  for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
    const i = (y * canvas.width + x) * 4;
    if (Math.abs(pixels[i] - 234) + Math.abs(pixels[i + 1] - 240) + Math.abs(pixels[i + 2] - 241) > 18) {
      count++; left = Math.min(left, x); top = Math.min(top, y); right = Math.max(right, x); bottom = Math.max(bottom, y);
    }
  }
  return { non_background_pixels: count, content_box_px: count ? [left, top, right, bottom] : null };
}

function saveView(view, suffix, configure) {
  const start = Date.now();
  study.setView(view);
  if (configure) configure();
  study.fit(); study.render();
  assert.ok(study.camera.span > 0 && study.camera.target.every(Number.isFinite), 'Invalid camera ' + view);
  assert.notEqual(document.getElementById('fail').style.display, 'block', 'Runtime error in ' + view);
  const source = backing.get(document.getElementById('canvas'));
  const stats = imageStats(source);
  assert.ok(stats.non_background_pixels > 200, 'Blank view: ' + view);
  const legend = [...document.querySelectorAll('#legend > span')].map(item => ({ label: item.textContent, color: item.querySelector('.swatch').style.background }));
  const headerHeight = 119, footerHeight = legend.length > 7 ? 97 : 73;
  const image = native.createCanvas(width, height + headerHeight + footerHeight), context = image.getContext('2d');
  context.fillStyle = '#eaf0f1'; context.fillRect(0, 0, image.width, image.height);
  context.fillStyle = '#167b7e'; context.font = '500 12px "Noto Sans CJK JP", sans-serif';
  context.fillText(model.revision + '  /  ' + document.getElementById('viewKicker').textContent, 26, 27);
  context.fillStyle = '#203238'; context.font = '500 22px "Noto Sans CJK JP", sans-serif';
  context.fillText(document.getElementById('viewTitle').textContent, 26, 60);
  context.fillStyle = '#62747a'; context.font = '400 13px "Noto Sans CJK JP", sans-serif';
  lines(context, document.getElementById('viewDesc').textContent, 26, 84, width - 52, 21, 2);
  context.drawImage(source, 0, headerHeight);
  context.font = '400 12px "Noto Sans CJK JP", sans-serif';
  let x = 26, y = headerHeight + height + 23;
  for (const entry of legend) {
    const space = context.measureText(entry.label).width + 35;
    if (x + space > width - 25) { x = 26; y += 24; }
    context.fillStyle = entry.color; context.fillRect(x, y - 9, 9, 9);
    context.fillStyle = '#415a63'; context.fillText(entry.label, x + 15, y); x += space;
  }
  context.fillStyle = '#62747a'; context.font = '400 11px "Noto Sans CJK JP", sans-serif';
  context.fillText((study.state.explode > 0 ? '分解表示・移動量は説明用' : '組立位置') + '  ·  平行投影  ·  mm  ·  レビュー用候補', 26, image.height - 15);
  const name = view + (suffix ? '-' + suffix : '') + '.png';
  fs.writeFileSync(path.join(output, name), image.toBuffer('image/png'));
  const result = { view, file: name, visible_parts: study.visibleParts.length, total_parts: study.parts.length, camera: JSON.parse(JSON.stringify(study.camera)), explode_mm: study.state.explode, ...stats, elapsed_ms: Date.now() - start };
  views.push(result); console.log(JSON.stringify(result));
}

const requestedViews = options.views ? options.views.split(',') : ['lidguides', 'lidfit', 'inside', 'assembly', 'nylon', 'corner', 'top', 'lap', 'lid', 'lidjoint', 'panels', 'slots', 'rail'];
for (const view of requestedViews) {
  if (!model.scenes[view]) continue;
  saveView(view);
}
for (const view of ['top', 'lap', 'lidjoint', 'lidfit']) if (model.scenes[view] && requestedViews.includes(view)) saveView(view, 'exploded', () => study.setExplode(4, true));

study.setView('assembly');
const initialCount = study.visibleParts.length;
document.getElementById('explodeBtn').click(); assert.ok(study.state.explode > 0);
document.getElementById('assembleBtn').click(); assert.equal(study.state.explode, 0); checks.explode_and_assemble = true;
if (study.parts.some(part => part.cat === 'hardware')) {
  document.getElementById('hardware').click(); assert.equal(study.visibleParts.some(part => part.cat === 'hardware'), false);
  document.getElementById('hardware').click(); checks.hardware_visibility = true;
}
if (study.parts.some(part => part.cat === 'lidFrame')) {
  const beforeLid = study.visibleParts.some(part => part.cat === 'lidFrame');
  document.getElementById('lid').click(); assert.equal(study.visibleParts.some(part => part.cat === 'lidFrame'), !beforeLid);
  document.getElementById('lid').click(); checks.lid_visibility = true;
}
document.getElementById('xray').click(); assert.equal(study.state.xray, true); document.getElementById('xray').click(); checks.panel_transparency_state = true;
const selected = study.parts.find(part => part.cat === 'corner') || study.parts[0];
study.select(selected.id); assert.equal(study.state.selected, selected.id);
assert.ok(document.getElementById('inspector').textContent.includes(selected.id));
document.getElementById('soloBtn').click(); assert.deepEqual([...study.visibleParts.map(part => part.id)], [selected.id]);
document.getElementById('clearBtn').click(); assert.equal(study.state.only, null); checks.selection_and_isolation = true;
document.getElementById('resetBtn').click(); assert.equal(study.visibleParts.length, initialCount);
study.cameraPreset('top'); assert.ok(study.camera.pitch > 1.5); study.cameraPreset('bottom'); assert.ok(study.camera.pitch < -1.5);
study.cameraPreset('iso'); checks.camera_presets = true;
study.exportPNG(); assert.ok(downloads.some(item => item.name === 'zudo-case-r11-assembly.png')); checks.png_export = true;
assert.deepEqual(errors, []);
const report = {
  passed: true,
  renderer: 'The actual viewer CPU triangle rasterizer in JSDOM + native canvas; not a browser/WebGL/layout test.',
  template_sha256: crypto.createHash('sha256').update(template).digest('hex'),
  model_sha256: crypto.createHash('sha256').update(modelText).digest('hex'),
  viewport_px: [width, height], views, interaction_checks: checks, errors
};
fs.writeFileSync(path.join(output, 'render-report.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ passed: true, output, images: views.length, interaction_checks: checks }));
dom.window.close();
