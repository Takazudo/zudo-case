/* ZUDO CASE TW-01 — seated closure / protected trunk. Millimetres. Layout study, not manufacturing CAD. */
(function(root){
'use strict';
const rad=d=>d*Math.PI/180,add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,k)=>a.map(v=>v*k),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],len=a=>Math.hypot(...a),norm=a=>mul(a,1/(len(a)||1)),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const spec=root.TwoWaySpec;
function validateSpec(v){
 if(v.schema!=='zudo-case-two-way-study/1'||v.revision!=='TW-01'||v.manufacturingApproved!==false)throw new Error('Invalid study status');
 const ids=['tw-3u60','tw-6u60','tw-7u40'];
 if(v.families.length!==3||new Set(v.families.map(p=>p.id)).size!==3||new Set(v.families.map(p=>p.alias)).size!==3||v.families.some(p=>!ids.includes(p.id)||!['compact','performance','twin40'].includes(p.alias)))throw new Error('Invalid families');
 function finite(x){if(typeof x==='number'&&!Number.isFinite(x))throw new Error('Non-finite spec');if(x&&typeof x==='object')Object.values(x).forEach(finite);}finite(v);
 return v;
}
validateSpec(spec);
const presets=Object.fromEntries(spec.families.map(p=>[p.alias,{...p,familyId:p.id,id:p.alias,name:p.letter,short:`各 ${p.layout}U・${p.hp}HP / 計 ${p.layout*2}U`} ]));
const kits={tilted:{id:'tilted',number:'04',name:'Seated collar + 45°',tag:'Trunk-carried instrument'}};
const profiles={
 straight:{name:'Straight plug study · 72 mm',gap:72,plugBase:28,plugLid:28,bend:4,knobBase:25,knobLid:25,elbow:false,note:'28 mm plug projection plus 4 mm exit allowance per side are assumptions. Measure your real cables; 72 mm is not a proven patch clearance.'},
 elbow:{name:'Low-profile elbow study · 58 mm',gap:58,plugBase:12,plugLid:12,bend:5,knobBase:25,knobLid:25,elbow:true,note:'Tendrils specifies 12 mm height when patched. With these inputs, the assumed 25 mm knobs determine the gap. Dense bundles and taller controls still require measurement.'}
};
const defaults={...spec.defaults};
function validate(s){
 if(!Object.hasOwn(presets,s.preset)||s.kit!=='tilted'||!Object.hasOwn(profiles,s.profile))throw new Error('未知のケース構成またはプロファイルです。');
 for(const [k,a,b] of [['gap',48,110],['baseDepth',60,110],['lidDepth',38,90],['thickness',1.5,2.5],['ply',6,10],['plugBase',8,60],['plugLid',8,60],['bend',2,20],['knobBase',10,40],['knobLid',10,40],['margin',4,20],['deskGap',24,160],['lead',200,1200],['overlap',4,10],['seatClearance',.25,1.2],['frameExplode',0,18],['jointLift',0,30],['hingeAngle',0,180],['foam',10,40],['trunkW',250,700],['trunkD',200,700],['trunkH',180,500]])if(!Number.isFinite(s[k])||s[k]<a||s[k]>b)throw new Error('範囲または型が不正です: '+k);
 for(const k of ['elbow','patch','cross','envelopes','cutaway','modules','structure','labels','highlight','straps'])if(typeof s[k]!=='boolean')throw new Error('範囲または型が不正です: '+k);
 if(!['frame','closed','play','parts','packing','joint','trunk','hinge'].includes(s.pose)||!['loose','hinged'].includes(s.collar)||!['graphite','silver','olive'].includes(s.finish)||!['iso','side','front','top','back'].includes(s.view))throw new Error('表示設定が不正です。');return s;
}
function polygonGap(A,B){
 let intersects=true;
 for(const P of [A,B])for(let i=0;i<P.length;i++){const v=sub(P[(i+1)%P.length],P[i]),axis=norm([-v[1],v[0]]),a=A.map(p=>dot(p,axis)),b=B.map(p=>dot(p,axis));if(Math.max(...a)<Math.min(...b)-1e-8||Math.max(...b)<Math.min(...a)-1e-8)intersects=false;}
 if(intersects)return 0;
 function segment(p,a,b){const v=sub(b,a),f=clamp(dot(sub(p,a),v)/dot(v,v),0,1);return len(sub(p,add(a,mul(v,f))));}
 let best=Infinity;for(const [P,Q] of [[A,B],[B,A]])for(const p of P)for(let i=0;i<Q.length;i++)best=Math.min(best,segment(p,Q[i],Q[(i+1)%Q.length]));return best;
}
function baseDimensions(s){
 validate(s);const p=presets[s.preset],t=s.thickness,hp=p.hp,rail=hp===40?204:305;
 const frame=root.FoldFrame.describe(p.layout,rail,t),frameD=frame.depth;
 const D=frame.caseDepth,W=rail+6.4+16+2*t,G=s.gap,rim=2,gasket=.5,collarH=G-2*rim-2*gasket;
 const rows=frame.rows;
 const qBase=Math.max(s.knobBase,s.plugBase+s.bend),qLid=Math.max(s.knobLid,s.plugLid+s.bend),bundleLayer=t+1.5,wrapStack=4*bundleLayer+4,standStack=2*s.ply+4;
 // Loose parts travel in separate trunk sleeves, never in patch clearance.
 const pocket=0,floor=-s.baseDepth-4;
 const standSpan=.8*D,run=standSpan/Math.sqrt(2),barH=Math.min(20,.065*D),heel=Math.min(50,Math.max(10,D-32-2*barH-run)),standWidth=W-28,standDepth=run+20,standHeight=run+heel+10;
 const packedSideW=standDepth,packedSideH=standHeight,packedStartY=-D/2+14+2*barH,packedTop=packedStartY+packedSideH;
 const d={W,D,G,t,hp,rail,frameD,rows,frame,rim,gasket,collarH,qBase,qLid,free:G-qBase-qLid,required:qBase+qLid+s.margin,excess:G-qBase-qLid-s.margin,totalU:p.layout*2,
 metalStack:s.baseDepth+s.lidDepth+G,closedW:W+6,closedD:D+6,closedH:s.baseDepth+s.lidDepth+G+pocket+8,pocket,wrapStack,standStack,bundleLayer,
 floor,usableBase:s.baseDepth-t-2-10,usableLid:s.lidDepth-t-2-10,overBusLid:s.lidDepth-t-2-10-12,
 standSpan,run,barH,heel,standWidth,standDepth,standHeight,packedSideW,packedSideH,packedStartY,packedTop,
 standPackFits:packedSideW<=W-12+1e-8&&packedTop<=D/2-6+1e-8,
 accessoryWithinFootprint:standWidth<=W&&standDepth<=D,
 strapClosedLoop:2*(D+s.baseDepth+s.lidDepth+G+pocket+2),strapPlayLoop:2*(W+D+4),strapMinimumBeforeOverlap:Math.max(2*(D+s.baseDepth+s.lidDepth+G+pocket+2),2*(W+D+4)),protrudingLinkages:0,poseIsKinematic:false};
 const c=lidPoint([0,0,0],s,d);d.lidPlaneZ=c[2];
 // Projected table footprint includes both trays and the optional stand, not a fictitious collapsed case.
 const ys=[];for(const y of [-D/2,D/2])for(const z of [-s.lidDepth-4,0])ys.push(lidPoint([0,y,z],{...s,pose:'play'},d)[1]);
 d.deskDepth=Math.max(D/2,...ys)-Math.min(-D/2,...ys);d.deskWidth=W+6;
 const play={...s,pose:'play'},rect=(y,z0,z1)=>[[-y,z0],[y,z0],[y,z1],[-y,z1]],xf=P=>P.map(p=>lidPoint([0,p[0],p[1]],play,d).slice(1));
 d.playFrontClearance=polygonGap(rect(frameD/2,0,qBase),xf(rect(frameD/2,0,qLid)));
 d.playShellClearance=polygonGap(rect(D/2+1.5,-s.baseDepth,2),xf(rect(D/2+1.5,-s.lidDepth,2)));
 d.playCheckScope='Static rectangular shell and front-envelope sections only. No cable, hardware or opening-sweep approval.';
 return d;
}
function orientation(s){return ['closed','trunk'].includes(s.pose)?180:(s.pose==='play'&&s.kit==='tilted'?45:0);}
function lidNormal(v,s){const a=rad(orientation(s)),c=Math.cos(a),n=Math.sin(a);return [v[0],c*v[1]-n*v[2],n*v[1]+c*v[2]];}
function lidPoint(v,s,d){
 if(['closed','trunk'].includes(s.pose))return [v[0],-v[1],d.G-v[2]];
 let yc=d.D+s.deskGap,zc=d.floor+4+s.lidDepth;
 if(s.pose==='play'&&s.kit==='tilted'){
  // Front bottom corner is behind the base, seated on the stand's sloped surface.
  const a=rad(45),c=Math.cos(a),n=Math.sin(a),y0=d.D/2+s.deskGap,z0=d.floor+4+d.heel;
  return [v[0],y0+c*(v[1]+d.D/2)-n*(v[2]+s.lidDepth),z0+n*(v[1]+d.D/2)+c*(v[2]+s.lidDepth)];
 }
 if(s.pose==='parts')yc=d.D+70;
 const r=lidNormal(v,s);return [r[0],r[1]+yc,r[2]+zc];
}
function modules(s,d,side){
 const widths=d.hp===60?[8,8,12,8,8,8,8]:[8,8,8,8,8],names=side?['LFO','ENV','MOD','VCA','CV','MIX','I/O']:['VCO','WAVE','VCF','ENV','VCA','MIX','OUT'];
 const modules=[],jacks=[];let id=0;d.rows.forEach((r,ri)=>{let x=-d.hp*5.08/2;widths.forEach((hp,mi)=>{const width=hp*5.08-.35,center=x+hp*5.08/2,mod={id:id++,x:center,y:r.y,w:width,h:r.h,u:r.u,screwY:r.screwY,name:r.u===1?['MULT','OFFSET','MIX','I/O','UTIL','CV','AUX'][mi]:names[(mi+ri*2)%names.length],metal:(mi+ri+side)%3===0,jacks:[]};
 const jy=r.u===1?r.y-5:r.y+(side?-1:1)*(r.h/2-22);for(let j=0;j<2;j++){const jack={p:[center+(j?1:-1)*Math.min(9,width*.22),jy,0],module:mod.id,index:j,row:ri};jacks.push(jack);mod.jacks.push(jack);}modules.push(mod);x+=hp*5.08;});});return {modules,jacks};
}
function crossAnchors(s,d){const b=modules(s,d,0).jacks.filter(j=>j.row===d.rows.length-1),l=modules(s,d,1).jacks.filter(j=>j.row===0);return [0,1].map(i=>({base:b[Math.min(b.length-1,2+4*i)].p,lid:l[Math.min(l.length-1,2+4*i)].p}));}
function plugExit(p,s,side){const h=side?s.plugLid:s.plugBase;return add(p,s.elbow?[0,side?8:-8,h-3]:[0,0,h]);}
function cableRoute(s,d,i){
 const an=crossAnchors(s,d)[i],a=plugExit(an.base,s,0),b=lidPoint(plugExit(an.lid,s,1),s,d);
 // Deliberately schematic; no assumption of a hinge or preserved cable length.
 if(['closed','trunk'].includes(s.pose)){
  const innerY=d.D/2-17-i*5;
  return [a,[a[0],innerY,s.plugBase+s.bend*.5],[(a[0]+b[0])/2,innerY,d.G/2],[b[0],innerY,d.G-s.plugLid-s.bend*.5],b];
 }
 const normal=lidNormal([0,0,1],s),l=add(b,mul(normal,10)),mid=(a[1]+b[1])/2;
 return [a,add(a,[0,14,7]),[a[0]*.55+b[0]*.45,mid,Math.max(a[2],b[2])+28+i*8],l,b];
}
function catmull(points,steps=10){const out=[];for(let i=0;i<points.length-1;i++){const a=points[Math.max(0,i-1)],b=points[i],c=points[i+1],d=points[Math.min(points.length-1,i+2)];for(let j=0;j<steps;j++){const t=j/steps;out.push(b.map((v,k)=>.5*((2*v)+(-a[k]+c[k])*t+(2*a[k]-5*v+4*c[k]-d[k])*t*t+(-a[k]+3*v-3*c[k]+d[k])*t*t*t)));}}out.push(points[points.length-1]);return out;}
function routeBudget(s,d){const lengths=[0,1].map(i=>{const ps=catmull(cableRoute(s,d,i));return ps.slice(1).reduce((sum,p,k)=>sum+len(sub(p,ps[k])),0);});return {lengths,max:Math.max(...lengths),spare:s.lead-Math.max(...lengths),scope:'Display route only. Real lead lengths, bundle volume and unpacking sweep are not solved.'};}
// Specific F5 closure allowances, distinct from the inherited playing geometry.
function resolveGeometry(s){
 const d=baseDimensions(s);
 d.frameRearClearLid=s.lidDepth-d.t-d.frame.rearReach;
 d.frameRearClearBase=s.baseDepth-d.t-d.frame.rearReach;
 const seatInner=s.thickness+3.5,collarOuter=1.2+s.seatClearance+s.thickness,innerLip=seatInner+s.seatClearance+s.thickness;
 const closedW=d.W+2*Math.max(8,collarOuter+1),closedD=d.D+22,closedH=d.metalStack+8;
 const standSleeve=2*s.ply+4,separator=13;
 const trunkRequired=[closedW+2*s.foam,closedD+2*s.foam,closedH+2*s.foam+separator+standSleeve];
 const trunkAvailable=[s.trunkW,s.trunkD,s.trunkH],trunkSpare=trunkAvailable.map((v,i)=>v-trunkRequired[i]);
 const profileDepth=innerLip+collarOuter;
 // Spacer storage is a reserved envelope; complex folded paths remain a coupon gate.
 const collarPacket={length:Math.max(d.W,d.D)+8,width:d.collarH+2*s.overlap+8,thickness:4*(profileDepth+2)+4,foldProven:false};
 const collarInward=innerLip,railSideGap=(d.W-d.hp*5.08)/2-collarInward;
 const panelYMax=Math.max(...d.rows.map(r=>Math.abs(r.y)+r.h/2)),railEndGap=d.D/2-panelYMax-collarInward;
 return {...d,seatInner,frameSideClearance:(d.W-d.frame.width)/2-innerLip,frameEndClearance:(d.D-d.frame.depth)/2-innerLip,closedW,closedD,closedH,collarOuter,innerLip,seatWidth:seatInner-d.t,overlap:s.overlap,seatClearance:s.seatClearance,
  floor:['packing','hinge'].includes(s.pose)?-4:s.pose==='joint'?-29:s.pose==='trunk'?-s.baseDepth-4-s.foam-5:d.floor,
  coreFloor:-s.baseDepth-4,standSleeve,separator,trunkRequired,trunkSpare,trunkFits:trunkSpare.every(v=>v>=0),collarPacket,
  rimClearance:Math.min(railSideGap,railEndGap),overStiffenerLid:d.usableLid-6,hingeHeight:15,hingeLeaf:35,hingeOpen:76,hingePitch:15,hingeBarrelAssumed:6,
  hingeCount:s.collar==='hinged'?2:0,strapWidth:25,strapClosedLoop:2*(d.D+10+d.metalStack+6.6),strapPlayLoop:0,strapMinimumBeforeOverlap:2*(d.D+10+d.metalStack+6.6),
  frontGapOccupiedByStorage:false,caseToCaseHinge:false,hingeRatingKnown:false,loadRated:false,poseIsKinematic:false,
  strapRouteLengthScope:'Geometric route before buckle, overlap, tails and adjustment. Not an order length.'};
}
function dimensions(s){
 const d=resolveGeometry(s),diagnostics=[];
 const add=(code,kind,message,value=null)=>diagnostics.push({code,kind,message,value});
 for(const [code,v,message] of [
 ['frame-lid',d.frameRearClearLid,'蓋の背板と元フレームが干渉します。PCBは短縮しません。'],
 ['frame-base',d.frameRearClearBase,'本体の背板と元フレームが干渉します。'],
 ['patch',d.excess,'入力したパッチ余裕を確保できません。'],
 ...d.trunkSpare.map((v,i)=>['trunk-'+['W','D','H'][i],v,'トランク内寸 '+['W','D','H'][i]+' が不足しています。'])])if(v<0)add(code,'nominal-conflict',message,v);
 const locator=Math.min(d.frameSideClearance,d.frameEndClearance);
 if(locator<1)add('locator','nominal-conflict','位置決め部と元フレームの余裕が1 mm未満です。',locator);
 if(d.rimClearance<.4)add('rim','nominal-conflict','位置決め部とパネル端の余裕が0.4 mm未満です。',d.rimClearance);
 if(d.playFrontClearance<.001||d.playShellClearance<.001)add('play','nominal-conflict','演奏姿勢のトレー包絡が重なります。');
 if(!s.straps)add('straps','inspection','ストラップなし：座面だけでは分離を防げません。');
 if(s.pose==='joint'&&s.jointLift>0)add('unseated','inspection','接合部を分離表示中。締結状態ではありません。',s.jointLift);
 if(s.pose==='frame'&&s.frameExplode>0)add('frame-exploded','inspection','フレーム積層は分解表示です。',s.frameExplode);
 if(s.collar==='hinged')add('hinge-fold','physical-unverified','カラー蝶番の折り畳み干渉・穴・耐荷重は未検証です。');
 add('physical','physical-unverified','実機嵌合・工具アクセス・ストラップ保持・強度・運搬・電気・温度は未検証です。');
 add('cables','physical-unverified','ケーブル曲線は模式表示です。実長と開閉時の経路は未検証です。');
 return {...d,effectiveLocatorEngagement:s.overlap-(s.pose==='joint'?s.jointLift:0),diagnostics,manufacturingApproved:false,units:'mm',upAxis:'Z',revision:'TW-01'};
}
function importConfig(c){
 if(!c||typeof c!=='object'||Array.isArray(c))throw new Error('設定はJSONオブジェクトで指定してください。');
 if(!['zudo-case-study/5','zudo-case-two-way/1'].includes(c.schema))throw new Error('F5 または TW-01 の設定ファイルを指定してください。F4は非互換です。');
 if(!c.state||typeof c.state!=='object'||Array.isArray(c.state))throw new Error('state がありません。');
 const next={};
 for(const k of Object.keys(defaults)){
  if(!Object.hasOwn(c.state,k))throw new Error('設定項目がありません: '+k);
  next[k]=c.state[k];
 }
 if(c.schema==='zudo-case-two-way/1'){
  const family=spec.families.find(p=>p.id===c.familyId);
  if(!family||family.alias!==next.preset)throw new Error('familyId と preset が一致しません。');
  if(c.units!=='mm'||c.upAxis!=='Z')throw new Error('単位は mm / Z-up が必要です。');
 }
 validate(next);dimensions(next);return next;
}
function config(s){const d=dimensions(s);return {schema:'zudo-case-two-way/1',revision:'TW-01',familyId:presets[s.preset].familyId,units:'mm',upAxis:'Z',datums:{rearDepth:'module front plane to exterior back plate',gap:'opposed module front planes',trunk:'inside usable dimensions'},state:Object.fromEntries(Object.keys(defaults).map(k=>[k,s[k]])),derived:d,manufacturingApproved:false,purchasedHardwareFitVerified:false,loadRated:false,displayOnly:true,caseToCaseHinge:false,poseIsKinematic:false,cableBudget:routeBudget(s,d)};}
root.FoldModel={presets,kits,profiles,defaults,validate,validateSpec,importConfig,dimensions,lidPoint,lidNormal,orientation,modules,crossAnchors,plugExit,cableRoute,catmull,routeBudget,config,math:{rad,add,sub,mul,dot,cross,len,norm,clamp}};
})(typeof window!=='undefined'?window:globalThis);
