/* Original zudo-case rail/frame arrangement. No rail scaling or PCB trimming.
 * All coordinates mm. Hardware dimensions other than fixed stack are schematic.
 */
(function(root){
'use strict';
const D=root.ZudoFrameData;
function arrangement(layout){
 if(layout===3)return [{kind:'3u',offset:0}];
 if(layout===6)return [{kind:'3u',offset:-(D.units['3u'].length+1)/2},{kind:'3u',offset:(D.units['3u'].length+1)/2}];
 if(layout===7)return [{kind:'7u',offset:0}];
 throw new Error('No source frame for layout '+layout);
}
function describe(layout,rail,t){
 const units=arrangement(layout),depth=Math.max(...units.map(i=>i.offset+D.units[i.kind].length/2))-Math.min(...units.map(i=>i.offset-D.units[i.kind].length/2));
 const rearReach=Math.max(...units.map(i=>D.units[i.kind].rearReach));
 const counts={rail:0,fixer:0,padder:0,spacer:0,mount:0,railEnd:0};
 const rows=[];
 for(const i of units){const u=D.units[i.kind];counts.rail+=u.rails.length;counts.fixer+=2;counts.padder+=u.padders.length*2;counts.spacer+=u.mounts.length*2;counts.mount+=u.mounts.length*2;counts.railEnd+=u.rails.length*2;
  u.rowY.forEach((y,k)=>rows.push({u:u.rowHeights[k]>100?3:1,y:i.offset+y,h:u.rowHeights[k],screwY:u.rails.slice(k*2,k*2+2).map(r=>i.offset+r[0]-u.length/2)}));
 }
 return {units,depth,rearReach,width:rail+6.4,caseDepth:Math.ceil(depth+16+3)+2*(t-1.5),rows,counts,
   sourceCommit:D.commit,railGeometry:'exact-source-mesh',pcbGeometry:'source-exterior-and-placement; rounded cutouts approximated for display',pcbManufacturingApproved:false,description:layout===6?'Two unchanged 3U frames / 1 mm assembly gap':layout===7?'Original 7U fixer / 3U + 3U + 1U padders':'Original 3U fixer + 3U padder',
   minimumLidDepthWith3mmFloorMargin:rearReach+t+3};
}
function transform(p,m){return [m[0]*p[0]+m[1]*p[1]+m[2]*p[2]+m[3],m[4]*p[0]+m[5]*p[1]+m[6]*p[2]+m[7],m[8]*p[0]+m[9]*p[1]+m[10]*p[2]+m[11]];}
function bounds(pos){const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];for(let i=0;i<pos.length;i+=3)for(let j=0;j<3;j++){lo[j]=Math.min(lo[j],pos[i+j]);hi[j]=Math.max(hi[j],pos[i+j]);}return {min:lo,max:hi,size:lo.map((x,j)=>hi[j]-x)};}
function parts(s,d,explode=0){
 const out=[],L=d.rail,F=L+6.4;
 function solid(id,role,data,matrix,flip=false){const pos=[];for(let i=0;i<data.positions.length;i+=3)pos.push(...transform(data.positions.slice(i,i+3),matrix));out.push({id,role,type:'solid',positions:pos,indices:data.indices,sourceEdges:data.edges,matrix,flip,bounds:bounds(pos),sourceBlobSHA:data.sourceBlobSHA,sourceCommit:D.commit});}
 function axial(id,role,x0,x1,y,z,outer,inner=0){const lo=Math.min(x0,x1),hi=Math.max(x0,x1);out.push({id,role,type:'tube',x0:lo,x1:hi,y,z,outer,inner,bounds:{min:[lo,y-outer,z-outer],max:[hi,y+outer,z+outer],size:[hi-lo,2*outer,2*outer]}});}
 for(const [n,inst] of d.frame.units.entries()){
  const u=D.units[inst.kind],yc=inst.offset-u.length/2,T=u.top;
  u.rails.forEach(([a,b],i)=>{const sy=i%2?1:-1;solid(`u${n}-rail${i}`,'rail',D.rails[String(d.hp)],[0,0,sy,-sy*L/2,0,sy,0,yc+a-sy*6.7535858154296875,-1,0,0,T-b+14.930564880371094]);});
  for(const sign of [-1,1]){
   function panel(kind,start,offsetU,offsetV,role,id,mult){
    const x=Math.min(sign*start,sign*(start+1.6))+sign*explode*mult;
    solid(`u${n}-${sign}-${id}`,role,D.panels[kind],[1,0,0,x,0,1,0,yc+offsetU,0,0,-1,T-offsetV],true);
   }
   u.padders.forEach((p,i)=>panel(p.kind,L/2,p.u,p.v,'padder','padder'+i,1));
   panel(u.fixer,L/2+1.6,0,0,'fixer','fixer',2);
   u.mounts.forEach(([a,b],i)=>{
    const y=yc+a,z=T-b,stem=`u${n}-${sign}-mount${i}`,seat=sign*(L/2+1.6),wall=sign*d.W/2;
    axial(stem+'-spacer','spacer',sign*F/2+sign*3*explode,sign*(F/2+8)+sign*3*explode,y,z,5,2.75);
    axial(stem+'-washer','washer',wall+sign*4*explode,wall+sign*(1+4*explode),y,z,5,2.75);
    axial(stem+'-head','head',seat-sign*1.4+sign*2*explode,seat+sign*2*explode,y,z,4.5);
    if(!explode)axial(stem+'-shaft','shaft',seat,wall+sign*6.8,y,z,2.5);
    axial(stem+'-nut','nut',wall+sign*(1+5*explode),wall+sign*(6+5*explode),y,z,4.62,2.5);
    if(s.pose!=='frame')out.push({id:stem+'-guard',role:'mountGuard',type:'guard',sign,x:wall+sign*4,y,z,outer:8,depth:8});
   });
   u.rails.forEach(([a,b],i)=>{
    const y=yc+a,z=T-b,seat=sign*F/2+sign*2*explode;
    axial(`u${n}-${sign}-end${i}`,'railEnd',seat,seat+sign*1.4,y,z,4.5);
    // Shaft length is viewing-only; source M5 length was also provisional.
    if(!explode)axial(`u${n}-${sign}-endshaft${i}`,'shaft',seat-sign*14,seat,y,z,2.5);
   });
  }
 }
 return out;
}
root.FoldFrame={describe,parts,transform,bounds,data:D};
})(typeof window!=='undefined'?window:globalThis);
