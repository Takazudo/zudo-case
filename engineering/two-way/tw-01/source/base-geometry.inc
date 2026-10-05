/* F5 — locating seats, retained straps and independent playing support.
   Display solids only; grooves, fastener bores and material strengths are not manufacturing-defined. */
(function(root){
'use strict';
const M=root.FoldModel,{Mesh,colors:C}=root.FoldRenderer,{add,sub,mul,norm,cross,rad}=M.math;
function transfer(target,source,point,normal=v=>v){
 for(let i=0;i<source.v.length;i+=9)target.v.push(...point(source.v.slice(i,i+3)),...normal(source.v.slice(i+3,i+6)),...source.v.slice(i+6,i+9));
 for(let i=0;i<source.edges.length;i+=3)target.edges.push(...point(source.edges.slice(i,i+3)));
 for(const l of source.labels)target.labels.push({...l,center:point(l.center)});
}
function prismYZ(m,x,points,t,col){
 for(const sign of [-1,1])for(let i=1;i<points.length-1;i++)m.tri([x+sign*t/2,...points[0]],[x+sign*t/2,...points[i]],[x+sign*t/2,...points[i+1]],col,[sign,0,0]);
 for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length];m.quad([x-t/2,...a],[x-t/2,...b],[x+t/2,...b],[x+t/2,...a],col);m.edges.push(x-t/2,...a,x-t/2,...b,x+t/2,...a,x+t/2,...b);}
}
function column(m,x,y,z,r,h,col){m.cylinder([x,y,z],[x,y,z+h],r,col,10);}
function sideCheek(s,d){
 const m=new Mesh(),R=d.run,h=d.heel,col=s.highlight?C.copper:C.wood;
 prismYZ(m,0,[[-10,0],[R+10,0],[R+10,h+R+10],[-10,h-10]],s.ply,col);
 // Toe and pad are explicit envelopes, not certified joinery or retention details.
 m.box([0,-7,h-3],[s.ply,6,14],col);
 const n=Math.sqrt(.5),strip=new Mesh();strip.box([0,d.standSpan/2,0],[s.ply,d.standSpan,2],C.guard);
 transfer(m,strip,p=>[p[0],p[1]*n-p[2]*n,h+p[1]*n+p[2]*n],p=>[p[0],p[1]*n-p[2]*n,p[1]*n+p[2]*n]);
 for(const y of [-2,d.run+3])m.box([0,y,-2],[s.ply,14,4],C.guard);
 return m;
}
function packedStand(target,s,d,origin=[0,0,0],exploded=false){
 const cheek=sideCheek(s,d),x0=-d.W/2+6,y0=d.packedStartY;
 for(let i=0;i<2;i++){
  const z0=2+i*(s.ply+(exploded?8:0));
  transfer(target,cheek,p=>[origin[0]+x0+p[1]+10,origin[1]+y0+p[2],origin[2]+z0+p[0]+s.ply/2],p=>[p[1],p[2],p[0]]);
 }
 // Two cross-ties fit in the unoccupied strip beside the packed cheeks, on layer 1.
 for(let i=0;i<2;i++)target.box([origin[0],origin[1]-d.D/2+6+d.barH/2+i*(d.barH+4),origin[2]+2+s.ply/2],[d.standWidth,d.barH,s.ply],s.highlight?C.copper:C.wood);
}
function assembledStand(target,s,d){
 const y0=d.D/2+s.deskGap,z0=d.floor+4,cheek=sideCheek(s,d);
 for(const x of [-d.W/2+20,d.W/2-20]){
  transfer(target,cheek,p=>[p[0]+x,p[1]+y0,p[2]+z0]);

 }
 // Fixed cross-ties, not a giant base cradle. Slots/retention require further design.
 for(const y of [12,d.run-12])target.box([0,y+y0,z0+Math.min(d.heel+y-8,d.barH/2+5)],[d.standWidth,s.ply,d.barH],s.highlight?C.copper:C.wood);
}
function outline(target,d,z=-1){
 for(const x of [-d.W/2,d.W/2])target.box([x,0,z],[1.2,d.D,1],[.70,.74,.69]);
 for(const y of [-d.D/2,d.D/2])target.box([0,y,z],[d.W,1.2,1],[.70,.74,.69]);
}

