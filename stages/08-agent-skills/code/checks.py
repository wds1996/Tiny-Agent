from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deepseek_skills import (
    activate_requested_skill,
    activation_result_message,
    build_reference_tool,
    build_skill_tool,
    read_requested_reference,
    reference_result_message,
)
from skills import SkillCatalog, SkillMetadata


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

    def test_discovery_does_not_use_complete_file_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "sample-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=AssertionError):
                metadata = SkillCatalog(tmp).discover()[0]
            self.assertEqual(metadata.description, "Use when checking a sample release.")

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

    def test_skill_tool_advertises_only_discovered_names(self) -> None:
        candidate = SkillMetadata("sample-skill", "Use when checking a sample release.", Path("."))
        tool = build_skill_tool([candidate])
        self.assertEqual(tool["function"]["name"], "activate_skill")
        self.assertEqual(tool["function"]["parameters"]["properties"]["name"]["enum"], ["sample-skill"])

    def test_host_rejects_unadvertised_skill_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = SkillCatalog(tmp)
            call = SimpleNamespace(
                type="function",
                id="call-1",
                function=SimpleNamespace(
                    name="activate_skill",
                    arguments='{"name": "invented-skill"}',
                ),
            )
            with self.assertRaises(RuntimeError):
                activate_requested_skill(
                    catalog=catalog,
                    candidates=[],
                    tool_calls=[call],
                )

    def test_host_loads_skill_then_reference_in_separate_tool_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "sample-skill"
            reference_dir = skill_dir / "references"
            reference_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(SAMPLE, encoding="utf-8")
            (reference_dir / "checklist.md").write_text("Run integration tests.", encoding="utf-8")
            catalog = SkillCatalog(tmp)
            candidates = catalog.discover()
            activation_call = SimpleNamespace(
                type="function",
                id="call-activate",
                function=SimpleNamespace(
                    name="activate_skill",
                    arguments='{"name": "sample-skill"}',
                ),
            )

            activated = activate_requested_skill(
                catalog=catalog,
                candidates=candidates,
                tool_calls=[activation_call],
            )
            activation_message = activation_result_message(activated)
            self.assertIn("# Procedure", activation_message["content"])
            self.assertNotIn("Run integration tests.", activation_message["content"])
            reference_tool = build_reference_tool(activated.skill)
            self.assertEqual(
                reference_tool["function"]["parameters"]["properties"]["path"]["enum"],
                ["references/checklist.md"],
            )

            reference_call = SimpleNamespace(
                type="function",
                id="call-reference",
                function=SimpleNamespace(
                    name="read_skill_reference",
                    arguments='{"path": "references/checklist.md"}',
                ),
            )
            reference = read_requested_reference(
                catalog=catalog,
                activated=activated,
                tool_calls=[reference_call],
            )
            self.assertIn("Run integration tests.", reference_result_message(reference)["content"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
