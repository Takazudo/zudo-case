(async () => {
  'use strict';
  const root = document.getElementById('tenbox-v2-r5');
  const $ = id => root.querySelector('[data-id="' + id + '"]');
  try {
    const bytes = Uint8Array.from(atob($('model').textContent.trim()), c => c.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const DATA = await new Response(stream).json();
    const state = {view:'floor-fit', explode:0, lidLift:0, lidVisible:false, rails:true, stand:false, color:true, xray:false, section:false, ortho:true, selected:null, only:null};
    const views = {
      'floor-fit': {title:'H2D · clipped floor, printed flat', detail:'45° diagonal · 5 mm high · left nozzle only · unsliced', target:[175,160,0], yaw:0, pitch:1.5706, span:390},
      'floor-top': {title:'One common floor · print twice', detail:'12 / 16 mm corner cuts · nine slots and four tabs retained', target:[0,72.49716,2.5], yaw:0, pitch:1.5706, span:400},
      underside: {title:'Clipped corners in the assembled case', detail:'Small triangular corner openings · original tabs and fixing positions retained', target:[0,0,30], yaw:.69, pitch:-.8, span:510},
      assembly: {title:'Revised assembly', detail:'337.4 mm wide · 8 mm spacers · unchanged 60HP frames', target:[0,0,38], yaw:.69, pitch:.72, span:510},
      insert: {title:'Slide the side panels into place', detail:'Only the side panels move. Front, back and both bottoms locate together along X.', target:[0,0,38], yaw:.69, pitch:.72, span:545},
      side: {title:'Side panel · four round screw holes', detail:'2 screws per frame × 2 rows · Ø5.5 mm · 3 mm-wide vents', target:[166.2,0,36], yaw:Math.PI/2, pitch:0, span:365},
      back: {title:'Back panel · new vents and bracket slots', detail:'25 vents · 3 × 32 mm, R0.5 · five 5.5 × 10.5 mm bracket slots', target:[0,147.5,36], yaw:Math.PI, pitch:0, span:365},
      'rail-gap': {title:'8 mm frame-to-panel gap', detail:'Actual frame contour and 8 mm spacer · cropped at the front mounting point', target:[160,-114,63], yaw:.45, pitch:.45, span:47},
      'lid-fit': {title:'Flat-print roof · 5 mm side extensions', detail:'317 × 290 mm roof · 337.4 mm lid assembly · eight roof fixings', target:[0,0,56], yaw:.69, pitch:.55, span:510},
      'lid-top': {title:'One continuous roof panel', detail:'317 × 290 × 5 mm · one nozzle · flat on the build plate', target:[0,0,110.5], yaw:0, pitch:1.5706, span:390},
      'lid-ledge': {title:'Side extension and roof support', detail:'5 mm inward × 5 mm thick · 0.2 mm seam · 2.8 mm bearing', target:[158,0,106], yaw:.28, pitch:.23, span:42},
      'lid-end': {title:'Lid front / back · two fixings each', detail:'Centre bracket holes removed · support ledges and lower locating tongue retained', target:[0,-147.5,92.5], yaw:0, pitch:0, span:390},
      h2d: {title:'H2D · flat roof, one nozzle', detail:'317 × 290 × 5 mm · left nozzle 325 × 320 mm · unsliced', target:[175,160,0], yaw:0, pitch:1.5706, span:390},
      'front-joint': {title:'Front wall → side panel', detail:'One 12 × 5 mm tab per end of the 36 mm-high front wall. 0.20 mm clearance per face.', target:[159,-146,53], yaw:1.03, pitch:.38, span:59},
      'floor-joint': {title:'Bottom → side panel', detail:'20 × 5 mm integral tab; 4.7 mm insertion. Closed receiver with a lower support land.', target:[159,95,4], yaw:1.0, pitch:.40, span:53},
      original: {title:'Previous R4 floor · uncut corners', detail:'Before trimming · this original floor does not fit flat', target:[0,72.49716,2.5], yaw:0, pitch:1.5706, span:400}
    };
    const fullViews = ['assembly','insert','lid-fit'];
    let activeParts=[], buffers=new Map(), matrix, eye, right, up, forward;
    let cam={target:[0,0,38],yaw:.69,pitch:.72,span:510,up:'z'}, dirty=true, frameNumber=0;
    const canvas=$('canvas');
    let gl;try{gl=new URLSearchParams(location.search).get('renderer')==='canvas'?null:canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:true})}catch(e){gl=null}
    const ctx=gl?null:canvas.getContext('2d');
    if(!gl&&!ctx)throw Error('No supported rendering context');

    const vsrc=`attribute vec3 aP;attribute vec3 aN;uniform mat4 uMVP;uniform vec3 uOffset;varying vec3 vN;varying vec3 vP;void main(){vP=aP+uOffset;vN=aN;gl_Position=uMVP*vec4(vP,1.0);}`;
const fsrc=`precision highp float;varying vec3 vN;varying vec3 vP;uniform vec4 uColor;uniform vec3 uEye;uniform float uMetal;uniform float uSection;uniform float uCut;uniform float uLine;void main(){if(uSection>.5&&vP.x>uCut)discard;vec3 n=normalize(vN);if(!gl_FrontFacing)n=-n;vec3 light=normalize(vec3(-.5,-.55,1.0));vec3 fill=normalize(vec3(.6,.7,.5));vec3 V=normalize(uEye-vP);float diffuse=.48+.34*max(dot(n,light),0.)+.18*max(dot(n,fill),0.);float s=pow(max(dot(n,normalize(light+V)),0.),mix(15.,65.,uMetal));float rim=pow(1.-abs(dot(n,V)),3.);vec3 c=uColor.rgb*diffuse+vec3(s*mix(.06,.26,uMetal))+vec3(rim*.035);if(uLine>.5)c=uColor.rgb;gl_FragColor=vec4(c,uColor.a);}`;
function shader(type,src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
let prog,AP,AN;const U={};if(gl){prog=gl.createProgram();gl.attachShader(prog,shader(gl.VERTEX_SHADER,vsrc));gl.attachShader(prog,shader(gl.FRAGMENT_SHADER,fsrc));gl.linkProgram(prog);if(!gl.getProgramParameter(prog,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(prog));gl.useProgram(prog);
for(const k of ['MVP','Offset','Color','Eye','Metal','Section','Cut','Line'])U[k]=gl.getUniformLocation(prog,'u'+k);
AP=gl.getAttribLocation(prog,'aP');AN=gl.getAttribLocation(prog,'aN');gl.enableVertexAttribArray(AP);gl.enableVertexAttribArray(AN);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);}
const V={add:(a,b)=>a.map((x,i)=>x+b[i]),sub:(a,b)=>a.map((x,i)=>x-b[i]),mul:(a,k)=>a.map(x=>x*k),dot:(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),cross:(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm:a=>{let k=Math.hypot(...a)||1;return a.map(x=>x/k)}};
function matmul(a,b){let c=new Float32Array(16);for(let j=0;j<4;j++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)c[j*4+i]+=a[k*4+i]*b[j*4+k];return c}
function lookAt(e,t,u){const z=V.norm(V.sub(e,t)),x=V.norm(V.cross(u,z)),y=V.cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-V.dot(x,e),-V.dot(y,e),-V.dot(z,e),1])}
function ortho(l,r,b,t,n,f){return new Float32Array([2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1])}
function perspective(fovy,a,n,f){let z=1/Math.tan(fovy/2);return new Float32Array([z/a,0,0,0,0,z,0,0,0,0,(f+n)/(n-f),-1,0,0,2*f*n/(n-f),0])}
function transform4(m,p){let v=[p[0],p[1],p[2],1];return [0,1,2,3].map(i=>v.reduce((s,a,j)=>s+a*m[j*4+i],0))}
function hex(c){return '#'+c.map(x=>Math.round(x*255).toString(16).padStart(2,'0')).join('')}
function createBuf(key){if(!gl){buffers.set(key,{});return {}}if(buffers.has(key))return buffers.get(key);let m=DATA.meshes[key],p=m.p,i=m.i,n=new Float32Array(p.length),edgeMap=new Map();for(let k=0;k<i.length;k+=3){let ia=i[k],ib=i[k+1],ic=i[k+2],a=p.slice(ia*3,ia*3+3),b=p.slice(ib*3,ib*3+3),c=p.slice(ic*3,ic*3+3),normal=V.cross(V.sub(b,a),V.sub(c,a)),nn=V.norm(normal);for(let q of [ia,ib,ic])for(let d=0;d<3;d++)n[q*3+d]+=normal[d];for(let [q,r] of [[ia,ib],[ib,ic],[ic,ia]]){let aa=p.slice(q*3,q*3+3),bb=p.slice(r*3,r*3+3),sa=aa.join(','),sb=bb.join(','),ek=sa<sb?sa+'|'+sb:sb+'|'+sa;let e=edgeMap.get(ek);if(!e)edgeMap.set(ek,{aa,bb,normal:nn,sharp:false,count:1});else{e.count++;if(V.dot(e.normal,nn)<.87)e.sharp=true}}}
for(let j=0;j<n.length;j+=3){let l=Math.hypot(n[j],n[j+1],n[j+2])||1;n[j]/=l;n[j+1]/=l;n[j+2]/=l}
let lines=[];for(let e of edgeMap.values())if(e.sharp||e.count===1)lines.push(...e.aa,...e.bb);
function buf(target,data){let b=gl.createBuffer();gl.bindBuffer(target,b);gl.bufferData(target,data,gl.STATIC_DRAW);return b}
let indexType=gl.UNSIGNED_SHORT,idx;if(p.length/3>65535){if(!gl.getExtension('OES_element_index_uint'))throw Error('Index extension unavailable');idx=new Uint32Array(i);indexType=gl.UNSIGNED_INT}else idx=new Uint16Array(i);
let b={p:buf(gl.ARRAY_BUFFER,new Float32Array(p)),n:buf(gl.ARRAY_BUFFER,n),i:buf(gl.ELEMENT_ARRAY_BUFFER,idx),count:i.length,indexType,lines:buf(gl.ARRAY_BUFFER,new Float32Array(lines)),lineCount:lines.length/3};buffers.set(key,b);return b}



    function offset(p) {
      const id=p.sourceId||p.id;
      if(['side','back','rail-gap','lid-top','lid-end','lid-ledge','h2d','floor-fit','floor-top','original'].includes(state.view))return [0,0,0];
      let o=[0,0,0];
      if(state.view==='insert'||state.view.endsWith('joint')){
        if(id==='body-left')o=[-state.explode,0,0];
        if(id==='body-right')o=[state.explode,0,0];
      }else{
        const d=p.explode||[0,0,0];
        o=d.map(x=>x*state.explode);
      }
      if(p.group==='lid')o[2]+=state.lidLift;
      return o.map((v,i)=>v+(p.staticOffset?.[i]||0));
    }
    function shown(p) {
      if(state.only&&p.id!==state.only)return false;
      if(state.view==='side')return (p.sourceId||p.id)==='body-right';
      if(state.view==='back')return (p.sourceId||p.id)==='body-back';
      if(state.view==='lid-top')return (p.sourceId||p.id)==='lid-top-single';
      if(state.view==='lid-end')return (p.sourceId||p.id)==='lid-front';
      if(p.group==='lid'&&!state.lidVisible)return false;
      if(['rails','mounts'].includes(p.group)&&!state.rails)return false;
      if(p.group==='stand'&&!state.stand)return false;
      return true;
    }
    function color(p) {
      const id=p.sourceId||p.id;
      let c;
      if(p.cat==='printBed')c=[.30,.38,.38];
      else if(p.cat==='printArea')c=[.58,.66,.62];
      else if(p.cat==='printLimits')c=[.43,.60,.55];
      else if(p.cat==='printExclusion')c=[.72,.39,.27];
      else if(p.cat==='brimAllowance')c=[.75,.58,.31];
      else if(p.group==='print')c=p.cat==='floor'?[.82,.60,.34]:[.73,.79,.70];
      else if(p.cat==='spacers')c=[.78,.57,.25];
      else if(p.group==='rails'||p.cat==='railPCB')c=p.cat==='railPCB'?[.38,.43,.43]:[.16,.20,.21];
      else if(p.group==='stand')c=[.43,.50,.48];
      else if(p.group==='lid')c=p.cat==='lidRoof'?[.72,.78,.71]:[.53,.64,.59];
      else if(id.includes('left')||id.includes('right'))c=[.77,.83,.78];
      else if(id.includes('bottom'))c=id.includes('front')?[.82,.60,.34]:[.72,.49,.28];
      else c=[.24,.50,.47];
      if(!state.color&&p.group!=='rails')c=p.group==='stand'?[.19,.23,.23]:[.17,.21,.21];
      if(p.id===state.selected)c=[.32,.71,.62];
      return c;
    }
    function positionPins() {
      const active=state.view==='rail-gap'&&!state.only;
      $('gapDimension').classList.toggle('tb-hidden',!active);
      const ledge=state.view==='lid-ledge'&&!state.only;
      $('ledgeDimension').classList.toggle('tb-hidden',!ledge);
      if(!active&&!ledge)return;
      const project=p=>{const a=transform4(matrix,p);return [(a[0]/a[3]+1)*canvas.clientWidth/2,(1-a[1]/a[3])*canvas.clientHeight/2]};
      if(ledge){
        function dim(name,pa,pb,shift){
          const a=project(pa),b=project(pb),len=Math.hypot(b[0]-a[0],b[1]-a[1])||1;
          const n=[-(b[1]-a[1])/len,(b[0]-a[0])/len];
          const tick=p=>`M${p[0]-n[0]*4},${p[1]-n[1]*4}L${p[0]+n[0]*4},${p[1]+n[1]*4}`;
          $(name+'Line').setAttribute('d',`M${a[0]},${a[1]}L${b[0]},${b[1]}${tick(a)}${tick(b)}`);
          $(name+'Text').setAttribute('x',(a[0]+b[0])/2+n[0]*shift);
          $(name+'Text').setAttribute('y',(a[1]+b[1])/2+n[1]*shift);
        }
        dim('flange',[158.7,-15,115],[163.7,-15,115],-12);
        dim('thick',[170.5,-15,108],[170.5,-15,113],20);
        dim('bearing',[155.7,-15,101.5],[158.5,-15,101.5],18);
        return;
      }
      const a=project([155.7,-119.6,71.2]),b=project([163.7,-119.6,71.2]);
      const len=Math.hypot(b[0]-a[0],b[1]-a[1])||1;
      const n=[-(b[1]-a[1])/len,(b[0]-a[0])/len];
      const end=p=>`M${p[0]-n[0]*5},${p[1]-n[1]*5}L${p[0]+n[0]*5},${p[1]+n[1]*5}`;
      $('gapLine').setAttribute('d',`M${a[0]},${a[1]}L${b[0]},${b[1]}${end(a)}${end(b)}`);
      $('gapText').setAttribute('x',(a[0]+b[0])/2-n[0]*12);$('gapText').setAttribute('y',(a[1]+b[1])/2-n[1]*12);
    }
    function updateScale(){
      const px=canvas.clientHeight/cam.span, vals=[1,2,5,10,20,50,100,200];
      const mm=vals.reduce((a,b)=>Math.abs(b*px-65)<Math.abs(a*px-65)?b:a);
      $('scale').style.width=(mm*px)+'px';$('scale').textContent=mm+' mm';
    }

    function drawPart(p,transparent=false){const b=buffers.get(p.mesh);gl.bindBuffer(gl.ARRAY_BUFFER,b.p);gl.vertexAttribPointer(AP,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ARRAY_BUFFER,b.n);gl.vertexAttribPointer(AN,3,gl.FLOAT,false,0,0);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,b.i);gl.uniform3fv(U.Offset,offset(p));let c=color(p),alpha=transparent?.23:1;gl.uniform4f(U.Color,...c,alpha);gl.uniform1f(U.Metal,['hardware','brackets','railHardware'].includes(p.cat)?1:0);gl.uniform1f(U.Line,0);gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);gl.drawElements(gl.TRIANGLES,b.count,b.indexType,0);gl.disable(gl.POLYGON_OFFSET_FILL);
if((p.cat==='panels'||p.id===state.selected||!fullViews.includes(state.view))&&b.lineCount){gl.enable(gl.BLEND);gl.uniform1f(U.Line,1);let ec=p.id===state.selected?[.05,.40,.39]:[.19,.27,.29];gl.uniform4f(U.Color,...ec,transparent?.20:.16);gl.bindBuffer(gl.ARRAY_BUFFER,b.lines);gl.vertexAttribPointer(AP,3,gl.FLOAT,false,0,0);gl.disableVertexAttribArray(AN);gl.vertexAttrib3f(AN,0,0,1);gl.drawArrays(gl.LINES,0,b.lineCount);gl.enableVertexAttribArray(AN);if(!transparent)gl.disable(gl.BLEND)}}
function updateCamera(){let cp=Math.cos(cam.pitch),sp=Math.sin(cam.pitch),sy=Math.sin(cam.yaw),cy=Math.cos(cam.yaw),direction=cam.up==='z'?[cp*sy,-cp*cy,sp]:[cp*sy,sp,cp*cy];let dis=cam.span*2.6;eye=V.add(cam.target,V.mul(direction,dis));forward=V.norm(V.sub(cam.target,eye));const worldUp=cam.up==='z'?[0,0,1]:[0,1,0];right=V.norm(V.cross(forward,worldUp));up=V.cross(right,forward);let aspect=canvas.clientWidth/canvas.clientHeight;let p=state.ortho?ortho(-cam.span*aspect/2,cam.span*aspect/2,-cam.span/2,cam.span/2,.01,cam.span*15):perspective(2*Math.atan(1/5.2),aspect,.05,cam.span*15);matrix=matmul(p,lookAt(eye,cam.target,worldUp));}
function render(){if(!dirty)return;dirty=false;let dpr=Math.min(window.devicePixelRatio||1,2),w=Math.max(1,Math.round(canvas.clientWidth*dpr)),h=Math.max(1,Math.round(canvas.clientHeight*dpr));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}if(!gl){updateCamera();renderSoftware();positionPins();updateScale();frameNumber++;return}gl.viewport(0,0,w,h);gl.clearColor(.87451,.91373,.90588,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(prog);updateCamera();gl.uniformMatrix4fv(U.MVP,false,matrix);gl.uniform3fv(U.Eye,eye);gl.uniform1f(U.Section,state.section?1:0);gl.uniform1f(U.Cut,0);gl.depthMask(true);gl.disable(gl.BLEND);let parts=activeParts.filter(shown);for(let p of parts)if(!((state.xray&&['panels','floor','lidRoof'].includes(p.cat))))drawPart(p);let trans=parts.filter(p=>(state.xray&&['panels','floor','lidRoof'].includes(p.cat)));trans.sort((a,b)=>{const ct=p=>V.add([(p.box[0]+p.box[3])/2,(p.box[1]+p.box[4])/2,(p.box[2]+p.box[5])/2],offset(p));return V.dot(V.sub(ct(b),eye),forward)-V.dot(V.sub(ct(a),eye),forward)});gl.enable(gl.BLEND);gl.depthMask(false);for(let p of trans)drawPart(p,true);gl.depthMask(true);gl.disable(gl.BLEND);positionPins();updateScale();frameNumber++;}

