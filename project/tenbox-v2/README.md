# 10BOX-v2の現行指定と保存記録

**最新版はR8です。** `current.json`が、2026-11-23のユーザー指定に基づく現行版、ソース、プレビュー、ダウンロード、出力台帳への参照を持ちます。10BOX-v2全体として試作・改良を継続中であり、R8を別の採用確認待ちにはしません。

| ファイル | 役割 |
| --- | --- |
| `current.json` | 現行R8の選択。全体の`project/current-selection.json`から参照 |
| `r8-review.json` | R8の生成時点の出力hash、印刷数量、検証結果と保存入力 |
| `r7-review.json`・`r6-review.json` | 前の版の生成記録。R8の比較・生成の根拠として保全 |
| `manifest.json` | R5受領時の入力・出力hash、数量、姿勢、検証範囲。後続ビルダーの固定入力 |

生成記録や版別・ZIP内READMEに残る`review-candidate`、`user_confirmation: pending`、R5現行という表記は当時の状態です。現行の指定は`current.json`が優先します。R5の`current_revision: r5`をR8へ書き換えると、R5の原入力・hash契約を壊すため、そのまま保存します。

元の受け入れZIPと10box(2).zipは`engineering/tenbox-v2/r5/inputs/`で不変保管しています。保存記録と配布ZIPを変更せずに現行指定を分離し、数量や検証値は出力台帳から参照します。金属用の`project/current-spec.json`をこのケースの仕様には使いません。`production_approved:false`と実スライス・現物未検証の事実を維持します。

[読者向け入口](../../src/content/docs/tenbox-v2/index.mdx)、[再生成](../../engineering/tenbox-v2/README.md)、[旧R5の案内](../../src/content/docs/archive/tenbox-v2/index.mdx)。現行指定の更新は[#147](https://github.com/Takazudo/zudo-case/issues/147)、R8形状の保存は[#143](https://github.com/Takazudo/zudo-case/issues/143)・[#144](https://github.com/Takazudo/zudo-case/pull/144)です。
