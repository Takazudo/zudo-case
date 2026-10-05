(function(){
'use strict';
const M=FoldModel,$=id=>document.getElementById(id),$$=q=>[...document.querySelectorAll(q)],fmt=n=>Number(n.toFixed(1)).toString();
const titles={frame:'Original zudo-case rail frame',closed:'Seated spacer · closed',joint:'The closure joint',play:'Independent trays · 45°',trunk:'Trunk packing · exploded lid sleeve',packing:'Separate stand sleeve',parts:'Four spacer profiles',hinge:'Purchased hinge · sizing coupon'};
let state={...M.defaults},viewer=null,queued=false,pendingFit=false,toastTimer;
try{const c=JSON.parse(localStorage.getItem('zudo-case-F5'));if(c?.schema==='zudo-case-study/5'){const n={...M.defaults};for(const k of Object.keys(n))if(Object.hasOwn(c.state||{},k))n[k]=c.state[k];state=M.validate(n);}}catch(_){}
function notify(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),5000);}
function save(name,content,type='application/json'){const u=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function patch(p,fit=false){try{state=M.validate({...state,...p});render(fit);}catch(e){notify(e.message);sync();}}
function go(pose){patch({pose,view:['packing','parts'].includes(pose)?'top':'iso',cutaway:false},true);if(pose==='hinge')$('hingeControls').open=true;if(pose==='trunk')$('trunkControls').open=true;}
function trunkSection(d){
 const blocks=[{h:state.foam,label:'Bottom cushion',c:'#9da596'},{h:d.closedH,label:'Closed instrument (feet + guards)',c:'#35443e'},{h:d.separator,label:'Separator + load-spreading divider',c:'#9da596'},{h:d.standSleeve,label:'Separate stand sleeve',c:'#ad8d64'},{h:state.foam,label:'Top protection',c:'#9da596'}];
 const scale=.66,top=25,total=d.trunkRequired[2]*scale,height=total+60;let yy=top+total;
 let svg=`<svg viewBox="0 0 550 ${height}" role="img" aria-label="Vertical space budget for instrument, separate stand sleeve and protective layers">`;
 for(const b of blocks){yy-=b.h*scale;svg+=`<rect x="35" y="${yy}" width="215" height="${b.h*scale}" fill="${b.c}" stroke="#f7f7f2"/><text x="269" y="${yy+b.h*scale/2+3}" fill="#4d5e51" font-size="10.5" font-family="system-ui">${fmt(b.h)} mm · ${b.label}</text>`;}
 return svg+`<text x="35" y="${height-10}" fill="#64705f" font-size="11" font-family="monospace">Minimum inside H ${fmt(d.trunkRequired[2])} mm · entered H ${fmt(state.trunkH)} mm</text></svg>`;
}
function warnings(d){
 const out=[];
 if(d.frameRearClearLid<0)out.push(`Original frame projects ${fmt(-d.frameRearClearLid)} mm into/past the lid back plate. Increase lid depth; the board is NOT trimmed.`);
 else if(d.frameRearClearLid<3)out.push(`Only ${fmt(d.frameRearClearLid)} mm between original frame and lid back plate. Check a deeper lid.`);
 if(d.frameRearClearBase<0)out.push('Original frame does not fit the base depth.');
 if(Math.min(d.frameSideClearance,d.frameEndClearance)<1)out.push('Locator-to-source-frame clearance is under 1 mm. Revise the seat before building.');if(d.free<0)out.push(`${fmt(-d.free)} mm front-envelope overlap: do not close.`);else if(d.excess<0)out.push(`${fmt(-d.excess)} mm short of the entered patch margin.`);
 if(!state.straps)out.push('Straps removed for inspection. The seated joint does NOT prevent separation.');
 if(!d.trunkFits)out.push(`Entered trunk is too small: ${['W','D','H'].filter((_,i)=>d.trunkSpare[i]<0).map((k)=>`${k} short by ${fmt(-d.trunkSpare[['W','D','H'].indexOf(k)])} mm`).join(', ')}.`);
 if(d.rimClearance<.4)out.push(`Only ${fmt(d.rimClearance)} mm nominal clearance between locator tongues and dummy panel edges; revise before building.`);
 if(d.usableLid<28)out.push(`Lid body allowance is only ${fmt(d.usableLid)} mm before local obstructions.`);
 if(d.playFrontClearance<.001||d.playShellClearance<.001)out.push('Playing tray envelopes intersect. Increase stand spacing.');
 if(state.pose==='joint'&&state.jointLift>0)out.push('Exploded view only: straps are drawn schematically, not tensioned around the displaced parts.');
 if(state.collar==='hinged')out.push('Hinges are spacer keep-together joints. Mounted folding, holes and loads remain unverified.');
 return out;
}
function sync(){
 const d=M.dimensions(state),p=M.presets[state.preset];
 $$('[data-family]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.family===state.preset)));
 $$('[data-pose]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.pose===state.pose)));
 $$('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
 for(const k of ['frameExplode','gap','profile','collar','baseDepth','lidDepth','deskGap','finish','thickness','ply','plugBase','plugLid','knobBase','knobLid','bend','margin','overlap','seatClearance','jointLift','hingeAngle','foam','trunkW','trunkD','trunkH'])$(k).value=state[k];
 for(const k of ['straps','highlight','patch','cutaway','envelopes','structure'])$(k).checked=state[k];
 for(const [id,key,unit] of [['frameOut','frameExplode',' mm / layer'],['gapOut','gap',' mm'],['baseOut','baseDepth',' mm'],['lidOut','lidDepth',' mm'],['deskOut','deskGap',' mm'],['jointOut','jointLift',' mm / joint'],['hingeOut','hingeAngle','°']])$(id).textContent=fmt(state[key])+unit;
 $('familyDetail').textContent=p.layout===7?'Each half: 3U + 3U + 1U, 40HP per row':`Each half: ${p.layout}U, ${p.hp}HP per row`;
 $('stageCode').textContent=`${p.letter} / ${d.totalU}U · ${p.hp}HP / F5`;$('stageTitle').textContent=titles[state.pose];
 const subs={frame:'PINNED SOURCE RAILS / PCB FRAME STACK / PER TRAY',closed:'FULL-WRAP RETENTION · NOT A LIFTING HANDLE',joint:'OUTBOARD STRAP / OVERLAPPING SHOE / FIXED RIM',play:'SPACER REMOVED · NO LOADED-LID HINGE',trunk:'CUTAWAY TRUNK · STAND SLEEVE SHOWN LIFTED',packing:'ACTUAL STAND PANELS · OUTLINE = TRAY FOOTPRINT',parts:'INDIVIDUAL PROFILES · NO MOUNTED FOLDING CLAIM',hinge:'USER DRAWING + EXPLICIT PLACEHOLDER GEOMETRY'};
 $('stageSub').textContent=subs[state.pose];
 const notes={frame:'Blue: fixer · copper: padder · green: 8 mm spacers. Shell omitted.',closed:'Both trays must be restrained inside the padded trunk',joint:'Blue locates · yellow supports · bands retain engagement',play:'Spacer stores in the emptied trunk; strap rolls shown beside base',trunk:'Sleeve is exploded above the trunk; its thickness is counted inside H',packing:'Sleeve not attached to case · no stand inside the patch cavity',parts:'Corners seat against the tray outline; return profiles add storage bulk',hinge:'76 × 15 / leaf 35 / hole pitch 15 mm · unmeasured details assumed'};
 $('stageNote').textContent=notes[state.pose];
 $('stageLegend').innerHTML=state.pose==='frame'?'<span><i class="loc"></i>Fixer 1.6</span><span><i class="seat"></i>Padder 1.6</span><span><i class="hold"></i>Source rail</span><span><i class="shim"></i>Spacer 8</span>':(state.pose==='joint'||state.highlight)?'<span><i class="loc"></i>Locating shoe</span><span><i class="seat"></i>Fixed support</span><span><i class="hold"></i>Strap</span><span><i class="shim"></i>Gasket / guides</span>':'';
 $('metricEnvelope').innerHTML=`${fmt(d.closedW)} × ${fmt(d.closedD)} × ${fmt(d.closedH)} <em>mm</em>`;
 $('metricPocket').innerHTML=fmt(d.standSleeve)+' <em>mm</em>';$('metricSeat').innerHTML=fmt(d.overlap)+' <em>mm</em>';
 const fc=d.frame.counts;
 $('frameInfo').textContent=`${d.frame.description}. Per tray: ${fc.rail} rails, ${fc.fixer} fixers, ${fc.padder} padders, ${fc.spacer} side spacers.`;
 $('frameFit').textContent=`Frame reaches ${fmt(d.frame.rearReach)} mm behind the module front. Lid back-plate clearance: ${fmt(d.frameRearClearLid)} mm. Locator-to-frame: ${fmt(Math.min(d.frameSideClearance,d.frameEndClearance))} mm nominal.${state.pose==='frame'&&state.frameExplode>0?' Exploded inspection, not a packed assembly.':''}`;
 $('frameFit').classList.toggle('frame-error',d.frameRearClearLid<0);
 $('frameTableTitle').textContent=p.letter+' / '+d.frame.description;
 $('frameLedger').innerHTML=[['Rail length',d.rail+' mm (unscaled)'],['Frame W × row span',fmt(d.frame.width)+' × '+fmt(d.frame.depth)+' mm'],['Rails / fixers / padders',fc.rail+' / '+fc.fixer+' / '+fc.padder],['8 mm spacers / 1 mm washers',fc.spacer+' / '+fc.mount],['Rear reach below panel',fmt(d.frame.rearReach)+' mm'],['Lid back-plate clearance',fmt(d.frameRearClearLid)+' mm'],['Side / end locator clearance',fmt(d.frameSideClearance)+' / '+fmt(d.frameEndClearance)+' mm']].map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td></tr>').join('');
 $('profileNote').textContent=M.profiles[state.profile].note;
 $('collarNote').textContent=state.collar==='loose'?'No hinge required for the first fit sample. Four profiled panels are located by both tray rims; they are not a loose fabric ring.':'Two of your hinges keep opposite corner pairs together. They do not join the loaded trays or hold the playing angle. Check full mounted folding with a coupon.';
 const warn=warnings(d);$('checkBanner').className='check-banner'+(warn.length?(d.frameRearClearLid<0||d.free<0||!d.trunkFits||!state.straps?' bad':' warn'):'');
 $('checkBanner').textContent=warn.length?warn.join(' '):`Nominal front gap leaves ${fmt(d.free)} mm free. Entered trunk dimensions fit the reserved boxes. This is source-frame layout only: closure, strength, cable turnover and actual hardware fit are untested.`;
 const rows=[['Module trays','Faces inward; independently retained by the seated stack','Base on feet; shallow tray on 45° stand'],['Spacer panels',state.collar==='hinged'?'Two hinged pairs seated between the tray rims':'Four panels seated between the tray rims','In a protective sleeve in the emptied trunk'],['Stand panels','Separate sleeve in a divided trunk compartment','2 cheeks + 2 cross-ties assembled'],['Closure straps','Two captured full-wrap loops; covered buckles','Rolled and put in the empty trunk'],['Locators / guards','Collar shoes overlap protected fixed rim seats','Tall shoes leave with collar; low rim remains']];
 $('partsLedger').innerHTML=rows.map(r=>`<tr>${r.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('');
 $('storageNote').textContent=`No underside pocket. Stand sleeve allowance ${fmt(d.standSleeve)} mm. Conservative spacer-package reservation during play: ${fmt(d.collarPacket.length)} × ${fmt(d.collarPacket.width)} × ${fmt(d.collarPacket.thickness)} mm. That reservation is not proof of a mounted folding path; the emptied trunk can instead hold separated profiles.`;
 $('sectionDiagram').innerHTML=trunkSection(d);
 $('depthNote').textContent=`Lid body allowance ${fmt(d.usableLid)} mm, ${fmt(d.overStiffenerLid)} mm over a 6 mm back support, or ${fmt(d.overBusLid)} mm over the assumed busboard (separate local budgets). Nominal locator-to-panel edge clearance ${fmt(d.rimClearance)} mm; the source frame is now present, but bolts, real tolerances and module bodies still need a physical check. 2 mm low playing rim. No power brick or spare cable compartment is included.`;
 $('packingProof').innerHTML=`<div class="packing-proof${d.trunkFits?'':' warn'}"><b>${d.trunkFits?'Reserved boxes fit entered trunk':'Entered trunk does not fit'}</b><span>Required inside W × D × H: ${d.trunkRequired.map(fmt).join(' × ')} mm</span><span>Entered inside dimensions: ${[state.trunkW,state.trunkD,state.trunkH].map(fmt).join(' × ')} mm</span><span>Unused allowance: ${d.trunkSpare.map(fmt).join(' / ')} mm</span><span>Padding density, compression, organizer and real trunk not selected</span></div>`;
 $('hingeNote').textContent='Your drawing identifies the compact 76 × 15 mm hinge. The workbench can place two hinges inside opposite spacer corners, leaving two seams free to open sideways around patch leads. The separate panels remain the lower-risk baseline for testing the seats first. The 15 mm pin-axis direction is vertical in the corner study; the 35 mm leaves run along the spacer walls.';
 return d;
}
function render(fit=false){pendingFit=pendingFit||fit;if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;try{const d=sync();if(viewer){if(pendingFit){viewer.state={...state};viewer.setView(state.view,false);}viewer.update({...state},d,pendingFit);}pendingFit=false;try{localStorage.setItem('zudo-case-F5',JSON.stringify({schema:'zudo-case-study/5',state}));}catch(_){}window.FoldApp.lastError=null;}catch(e){console.error(e);window.FoldApp.lastError=e.message;notify(e.message);}});}
$('familyChoices').innerHTML=Object.values(M.presets).map(p=>`<button data-family="${p.id}" aria-pressed="false"><b>${p.letter}</b><span>${p.short}</span></button>`).join('');
const cards=[['frame','Original frame','Inspect unscaled source rails, the PCB stack and 8 mm spacers.'],['closed','Closed instrument','Seated collar, two retained straps and protected buckle envelopes.'],['trunk','Protected trunk','Restraint at both tray bodies and a separate, divided stand sleeve.']];
$('compareCards').innerHTML=cards.map(([id,title,desc])=>`<article class="compare-card"><div class="compare-thumb">${window.FOLD_THUMBS?.[id]?`<img src="${window.FOLD_THUMBS[id]}" alt="${title}" loading="lazy">`:''}<span>F5 / ${id.toUpperCase()}</span></div><div class="compare-body"><h3>${title}</h3><p>${desc}</p><button data-go="${id}">Inspect view →</button></div></article>`).join('');
$$('[data-family]').forEach(b=>b.addEventListener('click',()=>{const p=M.presets[b.dataset.family];patch({preset:p.id,baseDepth:p.baseDepth,lidDepth:p.lidDepth},true);}));
$$('[data-pose]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.pose)));
$$('[data-go]').forEach(b=>b.addEventListener('click',()=>{go(b.dataset.go);$('workbench').scrollIntoView({behavior:'auto'});}));
for(const k of ['frameExplode','gap','baseDepth','lidDepth','deskGap','jointLift','hingeAngle'])$(k).addEventListener('input',e=>{const p={[k]:Number(e.target.value)};if(k==='frameExplode')p.pose='frame';if(k==='jointLift')p.pose='joint';if(k==='hingeAngle')p.pose='hinge';patch(p,k==='frameExplode'||k==='jointLift'||k==='hingeAngle');});
for(const k of ['plugBase','plugLid','knobBase','knobLid','bend','margin','thickness','ply','overlap','seatClearance','foam','trunkW','trunkD','trunkH'])$(k).addEventListener('change',e=>patch({[k]:Number(e.target.value)},true));
$('profile').addEventListener('change',e=>{const p=M.profiles[e.target.value],{gap,plugBase,plugLid,bend,knobBase,knobLid,elbow}=p;patch({profile:e.target.value,gap,plugBase,plugLid,bend,knobBase,knobLid,elbow},true);});
for(const k of ['finish','collar'])$(k).addEventListener('change',e=>patch({[k]:e.target.value},true));
for(const k of ['straps','highlight','patch','cutaway','envelopes','structure'])$(k).addEventListener('change',e=>patch({[k]:e.target.checked}));
$$('[data-view]').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;viewer?.setView(state.view);sync();}));
$('fit').addEventListener('click',()=>{viewer?.fit();viewer?.draw();});
$('full').addEventListener('click',()=>{const expanded=$('stage').classList.toggle('expanded');$('full').setAttribute('aria-label',expanded?'Close expanded viewer':'Expand viewer');document.body.style.overflow=expanded?'hidden':'';setTimeout(()=>{viewer?.fit();viewer?.draw();},50);});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('stage').classList.contains('expanded'))$('full').click();});
$('reset').addEventListener('click',()=>{state={...M.defaults};render(true);});
$('saveConfig').addEventListener('click',()=>save(`zudo-case-F5-${M.presets[state.preset].letter}-${state.pose}.json`,JSON.stringify(M.config(state),null,2)));
$('loadConfig').addEventListener('click',()=>$('fileInput').click());
$('fileInput').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>120000)throw new Error('Setup file is too large.');const c=JSON.parse(await f.text());if(c.schema!=='zudo-case-study/5')throw new Error('Use an F5 setup; older rounds use different structure.');const n={...M.defaults};for(const k of Object.keys(n))if(Object.hasOwn(c.state||{},k))n[k]=c.state[k];state=M.validate(n);render(true);notify('F5 setup loaded.');}catch(e){notify('Setup not loaded: '+e.message);}finally{$('fileInput').value='';}});
$('png').addEventListener('click',()=>{if(!viewer)return;viewer.draw();const c=document.createElement('canvas');c.width=$('viewer').width;c.height=$('viewer').height;const ctx=c.getContext('2d');ctx.drawImage($('viewer'),0,0);const scale=c.width/Math.max(1,$('viewer').clientWidth);ctx.scale(scale,scale);ctx.fillStyle='#35453a';ctx.font='600 12px system-ui';ctx.fillText(`ZUDO CASE / F5 · ${M.presets[state.preset].letter} / ${titles[state.pose]}`,20,25);ctx.font='9px monospace';ctx.fillText('DIMENSIONAL STUDY · no strength, real-hardware or patch-fit approval',20,43);const a=document.createElement('a');a.href=c.toDataURL('image/png');a.download=`zudo-case-F5-${state.preset}-${state.pose}.png`;a.click();});
window.FoldApp={get state(){return {...state};},get viewer(){return viewer;},get pending(){return queued;},setState(p,fit=true){state=M.validate({...state,...p});render(fit);},reset(){state={...M.defaults};render(true);},config(){return M.config(state);},warnings(){return warnings(M.dimensions(state));},ready:false,lastError:null};
try{viewer=new FoldRenderer.Viewer($('viewer'));$('rendererMode').textContent=viewer.mode==='webgl'?'WEBGL':'SOFTWARE 3D';const d=sync();viewer.update({...state},d,true);viewer.setView(state.view);window.FoldApp.ready=true;}catch(e){$('renderError').hidden=false;$('renderError').textContent='3D could not start: '+e.message;window.FoldApp.lastError=e.message;console.error(e);sync();}
})();
