# ZUDO CASE — モジュール用ケースの設計・製作資料

ユーロラック等のモジュールを収めるケースを、互いに独立した設計系列ごとに整理した日本語のzudo-docサイトとエンジニアリング資料です。現物確認・見積・注文の判断材料をまとめますが、**製造承認済みのファイルはありません**（`engineering/release/`は注意書きだけ、`project/release-state.json`の`production_approved`は`false`）。注文・支払い・製造承認はユーザーが別に判断します。

## 系列と入口

サイトは６つのセクションに分かれ、ヘッダーの各項目が１セクションに対応します。最初に読むページは[プロジェクトを選ぶ](src/content/docs/overview/start.mdx)、系列をまたぐ状態の要約は[全体の状態](src/content/docs/overview/status.mdx)です。

| セクション | 対象 | 現行の版と状態 | 入口 |
|---|---|---|---|
| 全体案内 | 系列の選択、全体の状態、用語 | — | [overview](src/content/docs/overview/index.mdx) |
| 金属ケース | 3U60・7U40・7U60の単トレー（アルミ平板＋L字ブラケット、載せ蓋＋外周バンド） | 7U40は**R10-FULLSET-01**の一式準備候補（JLCカート保存済み・未発注・未払い）。3U60・7U60はR6本体・R8載せ蓋の基準。R9系は旧候補の履歴 | [metal-case](src/content/docs/metal-case/index.mdx) |
| 家庭印刷ケース | 7U40・5mm黒ASAの家庭印刷版 | **P5-PRINTED-5MM-TAB-JOINTS-J3**が現行。P4（Uniform四壁通気孔）とP3（通気孔なし）は旧版。ソフトウェア検査のみ | [printed-5mm](src/content/docs/printed-5mm/index.mdx) |
| 2WAY 実験設計 | 2トレーのA／B／C構成 | **TW-01**が作業版、F5は不変の原資料。製作CADではない | [two-way](src/content/docs/two-way/index.mdx) |
| 共通部品・元データ | 家庭印刷8mmスペーサー、元レール・PCBと出典 | スペーサーは高さ8mm採用、外径10mm・穴径5.5mmは仮寸法 | [shared](src/content/docs/shared/index.mdx) |
| 開発・保守 | サイトの起動、更新手順、文書の構成と旧URL | — | [development](src/content/docs/development/index.mdx) |

画像・図は`/files/`のAsset Viewerにあります。ある系列の候補が他の系列の仕様・数量・注文記録を変えることはありません。

### 金属ケース7U40の現行候補

[R10-FULLSET-01 一式準備](src/content/docs/metal-case/design/r10-fullset-01.mdx): アルミ6枚、PA12 20個、家庭ASA 72個。2026-10-26のユーザー決定により、追加の有料試験片の注文を前提にしません。[2026-10-26 JLCカート準備記録](project/order-records/r10-fullset-01-jlc-cart-2026-10-26.md)のとおり、メタル6点・PA12 20点を各1個保存済みで、未発注・未払いです。R9系（R9-PROTOTYPE-01、R9-FITFIX-01、R9-LID-M5-01）は[旧候補の履歴](src/content/docs/metal-case/design/history/index.mdx)として保存しています。

### 家庭印刷用8mmスペーサー

フレームとケース側板の間に入れる[8mmスペーサーのSTL・編集用ソース・印刷手順](engineering/home-print-spacer-01/README.md)。文書は[共通部品](src/content/docs/shared/home-print-spacer.mdx)にあります。まず1個で現物確認し、3U60は4個、7U40/7U60は各10個を印刷します。

## まず起動する

Node.js 24以上とpnpm 10.30.3を用意してください。このスナップショットは公式scaffolderで初期化済みで、`package.json`と`pnpm-lock.yaml`を含みます。新しいチェックアウトでは、依存をロックファイルどおりに入れてから使います。2026-11-06のzudo-doc 9.1.2更新時に確認した環境はNode.js 24.22.2、pnpm 10.30.3です。

```sh
# リポジトリのルートで実行
pnpm install --frozen-lockfile
pnpm check:docs
pnpm check:assets
pnpm test:setup
pnpm build
pnpm dev
```

このセットの初期化には公式`create-zudo-doc@5.27.0`を使いました。`scripts/setup.mjs`はscaffoldをまだ取り込んでいない文書のみのスナップショット向けです。この初期化済みチェックアウトでは再実行せず、ロックファイルから依存を復元してください。Git初期化、デプロイ、注文は自動実行しません。

