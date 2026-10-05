# TW-01 検証記録 — 2026-10-05

対象: epic #106、実装順 #107 → #108 → #109 → #110 → #111。基準 main は `6a13d80d816b0247ab9eee761c29c1fb786b76cc`。実機開発 #112、R9 #102、フレームワーク移行 #105 は別管理。製造承認・発注・デプロイ・マージは行っていない。

## 原本と維持ソース

受領した `zudo-case-prototype-F5.zip` は SHA-256 `2060f83d75c93c7e5a29e6fe0751ac1fae101dccba8c7bf08d2a43080f7b4e58`、5,574,131 bytes。原本の読みやすい最小ビルド集合は `engineering/two-way/f5-reference/SOURCE-RECEIPT.json`で個別照合する。再構築したファイルを原本とは表示しない。

原本の使い捨てディレクトリーで HTML を再生成し、原本 HTML と SHA-256 `833eb36f5a18e4cec5135eb1e804069e6028b947187a0621f28d42d4628b2915` が一致。原本数値回帰117件のログは `original-F5-baseline.tap`。この117件は原本確認であり TW-01 納品数ではない。

TW-01 は canonical R6 PCB 全外周／切欠きと原寸レールを読み取り、1.6 / 1.6 / 8 / 1 mm の積層を保持。B の独立3U×2＋1 mm、C の全7U＋70 mm、両トレー原寸フレームを検査。C を48 mm蓋に戻す負例はクリアランス −15.450925 mm、70 mm は +6.549075 mm。物理ゲートは全て未測定のまま。

## 実行環境

Linux x86_64、Node 24.19.0、Python 3.12、pnpm 10.30.3（既存CIと同じ系列）。canonical conversion は `uv sync --frozen` の固定依存を使用し、変換結果を保存済み frame-data.js とバイト比較した。

Playwright 1.58.2、Chromium 133.0.6943.0（`@sparticuz/chromium@133.0.0`）、Noto Sans CJK JP。標準 Playwright browser CDN はアーカイブが途中で切れたため、npm 配布 Chromium を利用した。WebGL は実際の WebGL context と ANGLE/SwiftShader で実行しており、物理GPUでの検証とはしない。

## TW-01 自動検査

- `node --test engineering/two-way/tw-01/tests/*.test.cjs`: **142 / 142 pass**、0 skip。`tw-01-tests.tap`。原本117件を TW ソースへ適用する数値回帰に加え、canonical source・全15設定・安全なimport・成果物検査を含む。
- `node engineering/two-way/tw-01/build.cjs --check`: 29生成物に差分なし。独立した2回の生成が全バイト一致。
- ソースZIPを空ディレクトリーへ展開し、親Nodeテスト環境を分離し、原本receiptを含む24契約テストの実行（0 skip）とビルドを確認。出力がリポジトリからの生成物と全バイト一致。
- 6 GLB をバイナリから再読込し、メートル/Y-up変換後の頂点境界をresolverの期待値と照合。manifestのSHA-256とサイズを全成果物で照合。最大ファイルも25 MiB未満。
- `scripts/prepare-frame-data.py` の再変換が保存結果と一致。既存R6ソースは変更していない。

## ブラウザー（別々に記録）

| 検査 | 結果 | 証拠 |
|---|---|---|
| software rasterizer | 56 pass | browser-software.json / software-390.png |
| WebGL / SwiftShader | 56 pass | browser-webgl.json / webgl-B-play.png / webgl-C-invalid48.png |
| ネイティブ文書・preview origin・準備済みHTTP成果物 | 36 pass | browser-integration.json / docs-390.png |

オフライン file:// でA/B/C全8姿勢、原寸／分解フレーム、接合部、表示切替、カメラ、キーボード、拡大表示のフォーカス／Escape、320/390/768/1200/1600 pxおよび高さ360 px、JSON/PNG書出し、旧F5設定・TW設定・不正入力の原子的拒否、偽承認情報の無効化を確認。レポートに検査したHTMLのSHAを記録。C旧48 mmの負例も明示。

統合検査はローカルdocs、別origin `ZUDO_CASE_PREVIEW_ORIGIN` のiframeと表示元ラベル、6文書、390/1200 px、Worker準備ディレクトリーからの全26成果物HTTP応答のSHA照合、preview indexと直開きを含む。本番URL形は既存 built-preview-links チェックで検査。デプロイしていないため本番HTTPの新成果物確認は未実施。

