import { readFile, writeFile, mkdir, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

function renderLegacyPages(spec) {
const pages = [];
const models = Object.values(spec.models);
const f = (n, d=3) => Number(n.toFixed(d)).toString();
const dims = a => a.map(n=>f(n)).join(" × ");
function page(rel,title,desc,pos,body) {
  const text=`---\ntitle: ${JSON.stringify(title)}\ndescription: ${JSON.stringify(desc)}\nsidebar_position: ${pos}\n---\n\n{/* GENERATED: node scripts/sync-reference-tables.mjs / project/current-spec.json */}\n\n${body.trim()}\n`;
  pages.push({ rel: path.posix.join("src/content/docs/metal-case", rel), text });
}
let i=10;
for (const m of models) {
 const g=m.guards.t1p2, h=m.hardware_counts, l=m.lid_preview;
 const plates=m.plates.map(p=>`| ${p.part} | ${dims(p.size_mm)} | ${p.quantity} | ${p.holes_each} |`).join("\n");
 const catalog=g.catalog.map(p=>`| ${p.name} | ${p.quantity} | ${dims(p.dimensions)} | ${f(p.volumeCm3)} |`).join("\n");
 const candidate=m.candidate_revision ? `## ${m.candidate_revision}の製作候補（未承認）

7u40の旧候補データです（R10一式より前のR9系、未承認）。R6の本体形状を起点に、独立したアルミ板${m.candidate_body_summary.independent_plate_count}枚、ブラケット用の${m.candidate_body_summary.bracket_slot_count}か所の長穴候補（幅×全長 ${dims(m.candidate_body_summary.bracket_slot_size_mm)}mm、移動量候補 ±${f(m.candidate_body_summary.bracket_slot_candidate_travel_each_direction_mm)}mm）、レール固定用の丸穴${m.candidate_body_summary.rail_round_hole_count}か所を出力しています。長穴の方向・移動量、金具と座金の適合は製造判断・現物確認が残ります。

蓋はアルミ板${m.candidate_lid_summary.aluminum_plate_count}枚とPA12枠${m.candidate_lid_summary.pa12_frame_piece_count}部品の直線持ち上げ式です。蓋と本体のロックはなく、運搬時の外周バンドは別部品です。嵌合、ノブ・ケーブルの空間、枠の保持は未確認です。製造承認や価格確定を示すデータではありません。

${m.candidate_links ? m.candidate_links.map(x=>`<PreviewLink path="${x.path}">${x.label}</PreviewLink>`).join(' ／ ') : `<PreviewLink path="/downloads/candidate/7u40-r9-prototype-01-aluminum-NOT-APPROVED.zip">R9アルミ候補ZIP</PreviewLink> ／ <PreviewLink path="/downloads/candidate/7u40-r9-prototype-01-pa12-NOT-APPROVED.zip">R9 PA12候補ZIP</PreviewLink> ／ <PreviewLink path="/downloads/candidate/7u40-r9-prototype-01-coupons-NOT-APPROVED.zip">R9クーポン候補ZIP</PreviewLink> ／ <PreviewLink path="/previews/r9-prototype-01.html">R9プレビュー</PreviewLink>`}

${m.candidate_interface ? `基本案のガード外形は${dims(m.candidate_interface.t1p2.guard_exterior_mm)}mm、実肉厚1.2mm、ガード上端・蓋座面Z=${f(m.candidate_interface.t1p2.lid_seat_z_mm)}mm。天板は${dims(m.candidate_interface.t1p2.lid_plate_mm)}mm。ガード${m.candidate_guard_summary.t1p2.count}個で体積${f(m.candidate_guard_summary.t1p2.volume_cm3)}cm³（1.0mm案は${f(m.candidate_guard_summary.t1p0.volume_cm3)}cm³）。比較1.0mm案も専用の蓋を使います。[旧候補の詳細](../design/history/r9-fitfix-01.mdx)とBOMを確認してください。以下のR6/R8表と画像は履歴です。` : ''}

` : "";
 const candidateSection=candidate ? `\n\n${candidate.trim()}\n\n` : "\n\n";
 const holeNote=m.candidate_revision
   ? `R6は丸穴。R9候補は長穴${m.candidate_body_summary.bracket_slot_count}＋丸穴${m.candidate_body_summary.rail_round_hole_count}`
   : "R6の丸穴。長穴未反映";
 const description=m.candidate_revision
   ? `${m.id}のR6/R8基準と、旧・未承認の${m.candidate_revision}候補を示す。`
   : `本体はR6の名目CAD、載せ蓋はR8プレビュー。${m.id}の寸法と数量。`;
 page(`models/${m.id}.mdx`,m.label,description,i,`
## この機種

${m.id==='7u40'?'**主な確認対象。** リュックへ入れて運ぶ用途を重視する40HPの３列ケース。':'３機種に共通する金属平板と独立レールの構造を使う。'} ${m.id==='3u60'?'レール２本の単列。':'3U＋3U＋1Uは同じ平面に並ぶ。上下二段のケースではない。'}

![R6の組立形状](/assets/images/r6/${m.id}-assembled.png)

## ${m.candidate_revision ? "R6基準の寸法と数量（履歴）" : "寸法と数量"}

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
| 板の穴合計 | ${m.panel_holes}（${holeNote}） |${candidateSection}## ${m.candidate_revision ? "R6基準のアルミ本体５枚" : "アルミ本体５枚"}

| 部品 | サイズmm | 枚数 | 穴数/枚 |
|---|---|---:|---:|
${plates}

材質候補A5052、t1.5、黒アルマイト。外形・板厚は現在の名目値。長穴、穴中心、公差、表面の許容状態を確定してから製作承認する。

## ${m.candidate_revision ? "R6ガード1.2mmの参考内訳" : "ガード1.2mmの内訳"}

| 部品 | 数量 | 単体の外接寸法mm | 単体体積cm³ |
|---|---:|---|---:|
${catalog}

合計**${g.partCount}個、${f(g.totalVolumeCm3)}cm³**。1.0mm版は**${f(m.guards.t1p0.totalVolumeCm3)}cm³**。STLは１個ずつ、数量を注文画面へ指定する。

<PreviewLink path="/downloads/reference/${m.id}-r6-guards-t1p2-NOT-RELEASED.zip">1.2mm STL一式</PreviewLink> ／ <PreviewLink path="/downloads/reference/${m.id}-r6-guards-t1p0-NOT-RELEASED.zip">1.0mm STL一式</PreviewLink> ／ <PreviewLink path="/downloads/reference/${m.id}-r6-aluminum-NOT-RELEASED.zip">アルミ参考データ</PreviewLink>

## 蓋はR8の表示寸法

天板：**${dims(l.lidPlateMm)}mm**。蓋の外周：${dims(l.lidOuterMm)}mm。蓋付き高さは脚・模式ねじ頭まで**${f(l.closedHeightIncludingFeetMm)}mm**。バンド・側面ナットの突出は別。

前後の段差を差し込み、真上へ外す。30mmのノブ用高さ、2mm厚の段差、差し込み12mm、片側0.7mmの隙間は現在のプレビュー条件で、実物のフィットを保証しない。

バンド一周の幾何概算：**${f(l.strapLoopGeometricEstimateMm)}mm**。バックルと重なり代は含めていない。

${m.candidate_revision
  ? `R8の寸法は表示用の基準です。7u40では旧候補${m.candidate_revision}の蓋板・PA12枠も出力していますが、嵌合と仕様は未確定です。R7のロック用枠・前後M3穴は採用しません。[R8プレビュー](../resources/current-preview.mdx)と[発注前ゲート](../verification/before-order.mdx)を確認する。`
  : "**この載せ蓋の製作用CADは未更新。** R7のロック用枠・前後M3穴を発注しない。[R8プレビュー](../resources/current-preview.mdx)と[発注前ゲート](../verification/before-order.mdx)を確認する。"}

## 根拠

R6の ${m.sources[0]} と [本体サマリー](/evidence/r6-family-summary.json)、[ガードmanifest](/evidence/${m.id}-t1p2-r6-guard-manifest.json)、[R8パラメータ](/evidence/r8-preview-parameters.json)から表を生成した。今回、新しいCADを検証した値ではない。
 `);
 i+=10;
}
const cmp=models.map(m=>`| ${m.label} | ${dims(m.metal_mm)} | ${dims(m.candidate_interface ? [...m.candidate_interface.t1p2.guard_exterior_mm,m.candidate_interface.t1p2.guard_envelope_height_mm] : m.guards.t1p2.outerEnvelopeMm)} | ${m.hardware_counts.panelBracket} | ${m.hardware_counts.mountBolt} | ${m.guards.t1p2.partCount} | ${f(m.candidate_guard_summary?.t1p2.volume_cm3 ?? m.guards.t1p2.totalVolumeCm3)} | ${m.candidate_revision ? `${m.candidate_revision}・未承認` : "—"} |`).join("\n");
page("models/comparison.mdx","３機種の比較","共通値と、機種によって増える板・金具・ガードを一覧にする。",40,`
## 本体比較（7U40は旧R9候補の値）

| 機種 | アルミ外形mm | ガード込みmm | 金具 | ケース固定M5 | ガード個数 | 1.2mm体積cm³ | R9候補 |
|---|---|---|---:|---:|---:|---:|---|
${cmp}

上表の7U40ガード寸法・体積は旧候補[R9-FITFIX-01](../design/history/r9-fitfix-01.mdx)の生成値で、R10一式の値ではありません。R9-FITFIX-01は未承認のまま残る旧候補です。3u60と7u60の数値はR6/R8基準です。

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
const modelNote=fn=>models.map(m=>`${m.id}: ${fn(m)}`).join('；');
const bom=[row('本体アルミ板',counts('aluminumPanel'),modelNote(m=>m.candidate_revision?'R9候補・未承認':'t1.5、黒アルマイト候補')),row('L字ブラケット',counts('panelBracket'),'在庫20×20×16mm、厚2mm'),row('板接合用M5ネジ',counts('panelJointBolt'),'底面は頭を外向き'),row('板接合用ナット',counts('panelJointNut'),'品番・必要ねじ長は別確認'),row('板接合用座金',counts('panelJointWasher'),'モデル上の数量。実部品の厚さと受け面確認'),row('ユニット→ケースM5',counts('mountBolt'),'頭1.4mm、軸長未確定'),row('同ロックナット',counts('mountNut'),'外側'),row('内側8mmスペーサー',counts('innerSpacer'),'内外径は模式値を含む'),row('外側1mmナイロン座金',counts('outerWasher'),'ユニット固定用'),row('ゴム脚',counts('foot'),'φ10×高さ3mmは仮'),row('本体PA12ガード',models.map(m=>m.guards.t1p2.partCount),modelNote(m=>m.candidate_revision?'R9の1.2mm候補あり。保持・黒染め未確認':'1.2mm基本、黒染め候補')),row('蓋アルミ板',[1,1,1],modelNote(m=>m.candidate_revision?'R9で出力、嵌合未検証・未承認':'R8表示寸法、製作図未更新')),row('蓋PA12枠',[4,4,4],modelNote(m=>m.candidate_revision?'R9で4部品を出力、保持未確認・未承認':'R8の表示分割。発注数量は再CAD後に確定')),row('天板の組立M3',[8,8,8],'R7からの表示上の数量。長さ・ナット座を再確認'),row('外周バンド',[2,2,2],'品番未選定、開閉用のねじロックなし')].join('\n');
page('manufacturing/bom.mdx','ケース側BOM','レールユニットの費用を除き、本体・蓋・バンドを分けて管理する。',10,`
## ケース１台分の部品

以下の表はR6のhardwareCountsとR8の構成を基準に生成し、7u40のR9候補を注記したもの。予備率、破損、予備金具は含めていない。**発注承認済みBOMではなく、数量確認の起点**。

| 部品 | 3U60 | 7U40 | 7U60 | 仕様／状態 |
|---|---:|---:|---:|---|
${bom}

旧候補R9-FITFIX-01の材質別ZIP・試験片の数量は[R9-FITFIX-01](../design/history/r9-fitfix-01.mdx)を参照（R10一式の数量ではない）。1.2mm/1.0mmの蓋は専用で、C2の再利用部材（order_quantity=0）は重複発注しません。

## レール費用の除外

レール、fixer、padder、レール端固定ネジ、モジュール用ナット等のレールユニットの製作費は計算に入れない。数量の参考として、3Uはレール２本/fixer２枚/padder２枚、7Uはレール６本/fixer２枚/padder６枚をモデルに含む。

## まだ数量を確定しないもの

蓋組立用のナット・座金、ガード保持の接着材や爪、当たり材、バンド位置決め、梱包などは最終設計/品番が未確定。R7にあった蓋→本体のM3４本、ナット受けと圧縮スペーサー４個は最終方式には不要。

## 在庫と費用

手持ちL字金具は追加支払0円でも、製品原価には使用数×実仕入単価を入れる。その他の小物も画面上の形状から品番を推測して買わない。ケース側のM5で使う8mmスペーサーと外側座金はレール費用除外とは別に計上する。

出典：[R6サマリー](/evidence/r6-family-summary.json)、各機種のmodel-summary.json、<a href="/evidence/r8-original-readme.md">R8 README</a>。
`);
return pages;
}

// ---------------------------------------------------------------------------
// Per-model current tables. 3U60/7U60 keep their R6 body + R8 lid baseline
// (legacy template). 7U40 is generated from the active selection
// (release-state current_metal_7u40_candidate = R11-BUILD-FEEDBACK-04) and its
// imported parts manifest. The superseded R6/R9 7U40 tables and the old
// comparison/BOM rows are written to one archive page.
// ---------------------------------------------------------------------------
export const ARCHIVE_7U40 = "src/content/docs/archive/metal-case/models/7u40-r6-r9.mdx";

export async function loadR11Inputs(root) {
  const read = async p => JSON.parse(await readFile(path.join(root, p), "utf8"));
  const release = await read("project/release-state.json");
  const pointer = release.current_metal_7u40_candidate;
  if (!pointer || pointer.model !== "7u40") throw new Error("release-state current_metal_7u40_candidate missing");
  const out = path.posix.dirname(pointer.manifest_path);
  const scene = await read(`${out}/scene.json`);
  const validation = await read(`${out}/validation.json`);
  const params = await read(`${path.posix.dirname(out)}/parameters.json`);
  // Washer split, derived as in lib/r11-contract.mjs: distinct outer and retained inner body washers, plus lid-wall washers.
  const ids = prefix => new Set(validation.body_fastener_bearing_contacts.flatMap(c => [...c.a, ...c.b]).filter(id => id.startsWith(prefix))).size;
  const washers = { outside: ids("washer-out-"), inside: ids("washer-in-"), lid: scene.lid_metadata.counts.round_washers };
  return { pointer, manifest: await read(pointer.manifest_path), validation, lid: scene.lid_metadata.counts, envelope: params.body, washers };
}

export function renderReferencePages(spec, r11) {
  if (!r11) throw new Error("renderReferencePages needs the R11 inputs (loadR11Inputs)");
  const legacy = renderLegacyPages(spec);
  const byRel = rel => legacy.find(p => p.rel === `src/content/docs/metal-case/${rel}`).text;
  const f = (n, d = 4) => Number(n.toFixed(d)).toString();
  const dims = a => a.map(n => f(n, 3)).join(" × ");
  const zen = n => String(n).replace(/[0-9]/g, d => String.fromCharCode(d.charCodeAt(0) + 0xfee0));
  const head = (title, desc, pos, extra = "") => `---\ntitle: ${JSON.stringify(title)}\ndescription: ${JSON.stringify(desc)}\nsidebar_position: ${pos}\n${extra}---\n\n{/* GENERATED: node scripts/sync-reference-tables.mjs / project/current-spec.json + release-state current_metal_7u40_candidate */}\n\n`;
  const { pointer: c, manifest, validation, lid, envelope, washers: wb } = r11;
  const env = [envelope.width, envelope.depth, envelope.height];
  const counts = validation.counts;
  const m7 = spec.models["7u40"], h7 = m7.hardware_counts;
  if (c.revision !== manifest.revision || c.production_approved !== false || manifest.production_approved !== false) throw new Error("R11 pointer/manifest mismatch or approval drift");
  const parts = manifest.parts;
  const sheets = parts.filter(p => p.category === "aluminum");
  const pa12 = parts.filter(p => p.category === "pa12");
  const washer = parts.find(p => p.category === "home-print");
  const group = list => {
    const out = new Map();
    for (const p of list) {
      const key = `${p.id.replace(/-(?:-?1--?1|-?1-1|fl|fr|bl|br|front|back|left|right)$/, "")}|${dims(p.dimensions_mm)}|${f(p.volume_mm3 / 1000)}`;
      const g = out.get(key) ?? { ids: [], names: [], dims: dims(p.dimensions_mm), vol: p.volume_mm3 / 1000, qty: 0 };
      g.ids.push(p.id); g.names.push(p.name); g.qty += p.quantity; out.set(key, g);
    }
    return [...out.values()];
  };
  const link = (p, label) => `<PreviewLink path="${p}">${label}</PreviewLink>`;
  const sheetRows = sheets.map(p => `| ${p.name} | ${dims(p.dimensions_mm)} | ${p.quantity} |`).join("\n");
  const pa12Rows = group(pa12).map(g => `| ${g.names.join("、")} | ${g.qty} | ${g.dims} | ${f(g.vol)} |`).join("\n");
  const pages = [];
  const push = (rel, text) => pages.push({ rel: `src/content/docs/metal-case/${rel}`, text });

  push("models/3u60.mdx", byRel("models/3u60.mdx"));
  push("models/7u60.mdx", byRel("models/7u60.mdx"));

  push("models/7u40.mdx", head("7U40・40HP", "7U40の現行設計候補R11-BUILD-FEEDBACK-04の寸法と数量。製造承認ではない。", 20) + `
## この機種

**主な確認対象。** リュックへ入れて運ぶ用途を重視する40HPの３列ケース。3U＋3U＋1Uは同じ平面に並ぶ。上下二段のケースではない。現行は**${c.revision}**（CAD上のレビュー候補・現物未検証・製造承認なし）。設計の説明は[R11-04の設計候補](../design/r11-build-feedback-04.mdx)を参照。

${link(c.preview, "R11-04の3Dプレビューを開く")}

## 寸法と数量

| 項目 | 値 |
|---|---|
| 本体アルミ外形 W×D×H | **${dims(env)}mm** |
| アルミ板 | t${f(envelope.metal, 3)}、${c.quantities.aluminum}枚（本体${sheets.filter(p => p.id.startsWith("panel-")).length}＋蓋板${sheets.filter(p => p.id === "lid-plate").length}） |
| PA12部品 | ${c.quantities.pa12}個（本体${c.quantities.pa12_body}＋蓋${c.quantities.pa12_lid}）、最長辺${f(Math.max(...pa12.flatMap(p => p.dimensions_mm)), 3)}mm |
| PA12の実体積 | 本体${f(c.pa12_volume_cm3.body)}＋蓋${f(c.pa12_volume_cm3.lid)}＝**${f(c.pa12_volume_cm3.total)}cm³** |
| 金属L字ブラケット | ${counts.body_brackets} |
| 本体ねじ位置 | ${counts.body_screw_sites}（長穴 ${dims(c.body_slot_mm)}mm、内側へ片側5mm延長） |
| 本体ナット | 薄型${counts.body_thin_nuts}＋通常${counts.body_other_nuts}（M5、購入品の寸法は仮） |
| 板の切欠き合計 | ${c.sheet_cutouts.total}（本体長穴${c.sheet_cutouts.body_slots}＋レール丸穴${c.sheet_cutouts.rail_round_holes}＋蓋丸穴${c.sheet_cutouts.lid_round_holes}）。専用の吊り穴${counts.dedicated_hanging_holes} |
| 丸座金（家庭印刷ASA） | ${washer.name}、${washer.quantity}個（外側本体${wb.outside}＋上部内側本体${wb.inside}＋蓋の壁${wb.lid}） |
| 実レール長／レール本数 | ${f(m7.rail_length_mm, 3)}mm／${h7.rail}本（R11-04も元のレール・fixer/padder PCB・8mmスペーサーを変更しない。値は台帳の7U40レール構成） |
| レールと外箱のM5締結 | ${counts.body_round_rail_holes}点（レール丸穴。ナットはケース外側） |

## アルミ板${zen(c.quantities.aluminum)}枚

| 部品 | 外形 mm | 枚数 |
|---|---|---:|
${sheetRows}

材質候補A5052、t1.5、黒アルマイト。床・前後板は長穴だけで、アルマイトの吊り方法は未確認。

## PA12部品${c.quantities.pa12}個

| 部品 | 個数 | 単体の外接寸法 mm | 単体体積 cm³ |
|---|---:|---|---:|
${pa12Rows}

寸法はアセンブリ姿勢での書き出し値で、印刷姿勢の検証値ではない。体積はCADの実体積で、価格の見積ではない。現在価格は未見積（null）。

## 蓋（R11-04）

アルミ蓋板1枚とPA12蓋枠${c.quantities.pa12_lid}個の直線持ち上げ式。四辺の内側ガイドが本体開口に入り（差込み12mm、厚さ2mm、片側0.7mmの公称隙間、上部ナット・座金用の下側開放の逃げ8か所）、運搬時は外周バンド２本で保持する。蓋のねじ（天板${lid.vertical_screws}＋壁${lid.horizontal_screws}）は蓋の部品どうしを留めるもので、本体へのロックではない。

## 根拠

${link(c.packages.source, "R11-04の編集用ソースと出力")}内の\`out/parts-manifest.json\`（sha256 \`${c.manifest_sha256}\`）と\`out/validation.json\`から生成した。名目CADの整合確認で、強度・耐久・現物の嵌合や製造承認を示すものではない。旧R6基準・R9候補の7U40表は[アーカイブ](../../archive/metal-case/models/7u40-r6-r9.mdx)に保存している。
`);

  const legacyCmp = s => s.match(/\| 機種 \| アルミ外形mm[\s\S]*?\n\n/)[0];
  const r6 = ["3u60", "7u60"].map(id => spec.models[id]);
  const cmpRows = [
    ...r6.map(m => `| [${m.label}](./${m.id}.mdx) | R6本体＋R8載せ蓋（基準） | ${dims(m.metal_mm)} | 5＋蓋（R8は表示のみ） | ${m.hardware_counts.panelBracket} | ${m.hardware_counts.mountBolt} | ガード${m.guards.t1p2.partCount}個（1.2mm） | ${f(m.guards.t1p2.totalVolumeCm3)} |`),
    `| [${m7.label}](./7u40.mdx) | ${c.revision} | ${dims(env)} | ${c.quantities.aluminum}（本体${c.quantities.aluminum - 1}＋蓋1） | ${counts.body_brackets} | ${counts.body_round_rail_holes} | PA12 ${c.quantities.pa12}個（本体${c.quantities.pa12_body}＋蓋${c.quantities.pa12_lid}） | ${f(c.pa12_volume_cm3.total)} |`,
  ];
  // keep model order 3u60, 7u40, 7u60
  const ordered = [cmpRows[0], cmpRows[2], cmpRows[1]];
  push("models/comparison.mdx", head("３機種の比較", "機種ごとの現行版と、その版での板・金具・樹脂部品の数量。", 40) + `
## 本体比較（機種ごとの現行版）

| 機種 | 現行の版 | アルミ外形 W×D×H mm | アルミ板 | L字金具 | ケース固定M5 | 樹脂部品 | 樹脂体積 cm³ |
|---|---|---|---:|---:|---:|---|---:|
${ordered.join("\n")}

機種ごとに現行の版が異なる。7U40はR11-04の値、3U60と7U60はR6本体・R8載せ蓋の基準値で、互いの寸法・数量を流用しない。どの版も製造承認ではない。旧R9候補の7U40行は[アーカイブ](../../archive/metal-case/models/7u40-r6-r9.mdx#旧３機種比較（7u40はr9候補値）)に保存している。

## 共通部と差分

40HPは実STL長204mm、60HPは305mm。HPの比で引き延ばしていない。３機種とも元のレール・fixer/padder PCB・8mmスペーサーで組むレールユニットを本体から独立させる。3U→7Uは前後方向を長くし、fixerを7Uへ交換、3U padder２個と1U padder１個を各側へ配置する。

3U60と7U60のR6基準は、本体を丸穴とL字金具（3U60は16個、7U60は18個）とPA12ガードで組む。7U40のR11-04は、ねじ位置で重ねて締めるPA12の接続部と内側の位置決めで板を並べ、金属L字金具16個で補強する。長穴は${dims(c.body_slot_mm)}mm。

## 蓋と運搬

全機種とも直線持ち上げ式の載せ蓋＋外周バンド２本。3U60と7U60はR8の表示用プレビューが基準で、製作用CADは未更新。7U40はR11-04のアルミ蓋板とPA12蓋枠８個（四辺の内側ガイド）。ノブの高さ・締付時の天板のたわみ・実物の嵌合は未確認。

機種間で同じ部品として注文できるかは、完成したCADのファイルと数量を照合して決める。似た外形だけで同一品へまとめない。

出典：3U60・7U60は[R6サマリー](/evidence/r6-family-summary.json)と[R8パラメータ](/evidence/r8-preview-parameters.json)、7U40はR11-04の\`out/parts-manifest.json\`と\`out/validation.json\`。
`);

  const row = (name, a, b, d, note) => `| ${name} | ${a} | ${b} | ${d} | ${note} |`;
  const hc = id => spec.models[id].hardware_counts;
  const [h3, h6] = [hc("3u60"), hc("7u60")];
  const bomRows = [
    row("本体アルミ板", h3.aluminumPanel, sheets.filter(p => p.id.startsWith("panel-")).length, h6.aluminumPanel, "A5052 t1.5、黒アルマイト候補"),
    row("蓋アルミ板", "R8表示のみ", sheets.filter(p => p.id === "lid-plate").length, "R8表示のみ", `7U40はR11-04の蓋板（M5 ${counts.lid_plate_bolt_holes}穴）`),
    row("L字ブラケット", h3.panelBracket, counts.body_brackets, h6.panelBracket, "在庫20×20×16mm、厚2mm（実測）"),
    row("本体の板接合M5ネジ", h3.panelJointBolt, counts.body_screw_sites, h6.panelJointBolt, `R6は丸穴、R11-04は長穴${dims(c.body_slot_mm)}`),
    row("本体の板接合ナット", h3.panelJointNut, `${counts.body_thin_nuts + counts.body_other_nuts}（薄型${counts.body_thin_nuts}＋通常${counts.body_other_nuts}）`, h6.panelJointNut, "購入品の寸法は仮。R11-04は内側"),
    row("本体の座金", h3.panelJointWasher, `${wb.outside + wb.inside}（外側${wb.outside}＋上部内側${wb.inside}）`, h6.panelJointWasher, "R11-04は家庭印刷ASA丸座金Ø15/Ø5/t1。内側32か所は一体の受け座"),
    row("蓋の組立ねじ（M5×12モデル）", "未定", `${lid.vertical_screws + lid.horizontal_screws}（天板${lid.vertical_screws}＋壁${lid.horizontal_screws}）`, "未定", "蓋の部品どうしの締結。本体へのロックではない"),
    row("蓋の壁の座金", "—", lid.round_washers, "—", "R11-04は家庭印刷ASA丸座金"),
    row("ユニット→ケースM5", h3.mountBolt, counts.body_round_rail_holes, h6.mountBolt, "頭1.4mm、軸長未確定。R11-04はレール丸穴の数"),
    row("同ナット", h3.mountNut, h7.mountNut, h6.mountNut, "ケース外側（モジュール空間を確保）"),
    row("内側8mmスペーサー", h3.innerSpacer, h7.innerSpacer, h6.innerSpacer, "内外径は模式値を含む"),
    row("外側1mmナイロン座金", h3.outerWasher, h7.outerWasher, h6.outerWasher, "ユニット固定用"),
    row("ゴム脚", h3.foot, h7.foot, h6.foot, "仮寸法。R11-04はØ10×高さ6mmを表示"),
    row("PA12部品", `ガード${spec.models["3u60"].guards.t1p2.partCount}`, `${c.quantities.pa12}（本体${c.quantities.pa12_body}＋蓋${c.quantities.pa12_lid}）`, `ガード${spec.models["7u60"].guards.t1p2.partCount}`, "黒染めPA12-HP候補。R6は1.2mmガード、R11-04は接続部・蓋枠"),
  ];
  const legacyBom = byRel("manufacturing/bom.mdx");
  const keep = h => legacyBom.slice(legacyBom.indexOf(`## ${h}`)).split(/\n(?=## )/)[0].trim();
  push("manufacturing/bom.mdx", head("ケース側BOM", "機種ごとの現行版で、レールユニットの費用を除き、本体・蓋・バンドを分けて管理する。", 10) + `
## ケース１台分の部品

機種ごとの現行版で生成した表。3U60と7U60はR6のhardwareCountsとR8の構成、7U40は[R11-BUILD-FEEDBACK-04](../design/r11-build-feedback-04.mdx)の部品manifestと検証記録の数量。予備率、破損、予備金具は含めていない。**発注承認済みBOMではなく、数量確認の起点**。

| 部品 | 3U60（R6/R8） | 7U40（${c.revision}） | 7U60（R6/R8） | 仕様／状態 |
|---|---:|---:|---:|---|
${bomRows.join("\n")}

7U40のファイル一式は${link(c.packages.pa12, "PA12")}、${link(c.packages.aluminum, "アルミ")}、${link(c.packages["home-print"], "家庭印刷の座金")}のZIP。各ZIPの\`START-HERE.md\`が数量と版の入口。STEP・STL・DXFは同じ部品の別形式で、数量を二重に数えない。

${keep("レール費用の除外")}

## まだ数量を確定しないもの

ガード保持の接着材や爪、当たり材、バンド位置決め、梱包などは最終設計／品番が未確定。購入するM5ねじ・ナットの寸法は仮で、画面上の形状から品番を推測して買わない。蓋と本体をつなぐロック（旧R7のM3など）は採用していない。

${keep("在庫と費用")}
`);

  // Archive: superseded 7U40 R6-baseline / R9-candidate tables and the old comparison/BOM rows.
  const old7 = byRel("models/7u40.mdx").replace(/^---[\s\S]*?\n---\n\n\{\/\*[^\n]*\*\/\}\n\n/, "");
  const fixLinks = t => t.replaceAll("](../design/history/", "](../design/").replaceAll("](../resources/", "](../../../metal-case/resources/").replaceAll("](../verification/", "](../../../metal-case/verification/").replaceAll("](./3u60.mdx)", "](../../../metal-case/models/3u60.mdx)").replaceAll("](./7u40.mdx)", "](../../../metal-case/models/7u40.mdx)").replaceAll("](./7u60.mdx)", "](../../../metal-case/models/7u60.mdx)");
  const oldCmp = legacyCmp(byRel("models/comparison.mdx"));
  const oldBomTable = legacyBom.match(/\| 部品 \| 3U60 \| 7U40[\s\S]*?\n\n/)[0];
  pages.push({ rel: ARCHIVE_7U40, text: `---\ntitle: "旧7U40表（R6基準・R9候補）"\ndescription: "R11-04に置き換わった7U40のR6基準の寸法・数量、R9-FITFIX-01候補、旧３機種比較とBOMの7U40列。"\nsidebar_position: 10\nsearch_exclude: true\n---\n\n{/* GENERATED: node scripts/sync-reference-tables.mjs / project/current-spec.json */}\n\n:::warning[アーカイブ（履歴）]\n\n7U40の旧表です。R6基準の値とR9-FITFIX-01候補の値は、R10一式を経てR11-BUILD-FEEDBACK-04に置き換わりました。現在の作業には [7U40の現行の寸法と数量](../../../metal-case/models/7u40.mdx) と [ケース側BOM](../../../metal-case/manufacturing/bom.mdx) を使ってください。3U60・7U60のR6/R8基準は現行ページに残っています。\n\n:::\n\n${fixLinks(old7.trim())}\n\n## 旧３機種比較（7U40はR9候補値）\n\n${fixLinks(oldCmp.trim())}\n\n7U40の行はR9-FITFIX-01候補の生成値です。\n\n## 旧BOM（7U40はR6基準・R9候補注記）\n\n${oldBomTable.trim()}\n` });
  return pages;
}

async function main() {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const args = process.argv.slice(2);
  if (args.some(arg => arg !== "--check")) {
    console.error("Usage: node scripts/sync-reference-tables.mjs [--check]");
    process.exitCode = 2;
    return;
  }

  const spec = JSON.parse(await readFile(path.join(root, "project/current-spec.json"), "utf8"));
  const pages = renderReferencePages(spec, await loadR11Inputs(root));

  if (args.includes("--check")) {
    const drifted = [];
    for (const { rel, text } of pages) {
      try {
        const current = await readFile(path.join(root, rel), "utf8");
        if (current !== text) drifted.push(`${rel} (out of sync)`);
      } catch (error) {
        if (error.code !== "ENOENT" && error.code !== "ENOTDIR") throw error;
        drifted.push(`${rel} (missing)`);
      }
    }

    if (drifted.length) {
      console.error("Generated pages differ from project/current-spec.json:");
      for (const rel of drifted) console.error(`- ${rel}`);
      console.error("Run node scripts/sync-reference-tables.mjs to regenerate them.");
      process.exitCode = 1;
      return;
    }

    console.log("OK: generated reference pages match project/current-spec.json.");
    return;
  }

  for (const { rel, text } of pages) {
    const destination = path.join(root, rel);
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, text);
  }
  console.log(`Generated ${pages.length} reference pages from project/current-spec.json.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(await realpath(process.argv[1])).href) {
  await main();
}
