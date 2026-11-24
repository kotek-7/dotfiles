# Zenn記事の形式

公式: https://zenn.dev/zenn/articles/zenn-cli-guide
記法: https://zenn.dev/zenn/articles/markdown-guide
slug: https://zenn.dev/zenn/articles/what-is-slug

## 新規記事の下書き

ユーザーがZenn向けのファイルを希望する場合、既存リポジトリのルールとZenn CLIの生成形式を優先する。基本形:

```yaml
---
title: "記事のタイトル"
emoji: "🛠️"
type: "tech"
topics: ["example"]
published: false
---
```

- `type` は `tech` または `idea`。
- `topics` は実際の記事の技術名に合わせ、根拠のないタグを足さない。
- `emoji` は記事に合うものを1つ選ぶ。本文へ装飾目的の絵文字を強制しない。
- **未依頼の公開は禁止**: 初回は `published: false`。既存記事を改稿する場合は指定がない限り公開設定を保存する。
- GitHub連携でファイルは通常 `articles/<slug>.md`。slugは半角英数字・ハイフン・アンダースコアの12〜50字。公開後のslug変更は別記事扱いとなり得るため行わない。
- コマンド例: `npx zenn new:article --slug <slug>`。CLI生成直後の公開設定は確認して下書きへ修正する。

## 本文

- Zenn公式は見出しを `##` から始めることを推奨する。
- 特別な理由がない限り通常のMarkdownを使い、見出し・リンク・コードフェンスの互換性を保つ。
- Zenn固有の補足: `:::message` / `:::message alert`。折りたたみ: `:::details 見出し` など。使う場合は公式ドキュメントで文法を確認する。
- リンクカード・埋め込み・数式・Mermaidなどは、必要な記事だけで使用し、公式プレビューで検証する。
- 他媒体へ移植する場合、Zenn固有の埋め込みや独自記法をそのまま移さない。

## プレビューと公開

- 利用可能なら `npx zenn preview` を使ってローカル表示を確認する。
- `published: true` に変更する、GitHubへpushするなどの公開に直結する操作は、ユーザーの明示的な依頼を必要とする。
