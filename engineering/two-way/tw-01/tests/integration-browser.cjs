const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const repo=path.resolve(__dirname,'../../../..'),{chromium}=require(process.env.TW_PLAYWRIGHT_MODULE||path.join(__dirname,'browser/node_modules/playwright'));
const arg=(k,d)=>process.argv.includes(k)?process.argv[process.argv.indexOf(k)+1]:d;
const local=arg('--local','http://localhost:4173'),override=arg('--override','http://localhost:4174'),preview=arg('--preview','http://127.0.0.1:8787'),out=path.resolve(arg('--out',path.join(repo,'.cache/two-way-integration')));fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.TW_CHROMIUM||undefined,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});const ctx=await browser.newContext(),page=await ctx.newPage(),checks=[];try{
 for(const [origin,expected] of [[local,'/previews/two-way/tw-01.html'],[override,preview+'/previews/two-way/tw-01.html']]){
  await page.goto(origin+'/docs/two-way/preview');await page.waitForSelector('iframe');assert.equal(await page.locator('iframe').getAttribute('src'),expected);
  const frame=page.frames().find(f=>f.url().includes('/previews/two-way/'));assert.ok(frame);await frame.waitForFunction(()=>FoldApp?.ready&&!FoldApp.pending);assert.equal(await frame.evaluate(()=>FoldApp.config().revision),'TW-01');
  const body=await page.locator('body').innerText();assert.ok(body.includes('表示元:'));assert.ok(body.includes(origin===local?'ローカル':'127.0.0.1:8787'));checks.push('iframe and source label '+origin);
 }
 for(const slug of ['','design','rail-frame','resources','verification']){await page.goto(local+'/docs/two-way/'+slug);assert.ok((await page.locator('body').innerText()).includes('2WAY'));checks.push('page '+(slug||'index'));}
 for(const width of [390,1200]){await page.setViewportSize({width,height:900});await page.goto(local+'/docs/two-way');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'docs-'+width+'.png'),fullPage:false});checks.push('docs width '+width);}
 const manifest=JSON.parse(fs.readFileSync(path.join(repo,'project/two-way/artifact-manifest.json')));
 for(const entry of manifest.artifacts){const response=await ctx.request.get(preview+'/'+entry.path.replace(/^public\//,''));assert.ok(response.ok(),entry.path);const body=await response.body();assert.equal(crypto.createHash('sha256').update(body).digest('hex'),entry.sha256,entry.path);checks.push('prepared response '+entry.path);}
 const idx=await ctx.request.get(preview);assert.match(await idx.text(),/TW-01/);checks.push('prepared preview index');
 await page.goto(preview+'/previews/two-way/tw-01.html');await page.waitForFunction(()=>FoldApp?.ready);assert.equal(await page.evaluate(()=>FoldApp.config().revision),'TW-01');checks.push('prepared direct workbench');
 const report={status:'passed',revision:'TW-01',browser:browser.version(),checks:checks.length,results:checks};fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
