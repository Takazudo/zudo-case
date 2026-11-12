# サイトの図と共有カード

ZUDO CASEのトップページ図とリンク共有用カードの編集元です。図はモジュラーシンセ用ケースの枠とレールを表す装飾用のブランド図で、採用済みの設計・寸法・製作データを示すものではありません。

| ファイル | 役割 |
|---|---|
| `build.py` | 編集元。文言・色・配置・図形をここで変更する |
| `ogp-card.svg` | 生成したカード全体（1200×630、文字はアウトライン化済み） |
| `render.mjs` | `ogp-card.svg` をChromiumで `public/img/ogp.png` に描画する |
| `public/img/zudo-case-logo.svg` | 生成したトップページ図。透明背景の単色で、zudo-docのCSSマスク表示用 |
| `public/img/ogp.png` | 共有カード。1200×630 PNG |

## 再生成

```sh
pip install fonttools==4.68.0
python3 project/site-imagery/build.py          # 2つのSVGを書き出す
node project/site-imagery/render.mjs           # PNGを書き出す（playwright と Chromium が必要）
python3 project/site-imagery/build.py --check  # SVGが編集元と一致するか確認
python3 -c "from PIL import Image; print(Image.open('public/img/ogp.png').size)"  # (1200, 630)
```

文字は Inter（Debian/Ubuntu の `fonts-inter` 4.0+ds-1、`/usr/share/fonts/opentype/inter/`）からパスへ変換します。タイトルは InterDisplay-Bold 92px、副題と配信先は Inter-Medium 34px／24px です。別版のフォントではSVGのバイトが変わります。`ogp-card.svg` 冒頭のコメントに使用フォントのSHA-256先頭を記録しています。`build.py` は文字列が右側の余白80pxを越えると停止します。

色はGraphiteに合わせた背景 `#242629`、文字と図 `#D3D5D9`、控えめな銅色アクセント `#E9AA79` です。

2026-11-12の初回生成はNode.js 24、playwright 1.63.0 のChromiumで行いました。PNGは描画環境によりバイト単位では一致しない場合があります。寸法と見た目を確認してから差し替えてください。
