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
const {createCanvas,GlobalFonts,Path2D}=require('@napi-rs/canvas');
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
function element(){return {textContent:'',style:{},dataset:{},attributes:{},value:'',checked:false,disabled:false,classList:{add(){},remove(){},toggle(){}},setAttribute(key,value){this.attributes[key]=value},addEventListener(){},replaceChildren(){},append(){},requestFullscreen:async()=>{}}}
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
const report={renderer:study.renderer,validation:'Actual inline app under a minimal Node DOM shim; not a browser-layout or WebGL test.',source:input,source_model_sha256:study.DATA.previewMetadata.sourceModelSha256,current_parts:study.DATA.parts.length,views:[],errors};
for(const view of requested.length?requested:['assembly','lower-slot','rail-junction','side-fixing','inside-nuts','side','lid-fit','lid-ledge']){
 const before=view.endsWith('-r7');study.setRevision(before?'R7':'R8-LID-LEDGE-01');study.setView(before?view.slice(0,-3):view);study.render();
 const outputCanvas=createCanvas(width,height+120),ctx=outputCanvas.getContext('2d');
 ctx.fillStyle='#dfe9e7';ctx.fillRect(0,0,width,height+120);ctx.drawImage(real,0,90);
 if(view==='lid-fit'){
  // Render the actual SVG path/text attributes emitted by the viewer's dimension overlay.
  ctx.save();ctx.translate(0,90);ctx.font='16px ReviewSans';
  for(const [line,text,color]of[['lidRoomLine','lidRoomText','#174d48'],['envelopeLine','envelopeText','#954f30']]){
   const l=elements.get(line),t=elements.get(text);ctx.strokeStyle=color;ctx.lineWidth=1.5;
   if(l.attributes.d)ctx.stroke(new Path2D(l.attributes.d));
   ctx.textAlign=t.attributes['text-anchor']==='end'?'right':'left';ctx.lineWidth=5;ctx.strokeStyle='#dfe9e7';
   const x=Number(t.attributes.x),y=Number(t.attributes.y);if(!Number.isFinite(x+y))throw Error('Invalid dimension label');
   ctx.strokeText(t.textContent,x,y);ctx.fillStyle=color;ctx.fillText(t.textContent,x,y);
  }
  ctx.restore();
 }
 ctx.fillStyle='#233f40';ctx.font='27px ReviewSans';ctx.fillText(elements.get('stageTitle').textContent,28,38);
 ctx.fillStyle='#476461';ctx.font='18px ReviewSans';ctx.fillText(elements.get('stageDetail').textContent,28,68);
 ctx.font='16px ReviewSans';ctx.fillText(study.state.revision+' geometry · physical fit not verified',28,height+100);
 const file=path.join(output,view+'.png');fs.writeFileSync(file,outputCanvas.toBuffer('image/png'));
 const visible=study.visibleParts();
 report.views.push({view,file,visible_parts:visible.length,brackets:visible.filter(p=>p.cat==='brackets').length,nuts:visible.filter(p=>p.fastenerRole==='nut').length,wall_bolts:visible.filter(p=>p.fastenerRole==='bolt'&&p.fastenerAxis==='wall').length,frames:study.frames,camera:study.camera});
}
study.setRevision('R8-LID-LEDGE-01');
// Verify that the side inspection view includes its complete actual hardware set.
const rightWall=study.DATA.parts.filter(p=>p.attachmentWall==='body-right');
if(!rightWall.length)throw Error('R8 bracket attachment metadata is missing');
study.setView('side');
const sideShown=new Set(study.visibleParts().map(p=>p.id));
const omitted=rightWall.filter(p=>!sideShown.has(p.id)).map(p=>p.id);
if(omitted.length)throw Error('Side view omitted attached hardware: '+omitted.join(', '));
const bracketNuts=study.DATA.parts.filter(p=>p.fastenerRole==='nut'&&p.attachmentGroup==='brackets');
if(!bracketNuts.length||bracketNuts.some(p=>p.nutSide!=='inside'))throw Error('L-bracket nuts must be present and inside');
study.setView('inside-nuts');
const interiorShown=new Set(study.visibleParts().map(p=>p.id));
const missingInside=bracketNuts.filter(p=>p.group==='body'&&!interiorShown.has(p.id)).map(p=>p.id);
if(missingInside.length)throw Error('Inside nuts view omitted body nuts: '+missingInside.join(', '));
report.hardware_visibility={right_wall_attachment_parts:rightWall.length,right_wall_missing:omitted,bracket_nuts:bracketNuts.length,all_bracket_nuts_inside:true,inside_body_nuts_missing:missingInside};
// Exercise actual control handlers, not a separate interpretation of visibility.
study.setView('assembly');const initial=study.visibleParts().length;
elements.get('rails').onchange({target:{checked:false}});const noRails=study.visibleParts().length;
elements.get('brackets').onchange({target:{checked:false}});const noBrackets=study.visibleParts().length;
elements.get('endwalls').onchange({target:{checked:false}});const noEndwalls=study.visibleParts().length;
elements.get('lid').onchange({target:{checked:true}});const withLid=study.visibleParts().length;
elements.get('lidlift').oninput({target:{value:'50'}});study.render();
report.controls={initial,noRails,noBrackets,noEndwalls,withLid,lidLift:study.state.lidLift};
// Switching revision must keep the actual camera fixed and fixed part bounds identical.
study.setView('lower-slot');study.setRevision('R8-LID-LEDGE-01');const camera=JSON.stringify(study.camera);
study.setRevision('R7');if(JSON.stringify(study.camera)!==camera)throw Error('R7 comparison moved camera');
study.setRevision('R8-LID-LEDGE-01');if(JSON.stringify(study.camera)!==camera)throw Error('R8 comparison moved camera');
const worldBox=p=>p.box.map((n,i)=>n+(p.staticOffset?.[i%3]||0));
const key=p=>(p.sourceId||p.id).replace(/^r[78]-rail-/,'rail-');
const previous=new Map(study.DATA.baselineParts.map(p=>[key(p),p]));
let fixed=0,moving=0,maximumError=0;
for(const p of study.DATA.parts){const q=previous.get(key(p));if(!q)continue;const a=worldBox(p),b=worldBox(q);
 const shifted=/^r[78]-rail-/.test(p.id),expected=shifted?[0,0,12.631103,0,0,12.631103]:[0,0,0,0,0,0];
 const error=Math.max(...a.map((x,i)=>Math.abs(x-b[i]-expected[i])));maximumError=Math.max(maximumError,error);
 if(error>.00101)throw Error('Unexpected R7/R8 part displacement '+p.id);if(shifted)moving++;else fixed++;
}
if(moving!==11||fixed<250)throw Error('Incomplete R7/R8 comparison');
report.comparison={same_camera:true,moving_parts:moving,fixed_parts:fixed,maximum_display_bound_error_mm:maximumError};
if(!(initial>=noRails&&noRails>=noBrackets&&noBrackets>=noEndwalls&&withLid>noEndwalls&&report.controls.lidLift===50))throw Error('Visibility/lid controls failed');
// Reuse the very same ray-probe function used by the real-browser verifier.
// This executes the actual viewer's decoded meshes in a Node DOM shim; it does
// not turn the result into a Chromium / layout / WebGL validation.
const verifier=fs.readFileSync(new URL('./verify_browser.py',import.meta.url),'utf8');
const probeBody=verifier.match(/result = page\.evaluate\("""([\s\S]*?)"""\)/)?.[1];
if(!probeBody)throw Error('Missing actual-mesh verifier');
const lidProbe=vm.runInContext('('+probeBody+')()',context);
if(lidProbe.revision!=='R8-LID-LEDGE-01'||lidProbe.gaps.length!==36||!lidProbe.gaps.every(p=>p.current&&!p.previous)||!lidProbe.windows.every(p=>!p.current&&!p.previous)||!lidProbe.retained.every(p=>p.current&&p.previous))throw Error('Actual viewer lid gap / retained-window verification failed');
report.lid_geometry={...lidProbe,passed:true};
if(errors.length)throw Error(errors.join('\n'));
fs.writeFileSync(path.join(output,'render-report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
