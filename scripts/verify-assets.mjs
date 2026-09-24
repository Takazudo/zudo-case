import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(await readFile(path.join(root,'project/artifact-manifest.json'),'utf8'));
const failures=[];let count=0,total=0;
for(const item of manifest.files){
 const p=path.resolve(root,item.path);
 if(!p.startsWith(path.resolve(root)+path.sep)){failures.push(`不正なパス: ${item.path}`);continue;}
 try{
  const s=await stat(p);const data=await readFile(p);const digest=createHash('sha256').update(data).digest('hex');
  if(s.size!==item.bytes||digest!==item.sha256)failures.push(`差分: ${item.path}`);
  count++;total+=s.size;
 }catch(e){failures.push(`読み込み不可: ${item.path}: ${e.message}`);}
}
if(failures.length){console.error(failures.join('\n'));console.error('意図的な更新なら新しい版・変更記録・検証を作ってください。このツールは基準値を上書きしません。');process.exitCode=1;}
else console.log(`OK: ${count}資産、${total} bytes、SHA-256一致。これは引継ぎ時のファイル同一性検査で、機械設計の妥当性検証ではありません。`);
