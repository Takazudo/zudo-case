import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const spec = JSON.parse(await readFile(path.join(root,"project/current-spec.json"),"utf8"));
const models = Object.values(spec.models);
const f = (n, d=3) => Number(n.toFixed(d)).toString();
const dims = a => a.map(n=>f(n)).join(" × ");
async function page(rel,title,desc,pos,body) {
  const p=path.join(root,"src/content/docs",rel); await mkdir(path.dirname(p),{recursive:true});
  const text=`---\ntitle: ${JSON.stringify(title)}\ndescription: ${JSON.stringify(desc)}\nsidebar_position: ${pos}\n---\n\n{/* GENERATED: node scripts/sync-reference-tables.mjs / project/current-spec.json */}\n\n${body.trim()}\n`;
  await writeFile(p,text);
}
let i=10;
for (const m of models) {
 const g=m.guards.t1p2, h=m.hardware_counts, l=m.lid_preview;
 const plates=m.plates.map(p=>`| ${p.part} | ${dims(p.size_mm)} | ${p.quantity} | ${p.holes_each} |`).join("\n");
 const catalog=g.catalog.map(p=>`| ${p.name} | ${p.quantity} | ${dims(p.dimensions)} | ${f(p.volumeCm3)} |`).join("\n");
 await page(`models/${m.id}.mdx`,m.label,`本体はR6の名目CAD、載せ蓋はR8プレビュー。${m.id}の寸法と数量。`,i,`
## この機種

${m.id==='7u40'?'**主な確認対象。** リュックへ入れて運ぶ用途を重視する40HPの３列ケース。':'３機種に共通する金属平板と独立レールの構造を使う。'} ${m.id==='3u60'?'レール２本の単列。':'3U＋3U＋1Uは同じ平面に並ぶ。上下二段のケースではない。'}

![R6の組立形状](/assets/images/r6/${m.id}-assembled.png)

## 寸法と数量

| 項目 | 値 |
|---|---|
| 本体アルミ外形 W×D×H | **${dims(m.metal_mm)}mm** |
| 1.2mmガード込み（脚・外側金具を除く） | ${dims(g.outerEnvelopeMm)}mm |
| ガードと仮脚込み（外側金具を除く） | ${dims(g.feetIncludedEnvelopeMm)}mm |
| 実レール長 | ${f(m.rail_length_mm)}mm |
| レールユニット外幅 | ${f(m.rail_frame_width_mm)}mm |
| 全ユニットの前後包絡 | ${f(m.frame_depth_mm,6)}mm |
| 前後板の内面までの片側余白 | ${f(m.front_back_gap_to_metal_mm,6)}mm |
| 上端ガードまでの片側余白 | ${f(m.front_back_gap_to_guard_mm,6)}mm |
| レール本数 | ${h.rail} |
| ブラケット | ${h.panelBracket} |
| レールと外箱のM5締結 | ${h.mountBolt}点 |
| 内側8mmスペーサー／外側1mm座金 | 各${h.innerSpacer}個 |
| 板の穴合計 | ${m.panel_holes}（R6の丸穴。長穴未反映） |

## アルミ本体５枚

| 部品 | サイズmm | 枚数 | 穴数/枚 |
|---|---|---:|---:|
${plates}

材質候補A5052、t1.5、黒アルマイト。外形・板厚は現在の名目値。長穴、穴中心、公差、表面の許容状態を確定してから製作承認する。

## ガード1.2mmの内訳

| 部品 | 数量 | 単体の外接寸法mm | 単体体積cm³ |
|---|---:|---|---:|
${catalog}

合計**${g.partCount}個、${f(g.totalVolumeCm3)}cm³**。1.0mm版は**${f(m.guards.t1p0.totalVolumeCm3)}cm³**。STLは１個ずつ、数量を注文画面へ指定する。

[1.2mm STL一式](https://zudo-case-preview.zudolab.dev/downloads/reference/${m.id}-r6-guards-t1p2-NOT-RELEASED.zip) ／ [1.0mm STL一式](https://zudo-case-preview.zudolab.dev/downloads/reference/${m.id}-r6-guards-t1p0-NOT-RELEASED.zip) ／ [アルミ参考データ](https://zudo-case-preview.zudolab.dev/downloads/reference/${m.id}-r6-aluminum-NOT-RELEASED.zip)

## 蓋はR8の表示寸法

天板：**${dims(l.lidPlateMm)}mm**。蓋の外周：${dims(l.lidOuterMm)}mm。蓋付き高さは脚・模式ねじ頭まで**${f(l.closedHeightIncludingFeetMm)}mm**。バンド・側面ナットの突出は別。

前後の段差を差し込み、真上へ外す。30mmのノブ用高さ、2mm厚の段差、差し込み12mm、片側0.7mmの隙間は現在のプレビュー条件で、実物のフィットを保証しない。

バンド一周の幾何概算：**${f(l.strapLoopGeometricEstimateMm)}mm**。バックルと重なり代は含めていない。

**この載せ蓋の製作用CADは未更新。** R7のロック用枠・前後M3穴を発注しない。[R8プレビュー](../resources/current-preview.mdx)と[発注前ゲート](../verification/before-order.mdx)を確認する。

## 根拠

R6の ${m.sources[0]} と [本体サマリー](/evidence/r6-family-summary.json)、[ガードmanifest](/evidence/${m.id}-t1p2-r6-guard-manifest.json)、[R8パラメータ](/evidence/r8-preview-parameters.json)から表を生成した。今回、新しいCADを検証した値ではない。
 `);
 i+=10;
}
const cmp=models.map(m=>`| ${m.label} | ${dims(m.metal_mm)} | ${dims(m.guards.t1p2.outerEnvelopeMm)} | ${m.hardware_counts.panelBracket} | ${m.hardware_counts.mountBolt} | ${m.guards.t1p2.partCount} | ${f(m.guards.t1p2.totalVolumeCm3)} |`).join("\n");
await page("models/comparison.mdx","３機種の比較","共通値と、機種によって増える板・金具・ガードを一覧にする。",40,`
## 本体の比較

| 機種 | アルミ外形mm | ガード込みmm | 金具 | ケース固定M5 | ガード個数 | 1.2mm体積cm³ |
|---|---|---|---:|---:|---:|---:|
${cmp}

単位mm。ガード込みは脚・外側ナット・蓋・バンドを除く。３機種ともアルミの高さは91mm、レールの側面離隔は8mm、前後の全ユニットからの余白は約8mm。

## 共通部と差分

40HPは実STL長204mm、60HPは305mm。HPの比で引き延ばしていない。3U→7Uは前後方向を長くし、fixerを7Uへ交換、3U padder２個と1U padder１個を各側へ配置する。

3Uは16個の金具と４点の外箱固定、7Uは18個と10点。長い左右板の底辺には中央金具を追加する。ガードの分割数も12→16個へ変わる。

[3U60](./3u60.mdx) ／ [7U40](./7u40.mdx) ／ [7U60](./7u60.mdx)

## 蓋と運搬

全機種でR8の載せ蓋＋バンド２本を採用。蓋高さ30mm、閉じたモデルの高さ128.8mmは共通の表示条件だが、ノブ高さ・締付時の天板のたわみを確認して最終化する。

R8の天板サイズは各機種ページに示した。機種間で同じ部品として注文できるかは、完成したCADのファイルと数量を照合して決める。似た外形だけで同一品へまとめない。

出典：[R6サマリー](/evidence/r6-family-summary.json)、[R8パラメータ](/evidence/r8-preview-parameters.json)。
`);
const counts = (key)=>models.map(m=>m.hardware_counts[key]);
const row=(name,nums,note)=>`| ${name} | ${nums.join(' | ')} | ${note} |`;
const bom=[row('本体アルミ板',counts('aluminumPanel'),'t1.5、黒アルマイト候補'),row('L字ブラケット',counts('panelBracket'),'在庫20×20×16mm、厚2mm'),row('板接合用M5ネジ',counts('panelJointBolt'),'底面は頭を外向き'),row('板接合用ナット',counts('panelJointNut'),'品番・必要ねじ長は別確認'),row('板接合用座金',counts('panelJointWasher'),'モデル上の数量。実部品の厚さと受け面確認'),row('ユニット→ケースM5',counts('mountBolt'),'頭1.4mm、軸長未確定'),row('同ロックナット',counts('mountNut'),'外側'),row('内側8mmスペーサー',counts('innerSpacer'),'内外径は模式値を含む'),row('外側1mmナイロン座金',counts('outerWasher'),'ユニット固定用'),row('ゴム脚',counts('foot'),'φ10×高さ3mmは仮'),row('本体PA12ガード',models.map(m=>m.guards.t1p2.partCount),'1.2mm基本、黒染め候補'),row('蓋アルミ板',[1,1,1],'R8表示寸法、製作図未更新'),row('蓋PA12枠',[4,4,4],'R8の表示分割。発注数量は再CAD後に確定'),row('天板の組立M3',[8,8,8],'R7からの表示上の数量。長さ・ナット座を再確認'),row('外周バンド',[2,2,2],'品番未選定、開閉用のねじロックなし')].join('\n');
await page('manufacturing/bom.mdx','ケース側BOM','レールユニットの費用を除き、本体・蓋・バンドを分けて管理する。',10,`
## ケース１台分の部品

以下の表はR6のhardwareCountsとR8の構成から生成。予備率、破損、予備金具は含めていない。**発注承認済みBOMではなく、数量確認の起点**。

| 部品 | 3U60 | 7U40 | 7U60 | 仕様／状態 |
|---|---:|---:|---:|---|
${bom}

## レール費用の除外

レール、fixer、padder、レール端固定ネジ、モジュール用ナット等のレールユニットの製作費は計算に入れない。数量の参考として、3Uはレール２本/fixer２枚/padder２枚、7Uはレール６本/fixer２枚/padder６枚をモデルに含む。

## まだ数量を確定しないもの

蓋組立用のナット・座金、ガード保持の接着材や爪、当たり材、バンド位置決め、梱包などは最終設計/品番が未確定。R7にあった蓋→本体のM3４本、ナット受けと圧縮スペーサー４個は最終方式には不要。

## 在庫と費用

手持ちL字金具は追加支払0円でも、製品原価には使用数×実仕入単価を入れる。その他の小物も画面上の形状から品番を推測して買わない。ケース側のM5で使う8mmスペーサーと外側座金はレール費用除外とは別に計上する。

出典：[R6サマリー](/evidence/r6-family-summary.json)、各機種のmodel-summary.json、<a href="/evidence/r8-original-readme.md">R8 README</a>。
`);
console.log('Generated 5 reference pages from project/current-spec.json.');