2026-09-24（D1）の初回ビルドでは44ページを生成し、41件の文書ルートと検索項目、47件の公開資産を確認しました。以下の件数はその時点の記録です。同日のChrome 146.0.7680.153で、desktop 1440×900とnarrow 390×844の実表示も確認しました。41ルートと8カテゴリを両幅で開き、narrowでの横はみ出しはなく、検索・テーマ・画像・R8/R6プレビューの主要操作も動作しました。画面ごとの記録、ダウンロード件数、スクリーンショットは[検証記録](project/browser-validation.md)にまとめています。物理的な嵌合・強度・運搬試験はこのブラウザー確認に含みません。`pnpm dev`が表示するURLを開き、「プロジェクトを選ぶ」から読んでください。現在の文書数と旧URLの扱いは[文書の構成と旧URL](src/content/docs/development/doc-structure.mdx)を参照してください。

### ローカルと本番のプレビュー確認

`pnpm dev`で開いた文書のR8/R6プレビューと参照・旧版ZIPのリンクは、既定では同じチェックアウトの`public/previews/`と`public/downloads/`を参照します。R8ページの埋め込み枠の下にある「表示元: ローカル (public/)」を確認してください。`public/previews/r8-simple-lid.html`を変更すると、開き直したローカル文書からその変更を確認できます。

別のプレビュー配信元を試すときは、起動時にHTTP(S)のoriginだけを指定します。パスは付けません。

```sh
ZUDO_CASE_PREVIEW_ORIGIN=http://localhost:8787 pnpm dev
```

`dev`・`check`・`build` は同じチェックアウトで併用できます。起動ごとに `.cache/site-runs/run-*` の独立した設定と内部キャッシュを使うため、別コマンドを実行しても稼働中のdevの表示元は変わりません。異なるoverrideを指定したdevも、`pnpm dev --port 3001` のように別ポートで起動できます。記事・コード・設定は実行ごとのコピーを使い、devでは元の編集・追加・削除を約250ms間隔で反映します。`public/previews/` と `public/downloads/` は元のチェックアウトを直接参照します。`public/assets/` は zfb 4.5.0 で見つかったdev配信制限（zudo-front-builder#4233）の回避として、実行ごとの内部資産領域へ同期します。zfb 5.2.0でもこの同期を維持しています。設定を編集すると、同じ表示元とポートでネイティブdevプロセスを再起動します。build/checkは起動時のコード・設定コピーを使います。

内部キャッシュは終了時に削除します。強制終了などで残った実行フォルダーは、対応するプロセスが停止していることを確認してから削除してください。公開ビルドは従来どおりチェックアウトの `dist/` に出力し、`pnpm preview` もその出力を配信します。buildは `.cache/site-build.lock` で直列化し、同時の２件目をエラーで停止します。強制終了でロックが残った場合は、所有プロセスが停止済みと確認してから削除してください。

この場合は枠下に指定先のホストが表示されます。本番ビルドの既定値は`https://zudo-case-preview.zudolab.dev`で、文書とプレビューの２ホスト配信を維持します。本番ビルド前は上記環境変数を外してください。`pnpm build`後の`pnpm check:built-preview-links`で、生成した文書HTMLに本番ホストのリンクがあり、ローカルURLが混入していないことを確認できます。

### 依存・scaffoldの保守

現在のホストは zfb 5.2.0 / zudo-doc 9.1.2（history-server 9.1.2）、TypeScript 5.9を使います。Classicの外観を保つため`zfb.config.ts`で`themePack: "default"`を明示しています。コピーした公式scaffoldの版・変更箇所・同期手順は `ZUDO_DEPS_PINS.md`、9.1.2更新の実行結果は `project/maintenance-zudo-doc-9.1.2.md`、前回6.2.0更新は `project/maintenance-120.md` を参照してください。`pnpm check:wind` と `pnpm check:preview-isolation` は非デプロイ検証です。後者はインストール済みの実CLIで別ポート・並行build/check・編集・設定再読込を検証します。新CLIのscratch/defineは使えますが、build/checkの入力スナップショットを維持するためmirrorを残しています。

### 初期化履歴と確認範囲

元の文書のみのスナップショットではnpmレジストリの名前解決が`EAI_AGAIN`となり、その時点では初期化・ビルドを確認できませんでした。その後、2026-09-24に公式scaffolderの実行とロックファイルに基づく依存インストールを完了し、上記の実ビルドを確認しています。各画面のブラウザー確認結果・表示幅・残件は検証記録に記載します。

初期化前の文書のみのスナップショットで、取り込み内容だけを確認する場合:

```sh
node scripts/setup.mjs --dry-run
```

公式CLIを別フォルダーへ実行した場合は、次の形でも土台だけ取り込めます。

