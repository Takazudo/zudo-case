# R9-FITFIX-01 ローカル統合検証

2026-09-30。出発コミット `7f04c5bda0672ecf2cded79b6e1b48ad141e64b5`。受領セットのソースを独立候補へ追加し、保存R6入力のGit blob一致を確認した。

## CAD

- `uv run --locked --project engineering/r9-prototype-01 python engineering/r9-fitfix-01/build.py` をheavy-guard経由で実行。Python3.12.12 / CadQuery2.7.0 / ezdxf1.4.4 / numpy2.5.3。実行記録は `build.txt`、実環境は `../out/environment.json`。environmentのlockfile_execution_verifiedは生成器が自動判定しないnullであり、上記コマンドの実行が固定環境の根拠。
- 1.2/1.0mm両案、51種類のSTLとSTEP再読込、10パラメータ条件、C1/C2/C4/C5の検査が通過。詳細は `../out/validation.json`。
- 回帰11件すべて通過（`regression.txt`）。旧下辺形状が侵入する負の対照も含む。
- 旧R9の底・前後・左右のDXF３パターンは幾何エンティティが一致。ファイルのバイト一致とは別。双方のSHA-256付き記録は `body-patterns.json`。
- ガード16個の体積は基本39.235cm³、比較31.938cm³。蓋枠4個は84.378cm³ / 83.873cm³。価格未取得。

## 統合

`node scripts/sync-fitfix.mjs` で125候補・163資産を登録。元R9の141候補と217出力は保持し、旧版の台帳検査も通過。製造承認、G01〜G11、見積台帳は変更していない。

公開コピーは同じ出力のバイトを使う。`--check` は入力コード・uv.lock・ベンダーJS、CAD/ZIP/HTML、DXF比較証拠、公開コピー、現行指定、仕様台帳の差分を検出する。変更したバイト・旧版への現行指定の差戻しを拒否する回帰テストを追加した。

- 文書46件、内部リンク180件、表の再生成・台帳チェック通過。
- 628資産のサイズ・SHA-256照合通過。候補の各ファイルは25MiB以下、Git LFS不使用。
- TypeScript/コレクション検査、65ページのサイトビルド通過。
- 既存Nodeテスト一式147件通過（0失敗）。配信用資産の準備、ビルド内の本番プレビューURL、画像リンクも検査。
- ローカルChromeのWebGLで1440px / 390px、1.2/1.0mm、蓋開閉・バンド表示、C1/C2/C4/C5切替と文書内iframeを確認。横はみ出し、ページ/consoleエラーなし。`browser.json` と `preview-1440.png` / `preview-390.png` を参照。

再確認はルートで `pnpm dev --host 127.0.0.1 --port 4321` を起動し、heavy-guardとplaywright-guard経由で `node engineering/r9-fitfix-01/tools/check_preview.cjs` を実行する。PREVIEW_ORIGINとPLAYWRIGHT_MODULEで環境を指定できる。

## 未実施

現物嵌合・接着保持・反り・長穴/座金/工具適合・実ノブ寸法・バンド荷重・落下/疲労/運搬は未検証。蓋着脱は19位置のサンプル検査で、連続掃引ではない。3U60/7U60への展開はしていない。

旧R9のCAD一式は再生成せず、保存出力のハッシュと本体DXFの幾何を検査した。新候補の再生成と回帰テストはGitHub Actionsにも追加したが、このローカル作業ではリモートCI・commit/push・Issue close・デプロイ・発注を実行していない。#99〜#101はコード修正候補の検証済み範囲であり、現物ゲートを閉じる根拠ではない。

次の現物確認は `../handoff/FIT-RECORD.md` を使い、実際の試験片ID・SHA-256と結果を記録する。
