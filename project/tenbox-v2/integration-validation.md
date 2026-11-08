# R5統合のソフトウェア検証（2026-11-09 JST）

対象は独立系列`tenbox-v2`の採用済みR5と文書・ナビゲーション。基準mainは`634dde8cd8171e6aa539744135f360fc02a7cfde`、実装commitは`60f8466bbc37f83e4c60f7dd267de061168e617a`。[統合PR #133](https://github.com/Takazudo/zudo-case/pull/133)、[epic #130](https://github.com/Takazudo/zudo-case/issues/130)、[A #131](https://github.com/Takazudo/zudo-case/issues/131)、[B #132](https://github.com/Takazudo/zudo-case/issues/132)。この記録はネイティブStudio／現物の合格や製造承認ではない。

## 入力と再生成が一致

- 元STL ZIPと修正済みR5 bundleのSHA-256は依頼指定値と一致。原アーカイブ・受領記録は不変保存。
- 専用lock：Python3.12.14／CadQuery2.7.0／NumPy2.3.5／SciPy1.17.0。既存P5の環境は変更なし。
- `uv run --locked --project engineering/tenbox-v2/r5 python engineering/tenbox-v2/r5/regenerate.py`：clean＋source ZIP展開からの再生成に合格。最終配布source ZIPからも再生成を実施し合格（heavy guard PASS44秒）。元scratchディレクトリやprivate checkoutは不要。
- 最終`build.py --out <disposable> --publish-root <checkout>`はPASS50秒。実CAD82項目、独立export STEP27項目、importer contract29/29。STEPの形状差分体積、据置STEP/STLのbyte、全13 assembly STLと全15プロジェクト内meshの閉多様体・一貫した向き・正体積を実データから検査した。
- H2Dの15プロジェクト／22保存object／23印刷部品／16プレート実行、共通底板の2回印刷、実投影凸包、LEFT単一ノズル範囲、保存姿勢とtemplate/config byteを検査。native Studio load/sliceは未実施。
- ZIP5負例：truncated central directory、誤hash、重複member、manifest重複行で未検査memberを隠すケース、literal Relationshipを失うnamespace prefixを拒否。ZIPはclose/fsync、CRC・全inventory/hash確認後にatomic replace。
- タイムスタンプ／生成UUIDを含むZIP全体やSTEP headerの差は、実形状・model内容・設定byteの検査と区別する。元の受領hashを書き換えて形状差を容認しない。

## 文書と既存系列の回帰が合格

`pnpm check:docs`、`check:doc-routes`、`test:doc-structure`、`check:assets`、`test:setup`、`check`、`check:wind`、`build`、`check:built-doc-routes`、`check:built-preview-links`、`check:images`を実行し合格。128 MDX＝正式83＋互換45、build148ページ、検索83項目。built crawlは11180内部リンク／fragmentと互換URLを確認、production preview URL68件にlocal URL漏れなし。

既存の`check/test:two-way`（142 tests）、`check/test:printed-5mm`、R9／fitfix／fullset／M5／注文packet／ledger／生成table、setup、preview-origin unit/integration、asset preparation／Worker full-body fixturesも合格。`check:preview-isolation`は実CLIの2 testsに合格（guard PASS66秒）。`prepare:worker-assets`とWorker tests9件はローカル配信準備の検証だけで、deploymentは行っていない。

## 実ChromiumとHTTPの確認が合格

Chromium154.0.8037.57、desktop1440px／mobile390px。

- `scripts/verify-case-navigation.py`：default local originで244 checks、別dev server＋configured preview originでも244 checks。header4系列の所有、keyboard/mobile menu、P5/history/P4/P3のlinked parentsと初期collapse、focus/Restore/Broadenの上限、代表的な既存系列／shared／development、実検索UIと全正式検索項目・互換ページ除外を確認。
- `scripts/verify-tenbox-site.py`：339 checks。実CanvasとWebGL各11views（assembly／joints／rail gap／lid／floor／underside／H2D floor/roof）を描画し、distinct canvas画像と操作・iframe1440/390を確認。**built static siteをHTTP GET**した3 ZIP＋15 3MFの全bodyをcheckout byte／SHA-256と照合し、実ZIPを展開してCRC・manifest inventory/hashを確認。
- 観測JSONとスクリーンショットは[`project/validation/tenbox-v2-r5/`](../validation/tenbox-v2-r5/)に保存。描画は実ブラウザー証拠であり製造用meshの代替ではない。

初回downloadチェックはpublic packageの最終更新後に古いdistと比較して差を検出したため、最終asset固定後にbuildし直して合格を確認。中断したlocal HTTP serverの出力pipe切断も修復して再確認。これらの失敗を合格扱いにはしていない。

## レビューとCIを統合条件にする

独立レビューはZIP manifestの重複行欠陥を発見し、exact membership set検査と再現負例で修正。floorだけだったtopology確認も全現行STL／3MF meshへ拡張した。

最初のCI run42524776303では、既存uv0.10.2の埋込download一覧にPython3.12.14がないため新jobの環境準備が失敗。新jobに固定SHAのsetup-pythonで3.12.14を明示導入する修正を追加。uv0.10.2で同じlockを読み、3.12.14を指定した`sync --locked --dry-run`が変更なしで通ることをローカルで確認した。CIの最終結果はPRのcurrent-head runを参照し、未完了を合格とはしない。

mainへの統合はcurrent-head required CI・独立レビュー・必要なrepository approvalが揃ってから、最終commit messageに`[skip deploy]`を含めて行う。デプロイworkflowのpush条件を確認し、productionサイトはこの作業で更新しない。

Studio app load/slice、印刷、現物嵌合・締結・荷重・運搬、supplier価格／発注／支払い、製造承認は未実施。`production_approved:false`と既存のproduction holdsを保持する。
