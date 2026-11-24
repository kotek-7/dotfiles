# Qiita記事の形式

公式CLI: https://github.com/increments/qiita-cli
公式Markdown: https://help.qiita.com/ja/articles/qiita-markdown
記法の具体例: https://qiita.com/Qiita/items/c686397e4a0f4f11683d

## Qiita向けMarkdownとQiita CLI用ファイルは別

依頼が「Qiita向けの記事を書いて」のみなら、通常は**記事本文のMarkdown**を出力する。Qiitaウェブエディタへ貼り付ける原稿にFront Matterは要らない。Gitリポジトリの `public/*.md` 等を使うことが分かっている場合や、明示的にQiita CLI形式のファイルを求められた場合にだけ、以下のFront Matterを使う。

## Qiita CLIの新規記事

Qiita CLI管理のリポジトリでは、既存のFront Matterとファイル配置を優先する。新規記事の形の例:

```yaml
---
title: "記事のタイトル"
tags:
  - "example"
private: false
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---
```

- 新しいQiita CLIでは `ignorePublish: true` にすると `publish` 対象から除外できる。公開前の下書きはこれを基本とする。使用CLIのバージョンと構成を確認すること。
- `private: true` は限定共有記事であり「ローカル下書き」ではない。公開抑止の代用にしない。
- Qiita CLIプロジェクトは通常 `public/` 配下で管理するが、既存プロジェクトの配置を優先する。
- 新規作成コマンドの例は `npx qiita new <name>`。スキルが勝手に `qiita publish` を実行してはならない。
- 既存記事の `id`、`updated_at`、Organization情報などは、編集依頼だけでは変更しない。

## Markdownの扱い

- Qiita Markdownは基本的にGitHub Flavored Markdown系。Markdown記法は実際のQiita側の仕様で確認する。
- Qiitaの補足記法: `:::note`、`:::note warn`、`:::note alert`。Zennの `:::message` をそのまま使わない。
- いずれもコードフェンス・リンク・見出しの構文を壊さない。
- Qiita上での表示を保証するには、実際のプレビュー確認が必要。一般Markdownのレンダリングだけで保証しない。

## 公開

- `npx qiita publish`、GitHub Actions経由の投稿、公開API呼び出しはユーザーの明示的な公開依頼がある場合のみ扱う。
