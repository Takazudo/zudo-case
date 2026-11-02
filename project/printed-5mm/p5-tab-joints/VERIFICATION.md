# P5 J3検証記録

対象: P5-PRINTED-5MM-TAB-JOINTS-J3。家庭印刷候補、production_approved=false。

## 設計と保存

- 本体6枚のみ変更。旧P4の本体と混ぜず、6枚を一組で交換する。
- P4蓋6枚＋任意パッド／座金3型のSTL/STEP計18ファイルはバイト一致。対応表: `engineering/printed-5mm/p5-tab-joints/out/PRINT-MAPPING.json`。
- P3/P4、旧3MF、金属R10、発注記録等354ファイルのSHA-256を `reference/P5-BASELINE.json` で保護。既存P3のPRESERVATION記録も検査する。
- 受領J3の6 STEPは比較用fixture。保守CADから生成したBRepとの双方向差分・面積・接続を確認し、受領meshを本番生成に流用しない。
- 16タブ／16閉じた受け穴、側板341/349×98×5mm、片側余裕0.2、肩0.15、先端引込0.3、挿入4.7mm。
- 全体929、元レール187、J3接合117検査。公称干渉0。82通気孔、壁28長穴＋10丸穴、金具28個、元参照部品66個を保持。
- 受け穴―金具投影の最小距離1.13137085mm。通気孔の4mm条件と区別する。直径6mmの仮定ドライバー接近とネジ挿入を計算検査したが、実工具・手の空間を保証しない。

## 配布と印刷

4 ZIPとプレビューを `files.json` にサイズ／SHA-256付きで登録。全公開ファイル25MiB未満、Git LFSなし。
H2Dは15種類各1部品／1プレート、PLA・0.6mm元設定を保持しブリムをOFF。左右側板はRight手動、他13種類は元テンプレートの共通領域内。45度印刷姿勢のSTLへ追加回転なし。実メッシュと3MFの頂点・三角形一致、倍率1、Z0、右ノズル域と除外域を検査する。

## 再現手順

```sh
uv sync --locked --project engineering/printed-5mm/p5-tab-joints
uv run --locked --project engineering/printed-5mm/p5-tab-joints python engineering/printed-5mm/p5-tab-joints/build.py --out /tmp/p5-build
uv run --locked --project engineering/printed-5mm/p5-tab-joints python engineering/printed-5mm/p5-tab-joints/regenerate.py --published-root .
python3 engineering/printed-5mm/p5-h2d-3mf/regenerate.py --cad /tmp/p5-build --published-root .
```

ソースZIP単体は空フォルダへ展開後 `uv sync --locked; uv run python build.py --out /tmp/p5-build`。Python3.13.5/CadQuery2.8.0。旧金属版HTMLのPython3.12環境と区別する。

## 未確認・対象外

Bambu Studio実行ファイルがないためStudio再読込／再保存はNOT RUN。3MFは未スライス、G-codeなし。段付き蓋のsupport、実スライス、現物嵌合、荷重、反り、creep、運搬、脚の潰れ／机の凹凸は未確認。公称接地余裕1.5mm。
デプロイ、注文、支払い、製造承認、プリンター送信は実施しない。実mainマージには `[skip deploy]` が必要。

## 実行結果

- Canvas2D: 226検査PASS。Chromiumで直接file://表示、全21ビュー、表示切替、蓋／挿入操作、設定拒否、PNG、1440/390/320pxを検査。
- WebGL: 同じ226検査PASS。file://成功を別途記録。
- docs: 39検査PASS。同一origin iframe、1440/390/320pxの5ページ、4 ZIPの実GET SHA-256、runtime errorなし。
- 3MF contract: 3検査PASS（除外域凸包、旧P4入力拒否、決定的ZIP）。
- 既存保存／現行ポインター: 9回帰検査PASS。
- 独立read-only review: 配布body ZIP／3MF ZIPと生成物の照合不足2件を修正し、再レビューで残存阻害事項なし。
- 再生成検査でSTEP列挙順依存を検出してソートを追加。最新ソースの完全再生成とCIは完了後に追記する。

ブラウザ検査JSONと採用形状の3画像は `evidence/` に保存。
