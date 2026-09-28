# プレビュー配信元分離の確認記録

確認日: 2026-09-29
対象: Issue [#70](https://github.com/Takazudo/zudo-case/issues/70)、統合済み revision `e6f275cbe03f03564fcb0266fadbbf13e3328067`
目的: Issue #69 の実行単位ごとの配信元分離を、実ブラウザーと production 出力で確認する。

## 実ブラウザー

マネージャーが隔離された作業ツリーで既定値の `dev` を起動し、同じプロセスを稼働させたまま `check` と `build` を実行した。Playwright の実ブラウザーでプレビュー文書を再読込し、さらに MDX を一時編集して再コンパイルした後も、表示元キャプションは `表示元: ローカル (public/)`、iframe とプレビューリンクは `/previews/r8-simple-lid.html` の相対 URL を保った。

`public/previews/r8-simple-lid.html` に一時マーカーを入れ、実際の iframe 内に表示されることを確認した。確認時のスクリーンショットではマーカーとR8ケースのプレビューを視認できた。モデルページから取得した参照 ZIP は25,994 bytesで、ブラウザー取得物と `public/` 内ファイルの SHA-256 がともに `b50eb1140197d742d00b8192d7e9ad1750a4617422b8713ca3eb2e55f1e6d5eb` だった。

既定 `dev` を動かしたまま、`http://127.0.0.1:8787` を指定した2つ目の `dev` も起動した。指定先は2つ目の表示にだけ反映され、既定 `dev` はローカル表示を維持した。production build の文書は `https://zudo-case-preview.zudolab.dev` を参照し、ローカル override は含まれなかった。マーカーと MDX の一時変更は確認スクリプトの `finally` で元に戻され、作業ツリーの検査でも差分はなかった。

## チェック結果

- `node --test tests/preview-links.test.mjs tests/preview-origin-isolation.test.mjs`: 8/8 pass。
- `node scripts/check-docs.mjs`: 41 MDX、8カテゴリ、124内部リンクを確認。
- `node scripts/sync-reference-tables.mjs --check`: 生成ページと `project/current-spec.json` が一致。
- マネージャーによる `.github/workflows/check.yml` 相当の全工程を heavy guard 下で実行: `verdict=PASS exit=0 secs=23 min_mem_mb=10736`。資産241件のハッシュ、setup 7件、ledger 97件、実 `check` と TypeScript、fixture 21件、60ページの production build、built-preview-links（41文書中13 URL）、大容量資産2件の準備、Worker系テスト9件を通過。

補助ログとスクリーンショットはローカル Git 管理領域の `.git/agent-logs/sweep-260929/verification/`、全工程ログは `.git/agent-logs/sweep-260929/full-check.log` にある。スクリーンショットを視認した。これらのログは配布物ではないため、本記録には判定に必要な観測値を残した。

## 範囲と限界

この確認が示すのは、実行単位ごとのプレビュー参照先とローカル資産の表示が維持されること、および指定された文書・ビルド検査の結果である。筐体の嵌合、強度、落下、疲労、荷重、製造適合性は評価していない。CAD、価格、製造承認状態の変更はない。
