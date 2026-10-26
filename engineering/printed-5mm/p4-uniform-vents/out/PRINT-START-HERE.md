# P4 Uniform 7U40・5mm家庭印刷 開始案内

版: P4-PRINTED-5MM-UNIFORM-VENTS。黒ASAを想定。製造承認・現物検証は未完了。

構造部品12点: 底板2、壁4、蓋の縁4、屋根2。各STLを1個ずつ、mmで印刷する。STEPは組立座標。STLは非負のベッド座標。

任意の家庭印刷品: 横長パッド48、縦長パッド48、丸座金28。レール外側の既存座金10個と混同しない。金属L金具28個とレール・PCB・金属ねじ類は印刷データに含まない。

長い壁と蓋の縁は一体のまま45度で平置き。H2Dの単一ノズル325×320mmを5mmブリム込みで矩形検査。部品の最長辺は350mm以下。蓋の位置決め段差には局所サポートが必要。Bambu Studioでサポート・キープアウト・反りを別途確認する。

再生成: `uv sync --locked --project engineering/printed-5mm/p4-uniform-vents` の後、`uv run --locked --project engineering/printed-5mm/p4-uniform-vents python engineering/printed-5mm/p4-uniform-vents/build.py --out /tmp/printed-p4-uniform-vents-build`。出力先は空のディレクトリ。寸法変更は単なるキャッシュ更新でなく、CAD・検査・文書のレビューを要する。

通気孔は四壁のみ、計82個（左右25、前後16）。3×32mm、R0.5、11mmピッチ。締結穴28長穴＋10丸穴は独立して保持。開口面積は幾何値で、冷却・防塵・強度の実証ではない。旧P3と同名の4壁のみ交換、他11形式の形状は同一。PRINT-MAPPING.jsonに旧→新の30ファイルhash、VENTILATION.jsonに公称開口と距離、reference/P4-SOURCE-RECEIPT.jsonに元ソースの記録を同梱。

床・屋根の中央は結合しない。継ぎ目のたわみ、ASAの強度、現物嵌合、運搬は未検証。M5×25／M5×40は表示用の仮寸法。蓋の保持は外周の取り外し式バンド。
