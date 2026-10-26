# P4 Uniform家庭印刷版の検証記録

対象: `P4-PRINTED-5MM-UNIFORM-VENTS`。P3を保存して四壁に通気孔を追加した家庭印刷候補です。物理・スライサー・強度・熱・防塵の合格記録ではありません。

## 設計と根拠

採用アーカイブの申告SHA-256は `104de884b60615cadbabb8381880fa8ae08be418a3667ad0e74c712811cd0a8d`。引継ぎZIP内の `HANDOFF-MANIFEST.json` の全ファイルhashを照合しました。四壁の維持版STEPと採用プロトタイプSTEPのBRep対称差体積は許容1e-5mm³未満でした。結果は `verification/accepted-prototype-comparison.json`。

ねじが縦長の兼用通気孔内で長期使用中に下へ移動した、という別の10BOX式ケースに対するユーザー報告を受け、通気孔と専用締結穴を分離します。P4の耐久実測ではありません。

## 再生成と保存

Python3.13.5 / CadQuery2.8.0の固定環境。`source/build_case.py`で維持ソースから全形状を生成し、四壁の開口を切削した同じBRepをSTL・STEP・表示に使用します。P3出力メッシュを入力にはしません。元レールとPCBの入力hash、変換を保持します。

`reference/PRESERVATION.json` は作業開始時点のP3ソース・出力・検証、R10とカート関連、計221ファイルのhashおよびR10現行ポインターを記録します。P3台帳は `project/printed-5mm/files.json` を変更せず維持。P4はこのフォルダーの `files.json`。

変更しない11形式のSTL・正規化STEP計22ファイルはP3公開版とバイト一致をビルド時にも要求します。四壁を含む全30ファイルの旧→新対応は `out/PRINT-MAPPING.json`。

## 幾何結果

- 四壁82開口: 左右各25、前後各16。幅3 × 高さ32mm、R0.5、ピッチ11mm、Z30–62mm。
- 幾何開口面積: 7,854.402649mm²（約78.544cm²）。締結穴の面積は含めません。
- 実アセンブリ金具の保守的投影までの最小距離: 四壁とも4.000mm。
- 専用締結穴までの最小距離: 左右6.9394265mm、前後9.750mm。
- 隣接リブ8mm、外周余白25mm。28組立長穴＋10レール丸穴を維持。
- 本体検査552件、レール検査187件。全検査に偽の `passed` があればパッケージ生成を停止します。

## コマンド

```sh
uv sync --locked --project engineering/printed-5mm/p4-uniform-vents
uv run --locked --project engineering/printed-5mm/p4-uniform-vents python engineering/printed-5mm/p4-uniform-vents/build.py --out /tmp/p4-build
python3 engineering/printed-5mm/p4-uniform-vents/verify.py --out /tmp/p4-build --published-root .
uv run --locked --project engineering/printed-5mm/p4-uniform-vents python engineering/printed-5mm/p4-uniform-vents/regenerate.py --published-root .
uv run --locked --project engineering/printed-5mm/p4-uniform-vents python engineering/printed-5mm/p4-uniform-vents/validate_parameters.py --out /tmp/p4-build
python3 engineering/printed-5mm/p4-uniform-vents/negative.py --out /tmp/p4-build
```

`regenerate.py` は別々の空出力先へ2回生成し、2回目はソースZIPを展開したものからビルドします。ローカルの重い生成・ブラウザー・全チェックは共有heavy-guardを通します。

独立した空出力先2個（2回目はソースZIP展開）で、74ペイロードのバイト一致を確認しました。最終版Canvas／WebGLはそれぞれ189項目通過。直接file://、全14画面、P3比較、15印刷配置、設定保存・異常入力拒否、選択・solo・レイヤー、PNG、390/320pxを含みます。各経路の実rendererは `verification/browser-canvas-checks.json` と `verification/browser-webgl-checks.json` に記録しています。

ローカル文書の検査は `scripts/verify-printed-p4-site.py`、全体の実行手順は `.github/workflows/check.yml`。文書・P3/P4クリーンCAD・既存CADの最終コミットに対する結果は [PR #127](https://github.com/Takazudo/zudo-case/pull/127) のチェック記録を参照してください。devはHTMLにCSSと再読込タグを挿入するため、ZIPはGETの生バイトhashを照合し、埋込HTMLは同一オリジン・P4版・実操作を確認します。実スライス、ASA反り・クリープ、締結の長期保持、現物嵌合、運搬・荷重、熱・防塵性能は未確認です。製造承認・発注は行いません。

## 配布ファイル

| ファイル | SHA-256 |
|---|---|
| `public/downloads/candidate/printed-5mm-p4-uniform-vents-stl.zip` | `0587817a6243e6602da90d6b1386982b39b6841033aaadf8d30a0975d149c4f8` |
| `public/downloads/candidate/printed-5mm-p4-uniform-vents-source.zip` | `d3954dfd090b9791caf094699fb386442105a37e97ff685c937d46d2e40398fb` |

四壁は `engineering/printed-5mm/p4-uniform-vents/out/stl/wall-{front,back,right,left}.stl` と同 `out/step/wall-{front,back,right,left}.step`。左右各25、前後各16の通気孔。四壁だけの便宜ZIPは作らず、15 STL＋15 STEP入りの一式を配布します。

ローカル通常checkワークフロー全ステップと、既存CADワークフロー全ステップが通過しました（R10独立2回生成・保存済み99ファイル一致を含む）。最終P4の統合文書37項目も通過。両ZIPの実GET hash一致、desktop/390/320px、同一originのP4埋込と比較操作を確認しました。記録: `verification/site-checks.json`。
