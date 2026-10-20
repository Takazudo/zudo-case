// Browser check for the R9-LID-M5-01 preview. Writes verification/browser.json and review PNGs.
// PREVIEW_ORIGIN serves public/ (default http://127.0.0.1:4321); PLAYWRIGHT_MODULE selects playwright.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),path=require('path');
const origin=process.env.PREVIEW_ORIGIN||'http://127.0.0.1:4321';
const out=path.join(__dirname,'../verification');
(async()=>{
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const report={widths:[],errors:[],checks:[],images:[]};
const shot=async(page,name)=>{await page.waitForTimeout(400);await page.screenshot({path:path.join(out,name)});report.images.push(name)};
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:900}});
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
  await page.goto(origin+'/previews/r9-lid-m5-01.html');
  await page.waitForFunction(()=>window.fitfixReady===true);
  report.widths.push(await page.evaluate(()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,renderer:window.fitfixRenderer})));
  if(!(await page.locator('#info').innerText()).includes('六角対辺8.4'))throw Error('M5 summary missing');
  const fasteners=await page.evaluate(()=>window.fitfixInspection.meshes().filter(m=>['fastener','nut'].includes(m.userData.group)).length);
  if(fasteners!==16)throw Error('expected 8 screws + 8 nuts, got '+fasteners);
  await shot(page,`case-${width}.png`);
  await page.locator('#t1p0').click();
  if(!(await page.locator('#info').innerText()).includes('92.0'))throw Error('comparison seat missing');
  await page.locator('#open').click(); if(await page.locator('#lift').inputValue()!=='130')throw Error('open failed');
  const lifted=await page.evaluate(()=>window.fitfixInspection.meshes().filter(m=>['fastener','nut','lid','lidMetal'].includes(m.userData.group)).every(m=>m.position.z===130));
  if(!lifted)throw Error('fasteners do not lift with the lid');
  if(width===1440)await shot(page,'case-open-1440.png');
  await page.locator('#travel').click(); if(await page.locator('#lift').inputValue()!=='0')throw Error('travel failed');
  await page.locator('#t1p2').click();
  const modes=await page.evaluate(()=>Object.keys(window.fitfixData.coupons));
  for(const mode of modes){
   await page.locator('#mode').selectOption(mode);
   if(!(await page.locator('#info').innerText()).includes(mode))throw Error(mode);
   if(!(await page.locator('#section').isChecked()))throw Error('section off: '+mode);
   if(width===1440&&!mode.startsWith('LID-T1P0')){
    if(mode.endsWith('FRONT')||mode.startsWith('C2'))await page.locator('#left').click();
    const see=mode==='N1';if(see)await page.locator('#transparent').check();await shot(page,mode.toLowerCase()+'.png');if(see)await page.locator('#transparent').uncheck();
   }
  }
  report.checks.push(`width ${width}: M5 summary, 16 fastener envelopes, variants/open/travel, ${modes.join('/')}`);
  await page.close();
 }
 report.passed=report.errors.length===0&&report.widths.every(x=>!x.overflow);
 fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report));if(!report.passed)process.exitCode=1;
}finally{await browser.close()}
})();
