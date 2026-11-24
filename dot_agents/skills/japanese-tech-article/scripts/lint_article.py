#!/usr/bin/env python3
"""Conservative, dependency-free diagnostics for Qiita/Zenn Markdown drafts.

This is not a Markdown renderer, YAML parser, Japanese proofreader, or fact checker.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Diagnostic:
    severity: str
    line: int
    code: str
    message: str


def check(text: str, platform: str = "generic") -> list[Diagnostic]:
    lines = text.splitlines()
    results: list[Diagnostic] = []

    def add(severity: str, line: int, code: str, message: str) -> None:
        results.append(Diagnostic(severity, line, code, message))

    # Front Matter is only recognized at the beginning of the file.
    front: dict[str, str] = {}
    front_end = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                front_end = i + 1
                break
        if not front_end:
            add("error", 1, "frontmatter-unclosed", "YAML Front Matterの終端---がありません")
        else:
            for raw in lines[1 : front_end - 1]:
                match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
                if match:
                    front[match[1]] = match[2].split(" #", 1)[0].strip()
    elif platform in {"zenn", "qiita"}:
        add("error", 1, "frontmatter-missing", f"{platform} CLI形式のFront Matterがありません")

    if platform == "zenn" and front_end:
        for key in ("title", "emoji", "type", "topics", "published"):
            if key not in front:
                add("error", 1, "zenn-required", f"Zenn Front Matterに{key}がありません")
        if front.get("published", "").lower() == "true":
            add("warning", 1, "zenn-published", "published: trueです。未公開の下書きならfalseにしてください")
        if front.get("type", "").strip("'\"") not in {"", "tech", "idea"}:
            add("error", 1, "zenn-type", "typeはtechまたはideaを指定してください")
    if platform == "qiita" and front_end:
        for key in ("title", "tags"):
            if key not in front:
                add("error", 1, "qiita-required", f"Qiita Front Matterに{key}がありません")
        if front.get("ignorePublish", "").lower() == "false":
            add("warning", 1, "qiita-publish-eligible", "ignorePublish: falseです。CLIで公開対象となり得ます")
        if "ignorePublish" not in front:
            add("warning", 1, "qiita-no-ignore", "ignorePublish未指定です。CLIの公開設定を確認してください")
    if "title" in front and front["title"].strip("'\" ") == "":
        add("warning", 1, "empty-title", "タイトルが空です")

    fence_char = ""
    fence_len = 0
    fence_line = 0
    # Avoid inspecting Markdown-like content inside code fences.
    for i, line in enumerate(lines, start=1):
        if i <= front_end:
            continue
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            token = fence[1]
            if not fence_char:
                fence_char, fence_len, fence_line = token[0], len(token), i
                if not fence[2].strip():
                    add("warning", i, "fence-no-language", "コードブロックに言語指定がありません")
            elif token[0] == fence_char and len(token) >= fence_len and not fence[2].strip():
                fence_char, fence_len, fence_line = "", 0, 0
            continue
        if fence_char:
            continue
        if platform == "zenn" and re.match(r"^\s*:::note(?:\s|$)", line):
            add("warning", i, "qiita-note-in-zenn", "Qiita固有の:::noteです。Zenn記法の確認が必要です")
        if platform == "qiita" and re.match(r"^\s*:::message(?:\s|$)", line):
            add("warning", i, "zenn-message-in-qiita", "Zenn固有の:::messageです。Qiita記法の確認が必要です")
        if re.match(r"^\s*#{1,6}[^\s#]", line):
            add("warning", i, "heading-no-space", "見出し記号の後に半角スペースがありません")
        if re.search(r"\b(?:TODO|TBD|FIXME)\b|\[要確認\]|\[未確認\]", line, re.IGNORECASE):
            add("warning", i, "unresolved-marker", "執筆用の未解決マーカーがあります")
    if fence_char:
        add("error", fence_line, "fence-unclosed", "コードフェンスが閉じられていません")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--platform", choices=("generic", "zenn", "qiita"), default="generic")
    parser.add_argument("--json", action="store_true", help="機械処理向けJSON出力")
    args = parser.parse_args()
    try:
        content = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    issues = check(content, args.platform)
    if args.json:
        print(json.dumps([asdict(item) for item in issues], ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"{args.file}:{issue.line}: {issue.severity}: {issue.code}: {issue.message}")
    else:
        print("形式の簡易チェックで問題は検出されませんでした（正確性・プレビューは未検証）。")
    return 1 if any(item.severity == "error" for item in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