function trays(s,d,groups){const {W,D,G,t}=d,col=C[s.finish];
 for(let side=0;side<2;side++){
  const m=side?groups.lid:groups.base,back=side?s.lidDepth:s.baseDepth,top=d.rim;
  m.box([0,0,-back+t/2],[W,D,t],col);
  for(const y of [-D/2+t/2,D/2-t/2])m.box([0,y,(-back+t+top)/2],[W-2*t,t,back-t+top],col);
  for(const x of [-W/2+t/2,W/2-t/2])m.box([x,0,(-back+t+top)/2],[t,D,back-t+top],col);
  sourceFrame(m,s,d,0);
  // Ordinary fixed corner connections remain inside the metal shell.
  for(const x of [-W/2+t+7,W/2-t-7])for(const y of [-D/2+t+7,D/2-t-7]){m.box([x,y,-back+t+1],[14,14,2],C.metal);m.box([x,y+(y>0?6:-6),-back+t+8],[14,2,16],C.metal);}
  for(const x of [-W/2+t/2,W/2-t/2])for(const y of [-D/2+20,D/2-20])m.cylinder([x,y,-back+17],[x+Math.sign(x)*.6,y,-back+17],2.7,C.metal,10);
  for(const x of [-W/2,W/2])m.box([x,0,top-1.3],[2.4,D,2.6],C.guard);
  for(const y of [-D/2,D/2])m.box([0,y,top-1.3],[W,2.4,2.6],C.guard);
  const data=FoldModel.modules(s,d,side);
  if(s.modules&&!s.structure)for(const q of data.modules){
   const pc=q.metal?C.paper:C.panel,ink=q.metal?'dark':'light';m.box([q.x,q.y,-1],[q.w,q.h,2],pc);
   m.label(q.name,[q.x,q.y+(q.u===1?11:side?46:-44),.14],q.w*.80,q.u===1?5.7:6.3,ink);
   if(q.u===3)m.label(side?'SHALLOW':'TW-01',[q.x,q.y+(side?34:-34),.14],q.w*.78,3.3,ink);
   for(const x of [q.x-q.w/2+5,q.x+q.w/2-5])for(const y of q.screwY){column(m,x,y,.04,1.8,1,C.metal);m.box([x,y,1.1],[2.5,.4,.12],C.black,false);}
   const knobMax=side?s.knobLid:s.knobBase,knobs=q.u===1?[[q.x,q.y-5,3.6,7]]:[[q.x,q.y+(side?8:-2),6.2,Math.max(5,knobMax-1.6)],[q.x-q.w*.22,q.y+(side?22:-20),3.6,10],[q.x+q.w*.22,q.y+(side?22:-20),3.6,10]];
   for(const [x,y,r,h] of knobs){column(m,x,y,0,r+.6,1.3,C.metal);column(m,x,y,1.3,r,h,(q.id+side)%5===0?C.copper:C.black);m.box([x,y+r*.4,h+1.45],[.8,r*.6,.2],C.paper,false);}
   for(const j of q.jacks){column(m,j.p[0],j.p[1],0,3.2,2,C.metal);column(m,j.p[0],j.p[1],2.01,1.85,.2,C.black);}
  }
  if(s.structure){
   for(const q of data.modules){const depth=side?24:44;m.box([q.x,q.y,-depth],[q.w-4,q.h*.56,1.6],C.board);m.box([q.x,q.y,-depth+6],[q.w*.5,17,10],C.black);}
   m.box([0,side?-D/2+9:0,-back+5],[d.rail-20,12,1.6],C.board);
   for(let x=-d.rail/2+24;x<d.rail/2-22;x+=30)m.box([x,side?-D/2+9:0,-back+10],[10,10,8],C.black);
  }
  const drawPlug=(a,height,color)=>{
   if(s.elbow){column(m,a[0],a[1],a[2]+2,2.7,height-5,C.black);m.box([a[0],a[1]+(side?4:-4),a[2]+height-3],[6,11,6],color);return FoldModel.plugExit(a,s,side);}
   column(m,a[0],a[1],a[2]+2,2.7,height-2,C.black);column(m,a[0],a[1],a[2]+height-4,2.9,4,color);return FoldModel.plugExit(a,s,side);
  };
  if(s.patch&&s.modules&&!s.structure){
   const plug=side?s.plugLid:s.plugBase,colors=[C.copper,C.blue,C.green,C.yellow];
   for(let ri=0;ri<d.rows.length;ri++){const js=data.jacks.filter(j=>j.row===ri);
    for(let i=0;i<3;i++){const a=js[i*2].p,b=js[Math.min(js.length-1,i*2+3)].p,color=colors[(i+ri+side)%4],pa=drawPlug(a,plug,color),pb=drawPlug(b,plug,color),h=plug+s.bend-2,dy=(side?1:-1)*(14+i*7),c1=[pa[0],pa[1]+dy,h],c2=[pb[0],pb[1]+dy,h],points=[];
     for(let k=0;k<=18;k++){const u=k/18,v=1-u;points.push(pa.map((x,j)=>v*v*v*x+3*v*v*u*c1[j]+3*v*u*u*c2[j]+u*u*u*pb[j]));}m.tube(points,1.25,color,6);
    }
   }
   if(s.cross)for(let i=0;i<2;i++)drawPlug(FoldModel.crossAnchors(s,d)[i][side?'lid':'base'],plug,i?C.yellow:C.blue);
  }
  // Low protective feet; no underside storage pocket.
  const feet=4;
  for(const x of [-W/2+7,W/2-7])for(const y of [-D/2+7,D/2-7])m.box([x,y,-back-feet/2],[12,12,feet],C.guard);
 }
}
