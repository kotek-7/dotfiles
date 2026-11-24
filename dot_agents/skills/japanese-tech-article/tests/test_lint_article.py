import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lint_article import check


class TestLintArticle(unittest.TestCase):
    def codes(self, text: str, platform: str = "generic") -> set[str]:
        return {item.code for item in check(text, platform)}

    def test_valid_zenn_draft(self) -> None:
        text = '''---
title: "Example"
emoji: "🛠️"
type: tech
topics: ["go"]
published: false
---
## 例

```go
fmt.Println("hello")
```
'''
        self.assertEqual(self.codes(text, "zenn"), set())

    def test_unclosed_fence(self) -> None:
        self.assertIn("fence-unclosed", self.codes("## Example\n\n```python\nprint(1)"))

    def test_ignores_todos_inside_fences(self) -> None:
        self.assertNotIn("unresolved-marker", self.codes("```bash\n# TODO: sample\n```"))

    def test_wrong_platform_notes(self) -> None:
        self.assertIn("qiita-note-in-zenn", self.codes(":::note\n注意\n:::", "zenn"))
        self.assertIn("zenn-message-in-qiita", self.codes(":::message\n注意\n:::", "qiita"))

    def test_qiita_ignore_publish(self) -> None:
        txt = "---\ntitle: example\ntags:\n  - example\nignorePublish: true\n---\n"
        self.assertNotIn("qiita-no-ignore", self.codes(txt, "qiita"))

    def test_zenn_no_auto_publish(self) -> None:
        txt = "---\ntitle: test\nemoji: 🛠️\ntype: tech\ntopics: []\npublished: true\n---\n"
        self.assertIn("zenn-published", self.codes(txt, "zenn"))

    def test_no_front_matter(self) -> None:
        self.assertIn("frontmatter-missing", self.codes("## テスト\n", "zenn"))
        self.assertNotIn("frontmatter-missing", self.codes("## テスト\n", "generic"))

    def test_heading_and_unresolved(self) -> None:
        issues = self.codes("##見出し\n\nTODO: verify\n")
        self.assertTrue({"heading-no-space", "unresolved-marker"} <= issues)


if __name__ == "__main__":
    unittest.main()
