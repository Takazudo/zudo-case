# ローカルサイトのビルド・ブラウザー検証

この記録は文書サイトの表示と操作を扱う。ケースの嵌合、強度、落下、疲労、運搬を検証するものではない。

## 環境と再現手順

| 項目 | 記録 |
|---|---|
| 確認日 | 2026-09-24 |
| Node.js | v24.13.1 |
| pnpm | 10.30.3 |
| 公式 scaffolder | create-zudo-doc 5.27.0 |
| 依存導入 | pnpm install --frozen-lockfile 完了 |
| 静的文書検査 | Pass: 41 MDX、8カテゴリ、122内部リンク。 |
| 資産検査 | Pass: 241ファイル、223,675,056 bytes、SHA-256一致。 |
| setup単体テスト | Pass: 7/7。 |
| ビルド | 2026-09-24の最終・guarded pnpm buildが成功（verdict=PASS、13.64秒）。44ページ、検索index 41項目、broken-link warningなし。47公開資産。 |
| 起動 | pnpm dev が表示するローカルURL |
| ブラウザーと版 | Chrome 146.0.7680.153 |
| Desktop viewport | 1440 × 900; screenshots inspected: overview/start, R8 embedded preview, R6 standalone preview |
| Narrow viewport | 390 × 844; all 41 routes passed with H1 and zero horizontal overflow; overview/start, R8 docs, sidebar, and search screenshots inspected. |
| スクリーンショット・記録 | 下記basenameの画像は一時ローカル保存で、リポジトリには含めない。絶対パスは記録しない。 |

チェックアウト後の再現コマンド:

    pnpm install --frozen-lockfile
    pnpm check:docs
    pnpm check:assets
    pnpm test:setup
    pnpm build
    pnpm dev

ブラウザー確認は実際の画面を操作して行う。重いブラウザー実行にはリポジトリの作業指示にあるheavy guardを使う。HTTP取得だけの成功はUI確認として数えない。

スクリーンショット（temporary local evidence; not bundled）: zudo-case-start.png, zudo-case-r8.png, zudo-case-r6.png, zudo-case-mobile.png, zudo-case-mobile-menu-settled.png, zudo-case-mobile-search.png, zudo-case-mobile-r8.png, zudo-case-image-open.png, zudo-case-r8-standalone.png. The large R6 source preview also remains local.

## 8カテゴリの一覧ルート

| ルート | カテゴリ | Desktop | Narrow |
|---|---|---|---|
| /docs/decisions/ | decisions | 200 + H1 | 200 + H1 |
| /docs/design/ | design | 200 + H1 | 200 + H1 |
| /docs/handoff/ | handoff | 200 + H1 | 200 + H1 |
| /docs/manufacturing/ | manufacturing | 200 + H1 | 200 + H1 |
| /docs/models/ | models | 200 + H1 | 200 + H1 |
| /docs/overview/ | overview | 200 + H1 | 200 + H1 |
| /docs/resources/ | resources | 200 + H1 | 200 + H1 |
| /docs/verification/ | verification | 200 + H1 | 200 + H1 |

## 41文書ルート

以下の41ルートをdesktop 1440×900とnarrow 390×844で個別に開き、HTTP 200とH1を確認した。narrowでは全ルートで横方向のはみ出しがないことも確認した。この巡回は、各ページの本文・サイドバー・全リンクを個別に読み込んだという意味ではない。そうした操作は下の共通確認に記録する。

