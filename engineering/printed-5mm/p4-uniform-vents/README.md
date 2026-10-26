# P4 Uniform 四壁通気孔 / 7U40・5mm家庭印刷

`P4-PRINTED-5MM-UNIFORM-VENTS`。P3から独立した生成ソース。P3のソース・出力は変更しない。四壁だけに3×32mm、R0.5、ピッチ11mm、Z30–62mmの通気孔82個を追加。締結28長穴と10丸穴は独立して残す。床・蓋・支持・レール原典と変換は継承する。

```sh
uv sync --locked --project engineering/printed-5mm/p4-uniform-vents
uv run --locked --project engineering/printed-5mm/p4-uniform-vents python engineering/printed-5mm/p4-uniform-vents/build.py --out /tmp/p4-build
python3 engineering/printed-5mm/p4-uniform-vents/verify.py --out /tmp/p4-build --published-root .
```

ソースZIP展開後はそのディレクトリで `uv sync --locked`、`uv run python build.py --out /tmp/p4-rebuild`。出力先は空のディレクトリ。Python3.13.5 / CadQuery2.8.0。承認済みパラメータhashを固定し、変更には別途レビューが必要。

`VENTILATION.json` は生成した壁と完全アセンブリから求めた公称値。通気面積は熱・流量・防塵性能ではない。現物嵌合、実スライス、強度、ASAクリープ、運搬は未検証。製造承認・発注データではない。
