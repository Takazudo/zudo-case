# P5 H2D PLA06 / 未スライス

保存済みP4のH2D・0.6mm・PLAテンプレートを継承。ブリムは工程でno_brim／幅0、オブジェクト・プレートoverrideを再検査。長側板2枚は手動Right、他13種類は元テンプレートの共通ノズル領域内。入力STLは45度印刷姿勢済みで追加回転・縮尺変更なし。

```sh
python3 build.py --cad /tmp/p5-build --out /tmp/p5-3mf
```

1部品・1プレートを15種類。必要数量、入力STL hash、正規化メッシュfingerprint、倍率1、Z0、ノズル、全設定diffはPROJECTS.jsonとverificationへ記録。右ノズル領域X25..350／Y0..320と保存済み除外域を検査し、除外域は実メッシュ凸包との分離を確認する。凸包判定は形状を包含する保守的な判定で、ツールヘッド経路を保証しない。

工程設定の変更はbrim_type、brim_widthのみ。壁数・積層・infill・温度・support OFFは継承。段付き蓋のサポートは別途確認。G-codeなし。Studioがあれば --studio /path/to/bambu-studio で再読込・再保存し、なければNOT RUNと記録する。実スライス・現物嵌合・反り・運搬は未確認。
