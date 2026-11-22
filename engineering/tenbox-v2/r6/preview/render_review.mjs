/** Render the HTML's actual software 3D engine to PNG when browser IPC is unavailable.
 * This intentionally does not claim browser-layout or WebGL validation.
 * Usage: node render_review.mjs preview.html out-dir [view...]
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const [input,output,...requested]=process.argv.slice(2);
if(!input||!output)throw Error('Usage: node render_review.mjs preview.html out-dir [view...]');
const require=createRequire((process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()+'/node_modules')+'/');
const {createCanvas,GlobalFonts}=require('@napi-rs/canvas');
const font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';
if(fs.existsSync(font))GlobalFonts.registerFromPath(font,'ReviewSans');
const html=fs.readFileSync(input,'utf8');
const scripts=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
const compressed=scripts.find(x=>x[1].includes('data-id="model"'))?.[2];
const app=scripts.find(x=>!x[1].includes('data-id="model"'))?.[2];
if(!compressed||!app)throw Error('Missing model/app script');
const width=1440,height=1050;
const real=createCanvas(width,height),realGet=real.getContext.bind(real);
real.clientWidth=width;real.clientHeight=height;real.style={};
real.getContext=type=>type==='webgl'?null:realGet(type);
real.addEventListener=()=>{};real.setPointerCapture=()=>{};
real.getBoundingClientRect=()=>({left:0,top:0,width,height});
const elements=new Map(),views=[...html.matchAll(/data-view="([^"]+)"/g)].map(x=>x[1]);
function element(){return {textContent:'',style:{},dataset:{},value:'',checked:false,disabled:false,classList:{add(){},remove(){},toggle(){}},setAttribute(){},addEventListener(){},replaceChildren(){},append(){},requestFullscreen:async()=>{}}}
for(const id of [...html.matchAll(/data-id="([^"]+)"/g)].map(x=>x[1]))elements.set(id,element());
elements.set('canvas',real);elements.get('model').textContent=compressed;
const buttons=views.map(view=>({...element(),dataset:{view}}));
const root={...element(),isConnected:true,querySelector:s=>elements.get(s.match(/data-id="([^"]+)"/)?.[1]),querySelectorAll:s=>s==='[data-view]'?buttons:[]};
const errors=[];
const context={console:{...console,error:e=>errors.push(String(e))},Blob,Response,DecompressionStream,URLSearchParams,Uint8Array,Float32Array,Uint16Array,Uint32Array,Map,Set,Math,JSON,Promise,atob,location:{search:'?renderer=canvas'},Option:function(text,value){this.text=text;this.value=value},ResizeObserver:class{observe(){}},requestAnimationFrame:()=>0,document:{getElementById:()=>root,createElement:tag=>tag==='canvas'?createCanvas(1,1):element(),createTextNode:text=>({textContent:text}),addEventListener(){},fullscreenElement:null},window:{devicePixelRatio:1}};
vm.createContext(context);vm.runInContext(app,context,{timeout:120000});
for(let count=0;!root.dataset.ready&&!root.dataset.error&&count<3000;count++)await new Promise(r=>setTimeout(r,10));
if(root.dataset.error||!root.dataset.ready)throw Error(root.dataset.error||'3D engine did not initialize');
const study=context.window.tenboxStudy;fs.mkdirSync(output,{recursive:true});
const report={renderer:study.renderer,validation:'Actual inline app under a minimal Node DOM shim; not a browser-layout or WebGL test.',source:input,views:[],errors};
for(const view of requested.length?requested:['assembly','rail-junction','side-fixings','side-fixing','side','underside']){
 study.setView(view);study.render();
 const outputCanvas=createCanvas(width,height+120),ctx=outputCanvas.getContext('2d');
 ctx.fillStyle='#dfe9e7';ctx.fillRect(0,0,width,height+120);ctx.drawImage(real,0,90);
 ctx.fillStyle='#233f40';ctx.font='27px ReviewSans';ctx.fillText(elements.get('stageTitle').textContent,28,38);
 ctx.fillStyle='#476461';ctx.font='18px ReviewSans';ctx.fillText(elements.get('stageDetail').textContent,28,68);
 ctx.font='16px ReviewSans';ctx.fillText('R6 CAD review · physical fit pending',28,height+100);
 const file=path.join(output,view+'.png');fs.writeFileSync(file,outputCanvas.toBuffer('image/png'));
 report.views.push({view,file,visible_parts:study.visibleParts().length,frames:study.frames,camera:study.camera});
}
// Exercise actual control handlers, not a separate interpretation of visibility.
study.setView('assembly');const initial=study.visibleParts().length;
elements.get('rails').onchange({target:{checked:false}});const noRails=study.visibleParts().length;
elements.get('brackets').onchange({target:{checked:false}});const noBrackets=study.visibleParts().length;
elements.get('endwalls').onchange({target:{checked:false}});const noEndwalls=study.visibleParts().length;
elements.get('lid').onchange({target:{checked:true}});const withLid=study.visibleParts().length;
elements.get('lidlift').oninput({target:{value:'50'}});study.render();
report.controls={initial,noRails,noBrackets,noEndwalls,withLid,lidLift:study.state.lidLift};
if(!(initial>=noRails&&noRails>=noBrackets&&noBrackets>=noEndwalls&&withLid>noEndwalls&&study.state.lidLift===50))throw Error('Visibility/lid controls failed');
if(errors.length)throw Error(errors.join('\n'));
fs.writeFileSync(path.join(output,'render-report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
