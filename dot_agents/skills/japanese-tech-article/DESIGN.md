# v0.3 設計判断 — 上流規範の実利用

## 原典と採用した要素

1. [natural-japanese](https://github.com/coji/natural-japanese) — 文章を作る前に主メッセージ・見出し・素材・濃淡を整理し、書いた後は`lint.py`、`outline.py`、`--reading-load`でチェック。従来のv0.2が欠いていた実際の機械検査層を再利用する。
2. [yomiyasu](https://github.com/nanaism/yomiyasu) — 事実・条件・比重・断定の強さを変えない。推敲時には言い直しテスト、`yomiyasu_check.py run`と`verify`を使う。文章を全部機械的に書き換えるのではない。
3. [japanese-tech-writing](https://github.com/hikimay/japanese-tech-writing) — `reference/rules.md`の8観点と`reference/checklist.md`の6軸をレビューに利用。とくに厳密な因果・概念・不確実性を技術記事の中核とする。
4. [22本の技術記事を分析したzenn-writerの実践](https://zenn.dev/m43d4k/articles/ab284a6d4eba57) — 筆者の語尾を模倣するのでなく、入力にある試行、観測、判断の流れを保存。元にない体験談を増補しないことを不合格条件とする。
5. [write-zenn-article](https://github.com/tomokusaba/zenn/blob/main/.agents/skills/write-zenn-article/SKILL.md) — 投稿先の記法・ファイル管理と文体の規則を分ける。個々の著者の絵文字・話し方などは汎用規則にコピーしない。

## 以前からの変更

| v0.2 | v0.3 |
| --- | --- |
| 独自の日本語ガイドを主に適用 | 上流のSKILL.mdを直接読み、必要な役割を使う |
| 自作のMarkdown lintを日本語チェックの一部と扱いがち | 自作lintは投稿形式専用。日本語はupstreamで検査 |
| 自分の読み味で評価 | natural-japaneseの検出、japanese-tech-writingの規範、yomiyasuの意味保持を具体的に使う |
| 記事タイプ別の統一的な進め方 | 文章構成と論証は上流、記事形式と技術検証だけ独自に補う |
| 出力後の自然さを推測 | 同一プロンプトで再生成・ブラインド比較するまで合格を宣言しない |

## 今回解決しないこと

- 上流をインストールしていない環境で、上流と同品質の日本語評価を保証すること。
- モデルに既存Skillを3つ渡すだけで、人間の自然さ評価が上がることを保証すること。
- 文章をAIらしくなくするために筆者の経験を捏造すること。
- Qiita/Zennへの自動公開。

上流スキルに更新がある場合は原典を見直し、ここに固定したコマンドや優先順位を検証する。