再実行: `tests/browser/package.json` の固定 Playwright をインストールして Chromium を用意する。`node engineering/two-way/tw-01/tests/browser.cjs --backend software --out /tmp/tw-software` と `--backend webgl --out /tmp/tw-webgl` を別々に実行する。非標準browserは `TW_CHROMIUM`、Playwrightは `TW_PLAYWRIGHT_MODULE` で指定可能。統合検査は localhost:4173 の標準dev、4174 のpreview-origin上書きdev、127.0.0.1:8787 の dist-preview HTTP serverを起動し `node engineering/two-way/tw-01/tests/integration-browser.cjs` を実行する。

## 既存リポジトリ検査

`repository-checks.json` に全13コマンドの終了0を記録: check:docs / check:tables / check:assets / check:r9 / check:r9-doc-table / check:r9-ledger / check:fitfix / check:fit-test-order / test:r9 / test:setup / test:ledger、およびpreview links・origin isolation、Worker準備・deployed verifier fixture tests。

最終 `final-check-results.json` と `final-check-*.log`: full check、full build（73 pages、53 search entries）、built-preview-links（39 production URLs / 53 docs）、Worker assets準備、Worker実資産・deployment contractテスト9件、TW生成差分チェックは全て終了0。既存の巨大2資産のチャンク分割とpreview originルーティングを保持。

既存R6/R8/R9/fitfixソース、release/gate/quote台帳は変更なし。既存CIのCAD再生成ゲートはそのまま維持した。リモートCIの結果はPRの現在headで確認すること。この記録だけをリモートCIや物理検証の合格とはしない。

## 残る確認

PRで現在headのCIを確認し、変更差分と日本語UIをレビューする。実GPU・他OSブラウザーでの描画、実測寸法、パッチクリアランス、カラー位置決め、ストラップ保持、トランク収納／荷重は #112 の物理開発で別途検証する。72 / 58 mm の前方ギャップは仮定値。ソフトウェアの合格は製造承認ではない。


## 継続レビュー — 2026-10-05

