// Run the actual offline software renderer and UI handlers in a minimal DOM host.
// This is a renderer/interaction harness, not a claim of browser layout testing.
const fs=require('fs'),vm=require('vm'),path=require('path');
const {PNG}=require('pngjs');
const rootDir=path.resolve(__dirname,'..');
const html=fs.readFileSync(rootDir+'/deliverables/10box-v2-r5-preview.html','utf8');
const app=fs.readFileSync(__dirname+'/viewer-built.js','utf8');
class El{
 constructor(tag='div',id=''){this.tag=tag;this.id=id;this.dataset={};this.style={};this.value='';this.checked=false;this.disabled=false;this.textContent='';this.children=[];this.handlers={};this.attrs={};this.isConnected=true;this.classList={add:()=>{},remove:()=>{},toggle:()=>{}}}
 append(...a){this.children.push(...a)}replaceChildren(...a){this.children=a}
 addEventListener(k,f){this.handlers[k]=f}setAttribute(k,v){this.attrs[k]=v}getAttribute(k){return this.attrs[k]}
 getBoundingClientRect(){return {left:0,top:0,width:this.clientWidth,height:this.clientHeight}}
 setPointerCapture(){}
}
class Canvas extends El{
 constructor(w,h){super('canvas');this.clientWidth=w;this.clientHeight=h;this.width=w;this.height=h;this.image=null}
 getContext(type){if(type==='webgl')return null;const owner=this;return {createImageData:(w,h)=>({width:w,height:h,data:new Uint8ClampedArray(w*h*4)}),putImageData(img){owner.image=img},drawImage(c){owner.image=c.image},imageSmoothingEnabled:true}}
}
async function boot(width=531,height=570){
 const root=new El('div','tenbox-v2-r5'),elements=new Map();
 for(const match of html.matchAll(/data-id="([^"]+)"/g))elements.set(match[1],new El('div',match[1]));
 const canvas=new Canvas(width,height);elements.set('canvas',canvas);elements.get('stage').clientWidth=width;elements.get('stage').clientHeight=height;
 elements.get('model').textContent=html.match(/data-id="model">([^<]+)/)[1];
 const views=[...html.matchAll(/data-view="([^"]+)"/g)].map(m=>{const e=new El('button');e.dataset.view=m[1];return e});
 const cameras=[...html.matchAll(/data-camera="([^"]+)"/g)].map(m=>{const e=new El('button');e.dataset.camera=m[1];return e});
 root.querySelector=s=>elements.get(s.match(/data-id="([^"]+)"/)[1]);root.querySelectorAll=s=>s==='[data-view]'?views:cameras;
 const document={getElementById:id=>id===root.id?root:null,createElement:tag=>tag==='canvas'?new Canvas(width,height):new El(tag),createTextNode:s=>({textContent:s}),addEventListener(){},fullscreenElement:null};
 function Option(text,value){const e=new El('option');e.textContent=text;e.value=value;return e}
 const context=vm.createContext({document,window:{devicePixelRatio:1},location:{search:'?renderer=canvas'},console,Blob,Response,DecompressionStream,Uint8Array,Uint8ClampedArray,Float32Array,Uint16Array,Uint32Array,Map,Math,URLSearchParams,atob,Option,ResizeObserver:class{observe(){}},requestAnimationFrame(){},setTimeout});
 await vm.runInContext(app,context);
 if(root.dataset.error)throw Error(root.dataset.error);
 if(!root.dataset.ready)throw Error('Viewer did not reach ready state');
 return {context,root,canvas,elements,study:context.window.tenboxStudy,views,cameras};
}
function capture(h,name){h.study.render();const img=h.canvas.image;if(!img)throw Error('No rendered pixels');const p=new PNG({width:img.width,height:img.height});p.data=Buffer.from(img.data);fs.writeFileSync(__dirname+'/qa/'+name+'.png',PNG.sync.write(p));}
function ensure(test,msg){if(!test)throw Error(msg)}
async function main(){
 fs.mkdirSync(__dirname+'/qa',{recursive:true});const h=await boot();const checks=[];
 for(const view of ['floor-fit','floor-top','underside','lid-fit','lid-ledge','lid-top','lid-end','h2d','assembly','side','back','rail-gap','insert','front-joint','floor-joint','original']){
  h.study.setView(view);capture(h,view);ensure(h.study.visibleParts().length>0,view+' empty');checks.push({check:view+' has visible triangles',passed:true,parts:h.study.visibleParts().length});
 }
 for(const view of ['front-joint','floor-joint']){
  h.study.setView(view);h.elements.get('explode').handlers.input({target:{value:'18'}});const side=h.study.visibleParts().find(p=>p.sourceId==='body-right');ensure(side&&h.study.partOffset(side)[0]===18,view+' side does not move');capture(h,view+'-open');checks.push({check:view+' slider moves the actual side by18mm',passed:true});
 }
 h.study.setView('side');ensure(h.elements.get('part').children.length===2,'Side dropdown has irrelevant parts');checks.push({check:'Side-only menu excludes unavailable geometry',passed:true});
 h.study.setView('back');ensure(h.study.visibleParts().length===1&&h.study.visibleParts()[0].sourceId==='body-back','Back view does not isolate actual back panel');checks.push({check:'Back panel view isolates revised CAD',passed:true});
 h.study.setView('rail-gap');ensure(h.study.visibleParts().length===3,'Rail gap detail requires actual side, spacer, and frame');ensure(h.elements.get('gapLine').attrs.d?.length>10,'8mm dimension did not project');ensure(h.elements.get('explode').disabled,'Separation must be disabled in gap detail');checks.push({check:'8mm detail includes actual CAD and projected dimension',passed:true});
 h.study.setView('lid-fit');ensure(h.study.state.lidVisible&&h.study.state.lidLift===0,'Lid-fit preset is not closed');ensure(h.study.visibleParts().filter(p=>p.group==='lid').length===5,'Five updated lid parts missing');checks.push({check:'Lid-fit preset displays the complete one-piece lid assembly',passed:true});
 h.study.setView('lid-top');ensure(h.study.visibleParts().length===1&&h.study.visibleParts()[0].sourceId==='lid-top-single','One-piece roof view wrong');checks.push({check:'Roof view isolates the single continuous roof',passed:true});
 h.study.setView('lid-end');ensure(h.study.visibleParts().length===1&&h.study.visibleParts()[0].sourceId==='lid-front','Lid end view wrong');checks.push({check:'End-wall view shows the revised front wall',passed:true});
 h.study.setView('lid-ledge');ensure(h.study.visibleParts().length===2,'Ledge crop must contain actual side and roof');ensure(h.elements.get('flangeLine').attrs.d?.length>10&&h.elements.get('bearingLine').attrs.d?.length>10,'Ledge dimensions did not project');ensure(h.elements.get('explode').disabled,'Ledge detail should not explode');const labelPositions={};for(const n of ['flange','thick','bearing']){const a=h.elements.get(n+'Text').attrs;labelPositions[n]=[Number(a.x),Number(a.y)];ensure(Number(a.x)>25&&Number(a.x)<h.canvas.clientWidth-25&&Number(a.y)>60&&Number(a.y)<h.canvas.clientHeight-70,n+' label clipped');}checks.push({check:'Ledge section contains two CAD parts and projected flange/bearing dimensions',passed:true,labelPositions});
 h.study.setView('h2d');ensure(h.study.visibleParts().length===5,'H2D scene missing references');ensure(h.study.DATA.h2dView.sliced===false,'H2D scene must remain explicitly unsliced');const roof=h.study.visibleParts().find(p=>p.id==='h2d-roof');ensure(roof&&Math.abs(roof.box[5]-roof.box[2]-5)<.002,'H2D roof must be5mm high');ensure(Math.abs(roof.box[0]-4)<.002&&Math.abs(roof.box[3]-321)<.002,'H2D roof left-nozzle placement wrong');ensure(Math.abs(roof.box[1]-10)<.002&&Math.abs(roof.box[4]-300)<.002,'H2D roof rear clearance wrong');ensure(h.study.DATA.h2dView.nozzle==='left'&&h.study.DATA.h2dView.brimAllowanceMm===0,'Wrong nozzle or brim');checks.push({check:'H2D view contains the flat317×290×5 roof atX4–321,Y10–300 and the left-nozzle boundary',passed:true});
 h.study.setView('floor-fit');const floor=h.study.visibleParts().find(p=>p.id==='h2d-floor');ensure(floor&&h.study.visibleParts().length===5,'Floor print view missing mesh or bed references');ensure(h.study.DATA.floorPrintView.quantity===2&&!h.study.DATA.floorPrintView.sliced,'Floor reuse or unsliced metadata wrong');ensure(floor.box[0]>4&&floor.box[3]<321&&floor.box[1]>4&&floor.box[4]<316&&Math.abs(floor.box[5]-floor.box[2]-5)<.002,'Floor print envelope wrong');checks.push({check:'Floor scene shows exact flat diagonal pose and common-part quantity2',passed:true});
 h.study.setView('floor-top');ensure(h.study.visibleParts().length===1&&h.study.visibleParts()[0].sourceId==='body-bottom-back','Floor view must isolate revised rear floor');checks.push({check:'Clipped-floor view isolates the actual revised CAD',passed:true});
 h.study.setView('underside');ensure(h.study.visibleParts().length===6&&h.study.visibleParts().every(p=>p.group==='body'),'Underside must show six body panels only');checks.push({check:'Case underside shows the floor openings without lid or reference obstruction',passed:true});
 h.study.setView('assembly');h.elements.get('rails').onchange({target:{checked:true}});ensure(h.study.visibleParts().filter(p=>p.group==='rails').length===16,'Two rail sets missing');capture(h,'assembly-rails');
 ensure(h.study.visibleParts().filter(p=>p.group==='mounts').length===8,'Eight spacers missing');
 h.elements.get('rails').onchange({target:{checked:false}});ensure(!h.study.visibleParts().some(p=>['rails','mounts'].includes(p.group)),'Frame toggle must also hide spacers');h.elements.get('rails').onchange({target:{checked:true}});checks.push({check:'Frame toggle includes all eight 8mm spacers',passed:true});
 h.elements.get('lid').onchange({target:{checked:true}});h.elements.get('lidlift').oninput({target:{value:'90'}});h.study.fit();capture(h,'lid-open');
 h.elements.get('stand').onchange({target:{checked:true}});ensure(h.study.visibleParts().filter(p=>p.group==='stand').length===4,'Stand parts missing');capture(h,'with-stand');
 h.elements.get('part').onchange({target:{value:'body-bottom-front'}});ensure(h.study.visibleParts().length===1,'Isolation failed');capture(h,'isolated-bottom');
  h.elements.get('xray').onchange({target:{checked:true}});ensure(h.study.visibleParts().length===1&&h.study.state.only==='body-bottom-front','Transparency discarded isolation');checks.push({check:'Transparency preserves isolated part and selection',passed:true});
  const handlers=h.canvas.handlers;
  handlers.pointerdown({pointerId:1,clientX:100,clientY:100,button:0});handlers.pointerdown({pointerId:2,clientX:200,clientY:100,button:0});handlers.pointermove({pointerId:2,clientX:220,clientY:100});handlers.pointerup({pointerId:2,clientX:220,clientY:100,button:0});
  const yaw=h.study.camera.yaw;handlers.pointermove({pointerId:1,clientX:101,clientY:100});ensure(Math.abs(h.study.camera.yaw-yaw+.008)<1e-10,'Pinch release caused orbit jump');handlers.pointerup({pointerId:1,clientX:101,clientY:100,button:0});checks.push({check:'Pinch to single-finger transition has no orbit jump',passed:true});
 checks.push({check:'Reference toggles, lid lift,stand and part isolation',passed:true});
 h.study.setView('original');ensure(h.study.DATA.comparison.name==='Previous R4','Wrong comparison geometry');ensure(h.study.visibleParts().length===1&&h.study.visibleParts()[0].sourceId==='body-bottom-back','R4 comparison must show old floor only');const oldFloorMesh=h.study.visibleParts()[0].mesh;h.study.setView('floor-top');ensure(h.study.visibleParts()[0].mesh!==oldFloorMesh,'New and old floor unexpectedly share a mesh');checks.push({check:'Comparison shows the R4 floor with its original uncut corners',passed:true});
 h.study.setView('assembly');h.elements.get('lid').onchange({target:{checked:false}});h.study.setView('lid-ledge');ensure(h.study.visibleParts().length===2,'Ledge detail is hidden after body mode');checks.push({check:'Ledge preset restores lid visibility after body-only mode',passed:true});
 const m=await boot(390,480);ensure(m.study.state.view==='floor-fit','Default view must show the fixed floor on the H2D');capture(m,'narrow-floor-fit');m.study.setView('underside');capture(m,'narrow-underside');m.study.setView('lid-fit');capture(m,'narrow-lid-fit');m.study.setView('front-joint');m.elements.get('explode').handlers.input({target:{value:'10'}});capture(m,'narrow-front-joint');m.study.setView('h2d');capture(m,'narrow-h2d');m.study.setView('lid-ledge');capture(m,'narrow-lid-ledge');checks.push({check:'390px canvas renders floor, assembled openings, roof and ledge detail',passed:true});
 fs.writeFileSync(__dirname+'/qa/renderer-checks.json',JSON.stringify({scope:'Actual software rasterizer and UI event handlers in minimal DOM. Browser layout and WebGL not exercised.',checks},null,2));
 console.log(JSON.stringify({passed:checks.length,renderer:h.study.renderer,images:fs.readdirSync(__dirname+'/qa').filter(x=>x.endsWith('.png')).length}));
}
main().catch(e=>{console.error(e);process.exit(1)});
