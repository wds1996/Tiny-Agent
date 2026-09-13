"""Static checks for the chapter's Markdown; not a substitute for renderer testing.

Run with: python stages/04-agentic-rag/code/check_markdown.py
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

CHAPTER = Path(__file__).resolve().parent.parent
READMES = ("README.md", "README.zh-CN.md")
# GitHub has rejected this otherwise valid LaTeX macro. Keep the known
# regression separate from general MathJax syntax or an exhaustive allowlist.
BLOCKED_MACRO = re.compile(r"\\operatorname\b")
MATH_BLOCK = re.compile(r"^\$\$[ \t]*\n(.*?)^\$\$[ \t]*$", re.MULTILINE | re.DOTALL)
CODE_BLOCK = re.compile(r"^```([^\n]*)\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)


class MarkdownChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {
            name: (CHAPTER / name).read_text(encoding="utf-8") for name in READMES
        }

    def test_known_github_macro_regression(self) -> None:
        for name, text in self.documents.items():
            with self.subTest(file=name):
                self.assertIsNone(BLOCKED_MACRO.search(text),
                                  "Use the portable mathrm form instead of operatorname")

    def test_display_math_is_balanced_and_outside_plain_code(self) -> None:
        for name, text in self.documents.items():
            with self.subTest(file=name):
                delimiters = re.findall(r"^\$\$[ \t]*$", text, re.MULTILINE)
                equations = MATH_BLOCK.findall(text)
                self.assertTrue(equations, "The cosine equation must remain in the tutorial")
                self.assertEqual(len(delimiters), 2 * len(equations))
                for language, body in CODE_BLOCK.findall(text):
                    if language.strip() != "math":
                        self.assertNotRegex(body, r"(?m)^\$\$[ \t]*$")
                for equation in equations:
                    self.assertTrue(equation.strip())
                    self.assertEqual(equation.count("{"), equation.count("}"))

    def test_bilingual_equations_match(self) -> None:
        equations = [MATH_BLOCK.findall(self.documents[name]) for name in READMES]
        self.assertEqual(equations[0], equations[1])

    def test_no_encoding_or_renderer_error_artifacts(self) -> None:
        for name, text in self.documents.items():
            with self.subTest(file=name):
                self.assertNotIn("\ufffd", text)
                self.assertNotIn("The following macros are not allowed", text)

    def test_macro_detector_distinguishes_the_repair(self) -> None:
        self.assertIsNotNone(BLOCKED_MACRO.search(r"\operatorname{cosine}(a,b)"))
        self.assertIsNone(BLOCKED_MACRO.search(r"\mathrm{cosine}(a,b)"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
