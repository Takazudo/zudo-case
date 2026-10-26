import {readFileSync,writeFileSync,mkdirSync,copyFileSync,readdirSync,statSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,relative} from 'node:path';
const root=resolve(import.meta.dirname,'..'),build=resolve(process.argv[2]??'.cache/printed-p4-final');
const base='engineering/printed-5mm/p4-uniform-vents',project='project/printed-5mm/p4-uniform-vents';
mkdirSync(resolve(root,base,'out'),{recursive:true});mkdirSync(resolve(root,project),{recursive:true});
const files=[];
function copy(src,dest){mkdirSync(resolve(root,dest,'..'),{recursive:true});copyFileSync(resolve(build,src),resolve(root,dest));files.push(dest);}
for(const ext of ['stl','step'])for(const f of readdirSync(resolve(build,ext)))copy(`${ext}/${f}`,`${base}/out/${ext}/${f}`);
for(const name of ['BOM.json','DIMENSIONS.json','PRINT-PARTS.csv','PRINT-START-HERE.md','accepted-geometry-comparison.json','VENTILATION.json','PRINT-MAPPING.json'])copy(name,`${base}/out/${name}`);
for(const name of ['geometry-checks.json','rail-geometry-checks.json','print-bed-checks.json'])copy(`evidence/${name}`,`${base}/out/${name}`);
copy('reference/RAIL-PLACEMENT.json',`${base}/out/RAIL-PLACEMENT.json`);
copy('zudo-case-printed-5mm-p4-uniform-vents.html','public/previews/printed-5mm-p4-uniform-vents.html');
for(const name of ['printed-5mm-p4-uniform-vents-stl.zip','printed-5mm-p4-uniform-vents-source.zip'])copy(name,`public/downloads/candidate/${name}`);
// Source and receipts are also registered; runtime caches never are.
function walk(dir){for(const entry of readdirSync(resolve(root,dir),{withFileTypes:true})){if(['out','.venv','__pycache__'].includes(entry.name))continue;const path=`${dir}/${entry.name}`;if(entry.isDirectory())walk(path);else files.push(path);}}
walk(base);
const registry={revision:'P4-PRINTED-5MM-UNIFORM-VENTS',model:'7u40',status:'HOME_PRINT_CANDIDATE_NOT_PHYSICALLY_VERIFIED',print_parts:{structural:12,optional_types:3},optional_quantities:{'pad-horizontal':48,'pad-vertical':48,'washer-round':28},files:files.sort().map(path=>{const data=readFileSync(resolve(root,path));return {path,bytes:data.length,sha256:createHash('sha256').update(data).digest('hex')};})};
writeFileSync(resolve(root,project,'files.json'),JSON.stringify(registry,null,2)+'\n');