// Offline fallback: actual mesh triangles with a CPU z-buffer. No image substitution.
const softwareCache=new Map();let softCanvas=null;
function softwareMesh(key){if(softwareCache.has(key))return softwareCache.get(key);let d=DATA.meshes[key],p=d.p,ind=d.i,tri=[];for(let k=0;k<ind.length;k+=3){let a=p.slice(ind[k]*3,ind[k]*3+3),b=p.slice(ind[k+1]*3,ind[k+1]*3+3),c=p.slice(ind[k+2]*3,ind[k+2]*3+3);tri.push({a,b,c,n:V.norm(V.cross(V.sub(b,a),V.sub(c,a)))})}softwareCache.set(key,tri);return tri}
function renderSoftware(){
 const cssW=canvas.clientWidth,cssH=canvas.clientHeight,ratio=Math.min(1.1,1100/cssW,800/cssH),w=Math.max(1,Math.round(cssW*ratio)),h=Math.max(1,Math.round(cssH*ratio));
 if(!softCanvas)softCanvas=document.createElement('canvas');softCanvas.width=w;softCanvas.height=h;let sc=softCanvas.getContext('2d'),img=sc.createImageData(w,h),rgba=img.data,zbuf=new Float32Array(w*h);zbuf.fill(Infinity);for(let k=0;k<rgba.length;k+=4){rgba[k]=223;rgba[k+1]=233;rgba[k+2]=231;rgba[k+3]=255}
 const light=V.norm([-.5,-.55,1]),fill=V.norm([.6,.7,.5]),opaque=[],transparent=[];
 function clipX(poly){if(!state.section)return poly;let result=[];for(let j=0;j<poly.length;j++){let a=poly[j],b=poly[(j+1)%poly.length],ain=a[0]<=0,bin=b[0]<=0;if(ain)result.push(a);if(ain!==bin){let t=-a[0]/(b[0]-a[0]);result.push(a.map((v,k)=>v+(b[k]-v)*t))}}return result}
 function proj(p){let a=transform4(matrix,p);return[(a[0]/a[3]+1)*w/2,(1-a[1]/a[3])*h/2,a[2]/a[3]]}
 for(let part of activeParts){if(!shown(part))continue;let off=offset(part),base=color(part),alpha=((state.xray&&['panels','floor','lidRoof'].includes(part.cat)))?.20:1,metal=['hardware','brackets','railHardware'].includes(part.cat)?1:0;
 for(let t of softwareMesh(part.mesh)){let a=V.add(t.a,off),b=V.add(t.b,off),c=V.add(t.c,off),p=clipX([a,b,c]);if(p.length<3)continue;let nn=[...t.n],centroid=V.mul(V.add(V.add(a,b),c),1/3),vv=state.ortho?V.mul(forward,-1):V.norm(V.sub(eye,centroid));if(V.dot(nn,vv)<0)nn=V.mul(nn,-1);let diffuse=.48+.34*Math.max(V.dot(nn,light),0)+.18*Math.max(V.dot(nn,fill),0),sp=Math.pow(Math.max(V.dot(nn,V.norm(V.add(light,vv))),0),15+50*metal)*(.06+.20*metal),rim=Math.pow(1-Math.abs(V.dot(nn,vv)),3)*.035,col=base.map(v=>Math.max(0,Math.min(255,Math.round((v*diffuse+sp+rim)*255))));let pp=p.map(proj);for(let j=1;j<pp.length-1;j++){let triangle={a:pp[0],b:pp[j],c:pp[j+1],col,alpha};(alpha===1?opaque:transparent).push(triangle)}}}
 transparent.sort((a,b)=>(b.a[2]+b.b[2]+b.c[2])-(a.a[2]+a.b[2]+a.c[2]));
 function raster(t){let a=t.a,b=t.b,c=t.c,area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);if(Math.abs(area)<1e-6)return;let x0=Math.max(0,Math.floor(Math.min(a[0],b[0],c[0]))),x1=Math.min(w-1,Math.ceil(Math.max(a[0],b[0],c[0]))),y0=Math.max(0,Math.floor(Math.min(a[1],b[1],c[1]))),y1=Math.min(h-1,Math.ceil(Math.max(a[1],b[1],c[1])));if(x0>x1||y0>y1)return;let inv=1/area,e0x=(b[1]-c[1])*inv,e0y=(c[0]-b[0])*inv,e1x=(c[1]-a[1])*inv,e1y=(a[0]-c[0])*inv;for(let y=y0;y<=y1;y++){let u=((b[0]-(x0+.5))*(c[1]-(y+.5))-(b[1]-(y+.5))*(c[0]-(x0+.5)))*inv,v=((c[0]-(x0+.5))*(a[1]-(y+.5))-(c[1]-(y+.5))*(a[0]-(x0+.5)))*inv;for(let x=x0;x<=x1;x++,u+=e0x,v+=e1x){let q=1-u-v;if(u<-.000001||v<-.000001||q<-.000001)continue;let z=u*a[2]+v*b[2]+q*c[2],at=y*w+x;if(z>zbuf[at]+1e-7||z< -1||z>1)continue;let k=at*4;if(t.alpha===1){zbuf[at]=z;rgba[k]=t.col[0];rgba[k+1]=t.col[1];rgba[k+2]=t.col[2]}else for(let d=0;d<3;d++)rgba[k+d]=Math.round(rgba[k+d]*(1-t.alpha)+t.col[d]*t.alpha)}}}
 for(let t of opaque)raster(t);for(let t of transparent)raster(t);sc.putImageData(img,0,0);ctx.imageSmoothingEnabled=true;ctx.drawImage(softCanvas,0,0,canvas.width,canvas.height);
}



    function allParts() {
      return state.view==='original'?DATA.baselineParts:DATA.parts;
    }
    function chooseScene() {
      activeParts=DATA.jointScenes?.[state.view]||allParts();
      if(state.view==='side')activeParts=activeParts.filter(p=>(p.sourceId||p.id)==='body-right');
      if(state.view==='back')activeParts=activeParts.filter(p=>(p.sourceId||p.id)==='body-back');
      if(state.view==='lid-top')activeParts=activeParts.filter(p=>(p.sourceId||p.id)==='lid-top-single');
      if(state.view==='lid-end')activeParts=activeParts.filter(p=>(p.sourceId||p.id)==='lid-front');
      if(['floor-top','original'].includes(state.view))activeParts=activeParts.filter(p=>(p.sourceId||p.id)==='body-bottom-back');
      if(state.view==='underside')activeParts=activeParts.filter(p=>p.group==='body');
      for(const p of activeParts)createBuf(p.mesh);
      renderUI();dirty=true;
    }
    function renderUI() {
      const v=views[state.view];
      root.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
      $('stageTitle').textContent=v.title;$('stageDetail').textContent=v.detail;
      $('explodeLabel').textContent=(state.view==='insert'||state.view.endsWith('joint'))?'Side insertion gap':'Separate panels';
      $('explode').value=state.explode;$('explodeValue').textContent=Number(state.explode).toFixed(state.explode%1?1:0)+' mm';
      $('lid').checked=state.lidVisible;$('rails').checked=state.rails;$('stand').checked=state.stand;$('xray').checked=state.xray;
      $('lidControl').classList.toggle('tb-hidden',!state.lidVisible);$('lidlift').value=state.lidLift;$('lidValue').textContent=state.lidLift+' mm';
      $('color').setAttribute('aria-pressed',String(state.color));$('black').setAttribute('aria-pressed',String(!state.color));
      const referenceAvailable=fullViews.includes(state.view);
      for(const id of ['rails','lid','stand']){$(id).disabled=!referenceAvailable}
      for(const id of ['explode','assembled','separate'])$(id).disabled=['side','back','rail-gap','lid-top','lid-end','lid-ledge','h2d','floor-fit','floor-top','original'].includes(state.view);
      const isPrevious=state.view==='original';
      $('bodyWidth').textContent='337.4 mm';$('frameGap').textContent='8 mm';$('roofFixings').textContent='8';$('endFixings').textContent='2 each';$('roofWidth').textContent='317 mm';$('flangeWidth').textContent='5 mm';$('floorCuts').textContent=isPrevious?'0':'4';
      $('part').replaceChildren(new Option('Whole assembly',''));
      activeParts.filter(p=>p.selectable!==false).forEach(p=>{$('part').append(new Option(p.name,p.id))});
      $('part').value=state.only||'';
      const p=activeParts.find(p=>p.id===state.selected||p.id===state.only);
      const box=$('inspector');box.replaceChildren();
      const strong=document.createElement('strong');
      strong.textContent=p?p.name:(state.view==='original'?'Previous R4 floor':state.view==='floor-fit'?'Common floor · flat placement':state.view==='h2d'?'Roof · flat placement':state.view==='floor-top'?'Front / back common floor':state.view==='underside'?'Case underside':state.view==='lid-ledge'?'Right side · actual CAD section':'R5 case');box.append(strong);
      if(p){
        const dims=p.box.slice(0,3).map((n,i)=>(p.box[i+3]-n).toFixed(1)).join(' × ');
        box.append(document.createTextNode(dims+' mm'));
        if(p.note){box.append(document.createElement('br'),document.createTextNode(p.note))}
      }else box.append(document.createTextNode(state.view==='original'?'R4 floor with all four original corners.':state.view==='floor-fit'?'The rear tip clears the wipe zone on its left. One left nozzle; no brim or support. Print this common part twice.':state.view==='floor-top'?'Four corner cuts only. All nine fixing slots and four joint tabs remain.':state.view==='underside'?'The corner openings are the material removed to enable flat printing; the main floor and joint tabs remain.':state.view==='h2d'?'X4–321, Y10–300, Z0–5 mm. Left nozzle only; no brim or supports. Studio slicing pending.':state.view==='lid-ledge'?'The upper flange and roof finish flush. The lower shelf supports the roof from below.':'Select a part or click the model to inspect its geometry.'));
      $('partcount').textContent=state.view==='original'?'R4 comparison · uncut floor':state.view==='floor-fit'?'Common floor × 2 · flat diagonal placement':state.view==='floor-top'?'Four corner cuts · nine slots · four tabs':state.view==='h2d'?'Flat roof layout · no generated toolpaths':state.view==='lid-ledge'?'5 mm extension · 2.8 mm roof bearing':'R5 · floor corners clipped';
    }
    function boundsOfShown() {
      let lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
      for(const p of activeParts.filter(shown)){
        const off=offset(p);
        for(let k=0;k<3;k++){lo[k]=Math.min(lo[k],p.box[k]+off[k]);hi[k]=Math.max(hi[k],p.box[k+3]+off[k])}
      }
      return {lo,hi};
    }
    function fitCamera(){
      const {lo,hi}=boundsOfShown();if(!Number.isFinite(lo[0]))return;
      cam.target=lo.map((x,i)=>(x+hi[i])/2);updateCamera();
      const xx=[],yy=[];
      for(const a of[lo[0],hi[0]])for(const b of[lo[1],hi[1]])for(const c of[lo[2],hi[2]]){
        const p=V.sub([a,b,c],cam.target);xx.push(V.dot(p,right));yy.push(V.dot(p,up));
      }
      const aspect=canvas.clientWidth/canvas.clientHeight;
      cam.span=Math.max(Math.max(...yy)-Math.min(...yy),(Math.max(...xx)-Math.min(...xx))/aspect)*1.28;
      cam.span=Math.max(cam.span,30);dirty=true;
    }
    function setView(view){
      state.view=view;state.selected=null;state.only=null;state.explode=view==='insert'?18:0;
      if(['lid-fit','lid-ledge','lid-top','lid-end'].includes(view)){state.lidVisible=true;state.lidLift=0}
      else if(['assembly','insert','floor-fit','floor-top','underside','original'].includes(view)){state.lidVisible=false;state.lidLift=0}
      const v=views[view];cam={target:[...v.target],yaw:v.yaw,pitch:v.pitch,span:v.span,up:'z'};
      chooseScene();fitCamera();
    }
    function setCamera(kind){
      if(kind==='iso'){cam.yaw=.69;cam.pitch=.72}
      if(kind==='front'){cam.yaw=0;cam.pitch=0}
      if(kind==='side'){cam.yaw=Math.PI/2;cam.pitch=0}
      if(kind==='top'){cam.yaw=0;cam.pitch=1.5706}
      if(kind==='bottom'){cam.yaw=.45;cam.pitch=-1.0}
      fitCamera();
    }
    function pan(dx,dy){updateCamera();const s=cam.span/canvas.clientHeight;cam.target=V.add(cam.target,V.add(V.mul(right,-dx*s),V.mul(up,dy*s)));dirty=true}
    function rayBox(o,d,b){let t0=-Infinity,t1=Infinity;for(let k=0;k<3;k++){if(Math.abs(d[k])<1e-12){if(o[k]<b[k]||o[k]>b[k+3])return false}else{let a=(b[k]-o[k])/d[k],z=(b[k+3]-o[k])/d[k];if(a>z)[a,z]=[z,a];t0=Math.max(t0,a);t1=Math.min(t1,z);if(t1<t0)return false}}return t1>0}
    function rayTri(o,d,a,b,c){const e1=V.sub(b,a),e2=V.sub(c,a),h=V.cross(d,e2),det=V.dot(e1,h);if(Math.abs(det)<1e-10)return null;const inv=1/det,s=V.sub(o,a),u=inv*V.dot(s,h);if(u<0||u>1)return null;const q=V.cross(s,e1),v=inv*V.dot(d,q);if(v<0||u+v>1)return null;const t=inv*V.dot(e2,q);return t>0?t:null}
    function pick(cx,cy){
      updateCamera();const r=canvas.getBoundingClientRect(),x=(cx-r.left)/r.width*2-1,y=1-(cy-r.top)/r.height*2;
      const o=V.add(eye,V.add(V.mul(right,x*cam.span*r.width/r.height/2),V.mul(up,y*cam.span/2))),d=forward;
      let best=Infinity,found=null;
      for(const p of activeParts.filter(shown)){
        const oo=V.sub(o,offset(p));if(!rayBox(oo,d,p.box))continue;
        const {p:pts,i:ind}=DATA.meshes[p.mesh];
        for(let k=0;k<ind.length;k+=3){const t=rayTri(oo,d,pts.slice(ind[k]*3,ind[k]*3+3),pts.slice(ind[k+1]*3,ind[k+1]*3+3),pts.slice(ind[k+2]*3,ind[k+2]*3+3));if(t!==null&&t<best){best=t;found=p}}
      }
      state.selected=found?.id||null;renderUI();dirty=true;
    }
    let drag=null,lastPinch=null;const pointers=new Map();
    canvas.addEventListener('contextmenu',e=>e.preventDefault());
    canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);pointers.set(e.pointerId,[e.clientX,e.clientY]);drag={x:e.clientX,y:e.clientY,total:0,pan:e.button===2||e.shiftKey};if(pointers.size===2){const p=[...pointers.values()];lastPinch={d:Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]),m:[(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2]}}});
    canvas.addEventListener('pointermove',e=>{
      if(!pointers.has(e.pointerId)||!drag)return;pointers.set(e.pointerId,[e.clientX,e.clientY]);
      if(pointers.size===2){const p=[...pointers.values()],d=Math.hypot(p[0][0]-p[1][0],p[0][1]-p[1][1]),m=[(p[0][0]+p[1][0])/2,(p[0][1]+p[1][1])/2];if(lastPinch){cam.span=Math.max(5,Math.min(2000,cam.span*lastPinch.d/Math.max(1,d)));pan(m[0]-lastPinch.m[0],m[1]-lastPinch.m[1])}lastPinch={d,m};drag.total+=10;dirty=true;return}
      const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.x=e.clientX;drag.y=e.clientY;drag.total+=Math.abs(dx)+Math.abs(dy);
      if(drag.pan)pan(dx,dy);else{cam.yaw-=dx*.008;cam.pitch=Math.max(-1.55,Math.min(1.55,cam.pitch+dy*.007))}dirty=true;
    });
    canvas.addEventListener('pointerup',e=>{pointers.delete(e.pointerId);if(drag&&drag.total<5&&e.button===0)pick(e.clientX,e.clientY);if(!pointers.size)drag=null;else if(pointers.size===1&&drag){const point=[...pointers.values()][0];drag.x=point[0];drag.y=point[1];drag.total=Math.max(drag.total,5)}lastPinch=null});
    canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);drag=null;lastPinch=null});
    canvas.addEventListener('wheel',e=>{e.preventDefault();cam.span=Math.max(5,Math.min(2000,cam.span*Math.exp(e.deltaY*.001)));dirty=true},{passive:false});
    root.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
    root.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>setCamera(b.dataset.camera)));
    $('explode').addEventListener('input',e=>{state.explode=Number(e.target.value);renderUI();fitCamera();dirty=true});
    $('assembled').onclick=()=>{state.explode=0;renderUI();dirty=true};
    $('separate').onclick=()=>{state.explode=25;renderUI();fitCamera()};
    $('fit').onclick=()=>fitCamera();
    $('full').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('stage').requestFullscreen()}catch{fitCamera()}};
    for(const [id,key]of[['rails','rails'],['lid','lidVisible'],['stand','stand'],['xray','xray']]){
      $(id).onchange=e=>{state[key]=e.target.checked;if(id!=='xray'){state.only=null;state.selected=null}renderUI();if(id!=='xray')fitCamera();dirty=true};
    }
    $('lidlift').oninput=e=>{state.lidLift=Number(e.target.value);renderUI();fitCamera();dirty=true};
    $('color').onclick=()=>{state.color=true;renderUI();dirty=true};$('black').onclick=()=>{state.color=false;renderUI();dirty=true};
    $('part').onchange=e=>{state.only=e.target.value||null;state.selected=state.only;if(state.only){const p=activeParts.find(p=>p.id===state.only);if(p?.group==='lid')state.lidVisible=true;if(['rails','mounts'].includes(p?.group))state.rails=true;if(p?.group==='stand')state.stand=true}renderUI();fitCamera()};
    $('renderer').textContent=gl?'Interactive 3D':'Interactive 3D · software renderer';
    new ResizeObserver(()=>{fitCamera();dirty=true}).observe($('stage'));
    document.addEventListener('fullscreenchange',()=>{fitCamera();dirty=true});
    setView('floor-fit');render();$('loading').classList.add('tb-hidden');root.dataset.ready='true';
    let stopped=false;
    function tick(){if(stopped)return;if(!root.isConnected){stopped=true;return}render();requestAnimationFrame(tick)}
    requestAnimationFrame(tick);
    window.tenboxStudy={state,DATA,setView,setCamera,fit:fitCamera,render,visibleParts:()=>activeParts.filter(shown),partOffset:offset,get camera(){return cam},get frames(){return frameNumber},get renderer(){return gl?'webgl':'canvas'},get parts(){return activeParts}};
  }catch(e){
    $('loading').textContent='The 3D model could not start: '+e.message;root.dataset.error=e.message;console.error(e);
  }
})();
