# ZUDO CASE — zudo-doc引継ぎセット

**D1 / 文書スナップショット: 2026-09-24**

3U・60HP、3U＋3U＋1U・40HP、3U＋3U＋1U・60HPの金属ケースを、現物確認・見積・発注へ進めるためのドキュメントです。本文は日本語のMDX、サイト設定はzudo-doc用です。

このD1は**資料整理の版**です。ケースCADの新しい版や、製造承認ではありません。

## まず起動する

Node.js 22以上とpnpmを用意してください。このスナップショットは公式scaffolderで初期化済みで、`package.json`と`pnpm-lock.yaml`を含みます。新しいチェックアウトでは、依存をロックファイルどおりに入れてから使います。動作確認した環境はNode.js 24.13.1、pnpm 10.30.3です。

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

2026-09-24の初回ビルドでは44ページを生成し、41件の文書ルートと検索項目、47件の公開資産を確認しました。現在は画像・図15件をzudo-docのAsset Viewerに移し、`/files/`の一覧と各閲覧ページを追加して60ページを生成します。同日のChrome 146.0.7680.153で、desktop 1440×900とnarrow 390×844の実表示も確認しました。41ルートと8カテゴリを両幅で開き、narrowでの横はみ出しはなく、検索・テーマ・画像・R8/R6プレビューの主要操作も動作しました。画面ごとの記録、ダウンロード件数、スクリーンショットは[検証記録](project/browser-validation.md)にまとめています。物理的な嵌合・強度・運搬試験はこのブラウザー確認に含みません。`pnpm dev`が表示するURLを開き、「現在地と最初に読むページ」から読んでください。

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

既に運用中のサイトへ統合する場合は、setupを実行せず、記事・資産・設定を個別にマージしてください。補助スクリプトはファイル衝突があると上書きせず停止します。CLIの版は`ZUDO_DOC_CLI_VERSION`環境変数で指定でき、デフォルトは`5.27.0`です。生成結果は`.handoff/`に記録します。

## 入っているもの

| 大分類 | 内容 |
|---|---|
| 概要 | 現在地、採用仕様、未確認事項、用語 |
| ３機種 | 寸法、レール・金具・ガード数量、比較表 |
| 設計 | レール積層、8mmスペーサー、長穴、締結、ガード、載せ蓋とバンド |
| 製作 | BOM、見積依頼条件、印刷用データの扱い、過去価格の根拠 |
| 検証 | 嵌合・組立・持ち運びの確認と、発注前ゲート |
| 資料 | R8とR6の3Dプレビュー、CAD、STL、STEP、DXF、元データ |
| 判断履歴 | 5→8mm、ガード薄肉化、蓋のロック不採用、バンド採用 |
| 引継ぎ | セットアップ、次工程、更新手順 |

**41文書ページ、8カテゴリ**です。カテゴリ一覧は`project/navigation.json`にあります。画像・図は`/files/`の一覧と閲覧ページにも表示されます。既存のプレビューは、サイトを起動しなくても`public/previews/r8-simple-lid.html`をブラウザーで直接開けます。

## 最初に確認すべき状態

| 対象 | 現在の扱い |
|---|---|
| 採用方式 | 10BOX式の載せ蓋＋運搬時だけ外周バンド２本。蓋と本体のロックなし |
| 本体 | R6の名目CADが修正起点。３機種・8mmスペーサー・薄型ガード |
| ブラケット用長穴 | 意図は採用済み。R6の製作図にはまだ丸穴が残る |
| 蓋 | R8の表示用形状まで。新しい製作用STL/STEP/DXFは未生成 |
| R7のM3ロック蓋 | 不採用の参考資料。最終仕様として注文しない |
| 現在の総原価 | 未確定。旧R3ガード2,264円を現行全体の見積に流用しない |
| 製作承認ファイル | なし。`engineering/release/`は注意書きだけ |

ガードの固定方法・嵌合、公差、ノブ上方の隙間、バンドによる天板のたわみ等も確認待ちです。ここを見失わないため、`project/open-issues.json`と発注前ゲートを用意しました。

