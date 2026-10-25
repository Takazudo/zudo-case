# R10-FULLSET-01 — 7U40 一式準備

2026-10-26のユーザー決定に基づく独立候補。追加の有料試験片注文を前提にしない。R2の固定耳と小さい角丸押さえ、t1ガード／溝1.70mm、既存M5蓋を統合する。アルミ6枚、PA12 20個、家庭ASA新規72個を1つの選定構成にまとめる。業者DFM・価格・ユーザーの発注判断と、組立後の現物評価は別工程。製造承認ではない。

入口: [ORDER-START-HERE.md](out/ORDER-START-HERE.md)、[選定manifest](out/selected-order.json)、[BOM](out/BOM.csv)、[プレビュー](out/preview.html)、[検証記録](verification/LOCAL-VALIDATION.md)。

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

R2の斜面ジョグルは法線方向の肉厚が約0.969mm。R10では耳t1を保ち、接続部だけt2の段付きwebにする。また上側耳と帯の線接触はSTL非多様体となるため、帯上縁に0.1mmの局所逃げを設ける。この形状でSTEP/STL読み戻しと中央両側の非干渉を検査する。

底面の20×12座金はR2の中心穴だと下辺ガードと干渉したため、外形を穴からケース内側へ3mm偏心させた。新規72個の数は変わらないが、内側36個と底面10個を別STLに分離する。円形20個は再使用で、新規家庭印刷0個、交換用STLのみ付属する。

丸形/カプセル形の角Rは幅の半分。丸形の長さは幅と等しい。矛盾する指定はエラーにする。任意の角Rは角丸長方形で指定できる。家庭で試すときはwashers.jsonを別名コピーし、上のワッシャー専用コマンドへ渡す。

組立順は壁側ねじ→底板ねじ→元レールユニット。底板ねじを先に入れると壁側の直線工具経路を塞ぐ。後日の締め直しもこの順の取り外しを前提にする。

0.8mmガードや溝1.5/1.6の比較はreference/r2-build_geometry.pyの履歴研究に残す。今回の選定供給セットへは含めない。
