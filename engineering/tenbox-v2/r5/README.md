# 10BOX-v2 R5：受け入れた家庭印刷候補

独立系列 `tenbox-v2`。2組の3U60HPフレームを使う337.4mm幅のケースです。7U40 P5の新改訂ではありません。製造承認はfalse。Bambu Studioでの実ロード／スライス、印刷、現物嵌合・荷重・運搬試験は未実施です。

## 現行ファイルと数量

`tenbox-v2-r5-print.zip` は15個の設定済みH2D 0.6mm/PLAプロジェクトと印刷姿勢STLを含みます。共通底板 `body-bottom-common.3mf` は**同じ1枚を2回**印刷します。8個のスペーサーは1プレートです。保存オブジェクト22、16回のプレート実行で、ケース本体6＋蓋5＋スタンド4＋スペーサー8＝23部品となります。レール・PCB・金属締結材はこの印刷BOMに含みません。購入金物一式のBOMではありません。

`tenbox-v2-r5-review.zip` のSTEPとSTLは**組立座標**です。前底板のZ36..41mmは意図した配置です。印刷時は設定済み3MF、またはprint ZIP内の明記した印刷姿勢STLを使ってください。review ZIPの単体HTMLはオフラインで開けます。

底板は面を下にしてyaw −45°、外形316.850532×311.193678×5mm、X4.074734..320.925266/Y4.403161..315.596839。天板は317×290×5mm、X4..321/Y10..300。いずれもLEFTノズル1本、X0..325/Y0..320、Manual mapping `1 1`／extruder `1`、ブリム／サポートなし。他のプロジェクトに残る設定は維持しています。底板の実投影凸包と後方除外域の離隔21.194489mmを検査します。外接矩形だけなら除外域に重なるため、それを実干渉と誤認しないでください。

## 再生成

Python3.12.14 / CadQuery2.7.0 / NumPy2.3.5 / SciPy1.17.0を専用uv.lockで固定します。P5環境を変更しません。

```sh
uv sync --locked --project engineering/tenbox-v2/r5
uv run --locked --project engineering/tenbox-v2/r5 python engineering/tenbox-v2/r5/build.py --out .cache/tenbox-r5-build
uv run --locked --project engineering/tenbox-v2/r5 python engineering/tenbox-v2/r5/regenerate.py
python3 engineering/tenbox-v2/r5/test_contract.py
```

source ZIPを展開した場合は、そのディレクトリで`uv sync --locked`後、`uv run python build.py --out /tmp/tenbox-build`を実行します。既存出力は上書きせず停止します。`--publish-root`を明示した時だけリポジトリ候補配信先へコピーします。ZIPは一時ファイルで作成し、close・fsync・CRC・全ファイルhashとinventoryを検査後atomic replaceします。

CADは`source/10box-v2-r5/source-r4`のSTEP/modelから底板改訂を増分生成します。以前の壁・蓋構築全体がR5 configからパラメトリック再生成されるわけではありません。H2Dは底板を生成し、14個の修正済み凍結3MFを`source-flat-r4`からコピーします。viewerは凍結P5由来renderer、native rail geometry、R4比較model、正確なfloor/roof posesが依存入力です。これらは不要な履歴ではありません。依存入力と出力受領hashは`project/tenbox-v2/manifest.json`、元の不変アーカイブは`inputs/`に保管します。source ZIPには再生成に必要なこれらのbaselineを同梱します。

元資料の著作権・ライセンス表示を維持し、この統合作業で再ライセンスしません。出典commitはzudo-case `6a99404a4e4220bb18b88d7d0f063571d1dad7b9`、zzmod `78d5cb099b8b4a577b91419ec7cd1adb0a3d3810`。無関係なprivate checkoutは不要です。生成日時／UUIDによる差と形状／設定の差を分離して照合します。
