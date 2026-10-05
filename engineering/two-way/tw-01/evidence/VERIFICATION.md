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
- ソースZIPを空ディレクトリーへ展開し、原本receiptを含む契約テストとビルドを実行。出力がリポジトリからの生成物と全バイト一致。
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
