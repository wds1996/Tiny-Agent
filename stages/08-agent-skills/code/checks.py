from pathlib import Path
import tempfile
import unittest

from skills import SkillCatalog


SAMPLE = """---
name: sample-skill
description: Use when checking a sample release.
---

# Procedure

1. Check the version.
2. Run tests.
"""


class Stage08Checks(unittest.TestCase):
    def test_discovery_loads_metadata_without_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "sample-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            metadata = SkillCatalog(tmp).discover()[0]
            self.assertEqual(metadata.name, "sample-skill")
            self.assertFalse(hasattr(metadata, "instructions"))

    def test_activation_loads_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "sample-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            active = SkillCatalog(tmp).activate("sample-skill")
            self.assertIn("Run tests", active.instructions)

    def test_directory_must_match_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "wrong"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            with self.assertRaises(ValueError):
                SkillCatalog(tmp).discover()

    def test_invalid_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "Bad_Name"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                SAMPLE.replace("sample-skill", "Bad_Name"),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                SkillCatalog(tmp).discover()

    def test_resource_path_cannot_escape_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "sample-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            (Path(tmp) / "secret.txt").write_text("secret", encoding="utf-8")
            with self.assertRaises(ValueError):
                SkillCatalog(tmp).read_resource("sample-skill", "../secret.txt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
