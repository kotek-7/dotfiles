---
name: japanese-tech-article
description: Qiita・Zenn向けの日本語技術記事を企画、執筆、推敲、レビューする統合Skill。natural-japanese、japanese-tech-writing、yomiyasuの実際の規範と検査工程を使い、技術的な厳密さと自然な日本語を両立する。技術記事、解説、比較、検証、移行ガイド、トラブルシューティング、OSS紹介、記事リライト、公開前の日本語チェックで使用する。投稿操作そのものは行わない。
---

# japanese-tech-article — 既存の日本語執筆Skillを組み合わせる

このSkillは **文体規範を独自に再発明しない**。原則として、以下の上流Skillの指示ファイルを実際に読んで適用する。

- `natural-japanese` (<https://github.com/coji/natural-japanese>): 執筆前の設計、自然な日本語の生成、`lint.py` と `outline.py` 等による検査。
- `japanese-tech-writing` (<https://github.com/hikimay/japanese-tech-writing>): 技術的な主張・論証・専門用語、`reference/rules.md` と `reference/checklist.md`。
- `yomiyasu` (<https://github.com/nanaism/yomiyasu>): 元の意味と主張の比重を守る最終推敲、`yomiyasu_check.py run/verify`。

**実際のSKILL.md・参照ファイル・スクリプトを使うこと。名前を挙げるだけで使ったことにしない。** インストール場所・検査方法は [upstream-integration.md](references/upstream-integration.md) を読む。見つからない上流Skill・実行できない検査は「未実行」と扱う。`scripts/check_platform.py` は投稿形式しか点検せず、日本語の検査の代用ではない。

## 適用範囲

- `write`: 新規執筆（既定）。
- `revise`: 既存原稿の改稿。元の意味・立場・情報の比重・声を守る。
- `review`: 改稿せずにチェック。根拠と位置を挙げる。
- `plan`: 読者・中心の問い・構成だけを設計。
- `adapt`: 内容を変えずにQiita/Zennの投稿形式へ合わせる。

指定がない限り、記事の本文を作る。**「Qiita向け」はQiita CLIのFront Matterを要求する意味ではない**。投稿先固有のファイル形式が必要か、依頼やリポジトリから判定する。

## 優先順位（上流規則が衝突するとき）

1. 依頼にある意図と一次情報、コード・API・数値・条件・未検証の事実を保持する。体験・感想・実験を創作しない。
2. `japanese-tech-writing` の論証の厳密さ（観点3）を守る。因果・概念・確度の曖昧さを正す。
3. `yomiyasu` の意味保持（主張、比重、断定の強さ、文の働き・時制）を守る。
4. `natural-japanese` の文体規範と構造検査に従って、読者が自然に読める日本語にする。文法や単語検出だけで合格にしない。
5. 媒体別のMarkdown・Front Matterは最後に適用する。整形のために意味や読後感を損ねない。

例えば `japanese-tech-writing` の「一文一改行」「初出の用語を太字にする」は、読者・媒体の表示を踏まえた**編集上の既定値ではなく点検候補**とする。自然な段落やコード表現を壊す一律置換はしない。どの規則を適用しなかったか判断できるようにする。

## 作業手順

1. **調査と素材の整理**: 読者、既知の前提、解決する問いを決める。仕様・公式資料、実測、コード読解、筆者の意見、未確認事項を区別。現在の技術情報は可能なら一次情報で確認する。資料不足を体験談や想像のログで埋めない。
2. **記事の設計**: `natural-japanese` の「主メッセージ→見出しスケルトン→濃淡設計」を実行する。[article-patterns.md](references/article-patterns.md) から記事の種類を選ぶ。見出しと最初の文だけで主張が追えるか確認する。重要でない節を無理に同じ長さにしない。
3. **執筆**: `japanese-tech-writing/reference/rules.md` の **論証・読解負荷・語り・演出・冗長** の観点を確認して書く。同時に `natural-japanese` の生成時の制約（前置きを削る・構造の反復を避ける・根拠に接地する）を適用する。書き手にない体験や一人称を追加しない。コード・URLは意味保持対象。
4. **構造レビュー**: `natural-japanese` の実際の `outline.py` と章立て通読で、見出しだけを読んだ論旨、段落冒頭、節の濃淡、同じ型の繰り返しを検査する。`japanese-tech-writing/reference/checklist.md` の主張・厳密さの項目も点検する。
5. **日本語の機械検査**: 利用できる場合は `natural-japanese` の `lint.py --genre tech` と `--reading-load` を**原稿ファイルに実行**する。検出した箇所は文脈で採否を決める。指摘0件を自然な日本語の証明とは呼ばない。
6. **意味保持付き推敲**: `yomiyasu` の「初読→言い直しテスト（6点）→最小限の改稿」を実施。元稿と最終稿を分け、利用できる場合は本家の `yomiyasu_check.py run --source ... --final ...` を実行する。最終稿の `verify` も実行。意味が変わる変更は戻し、根拠のない事実補完をしない。
7. **投稿先の整形**: [qiita.md](references/qiita.md) または [zenn.md](references/zenn.md) に従う。独自記法・Front Matterは、依頼とファイル管理方式が必要とするときだけ使う。コードフェンス・リンク・説明の改行を保持する。`scripts/check_platform.py` の出力は補助情報として扱う。
8. **最終照合**: [acceptance.md](references/acceptance.md) に照らし、本文全体を初見の読者として通読。内容の変化や未検証事項、上流検査の実行・未実行を区別。最終稿を変更したら必要なチェックを再実行する。

工程ごとの詳しい使い分けとコマンドは [upstream-integration.md](references/upstream-integration.md) を参照する。上流の出力書式（「変えたところ」など）は記事本文へ混ぜず、必要なら本文外のレビュー報告に置く。

## 最終成果物

- `write`: 本文または記事ファイル。依頼されていない公開処理はしない。
- `revise`: 原稿と別ファイルの完成稿（上書き指示があれば従う）。意味を変えうる修正を本文外で簡潔に報告。
- `review`: 問題箇所・どの上流規範に照らしたか・修正候補・検証状態。主観的な印象点だけで終わらない。
- 上流検査を実行していない場合、実行済みと偽らない。手元で再現するコマンドを示してもよい。

**自動公開は禁止。** `published: true` への変更、`qiita publish`、push、公開API操作は、明示的な公開依頼があるまで行わない。