対象head `a5f36ab3245c978ae8638bb3fa05eac1e8e1705d` の run [37290162498](https://github.com/Takazudo/zudo-case/actions/runs/37290162498) は両ジョブ成功。実ログを読んだ。PR合成merge `339025ca9f62769ed532b20c48411236640c4899` は同headとbase `6a13d80d816b0247ab9eee761c29c1fb786b76cc` の組み合わせ。

- check: 142 pass / 0 fail / 0 skip、29成果物一致、73 pages build、39 production preview URLs / 53 docs、Worker 9 pass。
- cad-regenerate: R9検査156 pass / 14 flag / 0 fail（flagは物理承認ではない）、候補パッケージ生成、repeatability 6 pass、tracked outputsの差分なし。
- 後続fitfix: geometry 11 pass、使い捨て出力154 files / 51 mesh readbacks、t1p2 / t1p0および各coupon検査成功、body DXFの3種のdrawing patternが全て一致。

#107–#111の仕様・差分・日本語文書・変換器・ビルド・設定/UIをレビューした。独立した読み取り専用レビューで、連続範囲のF5入力をUIが正しく示さない不具合を確認。厚み1.75 mm / スタンド板7 mmが空のselect、gap72.3 mm / hinge93°がstepで丸めたslider表示になっていた。入力値・geometryは保持されていた。数値入力と非整列値のstep=anyでUIを修正し、整列値では元stepへ戻す。モデル・原本・レール/PCB・寸法JSON・GLBは変更しない。

最終HTMLをChromium 151.0.7922.173でlocal HTTP経由によりsoftwareとWebGL別々に検査し、各59 pass。新しい3チェックは連続厚みのimport表示、fractional slider表示、編集/export一致。レポートは `review-browser-software.json` / `review-browser-webgl.json` に新HTML SHAとtransportを記録。WebGLはANGLE/SwiftShader指定で物理GPU検証ではない。旧56件file://証拠は旧HTMLの記録として保持する。

この環境ではsystem Chromiumのfile://はERR_BLOCKED_BY_ADMINISTRATOR、npm Chromium133は起動後SIGSEGV。新HTMLのfile://再実行は**blocked**。local HTTPの成功をstandalone再確認とは表示しない。portable ZIPの24契約テスト/0 skipと再生成一致、TW142件、生成drift検査は再実行する。CIは修正後headで別途PRに結果を記録し、必須未確認がある間はDraftを維持する。

legacy R6/R8/R9/fitfix、current-spec、release-state、G01–G11、quoteのdiffは空。#112、#102、#105は別件。マージ・デプロイ・製造承認・連絡・発注・課題クローズは未実施。

## マージ判定基準の改訂 — 2026-10-05

ユーザーの追加指示により、今回のソフトウェア統合では `file://` の実行を一律のマージ条件から外す。管理ポリシーでページ読込自体が禁止されることと、HTMLの不具合を区別する。以下を今回の必要条件とする。この節は上記の「file再検査が終わるまでDraft」と以前のマージ禁止記述に優先する。

1. マージ対象のHTMLが検査レポートと同じSHA-256であること。
2. 単体配布の静的確認: JS/CSS/形状/画像をHTML内に持ち、外部script/stylesheet/画像、実行時fetch/XHR、module import、service worker、origin依存の読込がないこと。設定は選択したFileから読み、書出しはBlob/data URLを使う。localStorage拒否はcatchされ、起動・描画の必須条件にならないこと。
3. 同じHTMLのlocal HTTPでsoftware/WebGLを別々に検査し、各59チェック（fractional import表示・編集/exportを含む）、ページ例外なし、外部資産要求なしを確認すること。
4. TW数値/設定/生成差分・既存サイト/CAD回帰を含む現在PR headのCIが成功し、最終実ログを確認すること。変更後は新headで再確認する。

`file://` は許可された環境で行う追加の互換性検査として残す。最新HTMLの直接ファイル実行は依然 **blocked / 未確認**。HTTP合格をfile合格へ言い換えず、管理ポリシーを変更・回避しない。Playwright 1.58.2は再実行時の固定環境として維持し、既存レポートを新規実行とは表示しない。実GPU・他OS・ブラウザー固有の保存/ダウンロード制限も未確認。

### 今回の照合結果

対象実装head `8b8341e49f327c0cdfc4da3a44400b59f25c5594` のHTML Git blob `607c8954d2ac3b694adc541181d86ad86120e515` を取得し、1,379,050 bytes、SHA-256 `19a51c26c1549f4bde4a04d214a1edb62666d14f8675a73b0d19f805d72e6230` と照合した。静的検査で8個のinline classic scriptと1個のdata PNGを確認。外部script/link/iframe/object/base、CSS url/@import、fetch/XHR/WebSocket/dynamic import/service worker/location依存なし。localStorageの読み書きはともにtry/catch内。設定は `File.text()`、JSONはBlob URL、PNGはcanvas data URLを使用する。

`review-browser-software.json` と `review-browser-webgl.json` は同じSHAで各59 pass、errors空、transport `local-http`、Chromium151.0.7922.173。WebGLはANGLE/SwiftShaderで実GPU検証ではない。今回、既存レポートの照合と静的検査を実施した。新しいbrowser runや最新HTMLのfile screenshotsは作成していない。旧56件file記録と旧画像の対象版は変えない。実装の新たな具体的不具合は見つからず、HTML・モデル・設定・geometry・生成物を変更しない。

実装headのCI run37307366481は両ジョブsuccess、実ログ確認済み。今回の文書/CI変更は別の新headとして再検査し、最終結果・merge SHA・post-merge結果はPR #113に記録する。

### マージとデプロイの分離

既存deploy workflowはmain pushで自動公開するため、pushのhead commit messageに `[skip deploy]` がある場合だけdeploy jobをskipする条件を追加する。今回のmerge messageにこの印を付ける。通常pushと手動deployの動作は維持する。`check.yml` はmain pushでも既存のcheck/CAD両ジョブを実行し、マージ後を検査する。CIをskipする印は使用しない。

#112現物開発、#102 R9現物、#105基盤移行は別件。F5とlegacy台帳は不変。マージのみ許可され、デプロイ・製造承認・連絡・発注・課題クローズ・resource cleanupは行わない。
