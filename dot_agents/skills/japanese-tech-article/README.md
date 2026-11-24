# japanese-tech-article v0.3 (composition-first)

Qiita・Zenn向け技術記事の執筆を、既存の日本語執筆Skillの実際の工程に接続する薄い統合Skillです。**上流Skillを同梱していません**。日本語品質のための自作lintは含めず、上流の検査スクリプトを利用します。

## インストール例

まず以下の3件を導入し、配置されたSKILL.mdとスクリプトが読めることを確認してください。

```sh
npx skills add coji/natural-japanese
npx skills add nanaism/yomiyasu
# japanese-tech-writing は上流 README の手動導入方法を確認
# 例（Claude Code個人用。既存ディレクトリの上書きに注意）:
git clone https://github.com/hikimay/japanese-tech-writing.git ~/.claude/skills/japanese-tech-writing
```

Codexなど他のエージェントへの導入先は上流READMEとインストーラ表示を優先します。次に本フォルダ `japanese-tech-article/` をエージェントのスキル置き場へ配置します（Codexでは一般に `~/.agents/skills/` または `.agents/skills/`）。

```text
japanese-tech-article/
├── SKILL.md
├── references/
│   ├── upstream-integration.md
│   ├── acceptance.md
│   ├── article-patterns.md
│   ├── technical-verification.md
│   ├── qiita.md
│   └── zenn.md
├── scripts/
│   └── check_platform.py
├── tests/
│   └── regression-plan.md
└── DESIGN.md
```

### 使用例

```text
$japanese-tech-article
2024年からワープして来たNeovimユーザー向けに、2026年現在のNeovimの状況を教えるQiita記事を書いて。
```

`write` で記事、`review` でチェック、`revise` で既存原稿の推敲、`plan` で構成を扱います。

## なぜ書き直したか

v0.1/v0.2は、「natural-japaneseを参考にした」と言いながら日本語の検査には独自のMarkdown形式チェックしかなく、明示的な文体検出・段落の点検・意味保持の検査を実行していませんでした。v0.3では上流の`SKILL.md`と検査を実際に用いる仕組みに変更しました。

**確認済み**: upstreamのSKILL.mdと主要な参照ファイル・コマンドをオンラインで確認し、Skillパッケージを作成。
**未確認**: このv0.3を使って同じ記事を再生成した際の自然さ改善。上流のツールも現環境にはインストールしていないため、このパッケージ作成時に実行したわけではありません。

著作権・ライセンス: 既存スキルの規則を参考にしましたが、各リポジトリのソースコードは同梱していません。上流へのリンクは `DESIGN.md` に記載しています。