```sh
node scripts/setup.mjs --from /absolute/path/to/fresh-official-scaffold
```

既に運用中のサイトへ統合する場合は、setupを実行せず、記事・資産・設定を個別にマージしてください。補助スクリプトはファイル衝突があると上書きせず停止します。CLIの版は`ZUDO_DOC_CLI_VERSION`環境変数で指定でき、デフォルトは`9.1.2`です。生成結果は`.handoff/`に記録します。

## 文書の構成と旧URL

`src/content/docs/`の最上位は`overview`・`metal-case`・`printed-5mm`・`two-way`・`shared`・`development`の６セクションです。正式ページはどれか１つのセクションに属し、各カテゴリに`index.mdx`の入口があります。家庭印刷のサイドバーは`src/sidebars.js`で「現行 P5」「履歴 P4」「履歴 P3」に分けています。

2026-11-06の再編前にあった`models/`・`design/`・`manufacturing/`・`verification/`・`resources/`・`decisions/`・`handoff/`などのURLは、`unlisted: true`の互換ページとして残します。互換ページはサイドバー・検索・前後リンクに出ず、移動先へのリンクと旧見出しアンカーを持ちます。対応表は`project/doc-routes.json`で、互換ページと[所有表](src/content/docs/development/doc-structure.mdx)は`pnpm sync:doc-routes`で生成します。互換ページを手で編集しないでください。

## 金属ケースで最初に確認すべき状態

| 対象 | 現在の扱い |
|---|---|
| 採用方式 | 10BOX式の載せ蓋＋運搬時だけ外周バンド２本。蓋と本体のロックなし |
| 7U40 | R10-FULLSET-01の一式準備候補。現物嵌合・締結・運搬は未評価 |
| 3U60・7U60 | R6の名目CADとR8載せ蓋の表示寸法が基準。長穴・ガード保持・蓋の製作形状は未反映 |
| R7のM3ロック蓋 | 不採用の参考資料。最終仕様として注文しない |
| 現在の総原価 | 未確定。旧R3ガード2,264円を現行全体の見積に流用しない |
| 製作承認ファイル | なし。`engineering/release/`は注意書きだけ |

ガードの固定方法・嵌合、公差、ノブ上方の隙間、バンドによる天板のたわみ等も確認待ちです。`project/open-issues.json`と[発注前ゲート](src/content/docs/metal-case/verification/before-order.mdx)で管理します。

## フォルダー

```text
zudo-case/
├── README.md / AGENTS.md          # 全体ルール。系列別は engineering/*/AGENTS.md
├── zfb.config.ts                  # サイト設定（６セクションのヘッダー）
├── src/
│   ├── content/docs/             # MDX（６セクション＋旧URLの互換ページ）
│   └── sidebars.js               # 家庭印刷の明示サイドバー
├── public/
│   ├── assets/                   # Asset Viewerの画像・図・見積画面
│   ├── previews/                 # 単一HTMLの3Dプレビュー
│   ├── evidence/                 # 旧README、計算結果
│   └── downloads/                # 候補・参照・旧版のZIP
├── engineering/                   # 系列ごとのCADソースと出力（engineering/README.md）
├── project/                       # 仕様・根拠・見積・課題・注文記録・doc-routes.json
├── scripts/                       # 初期化、整合チェック、表とページの再生成
└── tests/                         # 初期化・台帳・文書構成などの検査
```

元のR6/R8ソースと旧アーカイブは保全しています。過去の生成コードやREADMEにある絶対パス・前提は作成当時のものです。そのまま全スクリプトを一括実行せず、[元レール・PCBと出典](src/content/docs/shared/rail-pcb-sources.mdx)と`engineering/README.md`を読んでからローカル環境に合わせてください。

## 更新と静的チェック

次は依存を入れる前でもNodeだけで実行できます。

```sh
node scripts/check-docs.mjs
node scripts/sync-doc-routes.mjs --check
node --test tests/doc-structure.test.mjs
node scripts/verify-assets.mjs
node --test tests/setup.test.mjs
```

- `check-docs`: メタデータ、ローカルリンク先、同じ階層での`sidebar_position`の重複、旧URL対応表との整合、機種寸法・数量・見積加算の整合を検査します。MDXコンパイラではありません。
- `check:doc-routes`／`test:doc-structure`: 互換ページと所有表が`project/doc-routes.json`から生成した内容と一致すること、６セクションとヘッダーの対応、家庭印刷サイドバーの網羅を確認します。ビルド後は`pnpm check:built-doc-routes`で旧URL・アンカー・検索除外・内部リンクを実HTMLで確認します。
- `verify-assets`: 同梱資産のSHA-256を、引継ぎ時の台帳に照合します。CADの強度・干渉・公差を保証するものではありません。意図的に変更した資産は差分になります。
- `test:setup`: 模擬scaffoldを使い、既存記事保護・衝突停止・復旧を確認します。公式CLIの実行確認ではありません。

