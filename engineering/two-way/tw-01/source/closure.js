// Cross-section datum: outside metal face y=0; positive y is inside the tray.
function localSide(p,side,d){if(side==='front')return [p[0],-d.D/2+p[1],p[2]];if(side==='back')return [-p[0],d.D/2-p[1],p[2]];if(side==='right')return [d.W/2-p[1],p[0],p[2]];return [-d.W/2+p[1],-p[0],p[2]];}
function normalSide(v,side){if(side==='front')return v;if(side==='back')return [-v[0],-v[1],v[2]];if(side==='right')return [-v[1],v[0],v[2]];return [v[1],-v[0],v[2]];}
function closureSection(s,d,L=100,detail=false){
 const m=new Mesh(),t=d.t,H=d.collarH,z0=d.rim+d.gasket,col=s.highlight?C.copper:C[s.finish];
 // Central wall, aligned above the fixed tray walls.
 m.box([0,t/2,z0+H/2],[L,t,H],col);
 // Separate stock-angle / folded-return envelopes. Metal takes compression; soft strip controls rattle only.
 for(const upper of [false,true]){
  const z=upper?d.G-z0:z0,sgn=upper?-1:1;
  m.box([0,(d.innerLip-d.collarOuter)/2,z+sgn*t/2],[L,d.innerLip+d.collarOuter,t],col);
  // Outer skirt surrounds the guarded tray edge. Inner tongue captures the structural return.
  m.box([0,-1.2-s.seatClearance-t/2,z+sgn*(t-s.overlap/2)],[L,t,s.overlap+2*t],s.highlight?C.blue:C.guard);
  m.box([0,d.seatInner+s.seatClearance+t/2,z+sgn*(t-s.overlap/2)],[L,t,s.overlap+2*t],s.highlight?C.blue:C[s.finish]);
  m.box([0,(t+d.seatInner)/2,z-sgn*d.gasket/2],[L,d.seatInner-t,d.gasket],s.highlight?C.green:C.guard);
 }
 if(detail){
  // Fasteners are representative machine-bolt axes, not a drilling pattern.
  for(const x of [-L*.30,L*.30])for(const z of [z0+5,d.G-z0-5]){
   m.cylinder([x,-1.0,z],[x,t+1.1,z],1.5,C.metal,10);m.cylinder([x,-1.45,z],[x,-1.0,z],2.7,C.metal,12);
  }
 }
 return m;
}
function reinforcedSection(s,d,L=100,back=25){
 const m=new Mesh(),t=d.t,col=C[s.finish];
 m.box([0,t/2,(2-back)/2],[L,t,back+2],col);
 m.box([0,(t+d.seatInner)/2,1],[L,d.seatInner-t,2],s.highlight?C.yellow:C.rail);
 m.box([0,t+1,-5],[L,2,14],s.highlight?C.yellow:C.rail);
 // Local backing strip below the seam, bolted to the fixed wall, not a floating latch plate.
 m.box([0,t+2,-16],[L,2,8],C.rail);
 m.box([0,-.6,-.5],[L,1.2,5],C.guard);
 return m;
}
function addStructureAndGuides(s,d,g){
 for(const side of [0,1]){
  const m=side?g.lid:g.base,back=side?s.lidDepth:s.baseDepth;
  for(const edge of ['front','back','left','right']){
   const section=reinforcedSection(s,d,(edge==='front'||edge==='back'?d.W:d.D)-24,18);
   // Tray walls already exist; only the reinforcement and exterior protective skin are added here.
   // Overlapping solids represent assembled fixed parts, not unioned manufacturing geometry.
   transfer(m,section,p=>localSide(p,edge,d),v=>normalSide(v,edge));
  }
  for(const x of [-d.W*.27,d.W*.27]){
   // Back-face load spreader rails at exactly the strap stations, connected to the front/back wall regions.
   m.box([x,0,-back+d.t+3],[28,d.D-2*d.t,6],s.highlight?C.yellow:C.rail);
   m.box([x,0,-back-1],[28,d.D-12,2],C.guard);
   for(const sign of [-1,1]){
    const y=sign*(d.D/2),z=-back+18;
    // Captured route: two posts and bridge; clear opening 27 mm for 25 mm webbing.
    for(const xx of [x-15,x+15])m.box([xx,y+sign*4,z],[2,8,6],C.guard);
    m.box([x,y+sign*7.5,z],[32,1.5,6],s.highlight?C.green:C.guard);
    m.box([x,y-sign*(d.t+1),z],[36,2,12],C.rail);
   }
  }
  // Corner bumpers below the playing rim, tied to the tray rather than to the loose collar.
  for(const x of [-d.W/2,d.W/2])for(const y of [-d.D/2,d.D/2]){
   m.box([x,y,-back/2],[8,8,back-5],C.guard);
  }
 }
}
function addCollar(s,d,g){
 for(const edge of ['front','back','left','right']){
  const L=(edge==='front'||edge==='back'?d.W:d.D)-24;
  transfer(g,closureSection(s,d,L),p=>localSide(p,edge,d),v=>normalSide(v,edge));
 }
 // At corners, short protected continuations and square tray-index pockets close the side seams.
 for(const sx of [-1,1])for(const sy of [-1,1]){
  const x=sx*(d.W/2-d.t/2),y=sy*(d.D/2-d.t/2),z=d.G/2;
  g.box([x,sy*(d.D/2-6),z],[d.t,12,d.collarH],s.highlight?C.copper:C[s.finish]);
  g.box([sx*(d.W/2-6),y,z],[12,d.t,d.collarH],s.highlight?C.copper:C[s.finish]);
  for(const zz of [d.rim+d.gasket,d.G-d.rim-d.gasket]){
   // The orthogonal returns index against the two tray sides. They do not latch the lid.
   g.box([sx*(d.W/2+2),sy*(d.D/2-6),zz],[2,12,2*s.overlap],s.highlight?C.blue:C.guard);
   g.box([sx*(d.W/2-6),sy*(d.D/2+2),zz],[12,2,2*s.overlap],s.highlight?C.blue:C.guard);
  }
 }
 if(s.collar==='hinged')for(const [sx,sy,a] of [[-1,-1,0],[1,1,Math.PI]]){
  const h=hinge(s,d,90),at=[sx*(d.W/2-5),sy*(d.D/2-5),d.G/2-7.5];
  const rot=p=>[Math.cos(a)*p[0]-Math.sin(a)*p[1],Math.sin(a)*p[0]+Math.cos(a)*p[1],p[2]];
  transfer(g,h,p=>add(rot(p),at),rot);
 }
}
function straps(s,d,m){
 if(!s.straps)return;
 const z0=-s.baseDepth-3.3,z1=d.G+s.lidDepth+3.3;
 for(const x of [-d.W*.27,d.W*.27]){
  for(const z of [z0,z1])m.box([x,0,z],[25,d.D+10,1.2],C.black,false);
  for(const y of [-d.D/2-5,d.D/2+5])m.box([x,y,(z0+z1)/2],[25,1.2,z1-z0],C.black,false);
  const z=-s.baseDepth+33;
  m.box([x,-d.D/2-7,z],[30,5,28],C.textile); // generic protected buckle envelope
  m.box([x,-d.D/2-9.8,z],[34,1.4,34],C.guard,false); // soft hood, not an exposed arm
  m.box([x,-d.D/2-6,z+30],[25,1.4,28],C.textile,false); // retained short tail envelope
 }
}
function hinge(s,d,angle=90){
 const m=new Mesh(),R=3,T=1.5,H=15,offset=-2.3;
 // Four knuckle envelopes follow the pictured hinge count. Diameter and leaf thickness are assumptions.
 for(let i=0;i<4;i++)m.cylinder([0,0,i*H/4+.1],[0,0,(i+1)*H/4-.1],R,C.metal,14);
 const leaf=new Mesh();
 leaf.box([16.75,offset,7.5],[27.5,T,15],C.metal);
 leaf.cylinder([30.5,offset-T/2,7.5],[30.5,offset+T/2,7.5],7.5,C.metal,20);
 // Unknown bore diameter/edge offsets: 4 mm / 13 and 28 mm from axis in the sizing model.
 for(const x of [13,28]){
  leaf.cylinder([x,offset-T/2-.12,7.5],[x,offset-T/2-.02,7.5],3.2,C.rail,16);
  leaf.cylinder([x,offset-T/2-.17,7.5],[x,offset-T/2-.13,7.5],2,C.black,16);
 }
 transfer(m,leaf,p=>p);
 const a=rad(angle-180),rot=p=>[Math.cos(a)*p[0]-Math.sin(a)*p[1],Math.sin(a)*p[0]+Math.cos(a)*p[1],p[2]];
 transfer(m,leaf,p=>rot([-p[0],p[1],p[2]]),v=>rot([-v[0],v[1],v[2]]));
 return m;
}
function hingeStudy(s,d,g){
 transfer(g.world,hinge(s,d,s.hingeAngle),p=>add(p,[0,0,2]));
 // Reference ruler, separate from the real hinge shape.
 g.world.box([0,-25,-1],[76,.5,.5],C.rail);
 for(const x of [-38,38])g.world.box([x,-25,0],[.6,5,2],C.rail);
 g.world.label('76 mm OPEN',[0,-34,.2],70,5,'dark');
 g.world.label('15 mm WIDE / 15 mm HOLE PITCH',[0,40,.2],110,5,'dark');
}
function jointStudy(s,d,g){
 const L=120,lift=s.jointLift;
 transfer(g.base,reinforcedSection({...s,highlight:true},d,L,24),p=>p);
 transfer(g.world,reinforcedSection({...s,highlight:true},d,L,24),p=>[p[0],p[1],d.G-p[2]+2*lift],v=>[v[0],v[1],-v[2]]);
 transfer(g.ring,closureSection({...s,highlight:true},d,L,true),p=>add(p,[0,0,lift]));
 // Strap route shown outboard, same role as the whole-case loop. Ends are clipped section boundaries.
 if(s.straps){g.world.box([0,-5,(d.G+2*lift)/2],[25,1.2,d.G+2*lift+48],C.black,false);for(const z of [-16,d.G+16+2*lift]){for(const x of [-15,15])g.world.box([x,-4,z],[2,8,6],C.guard);g.world.box([0,-7.5,z],[32,1.5,6],C.green);}}
 // Representative inner module front envelopes: remain outside the seam features.
 g.envBase.box([0,30,d.qBase/2],[L,30,d.qBase],C.copper);
 g.envLid=new Mesh();
 // Thin panel edge depicts local available clearance, not a particular module PCB.
 g.base.box([0,32,-1],[L,36,2],C.paper);
 g.world.box([0,32,d.G+1+2*lift],[L,36,2],C.paper);
}
function storage(s,d,g,at=[0,0,0],showStand=true){
 if(showStand){
  const st=new Mesh();packedStand(st,s,d,[0,0,0]);transfer(g,st,p=>add(p,at));
  g.box([at[0],at[1],at[2]+.4],[d.W,d.D,.8],C.textile,false);
 }
}
function partsStudy(s,d,g){
 // Exploded collar panels shown separately in order. Each profile is retained in the mesh.
 for(let i=0;i<4;i++){
  const L=(i%2?d.D:d.W)-24,section=closureSection({...s,highlight:true},d,L);
  // Turn the strip onto its outside face; height becomes the sheet's short planar dimension.
  const at=[0,(i-1.5)*(d.collarH+2*s.overlap+22),16];
  transfer(g.ring,section,p=>[p[0]+at[0],p[2]-d.G/2+at[1],p[1]+at[2]],v=>[v[0],v[2],v[1]]);
 }
 if(s.collar==='hinged')for(let i=0;i<2;i++)transfer(g.world,hinge(s,d,180),p=>add(p,[d.W/2+70,(i-.5)*80,0]));
}
function trunkStudy(s,d,g){
 const m=g.world,W=s.trunkW,D=s.trunkD,H=s.trunkH,wall=5,z0=d.coreFloor-s.foam,foam=C.foam||[.45,.48,.44],col=[.36,.39,.39];
 // Requested values are INSIDE the trunk. Front and right walls are cut down solely for visibility.
 m.box([0,0,z0-wall/2],[W+2*wall,D+2*wall,wall],col);
 m.box([0,D/2+wall/2,z0+H/2],[W+2*wall,wall,H],col);
 m.box([-W/2-wall/2,0,z0+H/2],[wall,D,H],col);
 m.box([0,-D/2-wall/2,z0+10],[W+2*wall,wall,20],col);
 m.box([W/2+wall/2,0,z0+10],[wall,D,20],col);
 // Bottom cushion; pads at both populated bodies avoid treating the lid as an empty cover.
 m.box([0,0,z0+s.foam/2],[W,D,s.foam],foam,false);
 const minX=d.W/2+4,minY=d.D/2+4,bodyZ=[-s.baseDepth/2,d.G+s.lidDepth/2];
 for(const zz of bodyZ)for(const sx of [-1,1])for(const sy of [-1,1]){
  const spanX=Math.max(.1,W/2-minX),spanY=Math.max(.1,D/2-minY);
  // Corner-contoured blocks reach the structural bumper faces. Buckle / guide routes remain relieved.
  m.box([sx*(minX+spanX/2),sy*(d.D/2-10),zz],[spanX,24,24],foam,false);
  m.box([sx*(d.W/2-12),sy*(minY+spanY/2),zz],[24,spanY,24],foam,false);
 }
 // A separate accessory sleeve on an open trunk-lid study. This is an EXPLODED view of the H budget.
 // Fixed closed volume allowance is computed separately; no actual trunk hinge/organizer is specified.
 const st=new Mesh();packedStand(st,s,d,[0,0,0]);
 const accessoryZ=z0+H+20;
 m.box([0,0,accessoryZ-1.5],[d.W+6,d.D+6,3],C.textile,false);
 transfer(m,st,p=>add(p,[0,0,accessoryZ]));
 for(const x of [-d.W/2-10,d.W/2+10])m.tube([[x,0,d.G+s.lidDepth+4+d.separator],[x,0,accessoryZ]],.4,C.rail,4);
}
function buildGeometry(s,d){
 const g={base:new Mesh(),lid:new Mesh(),world:new Mesh(),envBase:new Mesh(),envLid:new Mesh(),ring:new Mesh()};
 if(s.pose==='frame'){sourceFrame(g.base,s,d,s.frameExplode);return g;}
 if(s.pose==='hinge'){hingeStudy(s,d,g);return g;}
 if(s.pose==='joint'){jointStudy(s,d,g);return g;}
 if(s.pose==='packing'){
  outline(g.world,d,-2);storage(s,d,g.world,[0,0,0],true);
  return g;
 }
 if(s.pose==='parts'){partsStudy(s,d,g);return g;}
 trays(s,d,g);addStructureAndGuides(s,d,g);
 if(['closed','trunk'].includes(s.pose)){addCollar(s,d,g.ring);straps(s,d,g.world);}
 if(s.pose==='play'){
  assembledStand(g.world,s,d);
  // No attached pocket and no extra pedestal. The spacer goes back into the emptied trunk.
  // Loose strap bundles remain accounted for, shown on the table beside the base.
  for(let i=0;i<2;i++)g.world.cylinder([d.W/2+30,-d.D/2+35+i*60,d.floor+1],[d.W/2+30,-d.D/2+35+i*60,d.floor+26],20,C.textile,18);
 }
 if(s.pose==='trunk')trunkStudy(s,d,g);
 if(s.cross&&s.patch&&s.modules&&!s.structure)for(let i=0;i<2;i++)g.world.tube(M.catmull(M.cableRoute(s,d,i),9),1.25,i?C.yellow:C.blue,6);
 g.envBase.box([0,0,d.qBase/2],[d.hp*5.08,d.frameD-5,d.qBase],C.copper);
 g.envLid.box([0,0,d.qLid/2],[d.hp*5.08,d.frameD-5,d.qLid],C.blue);
 return g;
}
root.FoldGeometry={buildGeometry,transfer,prismYZ,closureSection,reinforcedSection,hinge,packedStand,sideCheek,localSide,normalSide};
})(typeof window!=='undefined'?window:globalThis);
