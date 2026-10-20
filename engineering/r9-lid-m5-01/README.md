# R9-LID-M5-01 — 7U40フタ 天板・PA12枠のM5化（#123）

**R9-FITFIX-01を起点にした独立した改訂候補。製造承認ではありません。** 元のR9-FITFIX-01／R9-ANODIZING-01のCAD・注文ZIP・試験片と、元注文を示すorder-mapは変更しません。

## 変更したもの・しないもの

- 変更: アルミ天板とPA12フタ枠を組み立てる8箇所の締結。M3（φ3.4・六角5.9・有効深さ2.9）→ **M5ネジ＋M5ナイロンロックナット**（φ5.5・六角対辺8.4・有効深さ5.5・屋根1.5・ボス深さ7.0）。ネジ軸は天板端から3.9→5.5mmへ内側に移動。
- 維持: フタの座面、位置決め段差、真上への脱着、外周バンド2本、本体アルミ5枚、ガード16個、レール。**フタと本体のロック機構は追加していません。**
- 新ボスはM3のボス・穴を完全に含む直方体で、それ以外のフタ枠形状はR9-FITFIX-01の `lid_quarter()` と体積差0で一致することを生成時に検査します。天板の外形も同じです。

寸法の根拠・採用理由・計測値は生成物 [`out/DIMENSIONS.md`](out/DIMENSIONS.md) と `parameters.json` の `adopted_reasons` にあります。ナット寸法はユーザー添付の商品寸法表の転記で、現物実測ではありません。

## 生成と検査

```sh
cd engineering/r9-lid-m5-01
uv run --locked --project ../r9-prototype-01 python build.py            # out/ を再生成
uv run --locked --project ../r9-prototype-01 python tests/test_m5.py    # 回帰12件
uv run --locked --project ../r9-prototype-01 python build.py --out /tmp/lidm5 \
  && uv run --locked --project ../r9-prototype-01 python tools/compare_outputs.py --fresh /tmp/lidm5
cd ../.. && node scripts/sync-lid-m5.mjs --check                       # 台帳・公開コピー
```

`build.py` は `lidm5/geometry.py` の1つのM5定義から、フタ枠4個×（1.2/1.0mm案）・対応天板・C2-M5試験片3種・N1ラダーを生成し、全部品のSTEP再読込、STLの閉じた辺・体積、DXF⇔STEPの穴と外形の一致を確認します。不合格時は停止します。

## 出力（out/）

| パス | 内容 |
|---|---|
| `pa12/t1p2/lid`, `pa12/t1p0/lid` | フタ枠4個（STL/STEP）。案ごとに専用品 |
| `aluminum/t1p2`, `aluminum/t1p0` | 天板（STEP/DXF、参照STL）。DXFはM5穴を `M5_HOLES` 層に分離 |
| `coupons/c2-m5` | C2-M5-01/02/03の枠（位置決めすきま0.7/0.5/0.9）と共用天板1枚。天板はM5穴φ5.5と、R9-ANODIZING-01と同じ位置のφ4吊り穴（`HANG_HOLE_D4` 層）を区別 |
| `coupons/n1` | N1: 六角対辺8.3/8.4/8.5を並べたナット収納ラダー（PA12） |
| `*-NOT-APPROVED.zip` | 材質別の見積用ZIP（PA12とアルミを分離）。本体・ガードは含まず、R9-FITFIX-01のZIPを据置で使う |
| `DIMENSIONS.md`, `dimensions.json` | 採用寸法と生成形状からの計測値 |
| `BOM.csv`, `BOM.json` | 部品・数量・M5ネジ／ナット（仮定）・据置部品の参照とハッシュ |
| `old-to-new.csv`, `old-to-new.json` | 旧R9-FITFIX-01／R9-ANODIZING-01ファイル→新ファイルの対応とSHA-256 |
| `validation.json` | 検査結果と未検証事項。`environment.json` は実行環境 |
| `preview.html` | 生成形状を内蔵するプレビュー。ネジ・ナットは仮定包絡 |
| `outputs-manifest.json` | 入力と出力のハッシュ |

C2-M5の壁とガードは寸法が変わらないため、注文済みのR9-FITFIX-01 C2部品を再利用し、新規ZIPに入れていません。

## 仮定（可変、`parameters.json` の `assumptions`）

ネジ頭φ10×高さ5、座金なし（ありの場合t1.0・外径10）、ナット角の面取り比 e/s=1.099（ISO 10511 M5のe_min 8.79／s 8.0）、ノブ包絡はR9と同じ「パネル2＋ノブ25mm」。いずれも商品の同定・実測をしていない値です。

## 範囲外

L字ブラケットの現物確認（#102）、ガードの接着剤／テープ選定、締付トルク・PA12のクリープ・強度・運搬試験、製造承認、発注は対象外です。