## フォルダー

```text
zudo-case-doc/
├── README.md / AGENTS.md
├── zfb.config.ts                 # この文書サイトの設定
├── setup.preset.json             # 公式初期化CLIへ渡す設定
├── src/content/docs/             # 41ページのMDX
├── public/
│   ├── assets/                  # Asset Viewerの画像・図・見積画面
│   ├── previews/                # R8/R6の単一HTML
│   ├── evidence/                # 旧README、計算結果
│   └── downloads/
│       ├── reference/           # 未承認のR6参照データ
│       └── archive/             # 不採用のR7・ロック比較
├── engineering/
│   ├── r6-body/                 # 元ソース・CAD・STL・PCB
│   ├── r8-preview/              # 載せ蓋の表示用ソース
│   └── release/                 # 承認後にのみ格納
├── project/                     # 仕様・根拠・見積・課題・ハッシュ
├── scripts/                     # 初期化、整合チェック、表の再生成
└── tests/                       # 初期化の安全な取り込みを検査
```

元のR6/R8ソースと旧アーカイブは保全しています。過去の生成コードやREADMEにある絶対パス・前提は作成当時のものです。そのまま全スクリプトを一括実行せず、`src/content/docs/resources/engineering.mdx`を読んでからローカル環境に合わせてください。

## 更新と静的チェック

次は依存を入れる前でもNodeだけで実行できます。

```sh
node scripts/check-docs.mjs
node scripts/verify-assets.mjs
node --test tests/setup.test.mjs
```

- `check-docs`: メタデータ、ローカルリンク先、機種寸法・数量・見積加算の整合を検査します。MDXコンパイラではありません。
- `verify-assets`: 同梱資産のSHA-256を、引継ぎ時の台帳に照合します。CADの強度・干渉・公差を保証するものではありません。意図的に変更した資産は差分になります。
- `test:setup`: 模擬scaffoldを使い、既存記事保護・衝突停止・復旧を確認します。公式CLIの実行確認ではありません。

機種別の表とBOMは台帳から再生成します。

```sh
# project/current-spec.jsonを根拠とともに更新した後:
node scripts/sync-reference-tables.mjs
node scripts/check-docs.mjs
```

自動生成の対象は３機種ページ、機種比較、BOMの５ページ。**台帳はCADジェネレーターの入力ではありません**。ここだけ直して製作データを更新済みにしないでください。

## 根拠と公開範囲

ユーザーが測定した寸法、採用方針、元STL/PCB、過去のモデル値、見積画面、助手の概算を分けました。会話由来の採用判断は`project/source-notes/user-decisions.md`、出典台帳は`project/sources.json`です。今回、サプライヤーの価格を取り直してはいません。

Cloudflare Workers Static Assetsへの公開設定は２つのホストに分けています。`zudo-case.zudolab.dev`は文書、Asset Viewerの画像・図、テキスト/JSON根拠を配信し、`zudo-case-preview.zudolab.dev`は単体HTMLプレビューと参照/旧版ZIPを配信します。`pnpm build`の後に`pnpm prepare:worker-assets`で配信フォルダーを分離し、25MiBを超える２ファイルは小片に分けてプレビューWorkerが元のURLでストリーム配信します。元ファイルのSHA-256は維持します。GitHub Actionsは`main`へのpushで２つのWorkerを順にデプロイし、`CLOUDFLARE_ACCOUNT_ID`と`CLOUDFLARE_API_TOKEN`をデプロイ手順だけに渡します。**noindexはアクセス制限ではありません。** 見積画像と旧版ZIPもそれぞれのホストで閲覧できる設定です。初期設定はルートパス配信です。

第三者ライブラリや元資料の著作権・ライセンス表示は元ファイルの記載に従います。資料整理によって再ライセンスしたものではありません。

公式資料: [Installation](https://zudo-doc.takazudomodular.com/docs/getting-started/installation/) / [CLI](https://zudo-doc.takazudomodular.com/docs/reference/create-zudo-doc/) / [Configuration](https://zudo-doc.takazudomodular.com/docs/guides/configuration/)
