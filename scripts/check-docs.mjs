import { readFile, readdir, mkdir, writeFile, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const docs=path.join(root,'src/content/docs');
const errors=[], warnings=[], nav=[];let localLinks=0;
const assert=(v,s)=>{if(!v)errors.push(s);};
const near=(a,b)=>Math.abs(a-b)<0.00002;
const json=async p=>JSON.parse(await readFile(path.join(root,p),'utf8'));
async function exists(p){try{await access(p);return true;}catch{return false;}}
async function walk(p){let out=[];for(const e of await readdir(p,{withFileTypes:true})){const q=path.join(p,e.name);if(e.isDirectory())out.push(...await walk(q));else if(e.name.endsWith('.mdx'))out.push(q);}return out.sort();}
const all=await walk(docs), groups=new Map();
for(const p of all){
 const rel=path.relative(docs,p).split(path.sep).join('/'), text=await readFile(p,'utf8');
 const match=text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
 if(!match){errors.push(`${rel}: frontmatterなし`);continue;}
 const fm={};
 for(const ln of match[1].split('\n')){const m=ln.match(/^(title|description|sidebar_position):\s*(.+)$/);if(!m)continue;try{fm[m[1]]=JSON.parse(m[2]);}catch{fm[m[1]]=m[2];}}
 assert(typeof fm.title==='string'&&fm.title.length>0,`${rel}: title必須`);
 assert(typeof fm.description==='string'&&fm.description.length>0,`${rel}: description必須`);
 assert(typeof fm.sidebar_position==='number',`${rel}: sidebar_positionは数値`);
 nav.push({path:rel,...fm});
 const parent=path.dirname(rel);if(!groups.has(parent))groups.set(parent,[]);groups.get(parent).push({rel,pos:fm.sidebar_position});
 let fenced=false, admonitions=0;const content=[];
 for(const line of text.slice(match[0].length).split('\n')){
  if(/^\s*```/.test(line)){fenced=!fenced;continue;}if(fenced)continue;
  if(/^\s*:::\s*(?:warning|note|tip|danger|info)/.test(line))admonitions++;
  else if(/^\s*:::\s*$/.test(line))admonitions--;
  assert(admonitions>=0,`${rel}: admonition閉じ過ぎ`);
  assert(!/^#\s/.test(line),`${rel}: H1はfrontmatterで生成`);
  content.push(line);
 }
 assert(!fenced,`${rel}: コードフェンス未閉鎖`);assert(admonitions===0,`${rel}: admonition未閉鎖`);
 const body=content.join('\n');
 assert(!/sandbox:\/|\/workspace\/scratch\/|\/mnt\/data\//.test(body),`${rel}: 実行環境固有URLが本文に残る`);
 const urls=[...body.matchAll(/!?\[[^\]\n]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g)].map(m=>m[1]);
 urls.push(...[...body.matchAll(/(?:src|href)=["']([^"']+)["']/g)].map(m=>m[1]));
 for(let u of urls){
  if(/^(?:https?:|mailto:|data:|#)/i.test(u))continue;
  u=decodeURIComponent(u.split(/[?#]/)[0]);if(!u)continue;
  let dest=u.startsWith('/')?path.join(root,'public',u.slice(1)):path.resolve(path.dirname(p),u);
  if(u.startsWith('/docs/')){const route=u.slice(6).replace(/\/$/,'');const c=[path.join(docs,route+'.mdx'),path.join(docs,route,'index.mdx')];dest=(await exists(c[0]))?c[0]:c[1];}
  localLinks++;assert(await exists(dest),`${rel}: リンク先なし ${u}`);
 }
}
// A category index belongs to the root navigation, not its own child position set.
for(const [parent,items]of groups){
 assert(await exists(path.join(docs,parent,'index.mdx')),`${parent}: カテゴリーindex.mdxなし`);
 const ps=items.filter(x=>!x.rel.endsWith('/index.mdx')).map(x=>x.pos);
 assert(new Set(ps).size===ps.length,`${parent}: sidebar_position重複`);
}
const catPos=nav.filter(x=>x.path.endsWith('/index.mdx')).map(x=>x.sidebar_position);
assert(new Set(catPos).size===catPos.length,'カテゴリのsidebar_position重複');
const s=await json('project/current-spec.json'), release=await json('project/release-state.json');
assert(release.production_approved===false,'この引継ぎ版を製造承認へ変更しないでください');
assert(release.current_lid_manufacturing===null,'R8製作データは未生成のはずです');
assert(release.published_release_files.length===0,'承認済みファイルを宣言しています');
const releaseEntries=await readdir(path.join(root,'engineering/release'));
assert(releaseEntries.every(x=>x==='README.md'),'release/に未承認データを置かないでください');
for(const [key,m]of Object.entries(s.models)){
 const a=s.adopted,t=m.metal_thickness_mm;
 assert(near(m.metal_mm[0],m.rail_length_mm+4*a.pcb_thickness_mm+2*a.side_spacer_mm+2*t),`${key}: 積層幅不一致`);
 assert(m.plates.reduce((n,p)=>n+p.quantity,0)===5,`${key}: 本体は5枚`);
 assert(m.plates.reduce((n,p)=>n+p.quantity*p.holes_each,0)===m.panel_holes,`${key}: パネル穴数不一致`);
 assert(m.joint_holes+m.hardware_counts.mountBolt===m.panel_holes,`${key}: 締結数不一致`);
 assert(m.hardware_counts.panelBracket*2===m.joint_holes,`${key}: ブラケットと接合穴数不一致`);
 for(const [v,g]of Object.entries(m.guards)){
  assert(g.catalog.reduce((n,p)=>n+p.quantity,0)===g.partCount,`${key}/${v}: ガード数量不一致`);
  assert(near(g.catalog.reduce((n,p)=>n+p.quantity*p.volumeCm3,0),g.volumeCm3),`${key}/${v}: ガード体積不一致`);
 }
 assert(m.manufacturing_release===null,`${key}: manufacturing releaseが空でない`);
}
const q=await json('project/quote-records.json');const actual=q.records.find(x=>x.id==='Q-R3-001');
assert(actual.rows.reduce((n,x)=>n+x.row_jpy,0)===actual.total_jpy,'R3見積の加算不一致');
assert(q.current_total_jpy===null,'現在総額は未見積のはずです');
nav.sort((a,b)=>a.path.localeCompare(b.path));
await writeFile(path.join(root,'project/navigation.json'),JSON.stringify(nav,null,2)+'\n');
const report={checkedAt:new Date().toISOString(),tool:'dependency-free static/document consistency check',
 officialZudoDocBuild:'not-run-in-this-check',mdxCompiler:'not-run-in-this-check',
 mdxPages:all.length,categories:groups.size,localLinksChecked:localLinks,errors,warnings,
 note:'リンク先の存在・frontmatter・数量/寸法の算術を確認。MDXコンパイル、機構の強度・干渉、発注適合の検証ではありません。'};
await mkdir(path.join(root,'project/validation'),{recursive:true});
await writeFile(path.join(root,'project/validation/static-check.json'),JSON.stringify(report,null,2)+'\n');
if(errors.length){console.error(errors.join('\n'));process.exitCode=1;}else console.log(`OK: ${all.length} MDX / ${groups.size}カテゴリ / ${localLinks}内部リンク。公式ビルド・MDXコンパイルはこの検査の対象外です。`);