機種別の表とBOMは台帳から再生成します。

```sh
# project/current-spec.jsonを根拠とともに更新した後:
node scripts/sync-reference-tables.mjs
node scripts/check-docs.mjs
```

自動生成の対象は`src/content/docs/metal-case/`の３機種ページ、機種比較、BOMの５ページ。R9とR10の表は`scripts/sync-r9-doc-table.mjs`と`scripts/sync-fullset.mjs`が金属ケースの各ページへ書き込みます。**台帳はCADジェネレーターの入力ではありません**。ここだけ直して製作データを更新済みにしないでください。

## 根拠と公開範囲

ユーザーが測定した寸法、採用方針、元STL/PCB、過去のモデル値、見積画面、助手の概算を分けました。会話由来の採用判断は`project/source-notes/user-decisions.md`、出典台帳は`project/sources.json`です。今回、サプライヤーの価格を取り直してはいません。

Cloudflare Workers Static Assetsへの公開設定は２つのホストに分けています。`zudo-case.zudolab.dev`は文書、Asset Viewerの画像・図、テキスト/JSON根拠を配信し、`zudo-case-preview.zudolab.dev`は単体HTMLプレビューと参照/旧版ZIPを配信します。`pnpm build`の後に`pnpm prepare:worker-assets`で配信フォルダーを分離し、25MiBを超える２ファイルは小片に分けてプレビューWorkerが元のURLでストリーム配信します。元ファイルのSHA-256は維持します。GitHub Actionsは`main`へのpushで２つのWorkerを順にデプロイし、`CLOUDFLARE_ACCOUNT_ID`と`CLOUDFLARE_API_TOKEN`をデプロイ手順だけに渡します。**noindexはアクセス制限ではありません。** 見積画像と旧版ZIPもそれぞれのホストで閲覧できる設定です。初期設定はルートパス配信です。

### 公開配信の検証範囲

ローカルのモックテスト（`node --test tests/verify-deployed-assets.test.mjs tests/worker-assets.test.mjs`）は、短いサンプル資産でHTTP転送、SHA-256照合、Workerのチャンク欠落・切り詰めを確認します。デプロイ後のGitHub Actionsと`pnpm verify:deployed`は、対象２ファイルを全量GETでストリーム読み込みし、チェックアウト内の元ファイルとバイト数・SHA-256を照合します。HEADリクエストは到達確認だけです。どちらもブラウザー/WebGL表示の証拠ではなく、ブラウザー表示の確認は[検証記録](project/browser-validation.md)を参照してください。

第三者ライブラリや元資料の著作権・ライセンス表示は元ファイルの記載に従います。資料整理によって再ライセンスしたものではありません。

## 再実行と復旧

`pnpm prepare:worker-assets`を同じビルド結果に対して再実行すると、世代番号と分割ファイルの完全性を確認してから「already prepared」と表示し、配信ファイルを変更せず終了します。不完全な分割ファイルや片方だけ残った入力が見つかった場合は停止します。`pnpm build`を再実行して入力を作り直し、改めて`pnpm prepare:worker-assets`を実行してください。準備中の失敗でも元の`dist/previews`と`dist/downloads`は移動せず、成功後にだけ配信用のコピーから除きます。`public/`や`engineering/`の元資料には触れません。

公式資料: [Installation](https://zudo-doc.takazudomodular.com/docs/getting-started/installation/) / [CLI](https://zudo-doc.takazudomodular.com/docs/reference/create-zudo-doc/) / [Configuration](https://zudo-doc.takazudomodular.com/docs/guides/configuration/)

## 2WAY 実験設計

独立した2トレーの検討は`engineering/two-way/AGENTS.md`と`project/two-way/`の範囲で扱います。F5は不変の原資料、TW-01が保守する作業版です。金属ケースのR9/R10とは別系列で、製造用リリースではありません。72/58mmのパッチ隙間の仮定は単トレーの蓋仕様を置き換えません。

TW-01の通常生成はオフラインで、既存CADの再生成を必要としません。

```sh
pnpm build:two-way
pnpm check:two-way
pnpm test:two-way
```

[2WAY文書](src/content/docs/two-way/index.mdx)と[ソース・ブラウザー検証手順](engineering/two-way/tw-01/README.md)を参照してください。元F5受入結果とTW-01の描画方式別結果は分けて記録します。