| # | ルート | 文書 | Desktop | Narrow |
|---:|---|---|---|---|
| 1 | /docs/decisions/decisions | 採用・不採用の判断 | 200 + H1 | 200 + H1; zero overflow |
| 2 | /docs/decisions/history | R1〜R8の変更履歴 | 200 + H1 | 200 + H1; zero overflow |
| 3 | /docs/decisions/ | 判断履歴 | 200 + H1 | 200 + H1; zero overflow |
| 4 | /docs/design/brackets-slots | ブラケットと公差吸収用の長穴 | 200 + H1 | 200 + H1; zero overflow |
| 5 | /docs/design/construction | 平板５枚と役割分担 | 200 + H1 | 200 + H1; zero overflow |
| 6 | /docs/design/fasteners-feet | 締結材・底面・接地 | 200 + H1 | 200 + H1; zero overflow |
| 7 | /docs/design/guards | 薄型PA12ガード | 200 + H1 | 200 + H1; zero overflow |
| 8 | /docs/design/ | 共通設計 | 200 + H1 | 200 + H1; zero overflow |
| 9 | /docs/design/lid-bands | 10BOX式の載せ蓋と外周バンド | 200 + H1 | 200 + H1; zero overflow |
| 10 | /docs/design/rail-stack | 実レール・PCB・8mmスペーサー | 200 + H1 | 200 + H1; zero overflow |
| 11 | /docs/handoff/ | ローカルへの引継ぎ | 200 + H1 | 200 + H1; zero overflow |
| 12 | /docs/handoff/maintenance | 文書・表・資産の更新 | 200 + H1 | 200 + H1; zero overflow |
| 13 | /docs/handoff/setup | ローカルでzudo-docを起動する | 200 + H1 | 200 + H1; zero overflow |
| 14 | /docs/handoff/tasks | 次に行う作業 | 200 + H1 | 200 + H1; zero overflow |
| 15 | /docs/manufacturing/aluminum-order | アルミ板の見積・発注条件 | 200 + H1 | 200 + H1; zero overflow |
| 16 | /docs/manufacturing/bands-suppliers | 調達先と運搬バンドの候補 | 200 + H1 | 200 + H1; zero overflow |
| 17 | /docs/manufacturing/bom | ケース側BOM | 200 + H1 | 200 + H1; zero overflow |
| 18 | /docs/manufacturing/costs | 見積・概算・未取得費用 | 200 + H1 | 200 + H1; zero overflow |
| 19 | /docs/manufacturing/ | 製作・見積 | 200 + H1 | 200 + H1; zero overflow |
| 20 | /docs/manufacturing/print-order | JLC3DP用STLの投入と数量 | 200 + H1 | 200 + H1; zero overflow |
| 21 | /docs/models/3u60 | 3U・60HP | 200 + H1 | 200 + H1; zero overflow |
| 22 | /docs/models/7u40 | 3U＋3U＋1U・40HP | 200 + H1 | 200 + H1; zero overflow |
| 23 | /docs/models/7u60 | 3U＋3U＋1U・60HP | 200 + H1 | 200 + H1; zero overflow |
| 24 | /docs/models/comparison | ３機種の比較 | 200 + H1 | 200 + H1; zero overflow |
| 25 | /docs/models/ | ３機種の仕様 | 200 + H1 | 200 + H1; zero overflow |
| 26 | /docs/overview/glossary | 用語と座標 | 200 + H1 | 200 + H1; zero overflow |
| 27 | /docs/overview/ | はじめに | 200 + H1 | 200 + H1; zero overflow |
| 28 | /docs/overview/scope | 目的・範囲・根拠の扱い | 200 + H1 | 200 + H1; zero overflow |
| 29 | /docs/overview/start | 現在地と最初に読むページ | 200 + H1 | 200 + H1; zero overflow |
| 30 | /docs/overview/status | 採用仕様とデータ状態 | 200 + H1 | 200 + H1; zero overflow |
| 31 | /docs/resources/body-preview | R6・本体とレールのプレビュー | 200 + H1 | 200 + H1; zero overflow |
| 32 | /docs/resources/current-preview | R8・載せ蓋＋外周バンド | 200 + H1 | 200 + H1; zero overflow |
| 33 | /docs/resources/engineering | CADの再生成とソースデータ | 200 + H1 | 200 + H1; zero overflow |
| 34 | /docs/resources/files | 版別ファイルとダウンロード | 200 + H1 | 200 + H1; zero overflow |
| 35 | /docs/resources/ | データとプレビュー | 200 + H1 | 200 + H1; zero overflow |
| 36 | /docs/resources/sources | 資料台帳と出典 | 200 + H1 | 200 + H1; zero overflow |
| 37 | /docs/verification/assemble-test | 組立・蓋・持ち運びの確認 | 200 + H1 | 200 + H1; zero overflow |
| 38 | /docs/verification/before-order | 発注前ゲート | 200 + H1 | 200 + H1; zero overflow |
| 39 | /docs/verification/fit-test | 小さい試験片から確認する | 200 + H1 | 200 + H1; zero overflow |
| 40 | /docs/verification/ | 現物確認・承認 | 200 + H1 | 200 + H1; zero overflow |
| 41 | /docs/verification/release | 検証記録と製作承認 | 200 + H1 | 200 + H1; zero overflow |

