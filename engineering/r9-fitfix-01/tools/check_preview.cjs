const {chromium}=require(process.env.PLAYWRIGHT_MODULE || require('path').join(require('os').homedir(), '.codex/skills/headless-browser/node_modules/playwright'));
const fs=require('fs');
const origin=process.env.PREVIEW_ORIGIN || 'http://127.0.0.1:4321';
(async()=>{
const browser=await chromium.launch({headless:true,channel:'chrome'});
const report={widths:[],errors:[],checks:[]};
try {
for(const width of [1440,390]) {
 const page=await browser.newPage({viewport:{width,height:900}});
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
 await page.goto(origin+'/previews/r9-fitfix-01.html');
 await page.waitForFunction(()=>window.fitfixReady===true);
 report.widths.push(await page.evaluate(()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,renderer:window.fitfixRenderer})));
 await page.locator('#t1p0').click();
 if(!(await page.locator('#info').innerText()).includes('92.0')) throw Error('comparison seat missing');
 await page.locator('#open').click(); if(await page.locator('#lift').inputValue()!=='130')throw Error('open failed');
 await page.locator('#travel').click(); if(await page.locator('#lift').inputValue()!=='0')throw Error('travel failed');
 for(const mode of ['C1-01','C2-01','C4-01','C5-01']) { await page.locator('#mode').selectOption(mode); if(!(await page.locator('#info').innerText()).includes(mode))throw Error(mode); }
 await page.locator('#mode').selectOption('case'); await page.locator('#t1p2').click(); await page.locator('#open').click();
 await page.screenshot({path:`/tmp/zudo-fitfix-${width}.png`});
 report.checks.push(`width ${width}: variants/open/travel/C1/C2/C4/C5`);
 await page.goto(origin+'/docs/design/r9-fitfix-01/');
 await page.waitForSelector('iframe');
 const frame=page.frames().find(f=>f.url().includes('/previews/r9-fitfix-01.html'));
 if(!frame) throw Error('local iframe missing'); await frame.waitForFunction(()=>window.fitfixReady===true);
 report.checks.push(`width ${width}: integrated doc iframe`); await page.close();
}
report.passed=report.errors.length===0&&report.widths.every(x=>!x.overflow);
fs.writeFileSync('engineering/r9-fitfix-01/verification/browser.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report)); if(!report.passed)process.exitCode=1;
}finally{await browser.close()}
})();
