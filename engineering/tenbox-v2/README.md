# 10BOX-v2

**最新版はR8-LID-LEDGE-01です。** 2組の3U60HPフレームを使う独立した家庭印刷ケースで、10BOX-v2全体として試作・改良を継続しています。R8の下側長穴によるレール配置を維持し、1枚天板に合わせて蓋の前後縁に残っていた中央棚の隙間を連結しました。2026-11-24にユーザーが採用し、リポジトリの現行版への反映を指示しています。

- [印刷ファイルと数量](../../src/content/docs/tenbox-v2/print-files.mdx)：一式の15個のH2Dプロジェクトと、蓋前後の共通STL・3MF。
- [現行プレビュー](../../src/content/docs/tenbox-v2/preview.mdx)：連結した蓋の棚、下側長穴、側面固定、蓋との位置関係。
- [設計と検証](../../src/content/docs/tenbox-v2/design-and-validation.mdx)：現行寸法と実施した検査の範囲。

現行指定は[`project/tenbox-v2/current.json`](../../project/tenbox-v2/current.json)、出力hash・数量・検証記録は[`r8-lid-ledge-01.json`](../../project/tenbox-v2/r8-lid-ledge-01.json)です。蓋前後は共通形状を2個使い、組立時に180°回して配置します。一式の`lid-front.3mf`と`lid-back.3mf`を各1回印刷する方法でも同じ2部品になります。

変更したのは蓋の前後縁の2メッシュです。残る13プロジェクトはR8保存物とバイト単位で一致し、変更した2プロジェクトも元のH2D・0.6mm・PLA設定、ブリム、サポート、ノズル割当て、印刷姿勢を保持します。数量は15プロジェクト、22保存オブジェクト、23部品、16回のプレート実行のままです。

## 再生成

既存のR5専用ロック環境（Python 3.12.14 / CadQuery 2.7.0 / NumPy 2.3.5 / SciPy 1.17.0）で現行版を生成します。出力先は存在しないディレクトリにします。

```sh
uv sync --locked --project engineering/tenbox-v2/r5
pnpm build:tenbox-v2
pnpm check:tenbox-v2
```

`build:tenbox-v2`は`r8-lid-ledge-01/`の現行一式ビルダーを実行します。詳細な再生成手順は[r8-lid-ledge-01/README.md](r8-lid-ledge-01/README.md)を参照してください。

## 保存記録と確認範囲

R5〜R8のソース、固定R4入力、既存ZIP・形状・設定と版別の生成記録は不変の根拠として保持します。R5の`manifest.json`は後続のビルダーが読む入力・hash契約です。旧記録の「R5を採用」「R8は確認候補」や`user_confirmation: pending`は当時の状態で、現在の版は`current.json`が指定します。旧読者向け案内は[アーカイブ](../../src/content/docs/archive/tenbox-v2/index.mdx)にあります。

レール面から天板内面までの高さは19.868897mmのままです。公称CAD・メッシュと保存済みプロジェクトの検査を、Bambu Studioでの実ロード・スライス、印刷・現物試験とは区別します。実アプリ・実機の確認は未実施、製造承認は`production_approved:false`のままです。
