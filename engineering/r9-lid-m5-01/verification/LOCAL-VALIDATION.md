# R9-LID-M5-01 検証記録

2026-10-20。起点 `6c8d980c1e12e4d7ceb78e056463a197526a8164`（main）。Issue #123。

## CAD（固定環境）

- `uv run --locked --project engineering/r9-prototype-01 python engineering/r9-lid-m5-01/build.py`。Python 3.12.3 / CadQuery 2.7.0（Linux x86_64）（`../out/environment.json`）。R9-FITFIX-01と同じuv.lock。
- 1.2/1.0mm両案のフタ枠4個・天板、C2-M5-01/02/03、N1を生成。全STEPの再読込（単一ソリッド・体積一致）、全STLの閉じた辺・向き・体積、天板DXFの外形と穴⇔STEP再読込の一致を確認。
- フタ枠8箇所すべてを生成立体で計測（点分類＋二分探索、最小肉厚は中間高さの薄板断面でBRepExtrema）。対辺8.400、有効深さ5.500、屋根1.500、最小肉厚1.600、外面側3.400、天板穴の残り2.750、天板端→軸5.500。前後辺と左右辺、両案で同値。
- 枠の穴軸8本と天板8穴が一致。新ボスの外ではR9-FITFIX-01の枠と体積差0、天板の外形・素板体積も一致。ガード12種類はR9-FITFIX-01保存STEPと立体差0。
- R9-FITFIX-01と同じ検査（ガード・本体５枚・保存金具・レール外接箱との干渉、座面の接触面積、0〜15mmの持ち上げ19位置）が両案で通過。フタ部品は仮定ノブ域（レール対の間、Z〜118）に入らない。
- 対辺8.0×全高5.0のナット包絡が収まる。最小対辺7.68は角が鋭い場合・面取り（e/s=1.099）の場合とも30°回転で干渉＝回り止めが働く。8.5では面取りナットが回り得ることを回帰テストで固定。
- 挿入経路（真下へ引き抜き→内側へ30mm、サンプル）、頭の上のドライバー空間φ10×80、ネジ10/12/14mm×座金有無の先端干渉とナイロン部の先への突出を全8箇所で計算。結果は `../out/validation.json`・`../out/DIMENSIONS.md`。
- C2-M5の天板は、M5穴φ5.5とR9-ANODIZING-01と同じUV(5, 21.4)のφ4吊り穴を別層で出力。吊り穴は枠の投影から8.50mm。
- 回帰テスト `tests/test_m5.py` 12件通過。旧M3収納部にM5ナットが入らない負の対照を含む。
- 一時フォルダーへの再生成で全出力のSHA-256が一致（`tools/compare_outputs.py`）。

## 統合

- `node scripts/sync-lid-m5.mjs` で候補40件・資産71件を登録。`project/release-state.json` の `lid_revision_candidates` に「本体・ガード＝R9-FITFIX-01、フタ枠・天板＝R9-LID-M5-01」を記録。`current_lid_manufacturing` はR9-FITFIX-01のまま。
- `--check` は出力・公開コピー・生成コード・入力（fitfixのコードとscene、anodizingのパラメータ、uv.lock）の変更と、現行指定の差替え・承認フラグの変更を拒否する（`tests/ledger-lid-m5.test.mjs`）。
- 既存の `check:fitfix`、`check:fit-test-order`、`check:r9`、`check:r9-ledger`、`check:r9-doc-table`、`check:tables`、`check:assets`、`check:docs`、`test:ledger`、`test:r9`、`test:setup`、`check:two-way`、`check`、`build`、`check:built-preview-links`、`check:images` を実行し通過。R9-ANODIZING-01の `test_revision.py` も通過。
- `tests/fitfix-pcb-materials.test.mjs` の「published HTML reproduces…」はこの作業環境のシステムPython 3.13ではmainのままでも不一致になる（環境依存、今回の変更前から）。CIの結果で確認する。

## ブラウザー

Chromium（Playwright、WebGL）で `public/previews/r9-lid-m5-01.html` を1440px / 390px表示。横はみ出し・ページ/consoleエラーなし。ネジ8＋ナット8の仮定包絡がフタと一緒に持ち上がること、1.2/1.0mm切替、全体フタのM5部・C2-M5・N1の断面表示を確認。`browser.json` と画像。再確認は `public/` を配信して `PREVIEW_ORIGIN=… node engineering/r9-lid-m5-01/tools/check_preview.cjs`。

## 未実施

現物のナット挿入・回り止め・締付トルク、PA12のクリープと強度、印刷後の実寸、実ネジの頭径・長さ・座金、バンドと頭の位置関係、フタ全体の嵌合・運搬。L字ブラケットの現物確認（#102）とガード接着は別件。製造承認・見積・発注・デプロイはしていない。
