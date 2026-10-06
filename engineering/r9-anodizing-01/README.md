# R9-ANODIZING-01 — 13枚のアルマイト吊り穴追加

Issue [#116](https://github.com/Takazudo/zudo-case/issues/116)。JLCCNC のアルミ試験片13枚に、各1個の専用丸穴を追加した別リビジョン。A5052、板厚1.5 mm、黒アルマイト。PA12の13設計・15個とは別です。元のR9/R9-FITFIXソース、注文ZIP、既存プレビューは変更しません。

`out/r9-anodizing-01-aluminum-13-NOT-APPROVED.zip` は13 STEP＋13 DXF、対応表と検査manifestを収録。STEP/DXFの組は同一品で、26個ではありません。各1枚です。`out/r9-anodizing-01-review.zip` は変更前後SVG13枚、参照STL13個、manifestです。STLはアルミ加工の提出原本ではありません。ZIPの `NOT-APPROVED` はサプライヤーへの製造承認・差替え操作を行っていない意味です。

## Ø4 mm、最小残り幅1.5 mmで保護領域を避ける

サプライヤーから伝達された許容径3.5–5 mmの中で、4 mmを選択。小さいC5でも既存接触面を避ける余地を残し、3.5 mmの下限より0.5 mm大きくしています。残り幅は**穴の端から板端まで**。許容の出発点1 mmに対し、通常2–3 mm、C5で1.5 mmを確保しました。

| ID | 板の平面寸法 mm | 穴中心 U,V mm | 最小残り幅 mm |
|---|---|---|---|
| c1-metal-edge | 40 × 20 | 5, 5 | 3 |
| c2-01-wall | 30 × 31 | 5, 5 | 3 |
| c2-01-plate | 30 × 26.4 | 5, 21.4 | 3 |
| c3-01-bottom / wall | 各32 × 20 | 各4, 16 | 2 |
| c3-02-bottom / wall | 各32 × 20 | 各4, 16 | 2 |
| c3-03-bottom / wall | 各32 × 20 | 各4, 16 | 2 |
| c4-01-floor | 30 × 20 | 5, 15 | 3 |
| c4-01-wall | 30 × 18.5 | 5, 13.5 | 3 |
| c5-01-front | 10.5 × 20 | 7, 7 | 1.5 |
| c5-01-left | 12 × 20 | 8.5, 7 | 1.5 |

U,Vは各DXF左下を原点、右・上が正。元のSTEPが組立座標の部品はそのまま保持。C3 STEPは従来どおり平置き座標です。manifestはSTEP座標と実ケース座標を明確に分離しています。

## 保護した領域とケースとの関係

- C1: 全比較ガードの上端5 mm帯を保持。
- C2: 3種類すべてのフレーム、ガード、支持棚、取付ねじ穴の周辺を避ける。壁の穴は下部、天板は棚から離れた内側の自由端。
- C3: 幅16 mmの金具帯全体と下端5 mmを保護。元の5.5×7.5 / 5.5×8.5 mm長穴および対照Ø5.5 mm丸穴は保持。金具帯は長い比較長穴の±1.5 mm移動と、計算上OD13.5 mmまでの座金受け面も含む保守的範囲。吊り穴との距離は2 mm。実座金・ねじ・工具は未選定。
- C4: 下ガード・床と壁の接触帯を保持。全体ケースの前底金具も再生成し投影を検査。
- C5: 上端ガードだけでなく、**試験片には含まれない全体ケースの縦角ガードと角金具**も検査。最初の穴案は縦ガード／金具帯にかかったため修正。採用位置は縦ガード帯から1.5 mm、角金具上端から1.5 mm、上ガード帯から6 mm離れる。

[既存ケース・試験片マップ](https://zudo-case-preview.zudolab.dev/previews/r9-order-map.html#part=c2-01-frame)は元注文の形状を表示する参照です。追加穴の正本は本リビジョンのSVG/STEP/DXFです。ケース本体の製造版へ穴を転記したものではありません。

## 再生成と検証

```sh
uv sync --locked --project engineering/r9-prototype-01
uv run --locked --project engineering/r9-prototype-01 python engineering/r9-anodizing-01/build.py
uv run --locked --project engineering/r9-prototype-01 python engineering/r9-anodizing-01/test_revision.py
```

`--out /tmp/anodizing-check` で出力先を分離できます。元の `fitfix.coupons.coupon_families` と `r9.coupons._build_c3` をパラメータから実行し、元STEPとの立体差分・元DXFの再構成一致を確認してから切削します。元ファイルと注文ZIPは注文時commit `541eca7f8ebc2e6da4375108b0d66773a0868b00` とバイト一致を検証。実装起点はプレビューPR115を含む `9bd8e65` です。

生成時に以下を全13枚で検査し、不合格時は停止します。

- 追加物なし、外形／厚み不変、削除領域がØ4×1.5 mm円柱1個だけ。削除体積は18.8495559 mm³。
- ガード／隣接部品の実BREP境界から保守的な平面投影を作り、穴との正の距離を確認。
- STEPを再読込し、DXFの外形・円・長穴円弧から再構成した立体と比較。
- STLの閉じた辺接続、向き、正体積、寸法／体積誤差を確認。
- `replacement-map.csv` と `manifest.json` が旧→新のファイル名・SHA-256を記録。`checksums.json` がZIPと図も含めて記録。
- 回帰テストで、欠落穴、余分な穴、径違い、元取付穴の埋戻し、端距離不足、ガード／金具干渉、誤ったDXFを検出。CIで39個のCADファイルと13枚の図の再生成一致を確認。

これは公称CAD・ファイル整合の検証です。実物の強度、アルマイト処理時の治具アクセス／跡、仕上がり公差、実金具との嵌合は保証しません。サプライヤーへのメール、JLCへの差替え・アップロード・発注／支払操作は実施していません。
