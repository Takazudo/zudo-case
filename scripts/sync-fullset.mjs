import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
const root=process.cwd(),base='engineering/r10-fullset-01/out',check=process.argv.includes('--check');
const read=p=>readFileSync(path.join(root,p)),json=p=>JSON.parse(read(p)),hash=b=>createHash('sha256').update(b).digest('hex'),encode=x=>JSON.stringify(x,null,2)+'\n';
function put(p,b){if(check){if(!read(p).equals(Buffer.from(b)))throw Error('R10 drift: '+p)}else{mkdirSync(path.dirname(p),{recursive:true});writeFileSync(p,b)}}
const m=json(base+'/outputs-manifest.json'),selected=json(base+'/selected-order.json');
if(selected.production_approved!==false||selected.profile!=='7u40-t1-groove1p70-m5')throw Error('Wrong fullset profile');
for(const input of m.inputs)if(hash(read(input.path))!==input.sha256)throw Error('Stale source: '+input.path);
for(const f of m.files){const b=read(base+'/'+f.path);if(hash(b)!==f.sha256||b.length!==f.bytes)throw Error('Changed output '+f.path);if(b.length>25*1024*1024)throw Error('25MiB exceeded');if(f.path==='preview.html')put('public/previews/r10-fullset-01.html',b);if(f.path.endsWith('.zip'))put('public/downloads/candidate/'+f.path,b)}
const pointer={revision:'R10-FULLSET-01',model:'7u40',profile:selected.profile,production_approved:false,manifest_path:base+'/selected-order.json',manifest_sha256:hash(read(base+'/selected-order.json')),preview:'/previews/r10-fullset-01.html',packages:['aluminum','pa12','home-print'].map(k=>'/downloads/candidate/R10-FULLSET-01-'+k+'.zip'),quantities:{aluminum:6,pa12:20,new_home_print:72,reused_circular_washers:20},interface:selected.interface};
for(const p of ['project/release-state.json','project/current-spec.json']){const d=json(p);d.current_fullset_candidate=pointer;put(p,encode(d))}
console.log('R10 selected fullset '+(check?'verified':'synchronized'));
const docPath='src/content/docs/design/r10-fullset-01.mdx';let doc=read(docPath).toString();
const packages=`| 区分 | 選定数量 | データ |\n|---|---:|---|\n`+[['aluminum','A5052 t1.5・加工後黒アルマイト',selected.parts.filter(p=>p.procurement==='aluminum').reduce((n,p)=>n+p.quantity,0),'枚'],['pa12','MJF PA12-HP・黒染め',selected.parts.filter(p=>p.procurement==='pa12').reduce((n,p)=>n+p.quantity,0),'個'],['home-print','家庭・黒ASA',selected.parts.reduce((n,p)=>n+(p.selected_print_quantity||0),0),'個']].map(([d,label,n,unit])=>`| ${label} | ${n}${unit} | <PreviewLink path="/downloads/candidate/R10-FULLSET-01-${d}.zip">${d}一式</PreviewLink> |`).join('\n');
const washerParams=json('engineering/r10-fullset-01/washers.json').types;
const washers='| 形状ID | 幅×長さ×厚さ mm | 穴径 mm | 偏心 mm | 選定家庭印刷数 |\n|---|---|---:|---:|---:|\n'+selected.parts.filter(p=>p.selected_print_quantity>0).map(p=>{const w=washerParams[p.id];return `| ${p.id} | ${w.width} × ${w.length} × ${w.thickness} | ${w.hole_diameter} | ${w.eccentricity} | ${p.selected_print_quantity} |`}).join('\n');
for(const [key,value] of [['PACKAGES',packages],['WASHERS',washers]])doc=doc.replace(new RegExp(`(\\{/\\* FULLSET-${key}-BEGIN \\*/\\})[\\s\\S]*?(\\{/\\* FULLSET-${key}-END \\*/\\})`),`$1\n${value}\n$2`);
put(docPath,doc);
