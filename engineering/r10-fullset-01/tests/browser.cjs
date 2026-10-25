const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'verification');fs.mkdirSync(out,{recursive:true});
const url=process.env.R10_URL||'file://'+path.join(root,'out/preview.html');
(async()=>{const report={url,cells:[],errors:[]};const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});try{
for(const renderer of ['WebGL','Canvas'])for(const width of [1440,390,320]){
 const page=await browser.newPage({viewport:{width,height:900},acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 if(renderer==='Canvas')await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(k,...a){return k.includes('webgl')?null:get.call(this,k,...a)}});
 await page.goto(url);await page.waitForFunction(()=>window.study?.frames>0,{timeout:60000});
 const info=await page.evaluate(()=>({renderer:study.glInfo(),parts:study.parts.length,view:study.state.view,overflow:document.documentElement.scrollWidth>innerWidth}));assert.equal(info.overflow,false);assert.equal(info.view,'case');assert(info.parts>250);
 for(const view of ['case','front','side','corner','joint','lap','top','washer']){
  await page.locator(`[data-view="${view}"]`).click();await page.waitForFunction(v=>study.state.view===v,view);assert((await page.evaluate(()=>study.parts.length))>0);
  await page.locator('#explodeBtn').click();assert((await page.evaluate(()=>study.state.explode))>0);await page.locator('#assembleBtn').click();
  if(await page.locator('#section').isEnabled()){await page.locator('#section').check();await page.locator('#section').uncheck()}else assert.equal(view,'top');
  await page.locator('#allBtn').click();await page.locator('#allBtn').click();
 }
 await page.locator('#washerKind').selectOption('lower');await page.locator('#travel').fill('-2.5');await page.locator('#travel').dispatchEvent('input');assert.equal(await page.locator('#coverage').getAttribute('data-status'),'outside-envelope');await page.locator('#nominalBtn').click();assert.equal(await page.locator('#coverage').getAttribute('data-status'),'fits');
 await page.locator('#resetBtn').click();await page.locator('#lidOpen').click();assert.equal(await page.evaluate(()=>study.state.lidOpen),true);await page.locator('#lidOpen').click();
 await page.locator('#blackBtn').click();await page.locator('#colorBtn').click();
 const layers=page.locator('#layerRows input[type=checkbox]');for(let i=0;i<await layers.count();i++){await layers.nth(i).click();await layers.nth(i).click()}
 const cam=await page.evaluate(()=>JSON.stringify(study.camera));const canvas=page.locator('#canvas');await canvas.scrollIntoViewIfNeeded();const box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.5+30,box.y+box.height*.5+20);await page.mouse.up();await page.mouse.wheel(0,80);await page.waitForFunction(c=>JSON.stringify(study.camera)!==c,cam);assert.notEqual(await page.evaluate(()=>JSON.stringify(study.camera)),cam);
 await page.locator('#resetBtn').click();
 await canvas.scrollIntoViewIfNeeded();const hit=await page.evaluate(()=>project([30,30,123.5]));const cb=await canvas.boundingBox();await page.mouse.click(cb.x+hit[0],cb.y+hit[1]);assert(await page.evaluate(()=>study.state.selected));await page.locator('#selectedSolo').click();assert(await page.evaluate(()=>study.state.only));await page.locator('#clearSelection').click();
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#saveBtn').click()]);const settings=JSON.parse(fs.readFileSync(await download.path()));assert.equal(settings.profile,'7u40-t1-groove1p70-m5');
 const invalid={...settings,profile:'old'};await page.locator('#fileInput').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});await page.waitForTimeout(100);assert.match(await page.locator('#toast').innerText(),/対応/);
 await page.locator('#fileInput').setInputFiles({name:'good.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(settings))});await page.waitForTimeout(100);assert.match(await page.locator('#toast').innerText(),/読み込み/);
 const [png]=await Promise.all([page.waitForEvent('download'),page.locator('#shotBtn').click()]);const bytes=fs.readFileSync(await png.path());assert.equal(bytes.subarray(1,4).toString(),'PNG');assert(bytes.length>1000);
 if(width!==320){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,`${renderer}-${width}.png`)});await page.locator('#lidOpen').click();await page.screenshot({path:path.join(out,`${renderer}-${width}-open.png`)})}
 console.log('PASS',renderer,width);report.cells.push({width,renderer,...info,checks:'8 inspection modes, assembly/explosion, section, layers, travel warnings, lid, colors, orbit/zoom, reset, JSON export/valid+invalid import, PNG bytes',errors});report.errors.push(...errors);await page.close();
}
report.passed=report.errors.length===0;fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');assert(report.passed);console.log(JSON.stringify(report));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
