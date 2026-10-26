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

実行結果とブラウザー記録は完了後に追記します。実スライス、ASA反り・クリープ、締結の長期保持、現物嵌合、運搬・荷重、熱・防塵性能は未確認です。製造承認・発注は行いません。
