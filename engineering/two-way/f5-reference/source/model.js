/* ZUDO CASE F5 — seated closure / protected trunk. Millimetres. Layout study, not manufacturing CAD. */
(function(root){
'use strict';
const rad=d=>d*Math.PI/180,add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,k)=>a.map(v=>v*k),dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],len=a=>Math.hypot(...a),norm=a=>mul(a,1/(len(a)||1)),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const presets={
 compact:{id:'compact',letter:'A',name:'Compact',short:'6U · 60HP',layout:3,hp:60,baseDepth:80,lidDepth:48},
 performance:{id:'performance',letter:'B',name:'Performance',short:'12U · 60HP',layout:6,hp:60,baseDepth:80,lidDepth:48},
 twin40:{id:'twin40',letter:'C',name:'Twin 7U',short:'14U · 40HP',layout:7,hp:40,baseDepth:91.5,lidDepth:70}
};
const kits={tilted:{id:'tilted',number:'04',name:'Seated collar + 45°',tag:'Trunk-carried instrument'}};
const profiles={
 straight:{name:'Straight plug study · 72 mm',gap:72,plugBase:28,plugLid:28,bend:4,knobBase:25,knobLid:25,elbow:false,note:'28 mm plug projection plus 4 mm exit allowance per side are assumptions. Measure your real cables; 72 mm is not a proven patch clearance.'},
 elbow:{name:'Low-profile elbow study · 58 mm',gap:58,plugBase:12,plugLid:12,bend:5,knobBase:25,knobLid:25,elbow:true,note:'Tendrils specifies 12 mm height when patched. With these inputs, the assumed 25 mm knobs determine the gap. Dense bundles and taller controls still require measurement.'}
};
const defaults={preset:'performance',kit:'tilted',profile:'straight',gap:72,baseDepth:80,lidDepth:48,thickness:1.5,ply:8,plugBase:28,plugLid:28,bend:4,knobBase:25,knobLid:25,margin:8,elbow:false,pose:'frame',patch:true,cross:true,envelopes:false,cutaway:false,modules:true,structure:false,labels:true,finish:'graphite',view:'iso',highlight:false,deskGap:70,lead:600,collar:'loose',straps:true,overlap:6,seatClearance:.6,jointLift:0,hingeAngle:90,foam:20,trunkW:420,trunkD:420,trunkH:330,frameExplode:0};
function validate(s){
 if(!presets[s.preset]||s.kit!=='tilted'||!profiles[s.profile])throw new Error('Unknown F5 family or plug study.');
 for(const [k,a,b] of [['gap',48,110],['baseDepth',60,110],['lidDepth',38,90],['thickness',1.5,2.5],['ply',6,10],['plugBase',8,60],['plugLid',8,60],['bend',2,20],['knobBase',10,40],['knobLid',10,40],['margin',4,20],['deskGap',24,160],['lead',200,1200],['overlap',4,10],['seatClearance',.25,1.2],['frameExplode',0,18],['jointLift',0,30],['hingeAngle',0,180],['foam',10,40],['trunkW',250,700],['trunkD',200,700],['trunkH',180,500]])if(!Number.isFinite(s[k])||s[k]<a||s[k]>b)throw new Error('Invalid '+k);
 for(const k of ['elbow','patch','cross','envelopes','cutaway','modules','structure','labels','highlight','straps'])if(typeof s[k]!=='boolean')throw new Error('Invalid '+k);
 if(!['frame','closed','play','parts','packing','joint','trunk','hinge'].includes(s.pose)||!['loose','hinged'].includes(s.collar)||!['graphite','silver','olive'].includes(s.finish)||!['iso','side','front','top','back'].includes(s.view))throw new Error('Invalid display state.');return s;
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
 // In kit 03 the wrap and stand alternate in the SAME pocket, never share the patch cavity.
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
 if(s.pose==='play'&&s.kit==='pedestal')zc+=d.collarH+1;
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
function dimensions(s){
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
function config(s){const d=dimensions(s);return {schema:'zudo-case-study/5',state:{...s},derived:d,manufacturingApproved:false,hingeDrawingIdentified:true,purchasedHardwareFitVerified:false,loadRated:false,allPartsAccountedInNominalPacking:true,packingScope:'Closed instrument + separate stand sleeve. No power brick, extra cables or specific trunk fit verified. Collar bundle is a conservative reservation, not a folding proof.',displayOnly:true,cableBudget:routeBudget(s,d),note:'Two independent loaded trays. Purchased hinges are optional spacer-panel keep-together joints only. No loaded-lid hinge or strength claim. Fitted trunk is required for intended transport.'};}
root.FoldModel={presets,kits,profiles,defaults,validate,dimensions,lidPoint,lidNormal,orientation,modules,crossAnchors,plugExit,cableRoute,catmull,routeBudget,config,math:{rad,add,sub,mul,dot,cross,len,norm,clamp}};
})(typeof window!=='undefined'?window:globalThis);
