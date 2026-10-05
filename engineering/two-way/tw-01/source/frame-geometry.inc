// Fixed source-frame meshes; all sources are embedded, no network dependency.
function sourceFrame(m,s,d,explode=0){
 const parts=root.FoldFrame.parts(s,d,explode),study=s.pose==='frame';
 const palette={rail:study?[.25,.30,.32]:C.frame,padder:study?C.copper:C.board,fixer:study?C.blue:C.frame,spacer:study?C.green:C.guard,washer:C.guard,head:C.metal,nut:C.metal,railEnd:C.metal,shaft:C.metal};
 for(const p of parts){const color=palette[p.role]||C.guard;
  if(p.type==='solid'){
   for(let i=0;i<p.indices.length;i+=3){const ids=p.indices.slice(i,i+3);if(p.flip)[ids[1],ids[2]]=[ids[2],ids[1]];m.tri(...ids.map(j=>p.positions.slice(j*3,j*3+3)),color);}
   // Sparse exterior edges only; never paint schematic rails over the source mesh.
   if(p.sourceEdges)for(let i=0;i<p.sourceEdges.length;i+=3)m.edges.push(...root.FoldFrame.transform(p.sourceEdges.slice(i,i+3),p.matrix));
  }else if(p.type==='tube'){
   const N=p.role==='nut'?6:14;
   if(!p.inner){m.cylinder([p.x0,p.y,p.z],[p.x1,p.y,p.z],p.outer,color,N);continue;}
   for(let i=0;i<N;i++){
    const a=i/N*Math.PI*2,b=(i+1)/N*Math.PI*2;
    const q=(x,r,t)=>[x,p.y+r*Math.cos(t),p.z+r*Math.sin(t)];
    m.quad(q(p.x0,p.outer,a),q(p.x0,p.outer,b),q(p.x1,p.outer,b),q(p.x1,p.outer,a),color);
    m.quad(q(p.x0,p.inner,b),q(p.x0,p.inner,a),q(p.x1,p.inner,a),q(p.x1,p.inner,b),color);
    m.quad(q(p.x0,p.inner,a),q(p.x0,p.inner,b),q(p.x0,p.outer,b),q(p.x0,p.outer,a),color);
    m.quad(q(p.x1,p.inner,b),q(p.x1,p.inner,a),q(p.x1,p.outer,a),q(p.x1,p.outer,b),color);
   }
  }else if(p.type==='guard'){
   // Hollow-cover wall detail is unresolved. This outside skin protects the
   // schematic nut + shaft envelope and is counted in the transport width.
   const wall=p.sign*d.W/2;
   for(let i=0;i<8;i++){
    const a=i/8*Math.PI/2,b=(i+1)/8*Math.PI/2;
    const q=(t,f)=>[wall+p.sign*(2+6*Math.sin(t)),p.y+p.outer*Math.cos(t)*Math.cos(f),p.z+p.outer*Math.cos(t)*Math.sin(f)];
    for(let j=0;j<16;j++){const f=j/16*Math.PI*2,g=(j+1)/16*Math.PI*2;m.quad(q(a,f),q(a,g),q(b,g),q(b,f),C.guard);}
   }
   m.cylinder([wall,p.y,p.z],[wall+p.sign*2,p.y,p.z],p.outer,C.guard,16);
  }
 }
 if(study){m.label(`${d.rail} mm / ${d.hp}HP  ·  SOURCE RAIL`,[0,-d.frameD/2-16,2],Math.min(d.rail,270),7,'dark');}
}
