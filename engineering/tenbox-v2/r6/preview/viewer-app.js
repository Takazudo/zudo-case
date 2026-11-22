(async () => {
  'use strict';
  const root = document.getElementById('tenbox-v2-r6');
  const $ = id => root.querySelector('[data-id="' + id + '"]');
  try {
    const bytes = Uint8Array.from(atob($('model').textContent.trim()), c => c.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const DATA = await new Response(stream).json();
    const state = {view:'assembly', explode:0, lidLift:0, lidVisible:false, rails:true, brackets:true, endwalls:true, stand:false, color:true, xray:false, section:false, ortho:true, selected:null, only:null};
    const views = {
      assembly: {title:'10BOX v2 · R6 assembly', detail:'Combined centre rail · 2 mm rail rise for hardware clearance · added side fixings', target:[0,0,38], yaw:.69, pitch:.72, span:480},
      'rail-junction': {title:'1 · One shared double rail', detail:'Native 60HP double rail · unchanged aluminium frames · assembly raised 2 mm.', target:[150,0,61], yaw:.72, pitch:.64, span:83, close:true},
      'side-fixings': {title:'2 · Side-panel supports and L brackets', detail:'Front / back panels and rails are hidden to reveal both floor levels.', target:[0,0,25], yaw:1.1, pitch:.90, span:450},
      'side-fixing': {title:'L-shaped bracket · floor / side connection', detail:'Actual revised side wall and floor geometry, with the metal bracket at its fastening position.', target:[157,-114.4079,49], yaw:-.72, pitch:.55, span:73, close:true},
      side: {title:'3 · Side-panel screw holes', detail:'Added L-bracket slots align with the existing floor fixing positions.', target:[166,0,36], yaw:Math.PI/2, pitch:0, span:350},
      underside: {title:'Underside · relocated support ledges', detail:'The former corner supports are removed; the new supports sit along the straight floor edges.', target:[0,0,28], yaw:.69, pitch:-.8, span:470},
      'lid-fit': {title:'Lift-off lid and revised body', detail:'Use the lid-lift slider to inspect how the existing lid fits above the R6 body.', target:[0,0,55], yaw:.69, pitch:.55, span:500},
      original: {title:'Before · R5 reference', detail:'Previous side-panel support geometry and separate centre rails.', target:[0,0,38], yaw:.69, pitch:.72, span:480}
    };
    const fullViews = ['assembly','side-fixings','underside','lid-fit','original'];
    let activeParts=[], buffers=new Map(), matrix, eye, right, up, forward;
    let cam={target:[0,0,38],yaw:.69,pitch:.72,span:480,up:'z'}, dirty=true, frameNumber=0;
    const canvas=$('canvas');
    let gl;try{gl=new URLSearchParams(location.search).get('renderer')==='canvas'?null:canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:true})}catch(e){gl=null}
    const ctx=gl?null:canvas.getContext('2d');
    if(!gl&&!ctx)throw Error('No supported rendering context');

    __ENGINE_CORE__

    function identity(p){return p.sourceId||p.id||''}
    function isBracket(p){return p.cat==='brackets'||p.group==='brackets'}
    function offset(p) {
      let o=[0,0,0];
      if(!views[state.view].close&&state.view!=='side')o=(p.explode||[0,0,0]).map(x=>x*state.explode);
      if(p.group==='lid')o[2]+=state.lidLift;
      return o.map((v,i)=>v+(p.staticOffset?.[i]||0));
    }
    function shown(p) {
      if(state.only&&p.id!==state.only)return false;
      const id=identity(p);
      if(state.view==='side')return id==='body-right';
      if(p.group==='lid'&&!state.lidVisible)return false;
      if(['rails','mounts'].includes(p.group)&&!state.rails)return false;
      if((isBracket(p)||p.attachmentGroup==='brackets')&&!state.brackets)return false;
      if(['body-front','body-back'].includes(id)&&!state.endwalls)return false;
      if(p.group==='stand'&&!state.stand)return false;
      return true;
    }
    function color(p) {
      const id=identity(p);let c;
      if(isBracket(p)||['hardware','washers'].includes(p.cat))c=[.21,.25,.27];
      else if(p.cat==='spacers')c=[.78,.57,.25];
      else if(p.group==='rails'||p.cat==='railPCB')c=p.cat==='railPCB'?[.38,.43,.43]:[.16,.20,.21];
      else if(p.group==='stand')c=[.43,.50,.48];
      else if(p.group==='lid')c=p.cat==='lidRoof'?[.72,.78,.71]:[.53,.64,.59];
      else if(id.includes('left')||id.includes('right'))c=[.77,.83,.78];
      else if(id.includes('bottom'))c=id.includes('front')?[.82,.60,.34]:[.72,.49,.28];
      else c=[.24,.50,.47];
      if(!state.color&&!['rails','brackets'].includes(p.group))c=p.group==='stand'?[.19,.23,.23]:[.17,.21,.21];
      if(p.id===state.selected)c=[.32,.71,.62];
      return c;
    }
    function positionPins(){}
    function updateScale(){
      const px=canvas.clientHeight/cam.span, vals=[1,2,5,10,20,50,100,200];
      const mm=vals.reduce((a,b)=>Math.abs(b*px-65)<Math.abs(a*px-65)?b:a);
      $('scale').style.width=(mm*px)+'px';$('scale').textContent=mm+' mm';
    }

    __ENGINE_RENDER__

    function allParts(){return state.view==='original'?DATA.baselineParts:DATA.parts}
    function chooseScene(){
      activeParts=DATA.jointScenes?.[state.view]||allParts();
      if(state.view==='side')activeParts=activeParts.filter(p=>identity(p)==='body-right');
      if(state.view==='underside')activeParts=activeParts.filter(p=>p.group==='body'||isBracket(p));
      if(state.view==='side-fixings')activeParts=activeParts.filter(p=>p.group==='body'||isBracket(p));
      if(state.view==='rail-junction'&&!DATA.jointScenes?.[state.view])activeParts=activeParts.filter(p=>['rails','mounts'].includes(p.group));
      if(state.view==='side-fixing'&&!DATA.jointScenes?.[state.view])activeParts=activeParts.filter(p=>['body-right','body-bottom-front','body-bottom-back'].includes(identity(p))||isBracket(p));
      for(const p of activeParts)createBuf(p.mesh);
      renderUI();dirty=true;
    }
    function renderUI(){
      const v=views[state.view];
      root.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
      $('stageTitle').textContent=v.title;$('stageDetail').textContent=v.detail;
      $('explode').value=state.explode;$('explodeValue').textContent=Number(state.explode).toFixed(state.explode%1?1:0)+' mm';
      for(const [id,key]of[['rails','rails'],['brackets','brackets'],['endwalls','endwalls'],['lid','lidVisible'],['stand','stand'],['xray','xray']])$(id).checked=state[key];
      $('lidControl').classList.toggle('tb-hidden',!state.lidVisible);$('lidlift').value=state.lidLift;$('lidValue').textContent=state.lidLift+' mm';
      $('color').setAttribute('aria-pressed',String(state.color));$('black').setAttribute('aria-pressed',String(!state.color));
      for(const id of ['explode','assembled','separate'])$(id).disabled=Boolean(v.close||state.view==='side');
      for(const id of ['rails','brackets','endwalls','lid','stand'])$(id).disabled=state.view==='side';
      $('bodyWidth').textContent=(DATA.dimensions?.body_width_mm||337.4)+' mm';
      $('frameGap').textContent=(DATA.mountParameters?.frame_to_side_inner_face_gap_mm||8)+' mm';
      $('centralRail').textContent=state.view==='original'?'Two singles':'Combined double';
      $('railRise').textContent=state.view==='original'?'0 mm':((DATA.mountParameters?.rail_panel_plane_z_mm||74)-72)+' mm';
      $('sideSlots').textContent=state.view==='original'?'Not present':(DATA.previewMetadata?.sideSlotsPerSide||4)+' per side';
      $('bracketCount').textContent=activeParts.filter(shown).filter(isBracket).length;
      $('part').replaceChildren(new Option('Whole assembly',''));
      activeParts.filter(p=>p.selectable!==false).forEach(p=>$('part').append(new Option(p.name||p.id,p.id)));
      $('part').value=state.only||'';
      const p=activeParts.find(p=>p.id===state.selected||p.id===state.only),box=$('inspector');box.replaceChildren();
      const strong=document.createElement('strong');strong.textContent=p?(p.name||p.id):(state.view==='original'?'Previous R5':'R6 case');box.append(strong);
      if(p){box.append(document.createTextNode(p.box.slice(0,3).map((n,i)=>(p.box[i+3]-n).toFixed(1)).join(' × ')+' mm'));if(p.note)box.append(document.createElement('br'),document.createTextNode(p.note))}
      else box.append(document.createTextNode('Drag to orbit; click a part or use the selector to inspect its geometry. Toggle panels to reveal the fastenings.'));
      $('partcount').textContent=(state.view==='original'?'R5 reference':'R6 review')+' · '+activeParts.filter(shown).length+' visible parts';
    }
    function boundsOfShown(){
      let lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
      for(const p of activeParts.filter(shown)){const off=offset(p);for(let k=0;k<3;k++){lo[k]=Math.min(lo[k],p.box[k]+off[k]);hi[k]=Math.max(hi[k],p.box[k+3]+off[k])}}
      return {lo,hi};
    }
    function fitCamera(){
      const {lo,hi}=boundsOfShown();if(!Number.isFinite(lo[0]))return;
      cam.target=lo.map((x,i)=>(x+hi[i])/2);updateCamera();const xx=[],yy=[];
      for(const a of[lo[0],hi[0]])for(const b of[lo[1],hi[1]])for(const c of[lo[2],hi[2]]){const p=V.sub([a,b,c],cam.target);xx.push(V.dot(p,right));yy.push(V.dot(p,up))}
      const aspect=canvas.clientWidth/canvas.clientHeight;
      cam.span=Math.max(Math.max(...yy)-Math.min(...yy),(Math.max(...xx)-Math.min(...xx))/aspect)*1.28;cam.span=Math.max(cam.span,30);dirty=true;
    }
    function setView(view){
      if(!views[view])return;
      state.view=view;state.selected=null;state.only=null;state.explode=0;state.lidLift=0;
      state.lidVisible=view==='lid-fit';state.rails=!['side-fixings','side-fixing','side','underside'].includes(view);state.endwalls=!['side-fixings','side-fixing'].includes(view);state.brackets=true;state.xray=false;
      const v=views[view];cam={target:[...v.target],yaw:v.yaw,pitch:v.pitch,span:v.span,up:'z'};
      chooseScene();if(!v.close||DATA.jointScenes?.[view])fitCamera();
    }
    function setCamera(kind){
      if(kind==='iso'){cam.yaw=.69;cam.pitch=.72}if(kind==='front'){cam.yaw=0;cam.pitch=0}if(kind==='side'){cam.yaw=Math.PI/2;cam.pitch=0}if(kind==='top'){cam.yaw=0;cam.pitch=1.5706}if(kind==='bottom'){cam.yaw=.45;cam.pitch=-1.0}
      if(!views[state.view].close||DATA.jointScenes?.[state.view])fitCamera();dirty=true;
    }
    function pan(dx,dy){updateCamera();const s=cam.span/canvas.clientHeight;cam.target=V.add(cam.target,V.add(V.mul(right,-dx*s),V.mul(up,dy*s)));dirty=true}
    function rayBox(o,d,b){let t0=-Infinity,t1=Infinity;for(let k=0;k<3;k++){if(Math.abs(d[k])<1e-12){if(o[k]<b[k]||o[k]>b[k+3])return false}else{let a=(b[k]-o[k])/d[k],z=(b[k+3]-o[k])/d[k];if(a>z)[a,z]=[z,a];t0=Math.max(t0,a);t1=Math.min(t1,z);if(t1<t0)return false}}return t1>0}
    function rayTri(o,d,a,b,c){const e1=V.sub(b,a),e2=V.sub(c,a),h=V.cross(d,e2),det=V.dot(e1,h);if(Math.abs(det)<1e-10)return null;const inv=1/det,s=V.sub(o,a),u=inv*V.dot(s,h);if(u<0||u>1)return null;const q=V.cross(s,e1),v=inv*V.dot(d,q);if(v<0||u+v>1)return null;const t=inv*V.dot(e2,q);return t>0?t:null}
    function pick(cx,cy){
      updateCamera();const r=canvas.getBoundingClientRect(),x=(cx-r.left)/r.width*2-1,y=1-(cy-r.top)/r.height*2;
      const o=V.add(eye,V.add(V.mul(right,x*cam.span*r.width/r.height/2),V.mul(up,y*cam.span/2))),d=forward;let best=Infinity,found=null;
      for(const p of activeParts.filter(shown)){const oo=V.sub(o,offset(p));if(!rayBox(oo,d,p.box))continue;const {p:pts,i:ind}=DATA.meshes[p.mesh];for(let k=0;k<ind.length;k+=3){const t=rayTri(oo,d,pts.slice(ind[k]*3,ind[k]*3+3),pts.slice(ind[k+1]*3,ind[k+1]*3+3),pts.slice(ind[k+2]*3,ind[k+2]*3+3));if(t!==null&&t<best){best=t;found=p}}}
      state.selected=found?.id||null;renderUI();dirty=true;
    }
    let drag=null,lastPinch=null;const pointers=new Map();
    canvas.addEventListener('contextmenu',e=>e.preventDefault());
    canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);drag={x:e.clientX,y:e.clientY,total:0,pan:e.button===2||e.shiftKey};if(pointers.size===2){const p=[...pointers.values()];lastPinch={d:Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]),m:[(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2]}}});
    canvas.addEventListener('pointermove',e=>{
      if(!pointers.has(e.pointerId)||!drag)return;pointers.set(e.pointerId,[e.clientX,e.clientY]);
      if(pointers.size===2){const p=[...pointers.values()],d=Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]),m=[(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2];if(lastPinch){cam.span=Math.max(5,Math.min(2000,cam.span*lastPinch.d/Math.max(1,d)));pan(m[0]-lastPinch.m[0],m[1]-lastPinch.m[1])}lastPinch={d,m};drag.total+=10;dirty=true;return}
      const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;drag.total+=Math.abs(dx)+Math.abs(dy);if(drag.pan)pan(dx,dy);else{cam.yaw-=dx*.008;cam.pitch=Math.max(-1.55,Math.min(1.55,cam.pitch+dy*.007))}dirty=true;
    });
    canvas.addEventListener('pointerup',e=>{pointers.delete(e.pointerId);if(drag&&drag.total<5&&e.button===0)pick(e.clientX,e.clientY);if(!pointers.size)drag=null;else if(pointers.size===1&&drag){const p=[...pointers.values()][0];drag.x=p[0];drag.y=p[1];drag.total=Math.max(drag.total,5)}lastPinch=null});
    canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);drag=null;lastPinch=null});
    canvas.addEventListener('wheel',e=>{e.preventDefault();cam.span=Math.max(5,Math.min(2000,cam.span*Math.exp(e.deltaY*.001)));dirty=true},{passive:false});
    root.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
    root.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>setCamera(b.dataset.camera)));
    $('explode').addEventListener('input',e=>{state.explode=Number(e.target.value);renderUI();fitCamera();dirty=true});
    $('assembled').onclick=()=>{state.explode=0;renderUI();dirty=true};$('separate').onclick=()=>{state.explode=25;renderUI();fitCamera()};$('fit').onclick=()=>fitCamera();
    $('full').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('stage').requestFullscreen()}catch{fitCamera()}};
    for(const [id,key]of[['rails','rails'],['brackets','brackets'],['endwalls','endwalls'],['lid','lidVisible'],['stand','stand'],['xray','xray']])$(id).onchange=e=>{state[key]=e.target.checked;if(id!=='xray'){state.only=null;state.selected=null}renderUI();if(id!=='xray'&&!views[state.view].close)fitCamera();dirty=true};
    $('lidlift').oninput=e=>{state.lidLift=Number(e.target.value);renderUI();fitCamera();dirty=true};
    $('color').onclick=()=>{state.color=true;renderUI();dirty=true};$('black').onclick=()=>{state.color=false;renderUI();dirty=true};
    $('part').onchange=e=>{state.only=e.target.value||null;state.selected=state.only;if(state.only){const p=activeParts.find(p=>p.id===state.only);if(p?.group==='lid')state.lidVisible=true;if(['rails','mounts'].includes(p?.group))state.rails=true;if(isBracket(p||{})||p?.attachmentGroup==='brackets')state.brackets=true;if(['body-front','body-back'].includes(identity(p||{})))state.endwalls=true;if(p?.group==='stand')state.stand=true}renderUI();fitCamera()};
    $('renderer').textContent=gl?'Interactive 3D':'Interactive 3D · software renderer';
    new ResizeObserver(()=>{if(!views[state.view].close||DATA.jointScenes?.[state.view])fitCamera();dirty=true}).observe($('stage'));
    document.addEventListener('fullscreenchange',()=>{if(!views[state.view].close||DATA.jointScenes?.[state.view])fitCamera();dirty=true});
    setView('assembly');render();$('loading').classList.add('tb-hidden');root.dataset.ready='true';
    let stopped=false;function tick(){if(stopped)return;if(!root.isConnected){stopped=true;return}render();requestAnimationFrame(tick)}requestAnimationFrame(tick);
    window.tenboxStudy={state,DATA,setView,setCamera,fit:fitCamera,render,visibleParts:()=>activeParts.filter(shown),partOffset:offset,get camera(){return cam},get frames(){return frameNumber},get renderer(){return gl?'webgl':'canvas'},get parts(){return activeParts}};
  }catch(e){$('loading').textContent='The 3D model could not start: '+e.message;root.dataset.error=e.message;console.error(e)}
})();
