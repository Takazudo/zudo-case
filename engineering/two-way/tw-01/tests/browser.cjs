/* Optional browser matrix. No deployment, no external runtime assets. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto'),{pathToFileURL}=require('node:url');
const argv=process.argv.slice(2),arg=(k,d)=>argv.includes(k)?argv[argv.indexOf(k)+1]:d;
const backend=arg('--backend','software'),repo=path.resolve(__dirname,'../../../..'),evidence=path.resolve(arg('--out',path.join(repo,'.cache/two-way-browser',backend)));
const html=path.join(repo,'public/previews/two-way/tw-01.html'),url=arg('--url',pathToFileURL(html).href);
const results=[],errors=[];fs.mkdirSync(evidence,{recursive:true});
const check=(name,fn)=>{fn();results.push({name,status:'passed'});};
async function main(){
 const {chromium}=require(process.env.TW_PLAYWRIGHT_MODULE||path.join(__dirname,'browser/node_modules/playwright'));
 const launchArgs=['--no-sandbox',...(backend==='webgl'?['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']:[])];
 const browser=await chromium.launch({headless:true,executablePath:process.env.TW_CHROMIUM||undefined,args:launchArgs});
 const ctx=await browser.newContext({viewport:{width:1200,height:900},acceptDownloads:true});
 // Force actual fallback independently of whether this browser has a working GPU.
 if(backend==='software')await ctx.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:original.call(this,type,...args);};});
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
 const remote=[];page.on('request',r=>{if(/^https?:/.test(r.url())&&!url.startsWith('http'))remote.push(r.url());});
 try{
  await page.goto(url);await page.waitForFunction(()=>window.FoldApp?.ready,{},{timeout:60000});
  const actual=await page.evaluate(()=>FoldApp.viewer.mode);
  if(actual!==backend){results.push({name:'backend',status:'blocked',expected:backend,actual});throw Error('Requested backend unavailable: '+actual);}
  check('backend',()=>assert.equal(actual,backend));
  async function settled(){await page.waitForFunction(()=>!FoldApp.pending&&FoldApp.lastError===null,{},{timeout:60000});}
  for(const family of ['compact','performance','twin40']){
   await page.locator(`[data-family="${family}"]`).click();await settled();
   check('family '+family,()=>{});
   for(const pose of ['play','closed','frame','joint','trunk','packing','parts','hinge']){
    if(['packing','parts','hinge'].includes(pose))await page.locator('.secondary').evaluate(e=>e.open=true);
    await page.locator(`[data-pose="${pose}"]`).click();await settled();
    const snapshot=await page.evaluate(()=>({state:FoldApp.state,mode:FoldApp.viewer.mode,error:FoldApp.lastError,bounds:FoldApp.viewer.bounds}));
    check(family+'/'+pose,()=>{assert.equal(snapshot.state.pose,pose);assert.equal(snapshot.mode,backend);assert.equal(snapshot.error,null);});
   }
  }
  await page.locator('[data-pose="closed"]').click();await settled();
  await page.evaluate(()=>FoldApp.setState({lidDepth:48,gap:48,trunkW:250,trunkD:200,trunkH:180,straps:false}));await settled();
  check('C invalid48 preserved with diagnostics',()=>{});
  assert.equal(await page.evaluate(()=>FoldApp.state.lidDepth),48);assert.ok(await page.locator('[data-diagnostic="frame-lid"]').count());
  await page.screenshot({path:path.join(evidence,'C-invalid48-'+backend+'.png'),fullPage:false});
  await page.evaluate(()=>FoldApp.reset());await settled();
  for(const width of [320,390,768,1200,1600]){
   await page.setViewportSize({width,height:900});await page.evaluate(()=>FoldApp.viewer.draw());
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   check('viewport '+width,()=>assert.equal(overflow,false));
   if([390,1200].includes(width))await page.screenshot({path:path.join(evidence,`TW-01-${backend}-${width}.png`),fullPage:false});
  }
  await page.setViewportSize({width:768,height:360});await page.locator('#full').click();
  await page.waitForFunction(()=>document.getElementById('stage').classList.contains('expanded'));
  await page.locator('#viewer').focus();const before=await page.evaluate(()=>FoldApp.viewer.camera.azimuth);await page.keyboard.press('ArrowRight');
  check('keyboard orbit',()=>{});assert.notEqual(await page.evaluate(()=>FoldApp.viewer.camera.azimuth),before);
  await page.keyboard.press('Escape');check('Escape restores focus',()=>{});assert.equal(await page.evaluate(()=>document.activeElement.id),'full');
  check('constrained height exits expansion',()=>{});assert.equal(await page.locator('.expanded').count(),0);
  await page.setViewportSize({width:1200,height:900});
  for(const id of ['modules','patch','cross','structure','cutaway','envelopes','highlight','labels']){
   const old=await page.evaluate(id=>FoldApp.state[id],id);await page.locator('#'+id).evaluate(e=>{e.checked=!e.checked;e.dispatchEvent(new Event('change'));});await settled();
   assert.equal(await page.evaluate(id=>FoldApp.state[id],id),!old);check('visibility '+id,()=>{});
   await page.evaluate(({id,old})=>FoldApp.setState({[id]:old}),{id,old});await settled();
  }
  await page.evaluate(()=>FoldApp.setState({pose:'frame',frameExplode:10}));await settled();assert.ok(await page.locator('[data-diagnostic="frame-exploded"]').count());check('frame layers',()=>{});
  await page.evaluate(()=>FoldApp.setState({pose:'joint',jointLift:12}));await settled();assert.ok(await page.locator('[data-diagnostic="unseated"]').count());check('unseated joint',()=>{});
  await page.evaluate(()=>FoldApp.reset());await settled();
  await page.locator('[data-pose="play"]').click();await settled();await page.screenshot({path:path.join(evidence,'B-play-'+backend+'.png'),fullPage:false});
  await page.locator('[data-pose="trunk"]').click();await settled();await page.screenshot({path:path.join(evidence,'B-trunk-'+backend+'.png'),fullPage:false});
  const original=await page.evaluate(()=>FoldApp.state);
  for(const [name,body] of [['malformed','{oops'],['unknown-schema',JSON.stringify({schema:'bad',state:original})],['invalid-type',JSON.stringify({schema:'zudo-case-study/5',state:{...original,gap:'72'}})]]){
   await page.locator('#fileInput').setInputFiles({name:name+'.json',mimeType:'application/json',buffer:Buffer.from(body)});
   await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('前の状態'));
   check(name+' atomic',()=>{});assert.deepEqual(await page.evaluate(()=>FoldApp.state),original);
  }
  const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../../f5-reference/models/C-elbow-hinged-F5.json')));fixture.manufacturingApproved=true;fixture.derived={approved:true};fixture.state.assetUrl='https://untrusted.invalid';
  await page.locator('[data-family="compact"]').click();await settled();
  await page.locator('#fileInput').setInputFiles({name:'F5.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});
  await page.waitForFunction(()=>FoldApp.state.preset==='twin40'&&!FoldApp.pending);
  const imported=await page.evaluate(()=>FoldApp.config());check('F5 restored after family change; derived untrusted',()=>{assert.equal(imported.state.profile,'elbow');assert.equal(imported.state.collar,'hinged');assert.equal(imported.manufacturingApproved,false);assert.equal(imported.state.assetUrl,undefined);});
  const dimensions=await page.evaluate(()=>({gap:FoldApp.state.gap,lidDepth:FoldApp.state.lidDepth}));
  await page.locator('[data-pose="play"]').click();await settled();check('pose preserves physical inputs',()=>{});assert.deepEqual(await page.evaluate(()=>({gap:FoldApp.state.gap,lidDepth:FoldApp.state.lidDepth})),dimensions);
  const png=page.waitForEvent('download');await page.locator('#png').click();const pngFile=await png;await pngFile.saveAs(path.join(evidence,'export-'+backend+'.png'));check('PNG download',()=>assert.ok(fs.statSync(path.join(evidence,'export-'+backend+'.png')).size>1000));
  const download=page.waitForEvent('download');await page.locator('#saveConfig').click();const file=await download;await file.saveAs(path.join(evidence,'export-config.json'));const saved=JSON.parse(fs.readFileSync(path.join(evidence,'export-config.json')));check('versioned export',()=>assert.equal(saved.schema,'zudo-case-two-way/1'));
  await page.locator('#fileInput').setInputFiles(path.join(evidence,'export-config.json'));await settled();
  check('standalone needs no remote assets',()=>assert.deepEqual(remote,[]));check('no page errors',()=>assert.deepEqual(errors,[]));
  return {status:'passed',browser:browser.version(),backend:actual,checks:results.length,results,errors};
 }finally{await browser.close();}
}
main().then(report=>{fs.writeFileSync(path.join(evidence,'results.json'),JSON.stringify({...report,revision:'TW-01',htmlSha256:crypto.createHash('sha256').update(fs.readFileSync(html)).digest('hex')},null,2)+'\n');console.log(JSON.stringify(report));}).catch(e=>{const report={status:results.some(x=>x.status==='blocked')?'blocked':'failed',backend,error:e.message,results,errors,revision:'TW-01'};fs.writeFileSync(path.join(evidence,'results.json'),JSON.stringify(report,null,2)+'\n');console.error(e);process.exitCode=1;});
