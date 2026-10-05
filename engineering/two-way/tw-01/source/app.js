(function(){
'use strict';
const M=FoldModel,$=id=>document.getElementById(id),$$=q=>[...document.querySelectorAll(q)],fmt=n=>Number(n.toFixed(2)).toString();
const titles={frame:'元フレームと積層',closed:'カラーを挟んで収納',joint:'座面と位置決め',play:'独立トレーで演奏',trunk:'トランク内の配置',packing:'スタンドを別袋へ',parts:'カラーを4枚に分離',hinge:'購入蝶番の単体検討'};
const notes={frame:'各トレーに繰り返す元フレームを1トレー分表示。筐体を省略しています。カラー・スタンドはこの検討表示では省略し、別袋で保管します。',closed:'上下トレーは独立部品です。スタンド別袋はトランク内の仕切り区画に入ります。',joint:'接合部の部分表示。座面が圧縮を受け、重なりが位置を決め、バンドが保持する設計仮説です。その他の部品は省略しています。',play:'カラーとバンドは空のトランクへ。丸めたバンドは一時的に本体脇に図示。蓋トレーは独立した45°スタンドに載せます。',trunk:'スタンド別袋は見やすさのため上方に分解表示。収納寸法ではトランク内に計上しています。',packing:'スタンド板の平置き検討。外周線はトレーの面積です。別袋は筐体に取り付けません。',parts:'独立したカラー部品の検討。他部品は省略。演奏中は保護袋に入れて空のトランクへ。',hinge:'蝶番の単体角度検討。段付きカラーに取り付けた状態の折り畳みを保証しません。'};
let state={...M.defaults},viewer=null,queued=false,pendingFit=false,toastTimer,restoreFocus=null;
try{const c=JSON.parse(localStorage.getItem('zudo-case-two-way/1'));if(c)state=M.importConfig(c);}catch(_){}
function notify(msg){$('toast').textContent=msg;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),6000);}
function save(name,content,type='application/json'){const u=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function patch(p,fit=false){try{const n=M.validate({...state,...p});M.dimensions(n);state=n;render(fit);}catch(e){notify('入力を確認してください: '+e.message);sync();}}
function go(pose){patch({pose,view:['packing','parts'].includes(pose)?'top':'iso'},true);if(pose==='hinge')$('hingeControls').open=true;if(pose==='trunk')$('trunkControls').open=true;}
function sync(){
 const d=M.dimensions(state),p=M.presets[state.preset];
 for(const [attr,key] of [['family','preset'],['pose','pose'],['view','view']])$$('[data-'+attr+']').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset[attr]===state[key])));
 for(const [k,v] of Object.entries(state)){const el=$(k);if(el){if(el.type==='checkbox')el.checked=v;else {if(el.type==='range'){const step=el.dataset.nominalStep||(el.dataset.nominalStep=el.step);const ticks=(v-Number(el.min))/Number(step);el.step=Math.abs(ticks-Math.round(ticks))<1e-8?step:'any';}el.value=v;}}const out=$(k+'Out');if(out)out.textContent=fmt(v)+(k==='hingeAngle'?'°':' mm');}
 $('frameInspection').hidden=state.pose!=='frame';$('jointInspection').hidden=state.pose!=='joint';
 $('familyDetail').textContent=`各トレー：${p.layout===7?'3U＋3U＋1U':p.layout+'U'}・各列 ${p.hp}HP。2トレー合計 ${d.totalU}U。`;
 $('stageCode').textContent=`${p.letter} / ${p.familyId} / TW-01`;$('stageTitle').textContent=titles[state.pose];$('stageNote').textContent=notes[state.pose];
 $('stageLegend').textContent=state.pose==='frame'?'青：fixer 1.6 mm / 銅：padder 1.6 mm / 緑：スペーサー8 mm / 元レールは無変更':state.highlight?'青：位置決め / 黄：支持 / 黒：ストラップ / 緑：パッキン・ガイド':'';
 $('metricEnvelope').textContent=[d.closedW,d.closedD,d.closedH].map(fmt).join(' × ')+' mm';$('metricMetal').textContent=[d.W,d.D,d.metalStack].map(fmt).join(' × ')+' mm';$('metricPocket').textContent=fmt(d.standSleeve)+' mm';$('metricSeat').textContent=fmt(d.overlap)+' mm';
 const fc=d.frame.counts;
 $('frameInfo').textContent=`各トレー：レール${fc.rail} / fixer ${fc.fixer} / padder ${fc.padder} / 側面スペーサー${fc.spacer}。`;
 $('frameFit').textContent=`前面からフレーム後端 ${fmt(d.frame.rearReach)} mm。蓋背板まで ${fmt(d.frameRearClearLid)} mm。位置決め部との最小余裕 ${fmt(Math.min(d.frameSideClearance,d.frameEndClearance))} mm。`;
 $('frameFit').classList.toggle('frame-error',d.frameRearClearLid<0);
 $('frameTableTitle').textContent=p.letter+' / 各トレー';
 $('frameLedger').innerHTML=[['レール長（無変更）',d.rail+' mm'],['フレーム幅 × 列方向',fmt(d.frame.width)+' × '+fmt(d.frame.depth)+' mm'],['レール / fixer / padder',fc.rail+' / '+fc.fixer+' / '+fc.padder],['8 mmスペーサー / 1 mm座金',fc.spacer+' / '+fc.mount],['前面から後端',fmt(d.frame.rearReach)+' mm'],['蓋背板との余裕',fmt(d.frameRearClearLid)+' mm'],['側面 / 端の位置決め余裕',fmt(d.frameSideClearance)+' / '+fmt(d.frameEndClearance)+' mm']].map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td></tr>').join('');
 $('profileNote').textContent=state.profile==='straight'?'72 mmは仮定です。片側28 mmのプラグと4 mmの出口余裕を見込みます。実配線を測定してください。':'58 mmは仮定です。L型12 mmと出口余裕5 mm、ノブ25 mmを見込みます。密集した束は別途確認してください。';
 $('collarNote').textContent=state.collar==='loose'?'独立4枚を基準に座面を確認します。トレーのリムが位置を決め、バンドが保持します。':'蝶番はカラー2組をまとめるためだけに使います。荷重のあるトレーをつなぎません。';
 const conflicts=d.diagnostics.filter(x=>x.kind==='nominal-conflict'),inspections=d.diagnostics.filter(x=>x.kind==='inspection');
 $('checkBanner').className='check-banner'+(conflicts.length?' bad':inspections.length?' warn':'');
 $('checkBanner').replaceChildren();
 const title=document.createElement('strong');title.textContent=conflicts.length?'名目寸法の干渉・不足あり':'名目寸法の検討 / 現物未検証';$('checkBanner').append(title);
 for(const diag of d.diagnostics){const line=document.createElement('p');line.textContent=diag.message+(diag.value===null?'':` (${fmt(diag.value)} mm)`);line.dataset.diagnostic=diag.code;$('checkBanner').append(line);}
 const rows=[['トレー2個','対向させカラー・バンドで保持','本体は脚、蓋は45°スタンド'],['カラー','4枚、または蝶番の2組を座面へ','保護袋に入れ空のトランクへ'],['スタンド','トランク内の独立した別袋','側板2枚＋横桟2本'],['ストラップ','2本の外周ループをガイドへ','外して丸め、空のトランクへ'],['位置決め・保護','カラーの重なりと低いリム','背の高い部分はカラーと外れる']];
 $('partsLedger').innerHTML=rows.map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('');
 $('storageNote').textContent=`下面ポケット・パッチ空間への部品収納はありません。スタンド袋 ${fmt(d.standSleeve)} mm。カラーの仮収納包絡 ${[d.collarPacket.length,d.collarPacket.width,d.collarPacket.thickness].map(fmt).join(' × ')} mm。折り畳み成立の証明ではありません。`;
 $('depthNote').textContent=`蓋のモジュール後方余裕 ${fmt(d.usableLid)} mm、6 mm背面補強上 ${fmt(d.overStiffenerLid)} mm、仮バス基板上 ${fmt(d.overBusLid)} mm。元フレーム後端 ${fmt(d.frame.rearReach)} mmとは別の局所予算です。電源アダプター・予備ケーブルは計上していません。`;
 $('packingProof').textContent=`必要内寸 W × D × H：${d.trunkRequired.map(fmt).join(' × ')} mm / 入力内寸：${[state.trunkW,state.trunkD,state.trunkH].map(fmt).join(' × ')} mm / 残り：${d.trunkSpare.map(fmt).join(' / ')} mm。緩衝材の硬さ・圧縮量・実トランクは未確認。`;
 $('sectionDiagram').textContent=`高さの内訳：底緩衝材 ${fmt(state.foam)} ＋ 完成包絡 ${fmt(d.closedH)} ＋ 仕切り ${fmt(d.separator)} ＋ スタンド袋 ${fmt(d.standSleeve)} ＋ 上緩衝材 ${fmt(state.foam)} mm。`;
 return d;
}
function render(fit=false){pendingFit=pendingFit||fit;if(queued)return;queued=true;requestAnimationFrame(()=>{try{const d=sync();if(viewer){if(pendingFit){viewer.state={...state};viewer.setView(state.view,false);}viewer.update({...state},d,pendingFit);}pendingFit=false;try{localStorage.setItem('zudo-case-two-way/1',JSON.stringify(M.config(state)));}catch(_){}window.FoldApp.lastError=null;}catch(e){console.error(e);window.FoldApp.lastError=e.message;notify(e.message);}finally{queued=false;}});}
$('familyChoices').innerHTML=Object.values(M.presets).map(p=>`<button data-family="${p.id}" aria-pressed="false"><b>${p.letter}</b><span>${p.short}</span></button>`).join('');
$$('[data-family]').forEach(b=>b.addEventListener('click',()=>{const p=M.presets[b.dataset.family];patch({preset:p.id,baseDepth:p.baseDepth,lidDepth:p.lidDepth},true);}));
$$('[data-pose]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.pose)));
for(const [k,v] of Object.entries(M.defaults)){const el=$(k);if(!el)continue;if(typeof v==='boolean')el.addEventListener('change',e=>patch({[k]:e.target.checked}));else if(typeof v==='number')el.addEventListener(el.type==='range'?'input':'change',e=>patch({[k]:Number(e.target.value)},['frameExplode','jointLift','hingeAngle'].includes(k)));}
$('profile').addEventListener('change',e=>{const p=M.profiles[e.target.value],{gap,plugBase,plugLid,bend,knobBase,knobLid,elbow}=p;patch({profile:e.target.value,gap,plugBase,plugLid,bend,knobBase,knobLid,elbow},true);});
for(const k of ['finish','collar'])$(k).addEventListener('change',e=>patch({[k]:e.target.value},true));
$$('[data-view]').forEach(b=>b.addEventListener('click',()=>{patch({view:b.dataset.view});viewer?.setView(b.dataset.view);}));
$('fit').addEventListener('click',()=>{viewer?.fit();viewer?.draw();});
function expand(open){if(open)restoreFocus=document.activeElement;$('stage').classList.toggle('expanded',open);$('stage').setAttribute('role',open?'dialog':'group');if(open)$('stage').setAttribute('aria-modal','true');else $('stage').removeAttribute('aria-modal');$('stage').setAttribute('aria-label','3Dモデルの拡大表示');$('full').setAttribute('aria-expanded',String(open));$('full').textContent=open?'閉じる':'拡大';document.body.style.overflow=open?'hidden':'';if(open)$('viewer').focus();else restoreFocus?.focus();requestAnimationFrame(()=>{viewer?.fit();viewer?.draw();});}
$('full').addEventListener('click',()=>expand(!$('stage').classList.contains('expanded')));
document.addEventListener('keydown',e=>{if(!$('stage').classList.contains('expanded'))return;if(e.key==='Escape'){e.preventDefault();expand(false);}if(e.key==='Tab'){const nodes=[...$('stage').querySelectorAll('button,canvas')],first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
$('reset').addEventListener('click',()=>{state={...M.defaults};render(true);});
$('saveConfig').addEventListener('click',()=>save(`zudo-case-TW-01-${M.presets[state.preset].letter}-${state.pose}.json`,JSON.stringify(M.config(state),null,2)));
$('loadConfig').addEventListener('click',()=>$('fileInput').click());
$('fileInput').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>120000)throw new Error('設定ファイルは120 KB以下にしてください。');const n=M.importConfig(JSON.parse(await f.text()));state=n;render(true);notify('設定を読み込み、寸法と診断を再計算しました。');}catch(e){notify('設定を読み込めませんでした。前の状態を維持します: '+e.message);}finally{$('fileInput').value='';}});
$('png').addEventListener('click',()=>{if(!viewer)return;viewer.draw();const c=document.createElement('canvas');c.width=$('viewer').width;c.height=$('viewer').height;const ctx=c.getContext('2d');ctx.drawImage($('viewer'),0,0);const scale=c.width/Math.max(1,$('viewer').clientWidth);ctx.scale(scale,scale);ctx.fillStyle='#35453a';ctx.font='600 12px system-ui';ctx.fillText(`ZUDO CASE / TW-01 · ${M.presets[state.preset].letter} / ${titles[state.pose]} / ${viewer.mode}`,16,55);ctx.font='10px system-ui';ctx.fillText('寸法検討・製造未承認・強度未検証',16,74);const a=document.createElement('a');a.href=c.toDataURL('image/png');a.download=`zudo-case-TW-01-${state.preset}-${state.pose}.png`;a.click();});
window.FoldApp={get state(){return {...state};},get viewer(){return viewer;},get pending(){return queued;},setState(p,fit=true){const n=M.validate({...state,...p});M.dimensions(n);state=n;render(fit);},reset(){state={...M.defaults};render(true);},config(){return M.config(state);},warnings(){return M.dimensions(state).diagnostics.map(x=>x.message);},ready:false,lastError:null};
try{viewer=new FoldRenderer.Viewer($('viewer'));$('rendererMode').textContent=viewer.mode==='webgl'?'WebGL':'Software 3D';const d=sync();viewer.update({...state},d,true);viewer.setView(state.view);window.FoldApp.ready=true;}catch(e){$('renderError').hidden=false;$('renderError').textContent='3Dを開始できません: '+e.message;window.FoldApp.lastError=e.message;console.error(e);sync();}
})();
