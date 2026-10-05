/* Dependency-free WebGL concept viewer. No CAD kernel or mechanical solver. */
(function(root){
'use strict';
const V=FoldModel.math,{add,sub,mul,dot,cross,len,norm,rad}=V;
const C={wood:[.49,.40,.28],textile:[.17,.185,.175],graphite:[.20,.235,.255],silver:[.66,.69,.69],olive:[.33,.38,.29],metal:[.69,.72,.71],rail:[.49,.53,.53],frame:[.12,.15,.16],guard:[.115,.13,.13],black:[.08,.10,.11],panel:[.16,.185,.20],paper:[.80,.82,.79],copper:[.76,.43,.25],blue:[.21,.49,.62],yellow:[.89,.66,.28],green:[.31,.55,.43],red:[.82,.34,.26],board:[.15,.34,.28],wire:[.49,.36,.23]};
class Mesh{
 constructor(){this.v=[];this.edges=[];this.labels=[];}
 vertex(p,n,c){this.v.push(...p,...n,...c);}
 tri(a,b,c,col,n){n=n||norm(cross(sub(b,a),sub(c,a)));[a,b,c].forEach(p=>this.vertex(p,n,col));}
 quad(a,b,c,d,col){this.tri(a,b,c,col);this.tri(a,c,d,col);}
 box(center,size,col,edges=true){
  const h=size.map(x=>x/2),axes=[[0,1,2],[1,2,0],[2,0,1]];
  for(const [a,b,c] of axes)for(const sign of [-1,1]){
   const n=[0,0,0],u=[0,0,0],v=[0,0,0];n[a]=sign;u[b]=h[b];v[c]=sign*h[c];const q=add(center,mul(n,h[a]));
   this.quad(sub(sub(q,u),v),add(sub(q,v),u),add(add(q,u),v),add(sub(q,u),v),col);
  }
  if(edges){
   const p=[];for(let i=0;i<8;i++)p.push(center.map((x,k)=>x+((i>>k)&1?1:-1)*h[k]));
   for(let i=0;i<8;i++)for(let j=0;j<3;j++)if(!((i>>j)&1))this.edges.push(...p[i],...p[i|(1<<j)]);
  }
 }
 cylinder(a,b,r,col,segments=12,r2=r){
  const axis=norm(sub(b,a)),u=norm(cross(axis,Math.abs(axis[2])<.9?[0,0,1]:[0,1,0])),v=cross(axis,u);
  for(let i=0;i<segments;i++){
   const f=i/segments*2*Math.PI,g=(i+1)/segments*2*Math.PI;
   const n1=add(mul(u,Math.cos(f)),mul(v,Math.sin(f))),n2=add(mul(u,Math.cos(g)),mul(v,Math.sin(g)));
   const p1=add(a,mul(n1,r)),p2=add(a,mul(n2,r)),p3=add(b,mul(n2,r2)),p4=add(b,mul(n1,r2));
   [[p1,n1],[p2,n2],[p3,n2],[p1,n1],[p3,n2],[p4,n1]].forEach(([p,n])=>this.vertex(p,n,col));
   this.tri(a,p2,p1,col,mul(axis,-1));this.tri(b,p4,p3,col,axis);
  }
 }
 tube(points,r,col,segments=8){
  for(let i=0;i<points.length-1;i++){
   const a=points[i],b=points[i+1];
   if(len(sub(b,a))>.01)this.cylinder(a,b,r,col,segments);
  }
 }
 label(text,center,width,height,color='light'){this.labels.push({text,center,width,height,color});}
}
function column(m,x,y,z,r,h,color){m.cylinder([x,y,z],[x,y,z+h],r,color);}
function buildGeometry(s,d){return root.FoldGeometry.buildGeometry(s,d);}
function identity(){return new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);}
function multiply(a,b){const o=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++){let v=0;for(let k=0;k<4;k++)v+=a[k*4+r]*b[c*4+k];o[c*4+r]=v;}return o;}
function lookAt(eye,at,up){const z=norm(sub(eye,at)),x=norm(cross(up,z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
function ortho(l,r,b,t,n,f){return new Float32Array([2/(r-l),0,0,0,0,2/(t-b),0,0,0,0,-2/(f-n),0,-(r+l)/(r-l),-(t+b)/(t-b),-(f+n)/(f-n),1]);}
function modelMatrix(s,d,lid){if(!lid)return identity();const z=FoldModel.lidNormal([0,0,1],s),y=FoldModel.lidNormal([0,1,0],s),p=FoldModel.lidPoint([0,0,0],s,d);return new Float32Array([1,0,0,0,...y,0,...z,0,...p,1]);}
const VS=`attribute vec3 aPosition;attribute vec3 aNormal;attribute vec3 aColor;uniform mat4 uVP;uniform mat4 uModel;varying vec3 vN;varying vec3 vC;varying vec3 vP;void main(){vec4 p=uModel*vec4(aPosition,1.);vP=p.xyz;vN=mat3(uModel)*aNormal;vC=aColor;gl_Position=uVP*p;}`;
const FS=`precision mediump float;varying vec3 vN;varying vec3 vC;varying vec3 vP;uniform float uAlpha;uniform bool uClip;uniform bool uFlat;void main(){if(uClip&&vP.x>0.)discard;vec3 n=normalize(vN);if(!gl_FrontFacing)n=-n;float k=.50+.46*max(0.,dot(n,normalize(vec3(-.5,-.6,1.))))+.19*max(0.,dot(n,normalize(vec3(1.,.4,.35))));vec3 c=uFlat?vC:vC*k;gl_FragColor=vec4(c,uAlpha);}`;
const TVS=`attribute vec3 aPosition;attribute vec2 aUV;uniform mat4 uVP;uniform mat4 uModel;varying vec2 vUV;varying vec3 vP;void main(){vec4 p=uModel*vec4(aPosition,1.);vP=p.xyz;vUV=aUV;gl_Position=uVP*p;}`;
const TFS=`precision mediump float;uniform sampler2D uTexture;uniform bool uClip;varying vec2 vUV;varying vec3 vP;void main(){if(uClip&&vP.x>0.)discard;if(!gl_FrontFacing)discard;vec4 c=texture2D(uTexture,vUV);if(c.a<.02)discard;gl_FragColor=c;}`;
function program(gl,vs,fs){
 function shader(type,src){const sh=gl.createShader(type);gl.shaderSource(sh,src);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(sh));return sh;}
 const p=gl.createProgram(),a=shader(gl.VERTEX_SHADER,vs),b=shader(gl.FRAGMENT_SHADER,fs);gl.attachShader(p,a);gl.attachShader(p,b);gl.linkProgram(p);gl.deleteShader(a);gl.deleteShader(b);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(p));return p;
}
class Viewer{
 constructor(canvas,onchange){
  this.canvas=canvas;this.gl=canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:true});
  this.mode=this.gl?'webgl':'software';this.ctx=this.gl?null:canvas.getContext('2d');
  if(!this.gl&&!this.ctx)throw new Error('This browser does not support a canvas context. Use the closed-section and comparison views.');
  const gl=this.gl;if(gl){this.program=program(gl,VS,FS);this.textProgram=program(gl,TVS,TFS);}this.objects={};this.ground=null;
  this.camera={azimuth:rad(41),elevation:rad(28),target:[0,100,60],span:700};this.onchange=onchange;this.dirty=true;this.drag=null;
  canvas.addEventListener('contextmenu',e=>e.preventDefault());
  canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,pan:e.shiftKey||e.button===2};canvas.classList.add('dragging');});
  canvas.addEventListener('pointermove',e=>{if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;
   if(this.drag.pan){const k=this.camera.span/canvas.clientHeight,az=this.camera.azimuth;this.camera.target[0]-=dx*k*Math.cos(az);this.camera.target[1]-=dx*k*Math.sin(az);this.camera.target[2]+=dy*k;}
   else{this.camera.azimuth-=dx*.007;this.camera.elevation=Math.max(-1.3,Math.min(1.54,this.camera.elevation+dy*.007));}
   this.draw();if(onchange)onchange();});
  const end=()=>{this.drag=null;canvas.classList.remove('dragging');};canvas.addEventListener('pointerup',end);canvas.addEventListener('pointercancel',end);
  canvas.addEventListener('wheel',e=>{e.preventDefault();this.camera.span=Math.max(40,Math.min(3400,this.camera.span*Math.exp(e.deltaY*.001)));this.draw();},{passive:false});
  canvas.addEventListener('keydown',e=>{const v=this.camera;if(e.key==='ArrowLeft')v.azimuth-=.1;else if(e.key==='ArrowRight')v.azimuth+=.1;else if(e.key==='ArrowUp')v.elevation=Math.min(1.54,v.elevation+.1);else if(e.key==='ArrowDown')v.elevation=Math.max(-1.3,v.elevation-.1);else if(e.key==='+'||e.key==='=')v.span*=.9;else if(e.key==='-')v.span*=1.1;else if(e.key.toLowerCase()==='r')this.fit();else return;e.preventDefault();this.draw();});
  new ResizeObserver(()=>{this.fit();this.draw();}).observe(canvas);
 }
 upload(mesh){
  if(!this.gl)return {mesh};
  const gl=this.gl,buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(mesh.v),gl.STATIC_DRAW);
  const edges=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,edges);
  const arr=[];for(let i=0;i<mesh.edges.length;i+=3)arr.push(...mesh.edges.slice(i,i+3),0,0,1,.065,.085,.09);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(arr),gl.STATIC_DRAW);
  let texture=null,labelBuffer=null,labelCount=0;
  if(mesh.labels.length){
   const c=document.createElement('canvas');c.width=1024;c.height=1024;const ctx=c.getContext('2d');ctx.clearRect(0,0,1024,1024);const l=[];
   mesh.labels.forEach((q,i)=>{
    const cx=i%8,cy=Math.floor(i/8),X=cx*128,Y=cy*64;ctx.fillStyle=q.color==='light'?'#edf0e6':'#27332f';ctx.font='600 25px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(q.text,X+64,Y+32,121);
    const x=q.center[0],y=q.center[1],z=q.center[2],w=q.width/2,h=q.height/2,u0=cx/8,u1=(cx+1)/8,v0=1-(cy+1)/16,v1=1-cy/16;
    l.push(x-w,y-h,z,u0,v0,x+w,y-h,z,u1,v0,x+w,y+h,z,u1,v1,x-w,y-h,z,u0,v0,x+w,y+h,z,u1,v1,x-w,y+h,z,u0,v1);
   });
   texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,c);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
   labelBuffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,labelBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(l),gl.STATIC_DRAW);labelCount=l.length/5;
  }
  return {buffer,edges,count:mesh.v.length/9,edgeCount:arr.length/9,texture,labelBuffer,labelCount};
 }
 dispose(o){if(!this.gl)return;const gl=this.gl;if(!o)return;gl.deleteBuffer(o.buffer);gl.deleteBuffer(o.edges);if(o.labelBuffer)gl.deleteBuffer(o.labelBuffer);if(o.texture)gl.deleteTexture(o.texture);}
 update(s,d,fit=false){
  this.state=s;this.dim=d;this.geometry=buildGeometry(s,d);
  Object.values(this.objects).forEach(o=>this.dispose(o));this.objects={};
  for(const [key,mesh] of Object.entries(this.geometry))this.objects[key]=this.upload(mesh);
  if(this.ground)this.dispose(this.ground);
  const g=new Mesh(),z=d.floor-1,size=3000;
  g.box([0,300,z-.5],[size,size,1],[.94,.945,.926],false);
  // Quiet ground avoids sub-pixel grid aliasing in software rendering.
  // A soft schematic contact footprint. Not a lighting/physical simulation.
  if(!['packing','joint','hinge','trunk'].includes(s.pose))for(let i=6;i>=0;i--){const W=d.W+10+i*4,D=d.D+10+i*4,c=.873+i*.006;g.box([0,0,z+.2+(6-i)*.015],[W,D,.015],[c,c+.014,c-.005],false);}
  this.ground=this.upload(g);if(fit)this.fit();this.draw();
 }
 bounds(){
  const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
  for(const key of ['base','lid','world','ring']){const v=this.geometry[key].v;for(let i=0;i<v.length;i+=9){const pt=key==='lid'?FoldModel.lidPoint(v.slice(i,i+3),this.state,this.dim):v.slice(i,i+3);for(let k=0;k<3;k++){min[k]=Math.min(min[k],pt[k]);max[k]=Math.max(max[k],pt[k]);}}}
  return {min,max};
 }
 fit(){
  if(!this.state)return;const b=this.bounds(),center=mul(add(b.min,b.max),.5),a=this.camera.azimuth,e=this.camera.elevation,right=[Math.cos(a),Math.sin(a),0],up=[-Math.sin(a)*Math.sin(e),Math.cos(a)*Math.sin(e),Math.cos(e)],ps=[];
  for(let i=0;i<8;i++)ps.push(sub([0,1,2].map(k=>((i>>k)&1?b.max:b.min)[k]),center));
  const xr=ps.map(p=>dot(p,right)),yr=ps.map(p=>dot(p,up)),w=this.canvas.clientWidth,h=Math.max(this.canvas.clientHeight,1),aspect=w/h,top=w<=600?145:w<900?130:100,bottom=38,usable=Math.max(100,h-top-bottom);
  this.camera.span=Math.max((Math.max(...xr)-Math.min(...xr))/(aspect*.92),(Math.max(...yr)-Math.min(...yr))*h/usable,100)*1.04;
  this.camera.target=add(center,mul(up,(top-bottom)*this.camera.span/(2*h)));
 }

 setView(v,draw=true){
  if(v==='top'){this.camera.azimuth=0;this.camera.elevation=1.565;}
  else if(v==='side'){this.camera.azimuth=Math.PI/2;this.camera.elevation=.02;}
  else if(v==='front'){this.camera.azimuth=0;this.camera.elevation=.02;}
  else if(v==='back'){this.camera.azimuth=Math.PI;this.camera.elevation=rad(22);}
  else{this.camera.azimuth=rad(32);this.camera.elevation=rad(this.state?.pose==='closed'?27:42);}
  if(draw){this.fit();this.draw();}
 }
 matrices(){
  const c=this.camera,a=c.azimuth,e=c.elevation,dir=[Math.sin(a)*Math.cos(e),-Math.cos(a)*Math.cos(e),Math.sin(e)],eye=add(c.target,mul(dir,1800));
  const aspect=this.canvas.width/this.canvas.height,hh=c.span/2;
  const vp=multiply(ortho(-hh*aspect,hh*aspect,-hh,hh,1,5000),lookAt(eye,c.target,[0,0,1]));this.vp=vp;return vp;
 }
 drawObject(o,model,alpha=1,clip=false,flat=false,edges=false){
  if(!o)return;const gl=this.gl,p=this.program;gl.useProgram(p);gl.bindBuffer(gl.ARRAY_BUFFER,edges?o.edges:o.buffer);
  for(const [name,size,offset] of [['aPosition',3,0],['aNormal',3,12],['aColor',3,24]]){const loc=gl.getAttribLocation(p,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,36,offset);}
  gl.uniformMatrix4fv(gl.getUniformLocation(p,'uVP'),false,this.vp);gl.uniformMatrix4fv(gl.getUniformLocation(p,'uModel'),false,model);gl.uniform1f(gl.getUniformLocation(p,'uAlpha'),alpha);gl.uniform1i(gl.getUniformLocation(p,'uClip'),clip?1:0);gl.uniform1i(gl.getUniformLocation(p,'uFlat'),flat?1:0);
  gl.drawArrays(edges?gl.LINES:gl.TRIANGLES,0,edges?o.edgeCount:o.count);
 }
 drawLabels(o,model,clip){
  if(!o.labelBuffer||!this.state.labels||this.state.structure)return;const gl=this.gl,p=this.textProgram;gl.useProgram(p);gl.bindBuffer(gl.ARRAY_BUFFER,o.labelBuffer);
  for(const [name,size,offset] of [['aPosition',3,0],['aUV',2,12]]){const loc=gl.getAttribLocation(p,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,20,offset);}
  gl.uniformMatrix4fv(gl.getUniformLocation(p,'uVP'),false,this.vp);gl.uniformMatrix4fv(gl.getUniformLocation(p,'uModel'),false,model);gl.uniform1i(gl.getUniformLocation(p,'uClip'),clip?1:0);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,o.texture);gl.uniform1i(gl.getUniformLocation(p,'uTexture'),0);gl.drawArrays(gl.TRIANGLES,0,o.labelCount);
 }
 draw(){
  if(!this.state)return;if(!this.gl){this.drawSoftware();return;}const gl=this.gl,c=this.canvas,dpr=Math.min(devicePixelRatio||1,2),w=Math.max(1,Math.round(c.clientWidth*dpr)),h=Math.max(1,Math.round(c.clientHeight*dpr));if(c.width!==w||c.height!==h){c.width=w;c.height=h;}
  gl.viewport(0,0,w,h);gl.clearColor(.94,.945,.926,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(true);this.matrices();
  const I=identity(),L=modelMatrix(this.state,this.dim,true),clip=this.state.cutaway;
  this.drawObject(this.ground,I,1,false,true);
  for(const key of ['base','lid','ring','world'])this.drawObject(this.objects[key],key==='lid'?L:I,1,clip,false);
  gl.depthMask(false);for(const key of ['base','lid','ring'])this.drawObject(this.objects[key],key==='lid'?L:I,.17,clip,true,true);gl.depthMask(true);
  for(const key of ['base','lid','ring','world'])this.drawLabels(this.objects[key],key==='lid'?L:I,clip);
  if(this.state.envelopes){gl.depthMask(false);this.drawObject(this.objects.envBase,I,.14,clip,true);this.drawObject(this.objects.envLid,L,.14,clip,true);this.drawObject(this.objects.envBase,I,.8,clip,true,true);this.drawObject(this.objects.envLid,L,.8,clip,true,true);gl.depthMask(true);}
  if(this.onDraw)this.onDraw();
 }

 // Actual depth-buffered software 3D for browsers without a WebGL context.
 // Uses the identical meshes and transforms, rather than a pre-rendered image.
 drawSoftware(){
  const c=this.canvas,ratio=Math.min(devicePixelRatio||1,1.5,1400/Math.max(c.clientWidth,1)),w=Math.max(1,Math.round(c.clientWidth*ratio)),h=Math.max(1,Math.round(c.clientHeight*ratio));
  if(c.width!==w||c.height!==h){c.width=w;c.height=h;this.image=this.ctx.createImageData(w,h);this.depth=new Float32Array(w*h);}
  if(!this.image){this.image=this.ctx.createImageData(w,h);this.depth=new Float32Array(w*h);}
  const img=this.image,pixels=new Uint32Array(img.data.buffer),depth=this.depth,pack=(r,g,b)=>((255<<24)|(b<<16)|(g<<8)|r)>>>0;
  pixels.fill(pack(240,241,236));depth.fill(Infinity);this.matrices();const vp=this.vp;
  const projection=p=>[(vp[0]*p[0]+vp[4]*p[1]+vp[8]*p[2]+vp[12])*.5*w+w*.5,(-vp[1]*p[0]-vp[5]*p[1]-vp[9]*p[2]-vp[13])*.5*h+h*.5,vp[2]*p[0]+vp[6]*p[1]+vp[10]*p[2]+vp[14]];
  const light=norm([-.5,-.6,1]),fill=norm([1,.4,.35]),cam=this.camera,eyeDir=[Math.sin(cam.azimuth)*Math.cos(cam.elevation),-Math.cos(cam.azimuth)*Math.cos(cam.elevation),Math.sin(cam.elevation)];
  const raster=(a,b,c,rgb,alpha=1,tex=null)=>{
   const den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<.025)return;
   const xmin=Math.max(0,Math.floor(Math.min(a[0],b[0],c[0]))),xmax=Math.min(w-1,Math.ceil(Math.max(a[0],b[0],c[0]))),ymin=Math.max(0,Math.floor(Math.min(a[1],b[1],c[1]))),ymax=Math.min(h-1,Math.ceil(Math.max(a[1],b[1],c[1])));
   const ax=(b[1]-c[1])/den,ay=(c[0]-b[0])/den,bx=(c[1]-a[1])/den,by=(a[0]-c[0])/den,col=pack(...rgb);
   for(let y=ymin;y<=ymax;y++){
    let wa=ax*(xmin+.5-c[0])+ay*(y+.5-c[1]),wb=bx*(xmin+.5-c[0])+by*(y+.5-c[1]);
    for(let x=xmin;x<=xmax;x++,wa+=ax,wb+=bx){const wc=1-wa-wb;if(wa<-.00001||wb<-.00001||wc<-.00001)continue;const z=wa*a[2]+wb*b[2]+wc*c[2],idx=y*w+x;if(z>depth[idx]+1e-7)continue;
     if(tex){const u=wa*a[3]+wb*b[3]+wc*c[3],v=wa*a[4]+wb*b[4]+wc*c[4],ti=(Math.min(tex.h-1,Math.max(0,Math.floor(v*tex.h)))*tex.w+Math.min(tex.w-1,Math.max(0,Math.floor(u*tex.w))))*4,ta=tex.data[ti+3]/255;if(ta<.15)continue;const o=idx*4;for(let k=0;k<3;k++)img.data[o+k]=Math.round(img.data[o+k]*(1-ta)+tex.data[ti+k]*ta);depth[idx]=z;}
     else if(alpha<1){const o=idx*4;for(let k=0;k<3;k++)img.data[o+k]=Math.round(img.data[o+k]*(1-alpha)+rgb[k]*alpha);}
     else{pixels[idx]=col;depth[idx]=z;}
    }
   }
  };
  const drawMesh=(mesh,isLid=false,flat=false,alpha=1,clip=false)=>{
   const v=mesh.v;
   for(let i=0;i<v.length;i+=27){let ps=[v.slice(i,i+3),v.slice(i+9,i+12),v.slice(i+18,i+21)];if(isLid)ps=ps.map(p=>FoldModel.lidPoint(p,this.state,this.dim));
    let n=v.slice(i+3,i+6);if(isLid)n=FoldModel.lidNormal(n,this.state);if(dot(n,eyeDir)<0)n=mul(n,-1);
    const k=flat?1:.50+.46*Math.max(0,dot(n,light))+.19*Math.max(0,dot(n,fill)),rgb=v.slice(i+6,i+9).map(x=>Math.min(255,Math.max(0,Math.round(x*k*255))));
    if(clip){const next=[];for(let j=0;j<ps.length;j++){const a=ps[j],b=ps[(j+1)%ps.length],ia=a[0]<=0,ib=b[0]<=0;if(ia)next.push(a);if(ia!==ib){const t=-a[0]/(b[0]-a[0]);next.push(a.map((x,k)=>x+t*(b[k]-x)));}}ps=next;}
    if(ps.length<3)continue;const pp=ps.map(projection);for(let j=1;j<pp.length-1;j++)raster(pp[0],pp[j],pp[j+1],rgb,alpha);
   }
  };
  if(this.ground)drawMesh(this.ground.mesh,false,true);
  for(const key of ['base','lid','ring','world'])drawMesh(this.geometry[key],key==='lid',false,1,this.state.cutaway);
  // Text remains depth-tested, including on the rotated upper half.
  if(this.state.labels&&!this.state.structure){this.softwareLabels=this.softwareLabels||new Map();
   for(const key of ['base','lid','ring','world'])for(const q of this.geometry[key].labels){
    const id=q.text+'/'+q.color;let tex=this.softwareLabels.get(id);
    if(!tex){const tc=document.createElement('canvas');tc.width=256;tc.height=64;const tx=tc.getContext('2d');tx.font='600 31px Arial';tx.textAlign='center';tx.textBaseline='middle';tx.fillStyle=q.color==='light'?'#edf0e6':'#27332f';tx.fillText(q.text,128,32,250);tex={data:tx.getImageData(0,0,256,64).data,w:256,h:64};this.softwareLabels.set(id,tex);}
    let n=key==='lid'?FoldModel.lidNormal([0,0,1],this.state):[0,0,1];if(dot(n,eyeDir)<0)continue;
    const pos=[[-1,1,0,0],[1,1,1,0],[1,-1,1,1],[-1,-1,0,1]].map(([x,y,u,v])=>{let p=add(q.center,[x*q.width/2,y*q.height/2,0]);if(key==='lid')p=FoldModel.lidPoint(p,this.state,this.dim);return {p,uv:[u,v]};});
    if(this.state.cutaway&&pos.some(p=>p.p[0]>0))continue;const pp=pos.map(p=>[...projection(p.p),...p.uv]);raster(pp[0],pp[1],pp[2],[0,0,0],1,tex);raster(pp[0],pp[2],pp[3],[0,0,0],1,tex);
   }
  }
  if(this.state.envelopes){drawMesh(this.geometry.envBase,false,true,.13,this.state.cutaway);drawMesh(this.geometry.envLid,true,true,.13,this.state.cutaway);}
  this.ctx.putImageData(img,0,0);if(this.onDraw)this.onDraw();
 }

 project(p){const m=this.vp,x=p[0],y=p[1],z=p[2],w=m[3]*x+m[7]*y+m[11]*z+m[15];return [(m[0]*x+m[4]*y+m[8]*z+m[12])/w/2*this.canvas.clientWidth+this.canvas.clientWidth/2,(-((m[1]*x+m[5]*y+m[9]*z+m[13])/w)/2+.5)*this.canvas.clientHeight];}
 meshExport(){
  const s=this.state,d=this.dim,result={units:'mm',manufacturingApproved:false,groups:{}};
  for(const key of ['base','lid','world','ring']){
   const v=this.geometry[key].v,out=[];
   for(let i=0;i<v.length;i+=9){const p=v.slice(i,i+3),n=v.slice(i+3,i+6),c=v.slice(i+6,i+9);out.push(...(key==='lid'?FoldModel.lidPoint(p,s,d):p),...(key==='lid'?FoldModel.lidNormal(n,s):n),...c);}
   result.groups[key]=out;
  }return result;
 }
}
root.FoldRenderer={Viewer,buildGeometry,Mesh,math:{multiply,identity,modelMatrix},colors:C};
})(typeof window!=='undefined'?window:globalThis);
