# 10BOX-v2の正本

`manifest.json`は独立系列`tenbox-v2`・現行R5のファイル、受領hash、印刷数量、姿勢と検証範囲を記録します。金属用の`project/current-spec.json`をこのケースの仕様として使いません。`production_approved:false`を維持します。

元の受け入れZIPと10box(2).zipは`engineering/tenbox-v2/r5/inputs/`で不変保管。元の出力受領記録はZIP内およびsource内に保持し、移植した生成コードと現在の配布物のhashはこのmanifestで分けています。日時・UUID差を理由に形状・設定変更を受け入れたことにはしません。

再生成手順は`engineering/tenbox-v2/r5/README.md`、読むための入口は`src/content/docs/tenbox-v2/index.mdx`。課題は[統合A #131](https://github.com/Takazudo/zudo-case/issues/131)、全体[epic #130](https://github.com/Takazudo/zudo-case/issues/130)です。
