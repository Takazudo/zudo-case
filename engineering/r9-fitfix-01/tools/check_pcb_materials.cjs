const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const out=path.resolve('engineering/r9-fitfix-01/verification/pcb-materials');
const origin=process.env.PREVIEW_ORIGIN || 'http://127.0.0.1:4175';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const results=[];
 for(const fallback of [false,true]){
  const browser=await chromium.launch({headless:true,args:fallback?['--disable-webgl']:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try{
   const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
   await page.goto(origin+'/previews/r9-fitfix-01.html');await page.waitForFunction(()=>window.fitfixReady===true);
   assert.equal(await page.evaluate(()=>window.fitfixRenderer),fallback?'canvas-fallback':'webgl');
   await page.locator('#railOnly').check();await page.locator('#fit').click();
   const snapshot=()=>page.evaluate(()=>window.fitfixInspection.meshes().filter(m=>m.userData.group==='pcb').map(m=>({id:m.userData.id,colors:Array.from(m.geometry.attributes.color.array),white:m.material.color.getHex(),position:m.position.x,visible:m.visible})));
   const original=await snapshot();assert.equal(original.length,8);assert.ok(original.every(m=>m.visible&&m.white===0xffffff));
   await page.locator('#color').uncheck();assert.deepEqual(await snapshot(),original);await page.locator('#color').check();
   if(!fallback){
    await page.screenshot({path:path.join(out,'inside.png')});
    for(const view of ['left','right']){await page.locator('#'+view).click();await page.screenshot({path:path.join(out,view+'-outside.png')});}
   }
   await page.locator('#pcbExplode').fill('30');await page.locator('#fit').click();
   const exploded=await snapshot();assert.ok(exploded.every(m=>Math.abs(m.position)===(m.id.startsWith('fixer-')?60:30)));
   await page.screenshot({path:path.join(out,fallback?'canvas-exploded.png':'exploded.png')});
   await page.locator('#pcbExplode').fill('0');await page.locator('#t1p0').click();assert.deepEqual(await snapshot(),original);
   await page.locator('#hardware').uncheck();assert.ok((await snapshot()).every(m=>!m.visible));await page.locator('#hardware').check();
   await page.locator('#mode').selectOption('C1-01');await page.locator('#mode').selectOption('case');assert.deepEqual(await snapshot(),original);
   await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(!fallback)await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
   assert.deepEqual(errors,[]);results.push({renderer:fallback?'canvas-fallback':'webgl',pcbParts:8,passed:true,errors});
  }finally{await browser.close()}
 }
 fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify({scope:'R9-FITFIX preview materials only; no physical/manufacturing validation',results},null,2)+'\n');console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1});
