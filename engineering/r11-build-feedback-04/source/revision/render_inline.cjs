#!/usr/bin/env node
/* Execute the compact inline fragment using its real CPU renderer.
 * Theme colors are host-style fixtures. This is not browser/layout/WebGL QA.
 * Uses the same dependency flags as render_preview.cjs.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const options = {};
for (let i = 2; i < process.argv.length; i += 2) options[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const input = options.input || '/workspace/zudo-case-r11-lid-guides.html';
const output = options.out || path.resolve(__dirname, '../out/inline-renders');
const width = Number(options.width || 736), height = Number(options.height || 450);
function dependency(name, explicit) {
  if (explicit) return require(explicit);
  try { return require(name); } catch (_) { return require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, name)); }
}
const { JSDOM, VirtualConsole } = dependency('jsdom', options.jsdom);
const native = dependency('@napi-rs/canvas', options.canvas);
const html = fs.readFileSync(input, 'utf8');
assert.ok(Buffer.byteLength(html) < 1_000_000);
assert.equal(/<!doctype|<html[ >]|<head[ >]|<body[ >]/i.test(html), false);
assert.equal(/\bfetch\s*\(|XMLHttpRequest|WebSocket/.test(html), false);
assert.equal(/__[A-Z_]+__/.test(html), false);
fs.mkdirSync(output, { recursive: true });
const themes = {
  light: {'--background':'rgb(255,255,255)','--foreground':'rgb(34,34,34)','--muted-foreground':'rgb(102,102,102)','--viz-series-1':'rgb(7,121,116)','--viz-series-2':'rgb(163,112,26)','--viz-series-3':'rgb(57,122,189)','--viz-series-4':'rgb(166,107,53)','--viz-series-5':'rgb(132,99,181)','--viz-series-6':'rgb(53,120,66)'},
  dark: {'--background':'rgb(31,33,37)','--foreground':'rgb(229,231,235)','--muted-foreground':'rgb(164,171,180)','--viz-series-1':'rgb(53,185,175)','--viz-series-2':'rgb(213,173,101)','--viz-series-3':'rgb(117,169,228)','--viz-series-4':'rgb(214,165,132)','--viz-series-5':'rgb(196,164,237)','--viz-series-6':'rgb(132,180,138)'}
};
const errors = [], backing = new WeakMap(), console = new VirtualConsole();
console.on('jsdomError', error => errors.push(error.message));
const dom = new JSDOM(html, {
  runScripts:'dangerously', pretendToBeVisual:true, virtualConsole:console,
  beforeParse(window) {
    window.Blob = Blob; window.Response = Response; window.DecompressionStream = DecompressionStream;
    window.ResizeObserver = class {observe() {}};
    window.requestAnimationFrame = () => 1; window.devicePixelRatio = 1;
    const computed = window.getComputedStyle.bind(window);
    window.getComputedStyle = element => {
      const token = element.style.color.match(/^var\((--[\w-]+)\)$/);
      if (token) return {color:themes[window.document.documentElement.dataset.theme || 'light'][token[1]]};
      return computed(element);
    };
    const proto = window.HTMLCanvasElement.prototype;
    for (const key of ['width','height']) {
      const descriptor = Object.getOwnPropertyDescriptor(proto,key);
      Object.defineProperty(proto,key,{get:descriptor.get,set(value){descriptor.set.call(this,value);if(backing.has(this))backing.get(this)[key]=value;}});
    }
    Object.defineProperty(proto,'clientWidth',{get(){return width;}});
    Object.defineProperty(proto,'clientHeight',{get(){return height;}});
    proto.getBoundingClientRect=()=>({x:0,y:0,left:0,top:0,width,height});
    proto.getContext=function(kind){
      if(kind!=='2d')return null;
      if(!backing.has(this)){
        const canvas=native.createCanvas(this.width,this.height);backing.set(this,canvas);
        const context=canvas.getContext('2d'),original=context.drawImage.bind(context);
        context.drawImage=(image,...rest)=>original(backing.get(image)||image,...rest);
      }
      return backing.get(this).getContext('2d');
    };
    proto.setPointerCapture=function(){};
  }
});
(async()=>{
  const root=dom.window.document.getElementById('zudo-case-r11-04-inline');
  for(let i=0;i<100&&!root.study;i++)await new Promise(resolve=>setTimeout(resolve,20));
  const ui=key=>root.querySelector('[data-ui="'+key+'"]');
  assert.ok(root.study,ui('fail').textContent||'Initialization failed');
  const study=root.study, report={passed:false,renderer:'Real inline CPU renderer in JSDOM/native canvas; host theme fixtures; not a browser/layout/WebGL test.',bytes:Buffer.byteLength(html),sha256:crypto.createHash('sha256').update(html).digest('hex'),source:study.metadata,scenes:[],checks:{},errors};
  function save(name){
    study.render();assert.equal(ui('fail').hidden,true,ui('fail').textContent);
    const canvas=backing.get(ui('canvas'));
    const file=name+'.png';fs.writeFileSync(path.join(output,file),canvas.toBuffer('image/png'));
    return file;
  }
  for(const key of ['lidguides','lidfit','inside','assembly','nylon','corner','top','lap','lid','lidjoint','panels','slots','rail']){
    ui('view').value=key;ui('view').dispatchEvent(new dom.window.Event('change',{bubbles:true}));
    assert.equal(study.state.view,key);assert.ok(study.visibleParts.length>0);
    report.scenes.push({scene:key,file:save(key),parts:study.parts.length,visible:study.visibleParts.length});
  }
  report.checks.scene_control=true;
  study.setView('top');ui('explode').value='4';ui('explode').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
  assert.equal(study.state.explode,4);save('top-exploded');report.checks.explosion=true;
  ui('hardware').click();assert.equal(study.visibleParts.some(p=>p.cat==='hardware'),false);ui('hardware').click();report.checks.hardware=true;
  study.select(study.parts[0].id);assert.ok(ui('detail').textContent.includes(study.parts[0].name));report.checks.selection=true;
  ui('camera').value='top';ui('camera').dispatchEvent(new dom.window.Event('change',{bubbles:true}));assert.ok(study.camera.pitch>1.5);report.checks.camera=true;
  study.setView('assembly');ui('metal').click();assert.equal(study.visibleParts.some(p=>p.cat==='panels'),false);report.checks.metal=true;
  const beforeLid=study.visibleParts.some(p=>p.cat==='lidFrame');
  ui('lid').click();assert.equal(study.visibleParts.some(p=>p.cat==='lidFrame'),!beforeLid);report.checks.lid=true;
  dom.window.document.documentElement.dataset.theme='dark';await new Promise(resolve=>setTimeout(resolve,10));
  study.setView('lidguides');save('lidguides-dark');report.checks.theme_change=true;
  assert.deepEqual(errors,[]);report.passed=true;
  fs.writeFileSync(path.join(output,'inline-report.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify(report,null,2)+'\n');dom.window.close();
})().catch(error=>{process.stderr.write(error.stack+'\n');dom.window.close();process.exitCode=1;});
