# R10-FULLSET-01 — 7U40 一式準備（実装中）

2026-10-26のユーザー決定に基づく独立候補。追加の有料試験片注文を前提にしない。R2の固定耳と小さい角丸押さえ、t1ガード／溝1.70mm、既存M5蓋を統合する。現時点では実装・検証中で、注文可能な完成セットではない。

```sh
uv run --locked --project engineering/r9-prototype-01 python engineering/r10-fullset-01/build.py --out /tmp/r10-fullset
uv run --locked --project engineering/r9-prototype-01 python engineering/r10-fullset-01/build.py --washers-only --washer-parameters engineering/r10-fullset-01/washers.json --out /tmp/r10-washers
```

`washers.json` は幅、長さ、厚さ、穴径、偏心、角R、穴の半径方向補正 `xy_fit`、穴入口の `elephant_foot` 面取りをmmで指定する。供給部品を再生成せず家庭用ワッシャーだけを生成できる。厚さ変更は積層の再検証を要する。供給用金属穴を自動変更しない。

下辺押さえの外形中心は穴より内側へ1mm。印刷時はZ=0の面をベッドに置く。黒ASAを用い、PA12外注品に混ぜない。円形交換用ファイルは既存座金の交換候補で、追加発注数量ではない。

`reference/` は元の判断とR2ソースの記録。過去の試験結果を今回の検証として扱わない。実物の嵌合、トルク、耐久、輸送は未確認。製造承認はfalse。

## 見た目の受入条件

- 固定耳の輪郭内に小さい角丸押さえを収める。中央は1mm＋1mmの耳を1本で固定。
- 禁止: 大きい楕円座金の張り出し、耳の拡大による帳尻合わせ、旧M3蓋やクーポンの混入。
- 画像では確定しないこと: 材料公差、実荷重、実物の長期保持。desktop／390px／320pxで統合表示を確認する。

## R2から必要となった局所補正

R2の斜面ジョグルは法線方向の肉厚が約0.969mm。R10では耳t1を保ち、接続部だけt2の段付きwebにする。また上側耳と帯の線接触はSTL非多様体となるため、帯上縁に0.1mmの局所逃げを設ける。生成・読み戻し検証は進行中。
