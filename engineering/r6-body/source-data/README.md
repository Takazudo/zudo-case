# R6の入力ソース

- `rail60/`: 提供60HP STLの原本・未修復メッシュ・取付中心解析。実長305mm。
- `rail40/`: 提供40HP STLの原本・未修復メッシュ・取付中心解析。実長204mm。60HPと断面は一致。
- `panels/`: fixer3u/fixer7u/padder3u/padder1uの元KiCadと全輪郭、source commit/hash。
- `panels/placements.json`: 7Uを3U+3U+1Uとするレール軸、パダー配置、選択した5個/側のM5位置、頭と窓の余裕を収録。

元の解析スナップショットにある初期案の5mmスペーサーや未確認板厚の記述は、その後のユーザー指定により更新されています。現在の条件は上位 `design-parameters.json` にあるPCB厚1.6mm、スペーサー8mm、頭厚1.4mm、ブラケット実厚2mmです。元STLとPCBファイルは変更していません。
