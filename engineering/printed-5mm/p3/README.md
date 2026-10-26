# 7U40・5mm 家庭印刷ケース P3

`P3-PRINTED-5MM-7U-RAILS` はR10金属ケースとは独立した家庭印刷用候補。元のP3ソースは `source/`、原典のレール/PCB入力と受領hashは `reference/` に保持する。外部のP3受領アーカイブはリポジトリへ複製しない。

```sh
uv sync --locked --project engineering/printed-5mm/p3
uv run --locked --project engineering/printed-5mm/p3 python engineering/printed-5mm/p3/build.py --out /tmp/printed-p3-build
```

出力先は空のディレクトリ。ビルドはソースと参照入力を出力先へコピーし、ケースCAD、STL/STEP、レール組立、9画面プレビュー、BOM、印刷案内、ZIP、hash manifestを順に生成する。保持した原典には書かない。`source/model.json` のキャッシュだけから再生成する操作は正式ビルドではない。

構造12点、任意パッド・座金3種、参照レール組立66点。元のレールメッシュの重複/非マニフォールド面は保存し、製造用STLへ流用しない。3D形状と矩形ベッド判定は実機スライス、強度、組立、運搬の合格ではない。

検査の実行範囲と未確認事項は `project/printed-5mm/verification.md` に記録。

P3の寸法設定は承認済みSHA-256へ固定しています。寸法変更は別版・CAD・プレビュー・日本語文書を同時レビューするまでビルドで拒否します。
