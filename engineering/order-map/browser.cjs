const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const origin=process.env.PREVIEW_ORIGIN || 'http://127.0.0.1:8765';
const output=process.env.SCREENSHOT_DIR || path.join(__dirname,'verification');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{channel:'chrome'}),args:['--enable-unsafe-swiftshader']});
 const report={origin,widths:[],errors:[],checks:[]};
 try {
  for(const width of [1440,390]) {
   const page=await browser.newPage({viewport:{width,height:1000}});page.on('pageerror',e=>report.errors.push(e.message));
   await page.goto(origin+'/previews/r9-order-map.html#part=c2-02-frame');
   await page.waitForFunction(()=>window.orderMapReady===true);
   assert.equal(await page.locator('#part').inputValue(),'c2-02-frame');
   assert.equal(await page.locator('#count').textContent(),'13 designs · 15 PA12 pieces');
   const options=await page.locator('#part option').evaluateAll(xs=>xs.map(x=>x.value));assert.equal(options.length,13);
   for(const id of options) {await page.locator('#part').selectOption(id);assert.equal(await page.evaluate(()=>window.orderMapState.selected),id);assert.ok((await page.locator('#share-link').inputValue()).includes('#part='+id+'&revision=revised'));}
   for(const family of ['C1','C2','C4','C5']) {
    await page.locator('.family[data-family='+family+']').click();
    assert.equal(await page.evaluate(()=>window.orderMapState.family),family);
    await page.locator('#assembled').click();await page.locator('#separate').click();
    await page.locator('#case-view').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,`order-map-${family}-${width}.png`),fullPage:true});
   }
   await page.locator('.marker[data-family=C1]').click();assert.equal(await page.evaluate(()=>window.orderMapState.family),'C1');
   await page.locator('.marker[data-family=C2]').click();assert.equal(await page.evaluate(()=>window.orderMapState.family),'C2');
   await page.locator('#metal').uncheck();await page.locator('#metal').check();await page.locator('#lid').uncheck();await page.locator('#lid').check();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   report.widths.push(width);report.checks.push(`${width}: all 13 IDs, family and case-marker selection, hash links, assembled/separated, visibility, no overflow`);
   await page.locator('#material').selectOption('aluminum');
   for(const [family,count] of Object.entries({C1:1,C2:2,C3:6,C4:2,C5:2})) assert.ok((await page.locator(`.family[data-family=${family}] span`).innerText()).includes(count+' aluminum plate'));
   const metalIds=await page.locator('#part option').evaluateAll(xs=>xs.map(x=>x.value));assert.equal(metalIds.length,13);
   for(const id of metalIds) {
    await page.locator('#part').selectOption(id);
    assert.equal(await page.evaluate(()=>window.orderMapProbe()),0,id+' revised hole must be open');
    assert.ok(await page.evaluate(()=>window.orderMapProbe(3))>0,id+' retained sheet must be solid');
    await page.locator('#revision').selectOption('original');
    assert.ok(await page.evaluate(()=>window.orderMapProbe())>0,id+' original sheet must fill hole');
    await page.locator('#revision').selectOption('revised');
    assert.ok((await page.locator('#share-link').inputValue()).endsWith('#part='+id+'&revision=revised'));
    if(['c1-metal-edge','c3-01-wall','c5-01-front','c5-01-left'].includes(id)) await page.screenshot({path:path.join(output,`anodizing-${id}-${width}.png`),fullPage:true});
   }
   assert.equal(await page.locator('#metal-controls').isVisible(),false);
   assert.equal(await page.locator('#assembled').isDisabled(),true);
   await page.goto(origin+'/previews/r9-order-map.html#part=c3-02-bottom&revision=original');
   await page.waitForFunction(()=>window.orderMapReady===true);
   assert.equal(await page.locator('#material').inputValue(),'aluminum');
   assert.equal(await page.locator('#revision').inputValue(),'original');
   await page.reload();await page.waitForFunction(()=>window.orderMapReady===true);
   assert.ok(await page.evaluate(()=>window.orderMapProbe())>0);
   await page.evaluate(()=>location.hash='part=c5-01-left&revision=revised');
   await page.waitForFunction(()=>window.orderMapState.selected==='c5-01-left');
   assert.equal(await page.evaluate(()=>window.orderMapProbe()),0);
   await page.locator('#material').selectOption('pa12');
   assert.equal(await page.locator('#part option').count(),13);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   report.checks.push(`${width}: all 13 aluminum actual-mesh hole/material raycasts in both revisions, mode switching, direct links/reload/hash change, no overflow`);
   await page.goto(origin+'/previews/r9-fitfix-01.html');await page.waitForFunction(()=>window.fitfixReady===true);
   assert.equal(await page.locator('a[href="r9-order-map.html"]').count(),1);
   await page.locator('#mode').selectOption('C2-01');await page.locator('#mode').selectOption('case');await page.locator('#t1p0').click();await page.locator('#open').click();assert.equal(await page.locator('#lift').inputValue(),'130');
   report.checks.push(`${width}: normal preview loads, entry exists, coupon/case/variant/lid controls work`);await page.close();
  }
  assert.deepEqual(report.errors,[]);report.passed=true;
 } finally { await browser.close();fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report)); }
})().catch(e=>{console.error(e);process.exitCode=1});
