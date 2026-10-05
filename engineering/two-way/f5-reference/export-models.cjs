/* F5 setups and viewing meshes. Frames remain fixed source-size. */
'use strict';
const fs=require('node:fs'),path=require('node:path');
require('./source/frame-data.js');require('./source/frame.js');require('./source/model.js');require('./source/renderer.js');require('./source/geometry.js');
const M=FoldModel,dir=path.join(__dirname,'models');fs.mkdirSync(dir,{recursive:true});
const base=id=>{const p=M.presets[id];return {...M.defaults,preset:id,baseDepth:p.baseDepth,lidDepth:p.lidDepth};};
const jobs=[];
for(const [id,p] of Object.entries(M.presets)){
 for(const profile of Object.keys(M.profiles))for(const collar of ['loose','hinged']){
  const pro=M.profiles[profile],s={...base(id),pose:'closed',profile,collar};
  for(const k of ['gap','plugBase','plugLid','bend','knobBase','knobLid','elbow'])s[k]=pro[k];
  fs.writeFileSync(path.join(dir,`${p.letter}-${profile}-${collar}-F5.json`),JSON.stringify(M.config(s),null,2)+'\n');
 }
 const inspection={...base(id),pose:'frame'};
 fs.writeFileSync(path.join(dir,`${p.letter}-frame-F5.json`),JSON.stringify(M.config(inspection),null,2)+'\n');
 for(const pose of ['frame','play']){
  const s={...base(id),pose},d=M.dimensions(s),g=FoldGeometry.buildGeometry(s,d),out={units:'mm',manufacturingApproved:false,caseFamily:p.letter,pose,sourceCommit:d.frame.sourceCommit,railGeometry:d.frame.railGeometry,pcbGeometry:d.frame.pcbGeometry,groups:{}};
  for(const key of ['base','lid','world','ring']){
   const v=g[key].v,arr=[];for(let i=0;i<v.length;i+=9){const a=v.slice(i,i+3),n=v.slice(i+3,i+6);arr.push(...(key==='lid'?M.lidPoint(a,s,d):a),...(key==='lid'?M.lidNormal(n,s):n),...v.slice(i+6,i+9));}out.groups[key]=arr;
  }
  const slug=`${p.letter}-${pose}`;fs.writeFileSync(path.join(dir,`${slug}-mesh-tmp.json`),JSON.stringify(out));jobs.push(slug);
 }
}
fs.writeFileSync(path.join(dir,'export-jobs.json'),JSON.stringify(jobs));
console.log('15 setups and six intermediate frame/playing meshes generated.');
