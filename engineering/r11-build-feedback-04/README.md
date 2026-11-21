# R11-BUILD-FEEDBACK-04 — 7U40 蓋の四辺内側ガイド

7U40 金属ケースの **現行の設計レビュー候補** です。R10-FULLSET-01（`7u40-t1-groove1p70-m5`、基準コミット `b7a9e3cd1fba3a12fa8a625ab4f0f43d4a06674a`）を基に、R11-BUILD-FEEDBACK-03 と比較した改訂で、蓋の内側位置決めスカートを前後に加えて左右にも延ばしました。**製造承認ではありません**（`production_approved=false`、状態 `CAD_REVIEW_CANDIDATE_NOT_PHYSICALLY_VERIFIED`）。他機種・他系統へは適用しません。

- PA12 20個（本体12＋蓋8、各1個）、アルミ板6枚、家庭印刷の丸ワッシャー1モデル（使用64個 = 本体外側40＋本体上部内側8＋蓋壁16）。
- 板の機能穴58個 = 本体長穴40（15.5 × 5.5 mm）＋レール丸穴10＋蓋丸穴8。専用の吊り穴はなし。
- R11-03 から形状が変わったのは蓋の4隅と左右中間の6個だけです。前後中間の蓋2個、本体12個、アルミ6枚、金具の定義・数量・位置は R11-03 と同一です。

## 構成

| パス | 内容 |
|---|---|
| `source/` | 受領アーカイブ `zudo-case-r11-04-design-files.zip` の全238ファイルを、ルート `zudo-case-r11-04/` を外して展開したもの。公開リポジトリのため、メールのメッセージID・注文番号・保存先パスを含む3ファイル（`README.md` の保存先の節、`research/hanging-hole-audit.{md,json}`）だけを一般的な表現へ置き換え、受領時のハッシュを `SOURCE-RECEIPT.json` の `received_sha256` に残しています。他の235ファイルはバイト単位で同一。**変更禁止**。 |
| `source/out/` | **現行**のレビュー済み出力（STEP/STL/DXF、`parts-manifest.json`、`validation.json`、`preview.html` など）。実物を作るときはここから。 |
| `source/reference/` | **履歴**の比較入力（R11-01〜03 の基準、R10 の記録など）。製造には使わない。 |
| `source/research/` | 価格・吊り穴の調査記録。価格はすべて未見積（null）。 |
| `SOURCE-RECEIPT.json` | 受領アーカイブの SHA-256・サイズ・メンバー一覧、基準リビジョン、付属ファイル（変更蓋部品ZIP・PA12見積用ZIP・PNG・Markdown）との照合結果。 |
| `package.py` | `source/out/` から役割別の配布用ZIPを、`source/` 全体から公開用の元データZIPを決定的に作る（Python 3 標準ライブラリのみ）。 |
| `packages/` | `R11-BUILD-FEEDBACK-04-{pa12,aluminum,home-print}.zip`。 |
| `packages-manifest.json` | 各パッケージの役割・SHA-256・メンバーと元ファイルの対応、`package.py` 自身のハッシュ。`source` 役は `source/` の決定的な再パッケージ（`verbatim_received_archive: false`）。受領アーカイブ自体は公開せず、SHA-256 `4c74dd94…` で識別します。 |

公開先: プレビュー `/previews/r11-build-feedback-04.html`（`source/out/preview.html` と同一）、ダウンロード `/downloads/candidate/R11-BUILD-FEEDBACK-04-{source,pa12,aluminum,home-print}.zip`、図 `/images/metal-case/r11-build-feedback-04/{lid-guides,lid-side-fit}.png`。

## 検証

```sh
pnpm check:r11   # 受領メンバー・parts-manifest・パッケージ・公開コピー・契約値・台帳ポインターを検査（書き込みなし）
pnpm test:r11    # 契約・パッケージ数・冪等性・改ざん検出のテスト
pnpm check:assets
```

`scripts/lib/r11-contract.mjs` は取り込んだ JSON/CSV から数量・穴・体積・外形・R11-03 との差分を読み、受け入れた値と照合します。これはデータとハッシュの一致確認であり、機械設計の妥当性検証ではありません。

## パッケージの再生成

```sh
python3 engineering/r11-build-feedback-04/package.py
pnpm sync:r11
```

同じ入力からは同じバイト列のZIPになります（固定時刻 2026-11-22 00:00:00、固定権限、名前順、ZIP_DEFLATED）。`pnpm sync:r11` は公開コピーと `project/release-state.json` の `current_metal_7u40_candidate`（7U40の現行選択）だけを更新します。旧来の `current_fullset_candidate`（R10記録）と `project/current-spec.json` は変更しません。

## CAD の再構築（取り込み時は実行していません）

依存: `cadquery==2.7.0`、`numpy==2.3.5`、`ezdxf==1.4.5`（`source/requirements.txt`）。

**必ず改訂ディレクトリ全体を別の場所へ丸ごとコピーし、そのコピーの中で、そのコピー既定の `out/` を使って実行してください。** `source/` 自体は受領物なので上書きしません。`--out` で出力先を変えたまま、`ROOT/out` を読むスクリプト（`review_followup.py`、`build_pricing_audit.py` など）を混ぜて実行しないでください。

```sh
cp -a engineering/r11-build-feedback-04/source /tmp/r11-04-rebuild
cd /tmp/r11-04-rebuild
python3 build.py --verify
python3 revision/review_followup.py
python3 research/build_pricing_audit.py
```

`python3 build.py --preview-only` は製造用書き出しなしでプレビューだけを作ります。単独の蓋ガイド報告を更新する場合は `python3 -m revision.review_lid_locators`。これらはアップロード・発注・印刷を行いません。形状を変えた場合は新しいリビジョンとして扱い、保存済みの報告を最新とみなさないでください。

## 根拠の範囲

- 検査はすべて **公称CAD** 上のものです（ソリッド妥当性、接触、重なり、穴・数量、STEP/STL/DXF の読み戻し）。
- 蓋は **0〜12.5 mm の連続した垂直移動** を掃引し、本体205部品、元の参照66点、上部ナット・ワッシャーの移動範囲16個と干渉しないことを確認しています。傾けた取り外し、公差、工具の入り、実物の嵌合は範囲外です。
- 本体の組立経路は R11-03 からの **継承** で、16段階・828位置の離散サンプル（1,098回の交差判定）です。連続的な証明でも実物の組立試験でもありません。
- プレビューの確認は **JSDOM＋CPU canvas** による13ビュー・17状態の描画で、実ブラウザ（レイアウトや WebGL）での確認ではありません。
- 現物の嵌合・強度・締付トルク・疲労・耐久・輸送保持についての主張はありません。
- 価格は **null（未見積）** です。業者へのアップロード・見積依頼・発注は行っていません。
