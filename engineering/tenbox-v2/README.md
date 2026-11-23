# 10BOX-v2

**最新版はR8です。** 2組の3U60HPフレームを使う独立した家庭印刷ケースで、10BOX-v2全体として試作・改良を継続しています。R8の採用確認待ちという扱いは終了しています。

- [印刷ファイルと数量](../../src/content/docs/tenbox-v2/print-files.mdx)：R8印刷ZIPと15個のH2Dプロジェクト。
- [R8のプレビュー](../../src/content/docs/tenbox-v2/preview.mdx)：下側長穴、側面固定、蓋との位置関係。
- [設計と検証](../../src/content/docs/tenbox-v2/design-and-validation.mdx)：現行寸法と実施した検査の範囲。

現行指定は[`project/tenbox-v2/current.json`](../../project/tenbox-v2/current.json)、出力hash・数量・検証記録は[`r8-review.json`](../../project/tenbox-v2/r8-review.json)です。R8のレール面から蓋天板内面までの高さは19.868897mmです。Bambu Studioでの実ロード・スライス、印刷・現物試験は未実施として記録しています。

## 再生成

既存のR5専用ロック環境（Python 3.12.14 / CadQuery 2.7.0 / NumPy 2.3.5 / SciPy 1.17.0）でR8を生成します。出力先は存在しないディレクトリにします。

```sh
uv sync --locked --project engineering/tenbox-v2/r5
pnpm build:tenbox-v2
pnpm check:tenbox-v2
pnpm check:tenbox-v2-r8
```

`build:tenbox-v2`は`r8/build.py`を実行します。詳細な再生成手順と設計変更時の記録は[r8/README.md](r8/README.md)に保存しています。

## 保存記録の読み方

版別README、配布ZIP内のREADME、`r8-review.json`は生成時点の保存記録です。その中の「R5を採用」「R8は確認候補」や`user_confirmation: pending`は当時の状態で、現在の選択を表しません。2026-11-23のユーザー指定を記録した`current.json`を現行判断に使います。ファイル名の`review`や配布パスの`candidate`も元のURLを保持しています。

R5の`manifest.json`は後続のビルダーが読む不変の入力・hash契約です。R5〜R7、固定R4入力、既存ZIP・形状・設定は保持しています。旧R5の読者向け案内は[アーカイブ](../../src/content/docs/archive/tenbox-v2/index.mdx)にあります。製造承認は`production_approved:false`のままです。
