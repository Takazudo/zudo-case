# ZUDO CASE — モジュール用ケースの設計・製作資料

独立したケース系列の現行設計、プレビュー、ファイル、検証根拠をまとめた日本語ドキュメントサイトです。[ケースを選ぶ](src/content/docs/overview/start.mdx)から読み、[全体の状態](src/content/docs/overview/status.mdx)で系列をまたぐ状態を確認できます。**製造承認済みのファイルはありません。** ソフトウェア検査と現物確認を区別し、`production_approved: false`を保持します。

## ケースと資料の入口

| 系列 | 現行の位置づけ | 入口 |
|---|---|---|
| 金属ケース | 3U60・7U40・7U60。7U40はR11-BUILD-FEEDBACK-04（CADレビュー候補、現物未検証・価格未見積・未発注）、3U60・7U60はR6本体＋R8載せ蓋の基準 | [metal-case](src/content/docs/metal-case/index.mdx) |
| 7U40家庭印刷 | 5mm板の現行P5-PRINTED-5MM-TAB-JOINTS-J3。旧P4/P3はアーカイブ | [printed-5mm](src/content/docs/printed-5mm/index.mdx) |
| 10BOX-v2 | 二段3U60HPの独立系列。採用済みR5を保持し、[R6のダブルレール・側板固定](engineering/tenbox-v2/r6/README.md)は設計確認中 | [tenbox-v2](src/content/docs/tenbox-v2/index.mdx) |
| 2WAY | TW-01が作業版（A/B/Cはどれも現行の比較対象）、F5はその入力の不変の原資料。製造用CADではない | [two-way](src/content/docs/two-way/index.mdx) |
| 共通部品・元データ | 家庭印刷8mmスペーサーHOME-PRINT-SPACER-01（外径・穴径は仮寸法）、元レール・PCBと出典 | [shared](src/content/docs/shared/index.mdx) |
| アーカイブ | 置き換わった旧版の記録（金属7U40のR10以前、家庭印刷P4/P3など）。現行の作業には使わない | [archive](src/content/docs/archive/index.mdx) |

各系列の現行版の指定は`project/current-selection.json`にあります。通常の文書とナビゲーションは現行版だけを示し、旧版は[アーカイブ](src/content/docs/archive/index.mdx)から読めます。画像・図はサイトの`/files/`、CAD作業の入口は[engineering/README.md](engineering/README.md)です。系列間で形状・数量・注文記録を混ぜません。`engineering/release/`には承認済みファイルを置いていません。注文・支払い・製造承認はユーザーが別に判断します。

## 起動する

Node.js 24以上、pnpm 10.30.3を使います。初期化済みのチェックアウトなので、公式scaffoldのセットアップは再実行せず既存のlockfileから復元します。

```sh
pnpm install --frozen-lockfile
pnpm check:docs
pnpm check:assets
pnpm test:setup
pnpm build
pnpm dev
```

`pnpm dev`が表示するURLを開いてください。起動環境、プレビュー配信元の変更、依存・scaffoldの保守、デプロイと復旧は[サイトの起動と保守](src/content/docs/development/setup.mdx)にあります。過去の実行結果は[ブラウザー記録](project/browser-validation.md)、[zudo-doc 10.0.3保守記録](project/maintenance-zudo-doc-10.0.3.md)、[zudo-doc 9.1.2保守記録](project/maintenance-zudo-doc-9.1.2.md)を参照してください。

## 文書と設計を更新する

ページ追加、役割変更、カテゴリ変更の前に、共通編集方針[src/content/docs/development/maintenance.mdx](src/content/docs/development/maintenance.mdx)を読んでください。読者の作業、既存ページの重複、カテゴリ所有と境界、意味の変化を確認します。旧URLと生成ページは[文書所有表](src/content/docs/development/doc-structure.mdx)で管理します。

エージェントは[AGENTS.md](AGENTS.md)、CAD変更は対象系列の`engineering/*/AGENTS.md`と版付きREADMEに従います。金属の見積・製作台帳は[金属台帳保守](src/content/docs/metal-case/maintaining-data.mdx)、10BOX-v2の現行契約は`project/tenbox-v2/manifest.json`を参照します。既存ソース・受領ZIP・保存マニフェストは不変の根拠として保持します。ライセンスは元資料の表示に従い、文書整理で再ライセンスしません。

検査コマンドと確認範囲は[共通編集方針](src/content/docs/development/maintenance.mdx#リンク・資産を確認する)、各系列の再生成・検証は[engineering](engineering/README.md)にあります。配信設定は２ホストですが、リポジトリの更新だけで本番サイト更新済みとは扱いません。
