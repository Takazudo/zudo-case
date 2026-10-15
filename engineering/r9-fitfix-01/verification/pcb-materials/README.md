# レールPCBの面別材質表示

R9-FITFIX-01の現行プレビューだけを修正。写真 `IMG_2152.jpeg`、`IMG_2151.jpeg`、`IMG_2153.jpeg`、`IMG_2125.jpeg` を実際に開いて照合した。元写真は再公開せず、SHA256を [photo-provenance.json](./photo-provenance.json) に記録する。

- fixer: 外面は黒、内面は銀色アルミ。切断面・穴壁も銀色。
- padder: 内向き面は写真で見える黒。裏面の銀色は片面仕上げを仮定した表示で、写真では未確認。
- 既存のworld X座標を使う。右側の外面はX最大、左側の外面はX最小。ポリゴンの巻き順やカメラの向きで表裏を判定しない。
- PCBだけ表示用バッファを三角形単位に展開して色を割り当てる。頂点位置・三角形・配置・穴・厚さを変えない。部品ごとに単一materialを使い、三角形ごとのdraw callを増やさない。
- 「部品を色分け」を解除してもPCBの面別材質を保つ。WebGLとCanvas簡易描画の両方に反映する。

更新対象は `fitfix/preview.py`、`out/preview.html`、`public/previews/r9-fitfix-01.html` と関連チェック・台帳。`out/scene.json`、STL/STEP/DXF、元発注ZIP、R6/R8/旧R9、2WAY、注文マップは変更しない。アルマイト候補の参照台帳がpreview.pyを入力として記録するため、そのハッシュと候補ZIP2本のmanifest.jsonだけ更新する。その他の全ZIPメンバーが変更前と同一であることを [照合記録](./consumer-provenance.json) に残した。製造承認・実物の嵌合検査ではない。

## 再現

```sh
python3 engineering/r9-fitfix-01/tools/refresh_preview.py
node scripts/sync-fitfix.mjs
node --test tests/fitfix-pcb-materials.test.mjs
node scripts/sync-fitfix.mjs --check
node scripts/verify-assets.mjs
```

refreshは保持されたsceneとすべての非preview出力の既存SHA256を先に照合する。CAD生成を実行せず、プレビューとそのハッシュ記録、およびアルマイト候補の参照台帳だけ更新する。10のテストで左右8枚の実メッシュ面色、元三角形の不変性、現行ソースからのHTML再現と下流候補パッケージの参照台帳整合を検査する。

ブラウザ確認は `public/` をHTTP配信し、Playwrightを利用できる環境で、環境のheavy guardを通して実行する。

```sh
# 別ターミナル
python3 -m http.server 4175 --bind 127.0.0.1 --directory public
# PLAYWRIGHT_MODULEに既存Playwrightパッケージを指定可能
node engineering/r9-fitfix-01/tools/check_pcb_materials.cjs
```

[内側](./inside.png)、[左外側](./left-outside.png)、[右外側](./right-outside.png)、[積層分解](./exploded.png)、[Canvas代替](./canvas-exploded.png)、[390px表示](./mobile.png)。[ブラウザ結果](./browser.json)はWebGL/Canvasそれぞれの色分け切替、厚さ切替、部品表示、分解、coupon往復、エラーと横はみ出しを検査した。Canvasは既存の簡易三角形ラスタライザで、細かな面の継ぎ目や照明差が残る。

独立レビューでは4枚の元写真と実描画を再確認し、左右の面・黒padから見える銀色frame・切断面の整合を確認した。公開デプロイやmainへのマージはこの変更では行わない。
