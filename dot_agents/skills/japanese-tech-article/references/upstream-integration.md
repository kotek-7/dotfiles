# 上流Skillの統合方法（2026-11-15に確認）

上流Skillは本リポジトリへコピーしていない。規範の重複や古い独自実装を防ぐため、**ユーザーが別途インストールした上流の実体を読む**。上流のバージョンやフォルダ構造が変わった場合、常に手元のSKILL.mdを優先する。

## 発見と導入

- 公開リポジトリ:
  - https://github.com/coji/natural-japanese
  - https://github.com/nanaism/yomiyasu
  - https://github.com/hikimay/japanese-tech-writing
- 安定して導入するなら `npx skills add coji/natural-japanese`、`npx skills add nanaism/yomiyasu` を上流READMEに従って実行し、`japanese-tech-writing` は上流READMEのクローン手順などで導入する。インストール前に実行主体の承認を得る。
- Codexであれば一般に `~/.agents/skills/` またはリポジトリの `.agents/skills/`、Claude Codeなら `~/.claude/skills/` または `.claude/skills/` を探す。ディレクトリ名だけを前提にしない。`SKILL.md` と参照先・スクリプトが同じインストール内にあるか確認する。
- インストールされていてもファイルにアクセスできなければ上流規範を読んだと見なさない。外部コマンド実行不可ならツール検査を未実行とする。**依存が欠けている場合は、自分の短い日本語ルールで同等の検査をしたと主張しない。**

## 役割を混ぜない

| 工程 | 最も参考にする原典 | 実行する内容 |
| --- | --- | --- |
| 執筆前 | natural-japanese `SKILL.md` | 主メッセージ、見出し、素材、節の濃淡 |
| 執筆中 | japanese-tech-writing `reference/rules.md` | 8観点、特に論証の厳密さ、読者負荷、空句 |
| 初稿後 | natural-japanese `scripts/lint.py` | AI的定型表現、構造・翻訳調の疑いを検出 |
| 初稿後 | natural-japanese `scripts/outline.py` | 見出しと段落冒頭の骨格を抽出 |
| 最終推敲 | yomiyasu `SKILL.md` | 主張・比重・言い切り・文の働きを守って必要箇所だけ直す |
| 最終推敲 | yomiyasu `scripts/yomiyasu_check.py` | lint+diffの検査記録と提出物のverify |
| 内容確認 | japanese-tech-writing `reference/checklist.md` | 論証と語りの点検、必要時に6軸評価 |

`natural-japanese` には文書全体の診断モードもある。ユーザーが採点を求めた場合だけ利用し、定義ファイルを読まずに独自の自然さスコアを作らない。

## 実行コマンドの例

`NAT`、`YOMI` は、**実際に発見した**上流Skillのルートの絶対パスに置き換える。コマンドの存在・オプションは、その環境の上流SKILL.mdで再確認する。

```sh
# natural-japanese: uvが必要（SudachiPyなどの依存は上流scriptが宣言）
uv run "$NAT/scripts/lint.py" draft.md --genre tech
uv run "$NAT/scripts/lint.py" draft.md --reading-load
uv run "$NAT/scripts/outline.py" draft.md
uv run "$NAT/scripts/terms.py" draft.md

# yomiyasu: Python標準ライブラリのみ。原稿と改稿を分けて保存する
python3 "$YOMI/scripts/yomiyasu_check.py" run \
  --source draft.md --final final.md --stance=説明 --fact-gaps
python3 "$YOMI/scripts/yomiyasu_check.py" verify --final final.md
```

`yomiyasu` は新規執筆のときも下書きと完成稿を分けてdiffを取る。元稿のない新規作成で `--material` を使う場合は、上流の記述を確認する。元の意味の保持をスクリプトが自動保証するわけではない。

## 検査の結果を扱うとき

- lintは修正候補であり、全件機械的に削除しない。専門分野で定着した比喩や、必要な否定・留保は残す。
- 3つの規範を上から1回ずつ「文章の全面改稿」に使うと、著者の声が消え、別の定型表現へ均質化する恐れがある。統合Skillは **natural-japaneseで生成を制御し、japanese-tech-writingで内容を点検し、yomiyasuで最終的な意味保持付き推敲をする**。無制限の逐次リライトは行わない。
- 上流の検査の未実行・失敗・有用な例外（誤検出）を記録する。レポートは本文とは別。
- 依存関係やツール結果が不明の場合に「チェック済み」「合格」と言わない。

## 上流とのライセンス関係

本Skillは既存Skillの構想・公開規範への参照と、短い独自の統合手順から成る。上流のコードや規範ファイルを複製・同梱しない。各上流リポジトリのライセンス（閲覧時はMIT）と更新に従う。
