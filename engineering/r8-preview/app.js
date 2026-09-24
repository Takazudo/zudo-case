/* R8 preview-only: locating lid + independent transport bands. Dimensions in mm, Z up. */
(async()=>{
'use strict';
const $=id=>document.getElementById(id),$$=q=>[...document.querySelectorAll(q)];
try {
 const bytes=Uint8Array.from(atob(window.ZUDO_SIMPLE_MODEL_GZIP),c=>c.charCodeAt(0));
 if(!window.DecompressionStream)throw new Error('内蔵データを展開できません。DecompressionStream対応ブラウザーを使用してください。');
 const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
 run(JSON.parse(await new Response(stream).text()));
} catch(error){$('loading').hidden=true;$('error').hidden=false;$('errorText').textContent=error.message;console.error(error);}

function run(family){
 const T=window.THREE;
 const state={model:'7u40',lift:0,bands:false,hideLid:false,ghost:false,colors:false,labels:false,detail:false,clearance:false,view:'iso'};
 const modelNames={'7u40':'7U / 40HP','3u60':'3U / 60HP','7u60':'7U / 60HP'};
 const palette={metal:0x15181c,guards:0x23282e,rails:0x727b86,brackets:0x969fa8,spacers:0x30353b,fasteners:0xadb5bd,feet:0x20262b,lidMetal:0x15181c,lidFrame:0x292e34,lidGasket:0x21262b,lidHardware:0x42484d,locator:0x292e34,band:0x0b0e12,bandPatch:0x232a30,clearance:0xe0ad62};
 const allMeshes=[],detailMeshes=[];let built,detailBuilt,animation=null,dirty=true,resizeNeeded=true,frames=0,notice='';
 const main=world($('mainCanvas'),false),detail=world($('detailCanvas'),true);
 const root=new T.Group(),detailRoot=new T.Group();main.scene.add(root);detail.scene.add(detailRoot);
 const weave=weaveTexture();
 const ray=new T.Raycaster(),pointer=new T.Vector2();let pointerDown=null;
 main.renderer.domElement.addEventListener('pointerdown',e=>pointerDown={x:e.clientX,y:e.clientY});
 main.renderer.domElement.addEventListener('pointerup',e=>{
  if(!pointerDown||Math.hypot(e.clientX-pointerDown.x,e.clientY-pointerDown.y)>5)return;
  const r=main.renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,main.camera);
  const hits=ray.intersectObjects(root.children,true),hit=hits.find(h=>h.object.isMesh&&h.object.userData.name&&visible(h.object));
  if(hit){$('selection').textContent=hit.object.userData.name;$('selection').hidden=false;}else $('selection').hidden=true;
 });
 function visible(obj){for(let p=obj;p;p=p.parent)if(!p.visible)return false;return true;}
 function world(el,isDetail){
  const renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.75));renderer.setClearColor(isDetail?0xe6edf4:0xedf0f3,1);renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;renderer.localClippingEnabled=true;
  renderer.domElement.setAttribute('aria-label',isDetail?'差し込み部の模式断面3D':'ケースと載せ蓋の3Dプレビュー');el.appendChild(renderer.domElement);
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(isDetail?33:35,1,.1,6000);camera.up.set(0,0,1);
  const controls=new window.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.09;controls.screenSpacePanning=true;controls.minDistance=isDetail?25:90;controls.maxDistance=isDetail?900:2400;controls.addEventListener('change',()=>dirty=true);
  scene.add(new T.HemisphereLight(0xffffff,0x708293,2.4));const key=new T.DirectionalLight(0xffffff,2.4);key.position.set(170,-280,380);scene.add(key);const fill=new T.DirectionalLight(0xe5eeff,1.5);fill.position.set(-180,180,200);scene.add(fill);
  const room=new window.RoomEnvironment(),pmrem=new T.PMREMGenerator(renderer),env=pmrem.fromScene(room,.06).texture;scene.environment=env;room.dispose();pmrem.dispose();
  return {element:el,scene,camera,renderer,controls};
 }
 function weaveTexture(){
  const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');x.fillStyle='#777777';x.fillRect(0,0,128,128);
  for(let i=0;i<128;i+=4){x.fillStyle=i%8?'#777777':'#909090';x.fillRect(i,0,2,128);x.fillStyle='#555555';x.fillRect(0,i,128,1);}
  const t=new T.CanvasTexture(c);t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(9,9);return t;
 }
 function material(role,options={}){
  const isMetal=['metal','lidMetal','rails','brackets','fasteners','lidHardware'].includes(role);
  const caseFace=['metal','lidMetal'].includes(role);
  const m=new T.MeshStandardMaterial({color:palette[role]??0x777777,roughness:caseFace?.72:isMetal?.45:.88,metalness:caseFace?.16:isMetal?.5:.01,side:T.DoubleSide});
  if(['band','bandPatch'].includes(role)){m.bumpMap=weave;m.bumpScale=.11;m.roughness=.96;}
  return m;
 }
 function add(parent,geo,pos,role,opts={}){
  const m=new T.Mesh(geo,material(role));m.position.set(...pos);m.userData={role,name:opts.name||'',context:!!opts.context,forceColor:opts.forceColor,detail:!!opts.detail};parent.add(m);(opts.detail?detailMeshes:allMeshes).push(m);
  if(opts.lines!==false){const edge=new T.LineSegments(new T.EdgesGeometry(geo,32),new T.LineBasicMaterial({color:0x2a3b4c,transparent:true,opacity:.23}));edge.userData.edge=true;m.add(edge);}return m;
 }
 function box(p,w,d,h,at,role,opts={}){return add(p,new T.BoxGeometry(w,d,h),at,role,opts);}
 function group(parent,position=[0,0,0]){const g=new T.Group();g.position.set(...position);parent.add(g);return g;}
 function reference(parent,p){
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p.positions,3));if(p.indices)g.setIndex(p.indices);if(p.normals?.length===p.positions.length)g.setAttribute('normal',new T.Float32BufferAttribute(p.normals,3));else g.computeVertexNormals();
  return add(parent,g,[0,0,0],p.category,{context:['metal','guards','lidMetal','lidFrame'].includes(p.category),name:p.name,lines:p.positions.length<45000});
 }
 function clear(parent,list){parent.traverse(o=>{if(o.isMesh||o.isLineSegments){o.geometry?.dispose();if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material?.dispose();}});parent.clear();list.length=0;}
 function roundedPath(x0,x1,y0,y1,r,asHole=false){
  const p=asHole?new T.Path():new T.Shape();
  p.moveTo(x0+r,y0);p.lineTo(x1-r,y0);p.quadraticCurveTo(x1,y0,x1,y0+r);p.lineTo(x1,y1-r);p.quadraticCurveTo(x1,y1,x1-r,y1);p.lineTo(x0+r,y1);p.quadraticCurveTo(x0,y1,x0,y1-r);p.lineTo(x0,y0+r);p.quadraticCurveTo(x0,y0,x0+r,y0);p.closePath();return p;
 }
 function makeBand(parent,axis,station,span,width=20){
  // A generic flat loop, not a dimensional model of any purchased strap/buckle.
  const th=1.4,half=span/2+.22,z0=-1.8,z1=124.2,r=.55;
  const s=roundedPath(-half-th,half+th,z0-th,z1+th,r+th);s.holes.push(roundedPath(-half,half,z0,z1,r,true));
  const g=new T.ExtrudeGeometry(s,{depth:width,bevelEnabled:false,curveSegments:10});
  const pos=g.getAttribute('position');
  for(let i=0;i<pos.count;i++){
   const q=pos.getX(i),z=pos.getY(i),b=pos.getZ(i)-width/2;
   if(axis==='x')pos.setXYZ(i,q,station+b,z);else pos.setXYZ(i,station+b,-q,z);
  }
  g.computeVertexNormals();g.computeBoundingSphere();
  add(parent,g,[0,0,0],'band',{name:'運搬用の外周バンド（模式）',lines:false});
  // An overlap area on the nylon lid skirt; no permanent attachment to the case.
  if(axis==='x'){
   box(parent,1.3,width,22,[half+th+.65,station,110],'bandPatch',{name:'バンドの重なり部（仕様未選定）',lines:false});
   for(const d of [-7,7])box(parent,.15,.4,16,[half+th+1.32,station+d,110],'band',{lines:false});
  }else{
   box(parent,width,1.3,22,[station,-half-th-.65,110],'bandPatch',{name:'バンドの重なり部（仕様未選定）',lines:false});
   for(const d of [-7,7])box(parent,.4,.15,16,[station+d,-half-th-1.32,110],'band',{lines:false});
  }
 }
 function build(){
  clear(root,allMeshes);const m=family[state.model],{meta,info}=m,[W,D,H]=meta.metalEnvelopeMm;
  const body=group(root),lid=group(root),bands=group(root),knobs=group(root);
  for(const p of m.body)reference(body,p);for(const p of m.lid)reference(lid,p);
  const bandSpan=Math.min(W,D)+2.4;
  info.strapStationsMm.forEach(st=>makeBand(bands,info.strapAxis,st,bandSpan,20));
  // Clearance is a proposal envelope, not actual modules, knobs or patch cables.
  box(knobs,meta.railLengthMm,meta.railUnitDepthMm-12,27,[0,0,89.5+13.5],'clearance',{name:'パネル2mm＋ノブ25mmの仮領域',lines:false});
  const floor=new T.Mesh(new T.PlaneGeometry(2400,2400),new T.MeshStandardMaterial({color:0xe5e9ed,roughness:1}));floor.position.z=-3.7;root.add(floor);
  const grid=new T.GridHelper(1200,60,0xc1ccd6,0xd5dde5);grid.rotation.x=Math.PI/2;grid.position.z=-3.65;grid.material.transparent=true;grid.material.opacity=.2;root.add(grid);
  const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d'),grad=ctx.createRadialGradient(64,64,15,64,64,64);grad.addColorStop(0,'rgba(25,43,62,0.24)');grad.addColorStop(1,'rgba(25,43,62,0)');ctx.fillStyle=grad;ctx.fillRect(0,0,128,128);
  const shadow=new T.Mesh(new T.PlaneGeometry(W*1.5,D*1.5),new T.MeshBasicMaterial({map:new T.CanvasTexture(c),transparent:true,depthWrite:false}));shadow.position.z=-3.6;root.add(shadow);
  built={body,lid,bands,knobs,W,D,H,info,meta,lastLift:state.lift};$('selection').hidden=true;
  buildDetail();makeMarkers();applyPose();applyLook();setView(state.view);
 }
 function buildDetail(){
  clear(detailRoot,detailMeshes);const base=group(detailRoot),lid=group(detailRoot),o={detail:true};
  // Section coordinates: outer front metal face = Y0, the interior is +Y.
  box(base,29,1.5,35,[0,.75,73.5],'metal',{...o,name:'本体の前板'});
  box(base,29,1.2,6.2,[0,-.6,89.1],'guards',o);
  box(base,29,3.7,1.2,[0,.65,91.6],'guards',o);
  box(lid,25,1.5,31.3,[0,-.45,108.35],'lidFrame',o);
  box(lid,25,6.4,2.5,[0,2,93.95],'locator',{...o,forceColor:0x58a2cd});
  box(lid,25,2,12.5,[0,4.2,86.45],'locator',{...o,forceColor:0x58a2cd});
  box(lid,25,8,1.5,[0,2.8,121.45],'lidFrame',o);
  box(lid,25,24,1.5,[0,12.9,122.95],'lidMetal',o);
  box(lid,25,1.5,.5,[0,-.45,92.45],'lidGasket',o);
  const near=1.5+family[state.model].meta.frontBackInsideClearanceMm;
  box(base,29,12.586,20.132,[0,near+6.293,79.434],'rails',{...o,name:'レールの模式包絡'});
  detailBuilt={base,lid};setDetailView();
 }
 function setDetailView(){
  const target=new T.Vector3(0,9,98+state.lift*.42),d=116+state.lift*.9;
  detail.controls.target.copy(target);detail.camera.position.copy(target).add(new T.Vector3(1.6,-1,.85).normalize().multiplyScalar(d));detail.controls.update();
 }
 function makeMarkers(){
  $('markers').innerHTML='';const points=[{id:'locF',p:[0,-built.D/2+4,88],label:'前側の差し込み',type:'locator',move:true},{id:'locB',p:[0,built.D/2-4,88],label:'奥側の差し込み',type:'locator',move:true}];
  const {strapAxis:ax,strapStationsMm:st}=built.info;st.forEach((s,i)=>points.push({id:'band'+i,p:ax==='x'?[0,s,127]:[s,0,127],label:'運搬用バンド '+(i+1),type:'band',move:false}));
  built.markers=points.map(p=>{const e=document.createElement('div');e.className='marker '+p.type;e.textContent=p.label;$('markers').append(e);return {...p,e};});
 }
 function applyPose(){
  dirty=true;const shift=(state.lift-built.lastLift)*.3;main.camera.position.z+=shift;main.controls.target.z+=shift;built.lastLift=state.lift;built.lid.position.z=state.lift;built.lid.visible=!state.hideLid;built.bands.visible=state.bands&&state.lift===0&&!state.hideLid;built.knobs.visible=state.clearance;
  detailBuilt.lid.position.z=state.lift;detailBuilt.lid.visible=!state.hideLid;sync();
 }
 function applyLook(){
  dirty=true;
  for(const mesh of [...allMeshes,...detailMeshes]){
   const {role,forceColor,detail:det}=mesh.userData;let col=forceColor??palette[role]??0x777777;
   if(state.colors&&role==='locator')col=0x489fcf;if(state.colors&&['band','bandPatch'].includes(role))col=role==='band'?0xc09359:0x9b744a;
   mesh.material.color.setHex(col);let opacity=1;
   if(role==='clearance')opacity=.2;
   else if(state.ghost&&mesh.userData.context)opacity=['metal','lidMetal'].includes(role)?.12:.2;
   mesh.material.opacity=opacity;mesh.material.transparent=opacity<1;mesh.material.depthWrite=opacity>=1;mesh.material.needsUpdate=true;
   mesh.children.forEach(c=>{if(c.userData.edge)c.material.opacity=opacity<1?.1:.23;});
  }
 }
 function sync(){
  const m=family[state.model],open=state.lift>0||state.hideLid,travel=state.bands&&!open;
  $('modelLabel').textContent=modelNames[state.model]+' · SIMPLE LID';
  $('statusText').textContent=state.hideLid?'蓋なし':travel?'運搬用バンド装着':open?'真上へ取り外す':'載せ蓋 / ロックなし';
  $('motionText').textContent=travel?'別体バンド × 2':state.hideLid?'本体とレール':`蓋 +${Math.round(state.lift)} mm`;
  $('statusDot').style.background=travel?'#b18750':open?'#6294b4':'#74876b';
  $('viewerCaption').textContent=travel?'バンドで外周を保持。ケースと蓋に固定ロックはありません。':'前後の差し込みで位置決め。蓋を横にずらす動作はありません。';
  $('lift').value=String(state.lift);$('liftValue').textContent=Math.round(state.lift)+' mm';
  $('bands').checked=state.bands;$('hideLid').checked=state.hideLid;
  $('phaseTitle').textContent=travel?'持ち出すときだけバンド':open?'バンドを外し、真上へ':'日常は載せるだけ';
  $('phaseDesc').textContent=travel?'幅20mmの汎用バンドを2本巻いた模式表示です。製品やバックルを指定したモデルではありません。':open?'蓋は天板とPA12枠が一体で外れます。ネジも、フックを外す操作も不要です。':'差し込み部は横ずれを抑えるためのものです。持ち運ぶ際はバンドで保持します。';
  $('bandBehavior').textContent=notice||'蓋を持ち上げると、バンドは外した表示へ切り替えます。';
  $('dimensions').textContent=m.meta.metalEnvelopeMm.map(v=>v.toFixed(1).replace('.0','')).join(' × ')+' mm / 本体アルミ W × D × H';
  $('bandAxisText').textContent=m.info.strapAxis==='x'?'幅方向を一周':'前後方向を一周';
  $('bandLength').textContent='矩形外形からの一周概算：約'+Math.round(m.info.strapLoopGeometricEstimateMm/10)+'cm。バンド全長の指定ではありません。留め具や重なりに必要な長さは別途。';
  $('play').textContent=animation?'Ⅱ 一時停止':state.lift>=149?'◀ 載せる動きを再生':'▶ 外す動きを再生';
  $$('[data-preset]').forEach(b=>{const active=b.dataset.preset===(travel?'travel':open?'open':'daily');b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));});
  $$('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===state.view));
 }
 function setView(v){
  state.view=v;const {W,D}=built,target=new T.Vector3(0,0,65+state.lift*.3),size=Math.max(W,D,230),aspect=main.element.clientWidth/Math.max(1,main.element.clientHeight);
  let distance=size/(2*Math.tan(main.camera.fov*Math.PI/360))*1.40;if(aspect<1)distance/=Math.max(.6,aspect);
  const direction={iso:[1,-1.27,1.05],front:[0,-1,.25],back:[.35,1,.5],top:[.001,-.001,1],bottom:[.15,-.25,-1]}[v]||[1,-1.27,1.05];
  main.controls.target.copy(target);main.camera.position.copy(target).add(new T.Vector3(...direction).normalize().multiplyScalar(distance));main.controls.update();dirty=true;sync();
 }
 function setLift(value,instant=false){
  if(state.bands&&value>0){state.bands=false;notice='バンドを取り外した状態に切り替えました。';}state.hideLid=false;
  if(instant){animation=null;state.lift=value;applyPose();setDetailView();}else {animation={from:state.lift,to:value,start:performance.now(),duration:1800};sync();}
 }
 function preset(name,instant=false){
  notice='';animation=null;
  if(name==='travel'){state.lift=0;state.hideLid=false;state.bands=true;applyPose();}
  else {state.bands=false;state.hideLid=false;setLift(name==='open'?110:0,instant);}
  setDetailView();if(instant)setView(state.view);sync();
 }
 function toggleDetail(on){state.detail=on;$('detailCheck').checked=on;$('inset').hidden=!on;$('viewer').classList.toggle('has-detail',on);resizeNeeded=true;dirty=true;setDetailView();}
 function changeModel(key){animation=null;notice='';state.model=key;$('model').value=key;build();resizeNeeded=true;}
 function resize(){for(const w of [main,detail]){const x=w.element.clientWidth,y=w.element.clientHeight;if(x&&y){w.renderer.setSize(x,y,false);w.camera.aspect=x/y;w.camera.updateProjectionMatrix();}}resizeNeeded=false;dirty=true;}
 function markers(){
  const r=main.element.getBoundingClientRect();for(const m of built.markers){
   const show=state.labels&&(m.type==='band'?built.bands.visible:!state.hideLid&&(state.lift>8||state.ghost));
   m.e.style.display=show?'block':'none';if(!show)continue;
   const p=new T.Vector3(...m.p);if(m.move)p.z+=state.lift;p.project(main.camera);
   if(p.z<0||p.z>1||Math.abs(p.x)>1.05||Math.abs(p.y)>1.05){m.e.style.display='none';continue;}
   m.e.style.left=((p.x+1)*.5*r.width)+'px';m.e.style.top=((-p.y+1)*.5*r.height-6)+'px';
  }
 }
 function tick(){requestAnimationFrame(tick);if(resizeNeeded)resize();
  if(animation){const t=Math.min((performance.now()-animation.start)/animation.duration,1),e=.5-.5*Math.cos(Math.PI*t);state.lift=animation.from+(animation.to-animation.from)*e;const done=t>=1;if(done){state.lift=animation.to;animation=null;}applyPose();setDetailView();}
  main.controls.update();if(state.detail)detail.controls.update();if(dirty){main.renderer.render(main.scene,main.camera);if(state.detail)detail.renderer.render(detail.scene,detail.camera);markers();frames++;dirty=false;}
 }
 $('model').onchange=e=>changeModel(e.target.value);
 $$('[data-preset]').forEach(b=>b.onclick=()=>preset(b.dataset.preset));
 $('lift').oninput=e=>setLift(Number(e.target.value),true);
 $('play').onclick=()=>{if(animation){animation=null;sync();}else setLift(state.lift>=149?0:150);};
 $('closeLid').onclick=()=>preset('daily');
 $('bands').onchange=e=>{if(e.target.checked)preset('travel',true);else {state.bands=false;notice='';applyPose();}};
 $('hideLid').onchange=e=>{animation=null;state.hideLid=e.target.checked;if(state.hideLid)state.bands=false;applyPose();};
 $('ghost').onchange=e=>{state.ghost=e.target.checked;applyLook();};$('colors').onchange=e=>{state.colors=e.target.checked;applyLook();};$('labels').onchange=e=>{state.labels=e.target.checked;dirty=true;};
 $('clearance').onchange=e=>{state.clearance=e.target.checked;applyPose();applyLook();};
 $('detailCheck').onchange=e=>toggleDetail(e.target.checked);$('closeDetail').onclick=()=>toggleDetail(false);
 $$('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
 $('saveImage').onclick=()=>{main.renderer.render(main.scene,main.camera);const a=document.createElement('a');a.href=main.renderer.domElement.toDataURL('image/png');a.download=`zudo-${state.model}-simple-lid-${state.bands?'travel':'daily'}.png`;a.click();};
 $('resetAll').onclick=()=>{Object.assign(state,{lift:0,bands:false,hideLid:false,ghost:false,colors:false,labels:false,detail:false,clearance:false,view:'iso'});['ghost','colors','labels','clearance','hideLid'].forEach(id=>$(id).checked=false);toggleDetail(false);notice='';animation=null;build();};
 const ro=new ResizeObserver(()=>resizeNeeded=true);ro.observe(main.element);ro.observe(detail.element);window.addEventListener('resize',()=>resizeNeeded=true);
 build();resize();setView('iso');$('loading').hidden=true;requestAnimationFrame(tick);
 window.__simpleLid={state,main,detail,family,setModel:changeModel,setPreset:(s)=>preset(s,true),setLift:n=>setLift(n,true),setView,setDetail:toggleDetail,
  setLook:(ghost,colors)=>{state.ghost=ghost;state.colors=colors;$('ghost').checked=ghost;$('colors').checked=colors;applyLook();},
  stats:()=>({state:{...state},meshes:allMeshes.length,frames,pose:built.lid.position.toArray(),bandsVisible:built.bands.visible,bandLoops:built.info.strapStationsMm.length,locks:0,bodySize:built.meta.metalEnvelopeMm,detailVisible:state.detail,sourceRevision:built.meta.revision})};
}
})();
