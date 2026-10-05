# TW-01 / 2WAY 実験設計

F5の採用構造を維持した独立トレーの作業版。製造承認・耐荷重・実機適合は未検証。
`../f5-reference/` は元ZIPの最小完全ソース。改変しない。

## 再生成

リポジトリルートで Node.js 24 / Python 3.11–3.12 を使用する。

```sh
node engineering/two-way/tw-01/build.cjs --out /tmp/two-way-output
node engineering/two-way/tw-01/build.cjs        # この版の公開資産だけ更新
node engineering/two-way/tw-01/build.cjs --check
node --test engineering/two-way/tw-01/tests/*.test.cjs
```

通常のHTML・設定・表・GLB・ZIP生成は標準ライブラリのみ、ネットワーク不要。
`--check` は一時出力と比較して消去する。ソースに書き込まない。
GLBは同じ表示メッシュを mm/Z-up から metres/Y-up に剛体座標変換した閲覧用。
製作STL/STEP/DXFは生成しない。決定的なZIP日時は2020-01-01。

## 正規輪郭を再変換する場合のみ

```sh
uv sync --locked --project engineering/two-way/tw-01
uv run --locked --project engineering/two-way/tw-01 python engineering/two-way/tw-01/scripts/prepare-frame-data.py --out /tmp/two-way-contours
cmp /tmp/two-way-contours/frame-data.js engineering/two-way/tw-01/source/frame-data.js
```

出力を確認後、意図的な更新時のみ `source/frame-data.js` を置換する。
入力は既存 `engineering/r6-body/source-data/` のレール全頂点・全インデックスとPCB全輪郭。
7Uでは raw Y→U / raw X→V。配置は `placements.json`。
空の3U側面固定軸だけはR6 `configure()` の明示規則（中心±45、V=21.3105735）を採用する。
Shapely/GEOS版、入力SHAは焼き込みデータに残す。非多様体レールを修復しない。

## 単一計算源

`project/two-way/study-spec.json` が宣言入力。`source/model.js` の `dimensions()` が純粋な寸法・診断リゾルバー。
UI・設定・表・エクスポートは同じ結果を使う。F5近似切欠きから正規輪郭へ変更したが、外形・固定軸・積層は変更しない。
Cの48mm蓋も入力可能で、背板干渉を警告する。元PCBは切り縮めない。

F5 `zudo-case-study/5` の全state項目を保持し、TW-01 `zudo-case-two-way/1` へ変換する。
新schemaはfamilyId、mm/Z-upを要求する。derived、承認フラグ、外部URLは信用せず再計算。
F4、欠落・不正項目、未知familyは失敗し、UIの前状態を保持する。非対応のF5 state項目はない。

## ブラウザー（任意の開発環境）

```sh
npm install --prefix engineering/two-way/tw-01/tests/browser
engineering/two-way/tw-01/tests/browser/node_modules/.bin/playwright install chromium
pnpm test:two-way:browser --backend software
pnpm test:two-way:browser --backend webgl
```

`--out` に証拠出力ディレクトリ、`--url` にローカルHTTPビューアーを指定できる。
既存Chromiumは `TW_CHROMIUM`、既存Playwrightモジュールは `TW_PLAYWRIGHT_MODULE` で指定可能。
softwareはgetContextでWebGLを無効化して強制する。WebGLに落ちた場合はblockedで終了する。
レポートにブラウザー版・描画方式・TW-01 HTMLハッシュを記録。物理承認を意味しない。
