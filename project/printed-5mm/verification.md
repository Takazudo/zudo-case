# P3家庭印刷版・ソフトウェア検証記録

対象は `P3-PRINTED-5MM-7U-RAILS`。これは現物、スライサー、荷重、運搬の合格記録ではありません。

- 元P3の15 STLはロック済みPython 3.13.5 / CadQuery 2.8.0の全生成結果とそれぞれSHA-256で一致。15 STEPはOpen CASCADEのヘッダー時刻を固定した後、再読込・体積・面積・境界・面数を受領版と比較。旧→新hashは `out/accepted-geometry-comparison.json`。
- 全ケースCADは正の単一BRep、印刷STLは閉じた整合メッシュ、STEPは再読込可能。ケースの幾何検査412件、実形状レール・PCBの追加検査187件、名目干渉0件。レール原典の非マニフォールド面はそのまま参照表示し、新規印刷品とは扱わない。
- source ZIPを空ディレクトリへ展開して正式ビルドを実行し、別の空ディレクトリで行ったビルドと66ファイルのhashがすべて一致。両ZIPのCRC、重複名なし、内部ファイルの一致を確認。
- 印刷品の欠落・重複、別版モデル、古いシーン、未対応板厚や未レビューの位置決め隙間変更を使う処理は失敗する。P3の寸法設定は固定され、別寸法を入れる場合はCAD・プレビュー・文書の新しい版が必要。検査は `negative.py` を使い、一時コピーにだけ変更を入れた。
- ChromiumのCanvas経路で、9画面、部品選択、レイヤー、蓋、分解、設定読込拒否、PNG、390/320pxを含む142項目が通過。WebGLは別実行で9画面を開き、ページエラーなし。単独HTMLの直接 `file://` 読込も346部品で成功。
- ローカル文書 `/docs/printed-5mm/preview/` は1440/390/320pxで開き、埋込srcは同一オリジンの `/previews/printed-5mm-p3.html`。STL/STEP ZIPとソースZIPはローカルHTTP GETで公開ファイルとhash一致。
- R10選定manifest、JLCカート記録、アルミ/PA12 ZIPは変更しない。金属一式の`check:fullset`と13テストも通過。

残る確認: Bambu Studioの実スライスとサポート・キープアウト、ASA反りと強度、中央継ぎ目のたわみ、ネジ長・ナット、物理嵌合、運搬。現物評価前に製造承認へ格上げしません。

画面記録: [組込ビュー](verification/assembly-ui.png)、[H2D配置](verification/bed.png)、[390px画面](verification/mobile-390.png)。この3枚は今回のCanvasブラウザー検査から選んだ記録で、旧アーカイブの画像ではありません。