## 共通操作と資産

| 確認項目 | Desktop | Narrow | 実際の操作・結果 |
|---|---|---|---|
| 入口: /docs/overview/start、初期ページへの誘導 | Pass: 200 + H1 | Pass: 200 + H1; screenshot inspected | |
| 8カテゴリ一覧とサイドバー移動 | Pass: category listing → 7U40 | Pass: open sidebar → メインメニューに戻る → 機種 → ３機種の仕様 | Narrow sidebar settled at 256px; readable screenshot |
| 文書内リンクを実際に開く | Pass: 93 unique local targets returned status below 400 by HEAD; selected real clicks | Pass: sidebar navigation above | 7U40 reference ZIP was downloaded and checked separately |
| 日本語の文字・折返し・見出し | Pass: inspected desktop screenshots | Pass: inspected overview/start, R8 docs, and sidebar screenshots | Route sweep checked H1 on all 41 pages; it did not manually inspect all page prose |
| 日本語検索: 検索語、候補、遷移先 | Pass: 「載せ蓋」 yielded 12 results | Pass: 「載せ蓋」 yielded 12 results; R8 result opened with H1 | |
| light/dark切替と表示 | Pass: dark→light; data-theme and background changed | Pass: dark→light | |
| 画像の拡大、閉じる操作 | Pass: overlay opened with 2 images; Escape closed it to 1 | Pass: overlay opened with 2 images; Escape closed after transition to 1 | |
| R8プレビューの表示と実際の操作 | Pass: embed loaded; model 7u40→3u60 and travel preset worked; standalone render/control screenshot inspected | Pass: iframe present without overflow; model 7u60 and open preset selected | |
| R6プレビューのリンク先起動と操作 | Pass: standalone opened; model, guard variant, exploded controls worked | Pass: linked standalone opened; 3u60 model selected | Current linked presentation preserved |
| 参照ダウンロード | Pass: browser click downloaded 7u40-r6-aluminum-NOT-RELEASED.zip (263,502 bytes) | Pass: same ZIP downloaded, 263,502 bytes | All 9 current ZIP URLs separately returned nonempty bytes matching their source assets |
| Console errors | Pass: none in stable-page capture | Pass: no console/page errors in narrow route sweep | |
| Failed network requests | Pass: no HTTP ≥400 in stable-page capture | Pass: no HTTP ≥400 in narrow route sweep | Earlier rapid-navigation run aborted dev reloads and an image/download after successful display/download; stable captures clean |

## 現行の参照ZIP

発注前の参考データとしてサイトが案内する9ファイル。R7・ロック比較のarchive ZIPは現行参照データに含めない。

| Filename | Live server bytes + source cmp | Browser desktop click | Browser narrow click |
|---|---:|---|---|
| 3u60-r6-guards-t1p2-NOT-RELEASED.zip | 17,781; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 3u60-r6-guards-t1p0-NOT-RELEASED.zip | 17,718; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 7u40-r6-guards-t1p2-NOT-RELEASED.zip | 25,994; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 7u40-r6-guards-t1p0-NOT-RELEASED.zip | 25,927; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 7u60-r6-guards-t1p2-NOT-RELEASED.zip | 25,932; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 7u60-r6-guards-t1p0-NOT-RELEASED.zip | 25,844; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 3u60-r6-aluminum-NOT-RELEASED.zip | 213,989; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |
| 7u40-r6-aluminum-NOT-RELEASED.zip | 263,502; source match | Pass: 263,502 bytes | Pass: 263,502 bytes |
| 7u60-r6-aluminum-NOT-RELEASED.zip | 263,555; source match | not individually clicked; live-server/CMP passed | not individually clicked; live-server/CMP passed |

## 結果と残件

ブラウザー全体の結果: **pass**。41文書ルートと8カテゴリをdesktop 1440×900、narrow 390×844で開き、各ルートのH1を確認した。narrowでは横方向のはみ出しはなかった。主要なナビゲーション、検索、テーマ、画像、R8/R6プレビュー、ダウンロード、安定ページのconsole/networkを実画面で確認した。現行参照ZIP9件はlive-serverから非空取得でき、各バイト列が同梱ソースと一致した。UIクリックは7U40アルミZIPを両幅で確認し、残る8件は個別クリックしていないことを記録した。ケースの現物試験や製造承認を示す結果ではない。
